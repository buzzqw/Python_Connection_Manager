"""
protocols.py - Definizioni centralizzate per protocolli PCM.

Colori, etichette, icone, porte di default, campi rilevanti per tipo
e costanti di modalità apertura.  Usato da session_dialog, session_panel,
session_command, quick_connect_dialog.
"""

# ---------------------------------------------------------------------------
# Enum protocolli
# ---------------------------------------------------------------------------

PROTOCOLS = ["ssh", "telnet", "file_transfer", "rdp", "vnc", "mosh", "serial", "exec"]

PROTO_LABEL = {
    "ssh": "SSH", "telnet": "Telnet", "file_transfer": "FTP/SFTP",
    "rdp": "RDP", "vnc": "VNC", "mosh": "Mosh", "serial": "Seriale",
    "exec": "Exec",
}

PROTO_COLOR = {
    "ssh":    "#4ec9b0", "telnet": "#c9b458", "sftp":   "#6ab187",
    "ftp":    "#b87a00", "rdp":    "#0078d4", "vnc":    "#e8a020",
    "mosh":   "#5aadad", "serial": "#888888", "exec":   "#c586c0",
    "file_transfer": "#6ab187",
}

PROTO_ICON_FILE = {
    "ssh":    "ssh.png",    "telnet": "network.png", "sftp":  "folder.png",
    "ftp":    "folder.png", "rdp":    "monitor.png", "vnc":   "vnc.png",
    "mosh":   "flash.png",  "serial": "cable.png",   "exec":  "flash.png",
    "file_transfer": "folder.png",
}

DEFAULT_PORT = {
    "ssh": "22", "telnet": "23", "file_transfer": "22",
    "rdp": "3389", "vnc": "5900", "mosh": "22", "serial": "",
    "exec": "",
}

# ---------------------------------------------------------------------------
# Costanti di modalità apertura (salvate nel JSON, mai tradotte)
# ---------------------------------------------------------------------------

MODE_INTERNAL        = "internal"
MODE_EXTERNAL        = "external"
MODE_BROWSER_INT     = "browser_int"       # per FTP/SFTP
MODE_BROWSER_EXT     = "browser_ext"
MODE_TERM_INT        = "term_int"
MODE_TERM_EXT        = "term_ext"
MODE_PANEL           = "panel"             # SFTP panel, FTP internal browser
MODE_RDP_EMBED       = "rdp_embedded"
MODE_EMBED           = "embedded"

# VNC sub-mode
VNC_EXT              = "vnc_external"
VNC_NOVNC            = "vnc_novnc"

# RDP monitor sub-mode
RDP_MON_SINGLE       = "single"
RDP_MON_ALL          = "all"
RDP_MON_CUSTOM       = "custom"

# Tunnel sub-types (salvati nel JSON, non le label tradotte)
TUNNEL_SOCKS         = "socks"
TUNNEL_LOCAL         = "local"
TUNNEL_REMOTE        = "remote"

# ---------------------------------------------------------------------------
# Campi rilevanti per protocollo (da salvare nel JSON)
# ---------------------------------------------------------------------------

# Campi comuni a tutte le sessioni
_COMMON_FIELDS = {
    "protocol", "group", "host", "port", "user", "password", "private_key",
    "notes", "credential_profile", "totp_secret",
    "is_template", "template_name", "tags",
}

_TERM_FIELDS = {
    "term_theme", "term_font", "term_size", "startup_cmd",
    "term_scrollback_lines", "term_infinite_scrollback", "term_encoding",
    "term_bell", "term_confirm_close", "term_warn_paste", "paste_on_right_click",
    "auto_reconnect", "reconnect_delay", "terminal_type",
    "log_output", "log_dir",
}

_GATEWAY_FIELDS = {"jump_host", "jump_user", "jump_port"}

_SSH_FIELDS = {
    "jump_host", "jump_user", "jump_port",
    "x11", "compression", "keepalive", "keepalive_interval",
    "strict_host", "agent_forward",
    "legacy_kex", "legacy_cipher", "legacy_hostkey",
    "legacy_mac", "legacy_pubkey",
    "ssh_open_mode",
}

_SFTP_FIELDS = {
    "ft_protocol", "sftp_open_mode",
    "sftp_browser",
}

_FTP_FIELDS = {
    "ft_protocol", "ftp_tls", "ftp_passive", "ftp_open_mode",
}

_RDP_FIELDS = {
    "rdp_client", "rdp_auth", "rdp_domain", "fullscreen",
    "redirect_clipboard", "redirect_drives", "rdp_open_mode",
    "rdp_monitor_mode", "rdp_monitor_ids",
}

_VNC_FIELDS = {
    "vnc_internal", "vnc_client", "vnc_color", "vnc_quality",
}

_SERIAL_FIELDS = {
    "device", "baud", "data_bits", "parity", "stop_bits",
}

_EXEC_FIELDS = {
    "exec_cmd",
}

_TUNNEL_FIELDS = {
    "tunnel_type", "tunnel_local_port", "tunnel_remote_host", "tunnel_remote_port",
}

_MON_FIELDS = {
    "mon_ssh_port", "panel_cpu_mem", "panel_processes",
    "panel_disk", "panel_network", "panel_log",
}

_WOL_FIELDS = {
    "wol_enabled", "wol_mac", "wol_wait",
}

_PRECMD_FIELDS = {
    "pre_cmd", "pre_cmd_timeout",
}

_MACRO_FIELDS = {"macros", "expect_rules"}

# Mappa protocol → set of relevant field keys
PROTO_FIELDS = {
    "ssh":           (_COMMON_FIELDS | _TERM_FIELDS | _SSH_FIELDS | _SFTP_FIELDS |
                       _TUNNEL_FIELDS | _MON_FIELDS | _WOL_FIELDS | _PRECMD_FIELDS | _MACRO_FIELDS),
    "telnet":        (_COMMON_FIELDS | _TERM_FIELDS | _TUNNEL_FIELDS |
                       _WOL_FIELDS | _PRECMD_FIELDS | _MACRO_FIELDS),
    "mosh":          (_COMMON_FIELDS | _TERM_FIELDS | _SSH_FIELDS | _SFTP_FIELDS |
                       _TUNNEL_FIELDS | _MON_FIELDS | _WOL_FIELDS | _PRECMD_FIELDS | _MACRO_FIELDS),
    "file_transfer": (_COMMON_FIELDS | _TERM_FIELDS | _SSH_FIELDS | _SFTP_FIELDS | _FTP_FIELDS |
                       _TUNNEL_FIELDS | _WOL_FIELDS | _PRECMD_FIELDS | _MACRO_FIELDS),
    "rdp":           (_COMMON_FIELDS | _RDP_FIELDS | _TUNNEL_FIELDS | _GATEWAY_FIELDS |
                        _MON_FIELDS | _WOL_FIELDS | _PRECMD_FIELDS | _MACRO_FIELDS),
    "vnc":           (_COMMON_FIELDS | _VNC_FIELDS | _TUNNEL_FIELDS | _GATEWAY_FIELDS |
                       _MON_FIELDS | _WOL_FIELDS | _PRECMD_FIELDS | _MACRO_FIELDS),
    "serial":        (_COMMON_FIELDS | _TERM_FIELDS | _SERIAL_FIELDS |
                       _PRECMD_FIELDS | _MACRO_FIELDS),
    "exec":          (_COMMON_FIELDS | _TERM_FIELDS | _EXEC_FIELDS |
                       _TUNNEL_FIELDS | _MACRO_FIELDS),
}

# Nomi validi dei protocolli (inclusi legacy per validazione)
VALID_PROTOCOLS = set(PROTOCOLS) | {"sftp", "ftp"}


def is_ftps(profile: dict) -> bool:
    """Return whether a file-transfer profile requires explicit TLS."""
    return bool(profile.get("ftp_tls") or
                str(profile.get("ft_protocol", "")).upper() == "FTPS")


# ---------------------------------------------------------------------------
# Validazione profili
# ---------------------------------------------------------------------------

def validate_profiles(profiles: dict) -> dict:
    """
    Valida e pulisce i profili caricati.
    - Normalizza protocolli legacy (sftp/ftp → file_transfer)
    - Rimuove campi non pertinenti al protocollo
    - Corregge tipi errati dove possibile
    Restituisce il dizionario validato.
    """
    valid = {}
    issues = []
    for nome, dati in profiles.items():
        if not isinstance(dati, dict):
            issues.append((nome, "non è un dizionario, ignorato"))
            continue
        proto = dati.get("protocol", "ssh")
        if proto == "sftp":
            proto = "file_transfer"
            dati = dict(dati)
            if "ft_protocol" not in dati:
                dati["ft_protocol"] = "SFTP"
        elif proto == "ftp":
            proto = "file_transfer"
            dati = dict(dati)
            if "ft_protocol" not in dati:
                dati["ft_protocol"] = "FTPS" if dati.get("ftp_tls") else "FTP"
        if proto not in VALID_PROTOCOLS:
            issues.append((nome, f"protocollo sconosciuto '{proto}', ignorato"))
            continue
        dati = dict(dati)
        dati["protocol"] = proto

        host = str(dati.get("host", ""))
        port = str(dati.get("port", ""))
        if host and any(c in host for c in ' ;|&$(){}[]`\'"\\!@#%^*'):
            issues.append((nome, f"host '{host}' contiene metacaratteri non consentiti"))
            continue
        if port and not port.isdigit():
            issues.append((nome, f"porta '{port}' non numerica"))
            continue

        # Pulisci campi non pertinenti
        allowed = PROTO_FIELDS.get(proto, _COMMON_FIELDS)
        dati = {k: v for k, v in dati.items() if k in allowed}
        # Normalizza vecchi valori tradotti in costanti
        dati = _normalize_modes(dati)
        valid[nome] = dati
    if issues:
        from pcm_logging import get_logger
        _log = get_logger(__name__)
        _log.warning("Problemi di validazione profili")
        for nome, msg in issues:
            _log.warning("  - %s: %s", nome, msg)
    return valid


def _normalize_modes(dati: dict) -> dict:
    """Converte vecchi valori testuali (IT/EN) nelle nuove costanti."""
    proto = dati.get("protocol", "ssh")

    for field in ("ssh_open_mode",):
        if field in dati:
            v = dati[field]
            if isinstance(v, str) and ("intern" in v.lower() or v == "internal"):
                dati[field] = MODE_INTERNAL
            elif isinstance(v, str) and ("estern" in v.lower() or "extern" in v.lower()):
                dati[field] = MODE_EXTERNAL

    if proto == "file_transfer" or proto in ("sftp", "ftp"):
        for field in ("sftp_open_mode", "ftp_open_mode"):
            if field in dati:
                v = str(dati[field])
                if "Browser esterno" in v or v == "browser_external":
                    dati[field] = MODE_BROWSER_EXT
                elif "Terminale interno" in v:
                    dati[field] = MODE_TERM_INT
                elif "Terminale esterno" in v:
                    dati[field] = MODE_TERM_EXT
                elif "Browser interno" in v:
                    dati[field] = MODE_BROWSER_INT

    if proto == "rdp" and "rdp_open_mode" in dati:
        v = str(dati["rdp_open_mode"])
        if "intern" in v.lower() or "panel" in v.lower():
            dati["rdp_open_mode"] = MODE_INTERNAL
        else:
            dati["rdp_open_mode"] = MODE_EXTERNAL

    return dati


# ---------------------------------------------------------------------------
# Dynamic protocol registration (for plugins)
# ---------------------------------------------------------------------------

def register_protocol(proto_id: str, label: str, color: str = "#888888",
                      icon_file: str = "network.png", default_port: str = "",
                      fields: set = None) -> None:
    """Register a new protocol from a plugin at runtime."""
    if proto_id not in PROTOCOLS:
        PROTOCOLS.append(proto_id)
    PROTO_LABEL[proto_id] = label
    PROTO_COLOR[proto_id] = color
    PROTO_ICON_FILE[proto_id] = icon_file
    if default_port:
        DEFAULT_PORT[proto_id] = default_port
    if fields:
        PROTO_FIELDS[proto_id] = fields
    VALID_PROTOCOLS.add(proto_id)


def unregister_protocol(proto_id: str) -> None:
    """Remove a dynamically registered protocol."""
    if proto_id in PROTOCOLS:
        PROTOCOLS.remove(proto_id)
    PROTO_LABEL.pop(proto_id, None)
    PROTO_COLOR.pop(proto_id, None)
    PROTO_ICON_FILE.pop(proto_id, None)
    DEFAULT_PORT.pop(proto_id, None)
    PROTO_FIELDS.pop(proto_id, None)
    VALID_PROTOCOLS.discard(proto_id)


def refresh_from_plugins() -> None:
    """Synchronize protocol definitions with loaded plugins."""
    from plugins.plugin_base import pcm_get_protocol_plugins
    for proto_id, plugin in pcm_get_protocol_plugins().items():
        info = plugin.plugin_info
        register_protocol(
            proto_id=proto_id,
            label=info.name,
            default_port=plugin.default_port or "",
            fields=plugin.profile_fields | _COMMON_FIELDS | _GATEWAY_FIELDS,
        )


# ---------------------------------------------------------------------------
# Compatibilità backward: mappa protocollo → label estesa per sidebar
# ---------------------------------------------------------------------------

def label_for_panel(proto: str) -> str:
    if proto in ("sftp", "ftp"):
        return proto.upper()
    return PROTO_LABEL.get(proto, proto.upper())


def color_for_panel(proto: str) -> str:
    return PROTO_COLOR.get(proto, "#888888")


def icon_for_panel(proto: str) -> str:
    return PROTO_ICON_FILE.get(proto, "network.png")
