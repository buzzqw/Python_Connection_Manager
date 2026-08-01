"""
session_command.py - Costruisce i comandi shell per ogni tipo di sessione PCM.
Supporta: SSH, Telnet, SFTP, RDP, VNC, SSH Tunnel, Mosh, Seriale.
"""

import os
import shlex
import shutil
import subprocess
from urllib.parse import quote
from typing import Optional, Tuple
import config_manager
from protocols import (MODE_INTERNAL, MODE_EXTERNAL, MODE_BROWSER_INT,
                       MODE_BROWSER_EXT, MODE_TERM_INT, MODE_TERM_EXT, is_ftps)


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
        mode = _normalize_mode(profilo.get("ssh_open_mode", MODE_INTERNAL), "ssh_open_mode")
        if mode == MODE_EXTERNAL:
            return _wrap_pre(_build_ssh(profilo), profilo), "ssh_term_ext"
        return _wrap_pre(_build_ssh(profilo), profilo), "embedded"
    elif proto == "mosh":
        mode = _normalize_mode(profilo.get("ssh_open_mode", MODE_INTERNAL), "ssh_open_mode")
        if mode == MODE_EXTERNAL:
            return _wrap_pre(_build_mosh(profilo), profilo), "ssh_term_ext"
        return _wrap_pre(_build_mosh(profilo), profilo), "embedded"
    elif proto == "telnet":
        return _wrap_pre(_build_telnet(profilo), profilo), "embedded"
    elif proto == "sftp":
        return _resolve_sftp_ftp(profilo, ft_sub="SFTP")
    elif proto == "file_transfer":
        ft_sub = profilo.get("ft_protocol", "SFTP").upper()
        if ft_sub == "SFTP":
            return _resolve_sftp_ftp(profilo, ft_sub="SFTP")
        else:
            return _resolve_sftp_ftp(profilo, ft_sub=ft_sub)
    elif proto == "ftp":
        return _resolve_sftp_ftp(profilo, ft_sub="FTP")
    elif proto == "rdp":
        mode = _normalize_mode(profilo.get("rdp_open_mode", MODE_EXTERNAL), "rdp_open_mode")
        if mode == MODE_INTERNAL:
            return None, "rdp_embedded"
        return _build_rdp(profilo), "external"
    elif proto == "vnc":
        return _build_vnc(profilo), "external"
    elif proto == "serial":
        return _wrap_pre(_build_serial(profilo), profilo), "serial"
    elif proto == "exec":
        cmd = profilo.get("exec_cmd", "").strip()
        if not cmd:
            return "bash -c 'echo \"Nessun comando configurato per questa sessione Exec.\"; sleep 5'", "embedded"
        return cmd, "embedded"
    else:
        return None, "embedded"


def _normalize_mode(mode: str, field: str = "") -> str:
    """Converte vecchi valori tradotti o abbreviazioni nelle costanti MODE_*."""
    if not isinstance(mode, str):
        return mode
    m = mode.lower()
    if "estern" in m or "extern" in m:
        if "browser" in m:
            return MODE_BROWSER_EXT
        if "terminal" in m:
            if "sftp_open_mode" in field or "ftp_open_mode" in field:
                return MODE_TERM_EXT
            return MODE_EXTERNAL
        return MODE_EXTERNAL
    if "intern" in m or "panel" in m:
        if "browser" in m:
            return MODE_BROWSER_INT
        if "terminal" in m:
            if "sftp_open_mode" in field or "ftp_open_mode" in field:
                return MODE_TERM_INT
            return MODE_INTERNAL
        return MODE_INTERNAL
    return mode


def _wrap_pre(cmd: Optional[str], profilo: dict) -> Optional[str]:
    if not cmd:
        return cmd
    pre = profilo.get("pre_cmd", "").strip()
    if not pre:
        return cmd
    return pre + " && " + cmd


def _resolve_sftp_ftp(p: dict, ft_sub: str) -> tuple:
    """Risolve comando e modalità per SFTP/FTP/FTPS in modo unificato."""
    if ft_sub == "SFTP":
        mode = _normalize_mode(p.get("sftp_open_mode", MODE_BROWSER_INT), "sftp_open_mode")
        if mode == MODE_BROWSER_EXT:
            return _build_sftp_uri(p, "browser_ext"), "sftp_external"
        elif mode == MODE_TERM_INT:
            return _wrap_pre(_build_sftp_cli(p), p), "embedded"
        elif mode == MODE_TERM_EXT:
            return _wrap_pre(_build_sftp_cli(p), p), "sftp_term_ext"
        else:
            return _build_sftp(p), "sftp_panel"
    else:
        mode = _normalize_mode(p.get("ftp_open_mode", MODE_BROWSER_INT), "ftp_open_mode")
        if mode == MODE_BROWSER_EXT:
            return _build_ftp(p, modalita="browser_ext"), "ftp_external"
        elif mode == MODE_TERM_INT:
            return _wrap_pre(_build_ftp(p, modalita="term_int"), p), "embedded"
        elif mode == MODE_TERM_EXT:
            return _wrap_pre(_build_ftp(p, modalita="term_ext"), p), "ftp_term_ext"
        else:
            return _build_ftp(p, modalita="browser_int"), "ftp_panel"


# ---------------------------------------------------------------------------
# Protocol Builders 
# ---------------------------------------------------------------------------

def _build_ssh(p: dict) -> str:
    host  = p.get("host", "")
    user  = p.get("user", "")
    port  = p.get("port", "22")
    pkey  = p.get("private_key", "")
    scmd  = p.get("startup_cmd", "")

    strict = "yes" if _strict_host_check(p) else "accept-new"

    args = [f"-p {_esc(port)}",
            f"-o StrictHostKeyChecking={strict}",
            "-o ConnectTimeout=10",
            *_keepalive_args(p)]

    if pkey and os.path.exists(pkey):
        args.append(f"-i {_q(pkey)}")
    if p.get("x11"): args.append("-X")
    if p.get("compression"): args.append("-C")
    if p.get("agent_forward"): args.append("-A")

    if p.get("jump_host"):
        jhost = p.get('jump_host', '')
        juser = p.get('jump_user', '')
        jport = p.get('jump_port', '22')
        jtarget = _q(f"{juser}@{jhost}:{jport}") if juser else _q(f"{jhost}:{jport}")
        args.append(f"-J {jtarget}")

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
    target = _q(f"{user}@{host}") if user else _q(host)
    ssh_exe = _get_tool("ssh")

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

    cmd = f"\"{telnet_exe}\" {_q(host)} {_q(port)}"
    if user:
        cmd = f"\"{telnet_exe}\" -l {_q(user)} {_q(host)} {_q(port)}"
    return cmd


def _build_sftp(p: dict) -> str:
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    return f"sftp://{quote(str(user), safe='')}@{host}:{port}"


def _build_ftp(p: dict, modalita: str = "browser_int") -> str:
    host   = p.get("host", "")
    port   = p.get("port", "21")
    user   = p.get("user", "")
    pwd    = p.get("password", "")
    tls    = is_ftps(p)
    schema = "ftps" if tls else "ftp"

    uri_user = quote(str(user), safe="")
    uri = f"{schema}://{uri_user}@{host}:{port}" if user else f"{schema}://{host}:{port}"

    if modalita == "browser_ext":
        for fm in ("nautilus", "thunar", "dolphin", "nemo", "pcmanfm", "xdg-open"):
            if _tool_exists(fm):
                return f"{_q(_get_tool(fm))} {_q(uri)}"
        return f"xdg-open {_q(uri)}"

    if modalita in ("term_int", "term_ext"):
        if _tool_exists("lftp"):
            lftp_exe = _get_tool("lftp")
            uri_cred = (f"{schema}://{uri_user}:{quote(str(pwd), safe='')}@{host}:{port}"
                        if user and pwd else uri)
            return f"{_q(lftp_exe)} -e {_q(f'open {uri_cred}')} {_q(host)}"
        elif _tool_exists("ftp"):
            ftp_exe = _get_tool("ftp")
            if user and pwd:
                script = f"open {host} {port}\nuser {user} {pwd}\nbinary\n"
                return f"printf %s {_q(script)} | {_q(ftp_exe)} -n"
            return f"{_q(ftp_exe)} {_q(host)} {_q(port)}"
        else:
            return "bash -c 'echo \"lftp non trovato.\"; sleep 5'"
    return uri


def _build_sftp_uri(p: dict, modalita: str = "browser_ext") -> str:
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    uri = (f"sftp://{quote(str(user), safe='')}@{host}:{port}"
           if user else f"sftp://{host}:{port}")
    
    if modalita == "browser_ext":
        for fm in ("nautilus", "thunar", "dolphin", "nemo", "pcmanfm", "xdg-open"):
            if _tool_exists(fm):
                return f"{_q(_get_tool(fm))} {_q(uri)}"
        return f"xdg-open {_q(uri)}"
    return uri


def _build_sftp_cli(p: dict) -> str:
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    pkey = p.get("private_key", "").strip()
    pwd  = p.get("password", "")

    strict = "yes" if _strict_host_check(p) else "accept-new"
    args = [f"-P {_q(port)}", f"-o StrictHostKeyChecking={strict}"]
    if pkey and os.path.exists(pkey):
        args.append(f"-i {_q(pkey)}")
    args_str = " ".join(args)
    target = _q(f"{user}@{host}") if user else _q(host)
    sftp_exe = _get_tool("sftp")

    if pkey and os.path.exists(pkey):
        return f"\"{sftp_exe}\" {args_str} {target}"

    if pwd and _tool_exists("lftp"):
        uri_cred = (f"sftp://{quote(str(user), safe='')}:{quote(str(pwd), safe='')}@{host}:{port}"
                    if user else f"sftp://{host}:{port}")
        return f"{_q(_get_tool('lftp'))} -e {_q(f'open {uri_cred}')} {_q(host)}"

    return f"\"{sftp_exe}\" {args_str} {target}"


def _build_rdp(p: dict) -> str:
    """Solo anteprima testuale (editor sessione): la connessione reale usa
    rdp_widget.build_rdp_args, unica fonte di verità per gli argomenti."""
    client = p.get("rdp_client", "xfreerdp3")
    if client not in ("xfreerdp", "xfreerdp3", "rdesktop"):
        host, port = p.get("host", ""), p.get("port", "3389")
        return f"{_q(_get_tool(client))} {_q(f'{host}:{port}')}"

    from rdp_widget import build_rdp_args
    args = build_rdp_args(p, client, exe=_get_tool(client))
    return " ".join(_q(a) for a in args)


def _build_vnc(p: dict) -> str:
    host   = p.get("host", "")
    port   = p.get("port", "5900")
    pwd    = p.get("password", "")
    client = p.get("vnc_client", "vncviewer")

    def _vnc_idx(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    depth = {0: 32, 1: 16, 2: 8}.get(_vnc_idx(p.get("vnc_color",   0), 0), 32)
    qual  = {0: 9,  1: 6,  2: 3}.get(_vnc_idx(p.get("vnc_quality",  2), 2),  6)

    endpoint = f"{host}::{port}"

    def _passwd_wrap(exe, extra="", password_option="-passwd", obfuscate=True):
        import tempfile
        contents = _vnc_obfuscate_password(pwd) if obfuscate else pwd.encode("utf-8")
        if contents is None:
            # vncpasswd non disponibile: niente file password. Scriverlo in
            # chiaro non funzionerebbe comunque, dato che -passwd si aspetta
            # il formato offuscato di vncpasswd(1), non testo semplice.
            # Il client chiederà la password in modo interattivo.
            return f"{_q(exe)} {extra}{_q(endpoint)}"
        fd, tmp_path = tempfile.mkstemp(prefix="pcm_vnc_", suffix=".passwd")
        os.close(fd)
        os.chmod(tmp_path, 0o600)
        with open(tmp_path, "wb") as f:
            f.write(contents)
        command = f"{_q(exe)} {extra}{password_option} {_q(tmp_path)} {_q(endpoint)}"
        # The viewer needs the file until it exits; remove it before returning
        # control to the interactive VTE shell.
        return f"{command}; _pcm_status=$?; rm -f -- {_q(tmp_path)}; (exit $_pcm_status)"

    # Tool personalizzato
    custom = _get_custom_tool("vnc", client)
    if custom:
        exe    = custom["path"]
        syntax = custom.get("syntax", "")
        if syntax == "TigerVNC":
            extra = f"-depth {depth} -quality {qual} "
            if pwd:
                return _passwd_wrap(exe, extra)
            return f"{_q(exe)} {extra}{_q(endpoint)}"
        return f"{_q(exe)} {_q(endpoint)}"

    if client == "realvnc-viewer":
        exe    = _get_tool("realvnc-viewer")
        if exe == "realvnc-viewer":
            exe = _trova_realvnc()
        qlevel = {9: "Full", 6: "Medium", 3: "Low"}.get(qual, "Full")
        clevel = {32: "rgb888", 16: "rgb565", 8: "rgb332"}.get(depth, "rgb888")
        extra  = f"-Quality={qlevel} -ColorLevel={clevel} "
        return f"{_q(exe)} {extra}{_q(endpoint)}"

    elif client in ("tigervnc", "xtigervncviewer"):
        exe   = _get_tool("xtigervncviewer")
        extra = f"-depth {depth} -quality {qual} "
        if pwd:
            return _passwd_wrap(exe, extra)
        return f"{_q(exe)} {extra}{_q(endpoint)}"

    elif client == "remmina":
        return f"{_q(_get_tool('remmina'))} -c {_q(f'vnc://{host}:{port}')}"

    elif client == "krdc":
        return f"{_q(_get_tool('krdc'))} {_q(f'vnc://{host}:{port}')}"

    else:
        exe = _get_tool(client)
        if pwd:
            return _passwd_wrap(exe, password_option="--PasswordFile", obfuscate=False)
        return f"{_q(exe)} {_q(endpoint)}"


def _vnc_obfuscate_password(pwd: str) -> Optional[bytes]:
    """Offusca la password nel formato binario richiesto da -passwd
    (vncviewer/xtigervncviewer): NON è testo semplice, ma il formato
    prodotto da vncpasswd(1) (DES a chiave fissa). Scrivere la password
    in chiaro nel file, come veniva fatto prima, produce un file che il
    client non riesce a leggere e la connessione fallisce sempre quando
    è impostata una password.

    Restituisce None se vncpasswd non è disponibile: in tal caso il
    chiamante deve rinunciare a -passwd (il client chiederà la password
    a schermo) invece di scrivere comunque un file che non funzionerebbe."""
    vncpasswd = shutil.which("vncpasswd")
    if not vncpasswd:
        return None
    try:
        result = subprocess.run(
            [vncpasswd, "-f"], input=pwd.encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=True,
        )
        return result.stdout
    except Exception:
        return None


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

    strict = "yes" if _strict_host_check(p) else "accept-new"
    ssh_args = [
        _q(_get_tool("ssh")), f"-p {_q(port)}",
        f"-o StrictHostKeyChecking={strict}", "-o ConnectTimeout=10",
        *_keepalive_args(p),
    ]
    if pkey and os.path.exists(pkey):
        ssh_args.append(f"-i {_q(pkey)}")
    if p.get("jump_host"):
        jhost = p.get("jump_host", "")
        juser = p.get("jump_user", "")
        jport = p.get("jump_port", "22")
        jump_target = f"{juser}@{jhost}:{jport}" if juser else f"{jhost}:{jport}"
        ssh_args.append(f"-J {_q(jump_target)}")
    args = [f"--ssh={shlex.quote(' '.join(ssh_args))}"]

    target = _q(f"{user}@{host}") if user else _q(host)
    return f"{_q(mosh_exe)} {' '.join(args)} {target}"


def _build_serial(p: dict) -> str:
    device = p.get("device", "/dev/ttyUSB0")
    baud   = p.get("baud", "115200")
    data_bits = str(p.get("data_bits", "8"))
    parity = str(p.get("parity", "None")).lower()
    stop_bits = str(p.get("stop_bits", "1"))

    if _tool_exists("picocom"):
        return (f"{_q(_get_tool('picocom'))} -b {_q(baud)} "
                f"--databits {_q(data_bits)} --parity {_q(parity)} "
                f"--stopbits {_q(stop_bits)} {_q(device)}")
    elif _tool_exists("minicom"):
        return f"{_q(_get_tool('minicom'))} -b {_q(baud)} -D {_q(device)}"
    elif _tool_exists("screen"):
        return f"{_q(_get_tool('screen'))} {_q(device)} {_q(baud)}"
    else:
        return f"bash -c 'echo \"Nessun client seriale trovato.\"; sleep 5'"


def _esc(s: str) -> str:
    """Escape per virgolette singole in contesto bash single-quoted."""
    return s.replace("'", "'\\''")


def _strict_host_check(profile: dict) -> bool:
    """Use the global secure default when a profile has no explicit choice."""
    default = config_manager.load_settings().get("ssh", {}).get("strict_host_check", True)
    return profile.get("strict_host", default)


def _keepalive_args(p: dict) -> list:
    """Argomenti -o ServerAliveInterval/-o ServerAliveCountMax per ssh/mosh.

    Usa l'intervallo per-sessione impostato nell'editor (session_dialog:
    spinner "keepalive_interval", 0 = disabilitato) quando il checkbox
    "Keepalive" è attivo; prima d'ora questo campo veniva salvato nel
    profilo ma non era mai letto da nessun builder, quindi non aveva
    alcun effetto sulla connessione reale."""
    if not p.get("keepalive"):
        return ["-o ServerAliveInterval=15", "-o ServerAliveCountMax=3"]
    default = config_manager.load_settings().get("ssh", {}).get("keepalive_interval", 60)
    try:
        interval = int(p.get("keepalive_interval", default))
    except (TypeError, ValueError):
        interval = default
    if interval <= 0:
        return []
    return [f"-o ServerAliveInterval={interval}", "-o ServerAliveCountMax=3"]


def _q(s: str) -> str:
    """shlex.quote: escape sicuro per qualsiasi parametro shell (previene command injection)."""
    return shlex.quote(str(s))


def check_dipendenze() -> dict:
    tools = {
        "ssh":         _tool_exists("ssh"),
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


def check_dipendenze_categorizzate() -> dict:
    """Controlla le dipendenze categorizzandole per importanza."""
    core_deps = {"ssh": _tool_exists("ssh"), "paramiko": True, "cryptography": True}
    try:
        import paramiko
        core_deps["paramiko"] = True
    except ImportError:
        core_deps["paramiko"] = False
    try:
        import cryptography
        core_deps["cryptography"] = True
    except ImportError:
        core_deps["cryptography"] = False

    _terminali = ["xterm", "xfce4-terminal", "gnome-terminal", "konsole",
                  "alacritty", "kitty", "terminator", "wezterm",
                  "foot", "tilix", "lxterminal", "mate-terminal", "st"]
    recommended_deps = {
        "terminal": any(shutil.which(t) for t in _terminali),
    }
    optional_deps = {
        "xwininfo":  _tool_exists("xwininfo"),
        "mosh":      _tool_exists("mosh"),
        "telnet":    _tool_exists("telnet"),
        "picocom":   _tool_exists("picocom"),
        "rdp_client": any(_tool_exists(c) for c in ["xfreerdp3", "xfreerdp", "rdesktop"]),
        "vnc_client": any(_tool_exists(c) for c in ["vncviewer", "realvnc-viewer", "tigervnc", "remmina", "krdc"]),
    }
    return {
        "core":                 core_deps,
        "recommended":          recommended_deps,
        "optional":             optional_deps,
        "missing_core":         [k for k, v in core_deps.items() if not v],
        "missing_recommended":  [k for k, v in recommended_deps.items() if not v],
    }


def _get_custom_tool(category: str, label: str) -> dict | None:
    """Restituisce il dizionario {label, path, syntax} del tool personalizzato, o None."""
    ct = config_manager.load_custom_tools()
    for entry in ct.get(category, []):
        if entry.get("label") == label:
            return entry
    return None


def installed_tools(category: str) -> list[str]:
    _map = {
        "terminal": ["xterm", "xfce4-terminal", "gnome-terminal", "konsole",
                     "alacritty", "kitty", "terminator", "wezterm",
                     "foot", "tilix", "lxterminal", "mate-terminal", "st"],
        "rdp":      ["xfreerdp3", "xfreerdp", "rdesktop"],
        "vnc":      ["vncviewer", "realvnc-viewer", "tigervnc", "remmina", "krdc"],
    }
    candidates = _map.get(category, [])
    result = [t for t in candidates if shutil.which(t) or _tool_exists(t)]
    # Aggiungi client personalizzati
    if category in ("vnc", "rdp"):
        ct = config_manager.load_custom_tools()
        for entry in ct.get(category, []):
            label = entry.get("label", "").strip()
            path  = entry.get("path", "").strip()
            if label and path and label not in result:
                result.append(label)
    return result
