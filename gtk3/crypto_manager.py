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



# ---------------------------------------------------------------------------
# Interfaccia Grafica (Dialog)
# ---------------------------------------------------------------------------
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

# Questa è la funzione che "pesca" le traduzioni dal file translations.py
from translations import t  

class CryptoManagerDialog(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(
            title=t("crypto.custom.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.set_default_size(400, 0)
        self._init_ui()
        self.show_all()

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(10)
        area.set_margin_start(16)
        area.set_margin_end(16)
        area.set_margin_top(16)
        area.set_margin_bottom(16)

        self.attiva = is_enabled()

        lbl = Gtk.Label()
        lbl.set_xalign(0.0)
        area.pack_start(lbl, False, False, 0)

        self.entry_pwd1 = Gtk.Entry()
        self.entry_pwd1.set_visibility(False)
        area.pack_start(self.entry_pwd1, False, False, 0)

        self.entry_pwd2 = Gtk.Entry()
        self.entry_pwd2.set_visibility(False)

        if not self.attiva:
            lbl.set_markup(f"<b>{t('crypto.custom.disabled_title')}</b>\n{t('crypto.custom.disabled_desc')}")
            self.entry_pwd1.set_placeholder_text(t("crypto.custom.new_pwd_ph"))
        else:
            lbl.set_markup(f"<b>{t('crypto.custom.active_title')}</b>\n{t('crypto.custom.active_desc')}")
            self.entry_pwd1.set_placeholder_text(t("crypto.custom.old_pwd_ph"))
            self.entry_pwd2.set_placeholder_text(t("crypto.custom.new_pwd_opt_ph"))
            area.pack_start(self.entry_pwd2, False, False, 0)

        # "sd.cancel" esiste già in translations.py!
        self.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button(t("crypto.custom.btn_apply"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")

    def run(self):
        resp = super().run()
        if resp == Gtk.ResponseType.OK:
            p1 = self.entry_pwd1.get_text()
            p2 = self.entry_pwd2.get_text() if self.attiva else ""

            if not self.attiva:
                if p1:
                    setup(p1)
                    self._mostra_msg(t("crypto.custom.success"), t("crypto.custom.msg_enabled"))
            else:
                if p1 and p2:
                    if change_password(p1, p2):
                        self._mostra_msg(t("crypto.custom.success"), t("crypto.custom.msg_changed"))
                    else:
                        self._mostra_msg(t("crypto.custom.error"), t("crypto.custom.msg_wrong_old"))
                elif p1 and not p2:
                    if disable(p1):
                        self._mostra_msg(t("crypto.custom.success"), t("crypto.custom.msg_disabled"))
                    else:
                        self._mostra_msg(t("crypto.custom.error"), t("crypto.custom.msg_wrong"))
        return resp

    def _mostra_msg(self, titolo, testo):
        m_type = Gtk.MessageType.INFO if titolo == t("crypto.custom.success") else Gtk.MessageType.ERROR
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=m_type,
            buttons=Gtk.ButtonsType.OK, text=titolo
        )
        dlg.format_secondary_text(testo)
        dlg.run()
        dlg.destroy()
