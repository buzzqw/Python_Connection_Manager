"""
config_manager.py - Gestione profili sessioni e impostazioni globali PCM
"""

import hashlib
import json
import os
import secrets

from pcm_logging import get_logger as _get_log

# Import lazy: crypto_manager potrebbe non avere cryptography installato
def _crypto():
    try:
        import crypto_manager
        return crypto_manager
    except ImportError:
        return None

# Percorsi di configurazione.
# Dentro AppImage la AppDir è read-only: i file vengono spostati in
# $XDG_CONFIG_HOME/pcm/ (default ~/.config/pcm/).
# In installazione normale si usa la stessa cartella del modulo.
def _resolve_config_dir() -> str:
    if os.environ.get("APPIMAGE"):
        xdg = os.environ.get("XDG_CONFIG_HOME",
                             os.path.join(os.path.expanduser("~"), ".config"))
        d = os.path.join(xdg, "pcm")
        os.makedirs(d, exist_ok=True)
        return d
    return os.path.dirname(os.path.abspath(__file__))

_HERE          = _resolve_config_dir()
SESSIONS_FILE  = os.path.join(_HERE, "connections.json")
SETTINGS_FILE  = os.path.join(_HERE, "pcm_settings.json")

# ---------------------------------------------------------------------------
# Sessioni
# ---------------------------------------------------------------------------

def load_profiles() -> dict:
    if first_run := not os.path.exists(SESSIONS_FILE):
        _create_default_sessions()
        s = load_settings()
        s.setdefault("crypto", {})["primo_avvio"] = True
        save_settings(s)

    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            profili = json.load(f)
    except json.JSONDecodeError:
        from pcm_logging import get_logger
        _log = get_logger(__name__)
        _log.warning("connections.json corrotto o illeggibile. Le sessioni non sono state caricate.")
        return {"_corrupted": True}
    except FileNotFoundError:
        return {}
    except Exception as e:
        from pcm_logging import get_logger
        _log = get_logger(__name__)
        _log.warning("Errore lettura sessioni: %s", e)
        return {"_error": str(e)}

    cm = _crypto()
    if cm and cm.is_enabled():
        profili = {nome: cm.decrypt_profile(p) for nome, p in profili.items()}

    from protocols import validate_profiles
    profili = validate_profiles(profili)

    profili = _resolve_template_inheritance(profili)

    return profili


def _resolve_template_inheritance(profiles: dict) -> dict:
    """Resolve template inheritance: merge template fields into child sessions.

    For each session with a valid template_name, fields from the template
    are used as defaults. Session-specific values take priority.
    """
    templates = {n: d for n, d in profiles.items() if d.get("is_template")}
    if not templates:
        return profiles

    resolved = {}
    for name, data in profiles.items():
        template_name = data.get("template_name", "").strip()
        if template_name and template_name in templates:
            merged = dict(templates[template_name])
            merged.update(data)
            merged["_inherits_from"] = template_name
            resolved[name] = merged
        else:
            resolved[name] = data
    return resolved


def get_templates() -> dict:
    """Return all sessions marked as templates."""
    profili = load_profiles()
    return {n: d for n, d in profili.items() if d.get("is_template")}


def save_profiles(profiles: dict) -> bool:
    """
    Salva i profili su connections.json.
    Se la cifratura è attiva e sbloccata, cifra automaticamente user/password
    prima di scrivere su disco.
    """
    cm = _crypto()
    if cm and cm.is_enabled() and cm.is_unlocked():
        try:
            to_save = {nome: cm.encrypt_profile(p) for nome, p in profiles.items()}
        except Exception as e:
            _get_log(__name__).error("Cifratura fallita, salvataggio annullato: %s", e)
            return False
    else:
        to_save = profiles

    try:
        _write_json_secure(SESSIONS_FILE, to_save)
        return True
    except Exception as e:
        _get_log(__name__).error("Errore salvataggio sessioni: %s", e)
        return False


def _create_default_sessions():
    default = {
        "Esempio SSH": {
            "protocol": "ssh",
            "host": "192.168.1.100",
            "port": "22",
            "user": "utente",
            "password": "",
            "private_key": "",
            "x11": False,
            "compression": False,
            "keepalive": False,
            "startup_cmd": "",
            "term_theme": "Scuro (Default)",
            "term_font": "Monospace",
            "term_size": "11",
            "jump_host": "",
            "jump_user": "",
            "jump_port": "22",
            "sftp_browser": True,
            "notes": "Sessione SSH di esempio"
        },
        "Esempio RDP": {
            "protocol": "rdp",
            "host": "10.0.0.50",
            "port": "3389",
            "user": "amministratore",
            "password": "",
            "rdp_client": "xfreerdp",
            "fullscreen": True,
            "redirect_drives": False,
            "redirect_clipboard": True,
            "notes": ""
        },
        "Esempio VNC": {
            "protocol": "vnc",
            "host": "192.168.1.20",
            "port": "5900",
            "password": "",
            "vnc_client": "vncviewer",
            "vnc_color": "Truecolor (32 bpp)",
            "vnc_quality": "Buona",
            "notes": ""
        },
        "Esempio SFTP": {
            "protocol": "file_transfer",
            "ft_protocol": "SFTP",
            "host": "192.168.1.100",
            "port": "22",
            "user": "utente",
            "password": "",
            "private_key": "",
            "notes": ""
        },
        "Esempio FTP": {
            "protocol": "file_transfer",
            "ft_protocol": "FTP",
            "host": "192.168.1.100",
            "port": "21",
            "user": "utente",
            "password": "",
            "ftp_tls": False,
            "ftp_passive": True,
            "notes": "FTP plain — usa FTPS per cifrare il traffico"
        },
        "Esempio Telnet": {
            "protocol": "telnet",
            "host": "192.168.1.200",
            "port": "23",
            "user": "",
            "notes": ""
        },
        "Esempio Mosh": {
            "protocol": "mosh",
            "host": "192.168.1.100",
            "port": "22",
            "user": "utente",
            "password": "",
            "private_key": "",
            "notes": ""
        },
        "Esempio Seriale": {
            "protocol": "serial",
            "device": "/dev/ttyUSB0",
            "baud": "115200",
            "data_bits": "8",
            "stop_bits": "1",
            "parity": "None",
            "notes": ""
        },
    }
    save_profiles(default)


# ---------------------------------------------------------------------------
# Impostazioni globali
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "general": {
        "home_dir": os.path.expanduser("~"),
        "default_editor": "nano",
        "confirm_on_exit": True,
        "language": "it",
        "protected_mode": False,
        "audit_log_enabled": False,
        "log_level": "INFO",
        "auto_lock_minutes": 15,
    },
    "terminal": {
        "default_theme": "Scuro (Default)",
        "default_font": "Monospace",
        "default_font_size": 11,
        "scrollback_lines": 10000,
        "confirm_on_close": True,
        "log_output": False,
        "log_dir": os.path.join(os.path.expanduser("~"), ".local", "share", "pcm", "logs"),
        "word_delimiters": "/~+-.&?$%",
        "warn_multiline_paste": True,
    },
    "ssh": {
        "keepalive_interval": 60,
        "strict_host_check": False,
        "default_sftp_browser": True,
    },
    "tunnels": [],
    "variables": {},
    "tool_paths": {},
    "recent_sessions": [],   # lista di {name, ts} — max 20 voci
    "display": {
        "sidebar_visible": True,
        "toolbar_visible": True,
        "statusbar_visible": True,
        "split_mode": "single",
    },
    "shortcuts": {
        "new_terminal": "Ctrl+Alt+T",
        "close_tab": "Ctrl+Alt+Q",
        "prev_tab": "Ctrl+Alt+Left",
        "next_tab": "Ctrl+Alt+Right",
        "new_session": "Ctrl+Shift+N",
        "toggle_sidebar": "Ctrl+Shift+B",
        "find": "Ctrl+Shift+F",
        "fullscreen": "F11",
    },
    "credential_profiles": [],
    "snippets": [],
}


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # merge con i default per aggiungere chiavi mancanti
        merged = _deep_merge(DEFAULT_SETTINGS, saved)
        return merged
    except Exception as e:
        _get_log(__name__).error("Errore lettura settings: %s", e)
        return dict(DEFAULT_SETTINGS)


def _write_json_secure(path: str, data: dict):
    """Scrive JSON atomicamente con permessi 0600 (solo proprietario)."""
    dirname = os.path.dirname(path) or "."
    os.makedirs(dirname, mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


def _fix_permissions():
    """Corregge i permessi dei file e directory di configurazione all'avvio."""
    from pcm_logging import get_logger
    _log = get_logger(__name__)
    config_dir = os.path.dirname(SESSIONS_FILE) or "."
    os.makedirs(config_dir, mode=0o700, exist_ok=True)
    os.chmod(config_dir, 0o700)
    for f in (SESSIONS_FILE, SETTINGS_FILE):
        if os.path.isfile(f):
            st = os.stat(f)
            if st.st_mode & 0o077:
                os.chmod(f, 0o600)
                _log.info("Permessi corretti per %s (era 0%o)", f, st.st_mode & 0o777)
    audit = os.path.join(config_dir, "audit_log.json")
    if os.path.isfile(audit):
        st = os.stat(audit)
        if st.st_mode & 0o077:
            os.chmod(audit, 0o600)
            _log.info("Permessi corretti per %s", audit)


def save_settings(settings: dict) -> bool:
    try:
        _write_json_secure(SETTINGS_FILE, settings)
        return True
    except Exception as e:
        _get_log(__name__).error("Errore salvataggio settings: %s", e)
        return False


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Tunnel manager
# ---------------------------------------------------------------------------

def load_tunnels() -> list:
    s = load_settings()
    tunnels = s.get("tunnels", [])
    cm = _crypto()
    if cm and cm.is_enabled():
        tunnels = [cm.decrypt_profile(t) for t in tunnels]
    return tunnels


def save_tunnels(tunnels: list):
    s = load_settings()
    cm = _crypto()
    if cm and cm.is_enabled() and cm.is_unlocked():
        to_save = [cm.encrypt_profile(t) for t in tunnels]
    else:
        to_save = tunnels
    s["tunnels"] = to_save
    save_settings(s)


# ---------------------------------------------------------------------------
# Strumenti personalizzati (client VNC/RDP custom)
# ---------------------------------------------------------------------------

def load_custom_tools() -> dict:
    """Restituisce il dizionario {"vnc": [...], "rdp": [...]} dei tool personalizzati."""
    s = load_settings()
    return s.get("custom_tools", {"vnc": [], "rdp": []})


def save_custom_tools(custom_tools: dict):
    """Salva il dizionario dei tool personalizzati."""
    s = load_settings()
    s["custom_tools"] = custom_tools
    save_settings(s)


# ---------------------------------------------------------------------------
# Variabili globali
# ---------------------------------------------------------------------------

def load_variables() -> dict:
    """Restituisce il dizionario {NOME: valore} delle variabili globali."""
    s = load_settings()
    return s.get("variables", {})


def save_variables(variables: dict):
    """Salva il dizionario variabili globali."""
    s = load_settings()
    s["variables"] = variables
    save_settings(s)


def expand_variables(testo: str) -> str:
    """Sostituisce {NOME} con il valore dalla tabella variabili globali."""
    vars_ = load_variables()
    for nome, valore in vars_.items():
        testo = testo.replace(f"{{{nome}}}", valore)
    return testo


# ---------------------------------------------------------------------------
# Sessioni recenti
# ---------------------------------------------------------------------------

_MAX_RECENT = 20


def load_recent() -> list:
    """Restituisce la lista dei recenti: [{name, ts, proto, host}, ...]."""
    s = load_settings()
    recenti = s.get("recent_sessions", [])
    # Filtra voci nel formato vecchio (stringhe) — compatibilità backward
    return [r for r in recenti if isinstance(r, dict)]


def add_recent(nome: str, dati: dict):
    """Aggiunge/aggiorna la sessione in cima alla lista recenti."""
    from datetime import datetime
    s = load_settings()
    recenti = [r for r in s.get("recent_sessions", []) if isinstance(r, dict) and r.get("name") != nome]
    recenti.insert(0, {
        "name":  nome,
        "ts":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "proto": dati.get("protocol", ""),
        "host":  dati.get("host", ""),
    })
    s["recent_sessions"] = recenti[:_MAX_RECENT]
    save_settings(s)


def clear_recent():
    s = load_settings()
    s["recent_sessions"] = []
    save_settings(s)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

_AUDIT_FILE = os.path.join(_HERE, "audit_log.json")

# Chiavi considerate sensibili: i loro valori vengono oscurati prima di
# scrivere nel log e prima del calcolo dell'hash di integrità.
_SENSITIVE_KEYS: frozenset = frozenset({
    "password", "passwd", "pwd", "secret", "token", "credential",
    "private_key", "pkey", "key", "passphrase", "pass",
    "auth", "authorization", "api_key", "apikey",
})


def _sanitize_audit_entry(obj):
    """Restituisce una copia dell'oggetto con i valori sensibili oscurati.

    Ricorre ricorsivamente su dict e list; qualsiasi chiave il cui nome
    (in minuscolo) sia in ``_SENSITIVE_KEYS`` viene sostituita con la
    stringa ``"[REDACTED]"``.
    """
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if k.lower() in _SENSITIVE_KEYS else _sanitize_audit_entry(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_sanitize_audit_entry(item) for item in obj]
    return obj


def _audit_hash(entry: dict, prev_hash: str) -> str:
    """Calcola l'SHA-256 di una voce incluso l'hash della voce precedente (hash chaining).

    L'entry passata qui deve essere già sanificata (nessun valore sensibile).
    SHA-256 è usato esclusivamente per garantire l'integrità della catena,
    non per derivare o proteggere segreti.
    """
    raw = json.dumps(entry, sort_keys=True, ensure_ascii=False) + prev_hash
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audit_append(entry: dict):
    """Aggiunge una voce all'audit log con hash chaining (integrità) e permessi 0600.

    Non scrive nulla se audit_log_enabled è False nelle impostazioni.
    I valori sensibili (password, token, chiavi) vengono rimossi dalla copia
    che viene scritta su disco e usata per il calcolo dell'hash, così da
    evitare che dati riservati transitino nell'audit log.
    """
    if not load_settings().get("general", {}).get("audit_log_enabled", False):
        return
    try:
        if os.path.exists(_AUDIT_FILE):
            with open(_AUDIT_FILE, "r", encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = []
        # Sanifica prima di toccare il log: nessun dato sensibile su disco
        safe_entry = _sanitize_audit_entry(entry)
        prev_hash = log[-1].get("_hash", "") if log else ""
        safe_entry["_hash"] = _audit_hash(safe_entry, prev_hash)
        log.append(safe_entry)
        fd = os.open(_AUDIT_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _get_log(__name__).error("Errore scrittura audit_log: %s", e)


def audit_load() -> list:
    try:
        if not os.path.exists(_AUDIT_FILE):
            return []
        with open(_AUDIT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def audit_clear():
    try:
        fd = os.open(_AUDIT_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump([], f)
    except Exception as e:
        _get_log(__name__).error("Errore cancellazione audit_log: %s", e)


def load_credential_profiles() -> list:
    """Load credential profiles with passwords decrypted."""
    import crypto_manager
    profiles = load_settings().get("credential_profiles", [])
    return [
        {**p, "password": crypto_manager.decrypt_field(p.get("password", ""))}
        for p in profiles
    ]


def save_credential_profiles(profiles: list) -> bool:
    """Save credential profiles encrypting passwords if crypto is active."""
    import crypto_manager
    s = load_settings()
    s["credential_profiles"] = [
        {**p, "password": crypto_manager.encrypt_field(p.get("password", ""))}
        for p in profiles
    ]
    return save_settings(s)


if __name__ == "__main__":
    p = load_profiles()
    _get_log(__name__).debug("Sessioni caricate: %d", len(p))
    s = load_settings()
    _get_log(__name__).debug("Impostazioni caricate: %s", list(s.keys()))
