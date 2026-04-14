"""
crypto_manager.py - Cifratura credenziali per PCM

Algoritmo: Fernet (AES-128-CBC + HMAC-SHA256)
KDF:       PBKDF2-HMAC-SHA256, 480.000 iterazioni (OWASP 2023)
Sale:      32 byte casuali, salvato in pcm_settings.json (non segreto)
Chiave:    derivata dalla password master, tenuta in memoria (_KEY),
           mai scritta su disco.

Campi cifrati in connections.json: "user" e "password".
I valori cifrati hanno il prefisso "ENC:" per distinguerli dal testo chiaro.

Flusso primo avvio:
  1. config_manager rileva che connections.json non esiste ancora
  2. Chiede se cifrare (dialog in PCM.py)
  3. Se sì: genera sale, deriva chiave, salva sale in settings, 
     setta _KEY in memoria
  4. Ogni save_profiles() cifra automaticamente user/password

Flusso avvii successivi (cifratura attiva):
  1. PCM.py rileva "crypto.enabled": True in settings
  2. Mostra dialog di sblocco password
  3. Chiama unlock(password) → deriva _KEY
  4. load_profiles() decifra automaticamente

API pubblica:
  is_enabled()          → bool
  is_unlocked()         → bool
  setup(password)       → configura cifratura (primo avvio o cambio password)
  unlock(password)      → bool  (verifica e sblocca)
  lock()                → cancella chiave dalla memoria
  change_password(old, new) → bool
  disable(password)     → bool  (rimuove cifratura, torna in chiaro)
  encrypt_field(val)    → str   (ENC:... o val se non cifrato)
  decrypt_field(val)    → str   (testo chiaro)
  encrypt_profile(p)    → dict  (copia del profilo con campi cifrati)
  decrypt_profile(p)    → dict  (copia del profilo con campi in chiaro)
"""

import os
import base64
import secrets

# Importazione lazy di cryptography per dare errore chiaro se mancante
def _get_fernet():
    try:
        from cryptography.fernet import Fernet, InvalidToken
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        return Fernet, InvalidToken, PBKDF2HMAC, hashes
    except ImportError:
        raise ImportError(
            "Il modulo 'cryptography' non è installato.\n"
            "Esegui: pip install cryptography\n"
            "oppure: bash setup.sh"
        )


# ---------------------------------------------------------------------------
# Stato in memoria (mai scritto su disco)
# ---------------------------------------------------------------------------

_KEY: bytes | None = None          # chiave Fernet derivata dalla password
_ENC_PREFIX = "ENC:"               # prefisso per valori cifrati
_FIELDS_TO_ENCRYPT = ("user", "password")  # campi da cifrare nei profili


# ---------------------------------------------------------------------------
# Accesso settings (import circolare evitato con import lazy)
# ---------------------------------------------------------------------------

def _load_settings() -> dict:
    import config_manager
    return config_manager.load_settings()


def _save_settings(s: dict):
    import config_manager
    config_manager.save_settings(s)


# ---------------------------------------------------------------------------
# API pubblica — stato
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    """Restituisce True se la cifratura è attiva (salt presente in settings)."""
    s = _load_settings()
    return bool(s.get("crypto", {}).get("enabled", False))


def is_unlocked() -> bool:
    """Restituisce True se la chiave è in memoria (app sbloccata)."""
    return _KEY is not None


# ---------------------------------------------------------------------------
# Derivazione chiave
# ---------------------------------------------------------------------------

def _derive_key(password: str, salt: bytes) -> bytes:
    """Deriva una chiave Fernet a 32 byte da password + salt via PBKDF2."""
    Fernet, InvalidToken, PBKDF2HMAC, hashes = _get_fernet()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    raw = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)   # formato atteso da Fernet


def _get_salt() -> bytes:
    """Legge il salt da settings (deve esistere se cifratura abilitata)."""
    s = _load_settings()
    salt_b64 = s.get("crypto", {}).get("salt", "")
    if not salt_b64:
        raise ValueError("Salt non trovato in settings — cifratura non configurata")
    return base64.b64decode(salt_b64)


# ---------------------------------------------------------------------------
# API pubblica — setup / unlock / lock
# ---------------------------------------------------------------------------

def setup(password: str):
    """
    Configura la cifratura per la prima volta (o dopo disable()).
    Genera un nuovo salt, deriva la chiave, salva la configurazione.
    NON cifra i profili esistenti — lo fa config_manager dopo.
    """
    global _KEY
    Fernet, _, __, ___ = _get_fernet()

    salt = secrets.token_bytes(32)
    _KEY = _derive_key(password, salt)

    # Verifica che la chiave sia valida
    f = Fernet(_KEY)

    # Salva salt e flag in settings
    s = _load_settings()
    s["crypto"] = {
        "enabled": True,
        "salt":    base64.b64encode(salt).decode("ascii"),
        # token di verifica: cifriamo una stringa nota per verificare la password
        "verify":  f.encrypt(b"pcm-verify").decode("ascii"),
    }
    _save_settings(s)


def unlock(password: str) -> bool:
    """
    Tenta di sbloccare con la password fornita.
    Restituisce True se la password è corretta, False altrimenti.
    """
    global _KEY
    try:
        Fernet, InvalidToken, _, __ = _get_fernet()
        salt = _get_salt()
        key = _derive_key(password, salt)

        # Verifica la password decifrando il token di verifica
        s = _load_settings()
        verify_token = s.get("crypto", {}).get("verify", "")
        if not verify_token:
            return False

        f = Fernet(key)
        decrypted = f.decrypt(verify_token.encode("ascii"))
        if decrypted != b"pcm-verify":
            return False

        _KEY = key
        return True

    except Exception:
        return False


def lock():
    """Rimuove la chiave dalla memoria (blocca l'app)."""
    global _KEY
    _KEY = None


def change_password(old_password: str, new_password: str) -> bool:
    """
    Cambia la password master:
    1. Verifica la vecchia password
    2. Decifra tutti i profili
    3. Genera nuovo salt, deriva nuova chiave
    4. Ricifra tutti i profili
    Restituisce True se riuscito.
    """
    global _KEY
    import config_manager

    if not unlock(old_password):
        return False

    # Decifra tutti i profili con la vecchia chiave
    profili = config_manager.load_profiles()   # già decifrati da load_profiles

    # Configura nuova cifratura
    setup(new_password)   # genera nuovo salt, nuova chiave, aggiorna settings

    # Ricifra e salva
    config_manager.save_profiles(profili)      # save_profiles cifra con la nuova chiave
    return True


def disable(password: str) -> bool:
    """
    Disabilita la cifratura:
    1. Verifica la password
    2. Decifra tutti i profili
    3. Salva in chiaro
    4. Rimuove configurazione crypto da settings
    Restituisce True se riuscito.
    """
    global _KEY
    import config_manager

    if not unlock(password):
        return False

    # Decifra tutti i profili
    profili = config_manager.load_profiles()   # load_profiles decifra

    # Rimuovi cifratura da settings
    s = _load_settings()
    s.pop("crypto", None)
    _save_settings(s)

    _KEY = None

    # Salva profili in chiaro (save_profiles ora vede is_enabled()==False)
    config_manager.save_profiles(profili)
    return True


# ---------------------------------------------------------------------------
# API pubblica — cifratura/decifratura campi singoli
# ---------------------------------------------------------------------------

def encrypt_field(value: str) -> str:
    """
    Cifra un singolo valore stringa.
    Restituisce "ENC:<base64>" oppure il valore originale se la chiave
    non è disponibile o il valore è già cifrato.
    """
    if not value:
        return value
    if value.startswith(_ENC_PREFIX):
        return value   # già cifrato
    if _KEY is None:
        return value   # cifratura non sbloccata
    Fernet, _, __, ___ = _get_fernet()
    f = Fernet(_KEY)
    token = f.encrypt(value.encode("utf-8")).decode("ascii")
    return _ENC_PREFIX + token


def decrypt_field(value: str) -> str:
    """
    Decifra un singolo valore stringa.
    Restituisce il testo in chiaro, oppure il valore originale se non cifrato
    o se la chiave non è disponibile.
    """
    if not value or not value.startswith(_ENC_PREFIX):
        return value   # già in chiaro
    if _KEY is None:
        return ""      # cifrato ma non sbloccato → restituisce stringa vuota
    try:
        Fernet, InvalidToken, _, __ = _get_fernet()
        f = Fernet(_KEY)
        token = value[len(_ENC_PREFIX):].encode("ascii")
        return f.decrypt(token).decode("utf-8")
    except Exception:
        return ""      # token corrotto o password sbagliata


# ---------------------------------------------------------------------------
# API pubblica — cifratura/decifratura profili interi
# ---------------------------------------------------------------------------

def encrypt_profile(profilo: dict) -> dict:
    """
    Restituisce una copia del profilo con i campi sensibili cifrati.
    Opera solo se la cifratura è abilitata e sbloccata.
    """
    if not is_enabled() or not is_unlocked():
        return profilo
    result = dict(profilo)
    for campo in _FIELDS_TO_ENCRYPT:
        if campo in result:
            result[campo] = encrypt_field(str(result[campo]))
    return result


def decrypt_profile(profilo: dict) -> dict:
    """
    Restituisce una copia del profilo con i campi sensibili in chiaro.
    Opera solo se la cifratura è abilitata (sbloccata o meno).
    """
    if not is_enabled():
        return profilo
    result = dict(profilo)
    for campo in _FIELDS_TO_ENCRYPT:
        if campo in result:
            result[campo] = decrypt_field(str(result[campo]))
    return result
