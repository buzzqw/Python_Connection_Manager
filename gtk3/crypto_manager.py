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
import copy
import secrets
import threading


class CryptoError(Exception):
    """Errore di cifratura: chiave non disponibile o operazione non consentita."""


class InvalidTokenError(CryptoError):
    """Token cifrato corrotto o password master errata."""


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
_lock = threading.Lock()           # protegge l'accesso a _KEY
_ENC_PREFIX = "ENC:"               # prefisso per valori cifrati
_FIELDS_TO_ENCRYPT = ("user", "password", "totp_secret")  # campi da cifrare nei profili


# ---------------------------------------------------------------------------
# Accesso settings (import circolare evitato con import lazy)
# ---------------------------------------------------------------------------

def _load_settings() -> dict:
    import config_manager
    return config_manager.load_settings()


def _save_settings(s: dict):
    import config_manager
    return config_manager.save_settings(s)


# ---------------------------------------------------------------------------
# API pubblica — stato
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    """Restituisce True se la cifratura è attiva (salt presente in settings)."""
    s = _load_settings()
    return bool(s.get("crypto", {}).get("enabled", False))


def is_unlocked() -> bool:
    """Restituisce True se la chiave è in memoria (app sbloccata)."""
    with _lock:
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
    s, key = _new_crypto_settings(password, _load_settings())
    if not _save_settings(s):
        raise CryptoError("Impossibile salvare la configurazione di cifratura")

    with _lock:
        _KEY = key


def _new_crypto_settings(password: str, settings: dict) -> tuple[dict, bytes]:
    """Create new crypto metadata without writing it to disk."""
    Fernet, _, __, ___ = _get_fernet()
    salt = secrets.token_bytes(32)
    key = _derive_key(password, salt)
    canary = secrets.token_bytes(32)
    updated = copy.deepcopy(settings)
    updated["crypto"] = {
        "enabled": True,
        "salt": base64.b64encode(salt).decode("ascii"),
        "canary": base64.b64encode(canary).decode("ascii"),
        "verify": Fernet(key).encrypt(b"pcm-verify:" + canary).decode("ascii"),
    }
    return updated, key


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
        # Supporta sia il formato vecchio (b"pcm-verify") che il nuovo (b"pcm-verify:" + canary)
        canary_b64 = s.get("crypto", {}).get("canary", "")
        if canary_b64:
            canary = base64.b64decode(canary_b64)
            if decrypted != b"pcm-verify:" + canary:
                return False
        else:
            # Compatibilità con installazioni precedenti senza canary
            if decrypted != b"pcm-verify":
                return False

        with _lock:
            _KEY = key
        return True

    except Exception:
        return False


def lock():
    """Rimuove la chiave dalla memoria (blocca l'app)."""
    global _KEY
    with _lock:
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

    old_key = _KEY
    new_settings, new_key = _new_crypto_settings(new_password, _load_settings())
    with _lock:
        _KEY = new_key
    try:
        encrypted_profiles = {
            nome: encrypt_profile(profilo) for nome, profilo in profili.items()
        }
    except Exception:
        with _lock:
            _KEY = old_key
        return False

    if not config_manager.replace_crypto_state(encrypted_profiles, new_settings):
        with _lock:
            _KEY = old_key
        return False
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

    new_settings = copy.deepcopy(_load_settings())
    new_settings.pop("crypto", None)
    if not config_manager.replace_crypto_state(profili, new_settings):
        return False
    with _lock:
        _KEY = None
    return True


# ---------------------------------------------------------------------------
# API pubblica — cifratura/decifratura campi singoli
# ---------------------------------------------------------------------------

def encrypt_field(value: str) -> str:
    """
    Cifra un singolo valore stringa.
    Restituisce "ENC:<base64>". Solleva CryptoError se la chiave non è
    disponibile e la cifratura è attiva.
    """
    if not value or value.startswith(_ENC_PREFIX):
        return value
    with _lock:
        key = _KEY
    if key is None:
        if is_enabled():
            raise CryptoError("Cifratura bloccata: impossibile cifrare il campo")
        return value
    Fernet, _, __, ___ = _get_fernet()
    f = Fernet(key)
    token = f.encrypt(value.encode("utf-8")).decode("ascii")
    return _ENC_PREFIX + token


def decrypt_field(value: str) -> str:
    """
    Decifra un singolo valore stringa.
    Restituisce il testo in chiaro. Solleva InvalidTokenError se il token
    è corrotto, CryptoError se la chiave non è disponibile.
    """
    if not value or not value.startswith(_ENC_PREFIX):
        return value
    with _lock:
        key = _KEY
    if key is None:
        raise CryptoError("Cifratura bloccata: impossibile decifrare il campo")
    try:
        Fernet, InvalidToken, _, __ = _get_fernet()
        f = Fernet(key)
        token = value[len(_ENC_PREFIX):].encode("ascii")
        return f.decrypt(token).decode("utf-8")
    except InvalidToken:
        from pcm_logging import get_logger
        get_logger(__name__).warning("Token cifrato corrotto")
        raise InvalidTokenError("Token cifrato corrotto o password errata")


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
