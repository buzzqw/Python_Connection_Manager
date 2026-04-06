"""
config_manager.py - Gestione profili sessioni e impostazioni globali PCM
"""

import json
import os

# Percorsi ancorati alla cartella di config_manager.py (indipendente dalla CWD)
_HERE          = os.path.dirname(os.path.abspath(__file__))
SESSIONS_FILE  = os.path.join(_HERE, "connections.json")
SETTINGS_FILE  = os.path.join(_HERE, "pcm_settings.json")

# ---------------------------------------------------------------------------
# Sessioni
# ---------------------------------------------------------------------------

def load_profiles() -> dict:
    if not os.path.exists(SESSIONS_FILE):
        _create_default_sessions()
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[config] Errore lettura sessioni: {e}")
        return {}


def save_profiles(profiles: dict) -> bool:
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[config] Errore salvataggio sessioni: {e}")
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
            "protocol": "sftp",
            "host": "192.168.1.100",
            "port": "22",
            "user": "utente",
            "password": "",
            "private_key": "",
            "notes": ""
        },
        "Esempio FTP": {
            "protocol": "ftp",
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
        "Esempio SSH Tunnel": {
            "protocol": "ssh_tunnel",
            "host": "192.168.1.100",
            "port": "22",
            "user": "utente",
            "password": "",
            "tunnel_type": "Proxy SOCKS (-D)",
            "tunnel_local_port": "1080",
            "tunnel_remote_host": "",
            "tunnel_remote_port": "",
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
    },
    "terminal": {
        "default_theme": "Scuro (Default)",
        "default_font": "Monospace",
        "default_font_size": 11,
        "scrollback_lines": 10000,
        "paste_on_right_click": False,
        "confirm_on_close": True,
        "log_output": False,
        "log_dir": "/tmp/pcm_logs",
        "word_delimiters": "/~+-.&?$%",
        "warn_multiline_paste": True,
    },
    "ssh": {
        "keepalive_interval": 60,
        "strict_host_check": False,
        "default_sftp_browser": True,
    },
    "tunnels": [],
    "variables": {},   # variabili globali {NOME: valore}
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
    }
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
        print(f"[config] Errore lettura settings: {e}")
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> bool:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[config] Errore salvataggio settings: {e}")
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
    return s.get("tunnels", [])


def save_tunnels(tunnels: list):
    s = load_settings()
    s["tunnels"] = tunnels
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


if __name__ == "__main__":
    p = load_profiles()
    print(f"Sessioni caricate: {len(p)}")
    s = load_settings()
    print(f"Impostazioni caricate: {list(s.keys())}")
