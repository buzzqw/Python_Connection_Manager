"""
session_command.py - Costruisce i comandi shell per ogni tipo di sessione PCM.
Supporta: SSH, Telnet, SFTP, RDP, VNC, SSH Tunnel, Mosh, Seriale.
"""

import os
import shutil
import subprocess
from typing import Optional, Tuple
import config_manager


# ---------------------------------------------------------------------------
# Helper per il recupero dei percorsi personalizzati
# ---------------------------------------------------------------------------

def _get_tool(cmd_id: str) -> str:
    """
    Recupera il comando da eseguire:
    1. Controlla se l'utente ha impostato un percorso custom (tool_paths).
    2. Altrimenti usa shutil.which per trovare il path assoluto.
    3. Fallback sul nome del comando stesso.
    """
    settings = config_manager.load_settings()
    custom_paths = settings.get("tool_paths", {})

    # Mappa gli alias: se PCM cerca "tigervnc", controlla se l'utente ha configurato "xtigervncviewer"
    alias_map = {
        "tigervnc": "xtigervncviewer",
        "vncviewer": "xtigervncviewer"
    }
    lookup_id = alias_map.get(cmd_id, cmd_id)

    if lookup_id in custom_paths and custom_paths[lookup_id].strip():
        return custom_paths[lookup_id].strip()
    
    if cmd_id in custom_paths and custom_paths[cmd_id].strip():
        return custom_paths[cmd_id].strip()

    return shutil.which(cmd_id) or cmd_id


def _tool_exists(cmd_id: str) -> bool:
    """Controlla se lo strumento esiste (sia esso custom o di sistema)."""
    tool = _get_tool(cmd_id)
    if os.path.isabs(tool) and os.path.exists(tool):
        return True
    return shutil.which(tool) is not None


# ---------------------------------------------------------------------------
# Builders pubblici
# ---------------------------------------------------------------------------

def build_command(profilo: dict) -> Tuple[Optional[str], str]:
    """Restituisce (comando, modalità)"""
    proto = profilo.get("protocol", "ssh").lower()

    if proto == "ssh":
        mode = profilo.get("ssh_open_mode", "Terminale interno")
        if mode.startswith("Terminale esterno"):
            return _wrap_pre(_build_ssh(profilo), profilo), "ssh_term_ext"
        return _wrap_pre(_build_ssh(profilo), profilo), "embedded"
    elif proto == "mosh":
        mode = profilo.get("ssh_open_mode", "Terminale interno")
        if mode.startswith("Terminale esterno"):
            return _wrap_pre(_build_mosh(profilo), profilo), "ssh_term_ext"
        return _wrap_pre(_build_mosh(profilo), profilo), "embedded"
    elif proto == "telnet":
        return _wrap_pre(_build_telnet(profilo), profilo), "embedded"
    elif proto == "sftp":
        mode = profilo.get("sftp_open_mode", "Browser interno")
        if mode.startswith("Browser esterno"):
            return _build_sftp_uri(profilo, "browser_ext"), "sftp_external"
        elif mode.startswith("Terminale interno"):
            return _wrap_pre(_build_sftp_cli(profilo), profilo), "embedded"
        elif mode.startswith("Terminale esterno"):
            return _wrap_pre(_build_sftp_cli(profilo), profilo), "sftp_term_ext"
        else:  
            return _build_sftp(profilo), "sftp_panel"
    elif proto == "ftp":
        mode = profilo.get("ftp_open_mode", "Browser interno")
        if mode.startswith("Browser esterno"):
            return _build_ftp(profilo, modalita="browser_ext"), "ftp_external"
        elif mode.startswith("Terminale interno"):
            return _wrap_pre(_build_ftp(profilo, modalita="term_int"), profilo), "embedded"
        elif mode.startswith("Terminale esterno"):
            return _wrap_pre(_build_ftp(profilo, modalita="term_ext"), profilo), "ftp_term_ext"
        else:  
            return _build_ftp(profilo, modalita="browser_int"), "ftp_panel"
    elif proto == "rdp":
        mode = profilo.get("rdp_open_mode", "external")
        if mode == "internal" or "intern" in mode.lower() or "panel" in mode.lower():
            return None, "rdp_embedded"
        return _build_rdp(profilo), "external"
    elif proto == "vnc":
        return _build_vnc(profilo), "external"
    elif proto == "serial":
        return _wrap_pre(_build_serial(profilo), profilo), "serial"
    else:
        return None, "embedded"


def _wrap_pre(cmd: Optional[str], profilo: dict) -> Optional[str]:
    if not cmd:
        return cmd
    pre = profilo.get("pre_cmd", "").strip()
    if not pre:
        return cmd
    pre_esc = pre.replace("'", r"'\''")
    cmd_esc = cmd.replace("'", r"'\''")
    return (
        "bash -c '"
        "echo \">>> Eseguo pre-connessione: " + pre_esc + "\"; "
        + pre_esc + " && "
        "echo \">>> Pre-connessione completata. Connetto...\"; "
        + cmd_esc +
        " || (echo \">>> Pre-connessione fallita. Connessione annullata.\"; sleep 5)'"
    )


# ---------------------------------------------------------------------------
# Protocol Builders 
# ---------------------------------------------------------------------------

def _build_ssh(p: dict) -> str:
    host  = p.get("host", "")
    user  = p.get("user", "")
    port  = p.get("port", "22")
    pwd   = p.get("password", "")
    pkey  = p.get("private_key", "")
    scmd  = p.get("startup_cmd", "")
    
    args = [f"-p {port}", "-o StrictHostKeyChecking=accept-new", "-o ServerAliveInterval=15", "-o ServerAliveCountMax=3"]

    if pkey and os.path.exists(pkey):
        args.append(f"-i '{pkey}'")
    if p.get("x11"): args.append("-X")
    if p.get("compression"): args.append("-C")
    if p.get("keepalive"):
        args.append("-o ServerAliveInterval=60")
    
    if p.get("jump_host"):
        ju = f"{p.get('jump_user')}@" if p.get('jump_user') else ""
        args.append(f"-J {ju}{p.get('jump_host')}:{p.get('jump_port', '22')}")

    # Compatibilità SSH legacy (server datati, router, NAS, Cisco, ecc.)
    if p.get("legacy_kex"):
        args.append("-o KexAlgorithms=+diffie-hellman-group1-sha1,diffie-hellman-group14-sha1")
    if p.get("legacy_cipher"):
        args.append("-o Ciphers=+aes128-cbc,aes256-cbc,3des-cbc")
    if p.get("legacy_hostkey"):
        args.append("-o HostKeyAlgorithms=+ssh-rsa,ssh-dss")
    if p.get("legacy_mac"):
        args.append("-o MACs=+hmac-sha1,hmac-md5")
    if p.get("legacy_pubkey"):
        args.append("-o PubkeyAcceptedAlgorithms=+ssh-rsa")

    args_str = " ".join(args)
    target = f"{user}@{host}" if user else host
    ssh_exe = _get_tool("ssh")

    if pwd and not pkey:
        if _tool_exists("sshpass"):
            sshpass_exe = _get_tool("sshpass")
            base = f"SSHPASS='{_esc(pwd)}' \"{sshpass_exe}\" -e \"{ssh_exe}\" {args_str} {target}"
        else:
            base = f"\"{ssh_exe}\" {args_str} {target}"
    else:
        base = f"\"{ssh_exe}\" {args_str} {target}"

    if scmd:
        base += f" -t '{_esc(scmd)}; exec $SHELL -l'"
    return base


def _build_telnet(p: dict) -> str:
    host = p.get("host", "")
    port = p.get("port", "23")
    user = p.get("user", "")
    telnet_exe = _get_tool("telnet")

    if not _tool_exists("telnet"):
        return f"bash -c 'echo \"telnet non trovato. Installa telnet.\"; sleep 5'"

    cmd = f"\"{telnet_exe}\" {host} {port}"
    if user:
        cmd = f"\"{telnet_exe}\" -l {user} {host} {port}"
    return cmd


def _build_sftp(p: dict) -> str:
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    return f"sftp://{user}@{host}:{port}"


def _build_ftp(p: dict, modalita: str = "browser_int") -> str:
    host   = p.get("host", "")
    port   = p.get("port", "21")
    user   = p.get("user", "")
    pwd    = p.get("password", "")
    tls    = p.get("ftp_tls", False)
    schema = "ftps" if tls else "ftp"

    uri = f"{schema}://{user}@{host}:{port}" if user else f"{schema}://{host}:{port}"

    if modalita == "browser_ext":
        for fm in ("nautilus", "thunar", "dolphin", "nemo", "pcmanfm", "xdg-open"):
            if _tool_exists(fm):
                return f"\"{_get_tool(fm)}\" '{uri}'"
        return f"xdg-open '{uri}'"

    if modalita in ("term_int", "term_ext"):
        if _tool_exists("lftp"):
            lftp_exe = _get_tool("lftp")
            uri_cred = f"{schema}://{_esc(user)}:{_esc(pwd)}@{host}:{port}" if user and pwd else uri
            return f"\"{lftp_exe}\" -e 'open {uri_cred}' {host}"
        elif _tool_exists("ftp"):
            ftp_exe = _get_tool("ftp")
            if user and pwd:
                return f"bash -c 'printf \"open {host} {port}\\nuser {_esc(user)} {_esc(pwd)}\\nbinary\\n\" | \"{ftp_exe}\" -n'"
            return f"\"{ftp_exe}\" {host} {port}"
        else:
            return "bash -c 'echo \"lftp non trovato.\"; sleep 5'"
    return uri


def _build_sftp_uri(p: dict, modalita: str = "browser_ext") -> str:
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    uri = f"sftp://{user}@{host}:{port}" if user else f"sftp://{host}:{port}"
    
    if modalita == "browser_ext":
        for fm in ("nautilus", "thunar", "dolphin", "nemo", "pcmanfm", "xdg-open"):
            if _tool_exists(fm):
                return f"\"{_get_tool(fm)}\" '{uri}'"
        return f"xdg-open '{uri}'"
    return uri


def _build_sftp_cli(p: dict) -> str:
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    pkey = p.get("private_key", "").strip()
    pwd  = p.get("password", "")

    args = [f"-P {port}", "-o StrictHostKeyChecking=accept-new"]
    if pkey and os.path.exists(pkey):
        args.append(f"-i '{pkey}'")
    args_str = " ".join(args)
    target = f"{user}@{host}" if user else host
    sftp_exe = _get_tool("sftp")

    if pkey and os.path.exists(pkey):
        return f"\"{sftp_exe}\" {args_str} {target}"

    if pwd:
        if _tool_exists("sshpass"):
            return f"SSHPASS='{_esc(pwd)}' \"{_get_tool('sshpass')}\" -e \"{sftp_exe}\" {args_str} {target}"
        elif _tool_exists("lftp"):
            uri_cred = f"sftp://{_esc(user)}:{_esc(pwd)}@{host}:{port}" if user else f"sftp://{host}:{port}"
            return f"\"{_get_tool('lftp')}\" -e 'open {uri_cred}' {host}"

    return f"\"{sftp_exe}\" {args_str} {target}"


def _build_rdp(p: dict) -> str:
    host   = p.get("host", "")
    port   = p.get("port", "3389")
    user   = p.get("user", "")
    pwd    = p.get("password", "")
    domain = p.get("rdp_domain", "").strip()
    client = p.get("rdp_client", "xfreerdp3")
    
    exe = _get_tool(client)

    if client in ("xfreerdp", "xfreerdp3"):
        args = [f"/v:{host}:{port}"]
        if user: args.append(f"/u:{user}")
        if domain: args.append(f"/d:{domain}")
        if pwd: args.append(f"/p:'{_esc(pwd)}'")
        args.append("/cert:ignore")
        if p.get("fullscreen"): args.append("/f")
        if p.get("redirect_clipboard"): args.append("/clipboard")
        if p.get("redirect_drives"): args.append("/drive:home,/home")
        return f"\"{exe}\" {' '.join(args)}"

    elif client == "rdesktop":
        args = ["-a 16"]
        if user: args.append(f"-u {user}")
        if domain: args.append(f"-d {domain}")
        if pwd: args.append(f"-p '{_esc(pwd)}'")
        if p.get("fullscreen"): args.append("-f")
        return f"\"{exe}\" {' '.join(args)} {host}:{port}"

    return f"\"{exe}\" {host}:{port}"


def _build_vnc(p: dict) -> str:
    host   = p.get("host", "")
    port   = p.get("port", "5900")
    pwd    = p.get("password", "")
    client = p.get("vnc_client", "vncviewer")
    # vnc_color: 0=32bpp 1=16bpp 2=8bpp | vnc_quality: 0=best 1=good 2=fast
    # _vnc_idx: gestisce valori legacy salvati come stringa (es. "Truecolor (32 bpp)")
    def _vnc_idx(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    depth = {0: 32, 1: 16, 2: 8}.get(_vnc_idx(p.get("vnc_color",   0), 0), 32)
    qual  = {0: 9,  1: 6,  2: 3}.get(_vnc_idx(p.get("vnc_quality",  2), 2),  6)

    def _passwd_wrap(exe, extra=""):
        return (
            f"bash -c 'TMP=$(mktemp); "
            f"printf '%s' '{_esc(pwd)}' | vncpasswd -f > \"$TMP\"; "
            f'"{exe}" {extra}-passwd "$TMP" {host}::{port}; '
            f"rm -f '$TMP''"
        )

    if client == "realvnc-viewer":
        exe    = _get_tool("realvnc-viewer")
        if exe == "realvnc-viewer":
            exe = _trova_realvnc()
        qlevel = {9: "Full", 6: "Medium", 3: "Low"}.get(qual, "Full")
        clevel = {32: "rgb888", 16: "rgb565", 8: "rgb332"}.get(depth, "rgb888")
        extra  = f"-Quality={qlevel} -ColorLevel={clevel} "
        return f'"{exe}" {extra}{host}::{port}'

    elif client in ("tigervnc", "xtigervncviewer"):
        exe   = _get_tool("xtigervncviewer")
        extra = f"-depth {depth} -quality {qual} "
        if pwd:
            return _passwd_wrap(exe, extra)
        return f'"{exe}" {extra}{host}::{port}'

    elif client == "remmina":
        return f'"{_get_tool("remmina")}" -c vnc://{host}:{port}'

    elif client == "krdc":
        return f'"{_get_tool("krdc")}" vnc://{host}:{port}'

    else:
        # vncviewer generico: può essere TigerVNC rinominato o altro.
        # NON passare -depth/-quality: TigerVNC non li accetta (usa -FullColour
        # e -CompressLevel internamente). Lasciamo solo host::port.
        exe = _get_tool(client)
        if pwd:
            return (
                f"bash -c 'TMP=$(mktemp); "
                f"printf '%s' '{_esc(pwd)}' | vncpasswd -f > \"$TMP\" 2>/dev/null "
                f"|| printf '%s' '{_esc(pwd)}' > \"$TMP\"; "
                f'"{exe}" --PasswordFile="$TMP" {host}::{port} 2>/dev/null '
                f'|| "{exe}" -passwd "$TMP" {host}::{port}; '
                f"rm -f '$TMP''"
            )
        return f'"{exe}" {host}::{port}'


_REALVNC_PATHS = [
    "/usr/bin/realvnc-viewer",
    "/usr/bin/vncviewer-real",
    "/opt/realvnc/VNC-Viewer/vncviewer",
    "/opt/VNC/bin/vncviewer",
    "/snap/bin/realvnc-viewer",
]

def _trova_realvnc() -> str:
    found = shutil.which("realvnc-viewer")
    if found: return found
    for p in _REALVNC_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK): return p
    return "realvnc-viewer"


def _build_mosh(p: dict) -> str:
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    pkey = p.get("private_key", "")
    mosh_exe = _get_tool("mosh")

    if not _tool_exists("mosh"):
        return f"bash -c 'echo \"mosh non trovato.\"; sleep 5'"

    if pkey and os.path.exists(pkey):
        args = [f"--ssh='{_get_tool('ssh')} -p {port} -i {pkey}'"]
    else:
        args = [f"--ssh='{_get_tool('ssh')} -p {port}'"]

    target = f"{user}@{host}" if user else host
    return f"\"{mosh_exe}\" {' '.join(args)} {target}"


def _build_serial(p: dict) -> str:
    device = p.get("device", "/dev/ttyUSB0")
    baud   = p.get("baud", "115200")

    if _tool_exists("picocom"):
        return f"\"{_get_tool('picocom')}\" -b {baud} {device}"
    elif _tool_exists("minicom"):
        return f"\"{_get_tool('minicom')}\" -b {baud} -D {device}"
    elif _tool_exists("screen"):
        return f"\"{_get_tool('screen')}\" {device} {baud}"
    else:
        return f"bash -c 'echo \"Nessun client seriale trovato.\"; sleep 5'"


def _esc(s: str) -> str:
    return s.replace("'", "'\\''")


def check_dipendenze() -> dict:
    tools = {
        "ssh":         _tool_exists("ssh"),
        "sshpass":     _tool_exists("sshpass"),
        "xdotool":     _tool_exists("xdotool"),
        "xwininfo":    _tool_exists("xwininfo"),
        "mosh":        _tool_exists("mosh"),
        "telnet":      _tool_exists("telnet"),
        "picocom":     _tool_exists("picocom"),
    }
    _terminali = ["xterm", "xfce4-terminal", "gnome-terminal", "konsole",
                  "alacritty", "kitty", "terminator", "wezterm",
                  "foot", "tilix", "lxterminal", "mate-terminal", "st"]
    for t in _terminali: tools[t] = shutil.which(t) is not None
    for c in ["xfreerdp3", "xfreerdp", "rdesktop"]: tools[c] = _tool_exists(c)
    for c in ["vncviewer", "realvnc-viewer", "xtigervncviewer", "remmina", "krdc"]: 
        tools[c] = _tool_exists(c)
        
    try:
        import paramiko
        tools["paramiko"] = True
    except ImportError:
        tools["paramiko"] = False
    try:
        import cryptography
        tools["cryptography"] = True
    except ImportError:
        tools["cryptography"] = False
    return tools


def installed_tools(category: str) -> list[str]:
    _map = {
        "terminal": ["xterm", "xfce4-terminal", "gnome-terminal", "konsole",
                     "alacritty", "kitty", "terminator", "wezterm",
                     "foot", "tilix", "lxterminal", "mate-terminal", "st"],
        "rdp":      ["xfreerdp3", "xfreerdp", "rdesktop"],
        "vnc":      ["vncviewer", "realvnc-viewer", "tigervnc", "remmina", "krdc"],
    }
    candidates = _map.get(category, [])
    return [t for t in candidates if shutil.which(t) or _tool_exists(t)]
