"""
session_command.py - Costruisce i comandi shell per ogni tipo di sessione PCM.
Supporta: SSH, Telnet, SFTP, RDP, VNC, SSH Tunnel, Mosh, Seriale.
"""

import os
import shutil
import subprocess
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Builders pubblici
# ---------------------------------------------------------------------------

def build_command(profilo: dict) -> Tuple[Optional[str], str]:
    """
    Restituisce (comando, modalità) dove modalità è:
      'embedded'   -> aprire in TerminalWidget interno
      'external'   -> lanciare in background (RDP, VNC standalone, ecc.)
      'sftp_gui'   -> aprire con file manager grafico (thunar, nautilus…)
      'sftp_panel' -> aprire SFTP browser interno via paramiko
      'tunnel'     -> gestire come tunnel SSH
      'serial'     -> connessione seriale
      None         -> errore (comando None)

    Se il profilo contiene 'pre_cmd' (comando locale), il comando finale viene
    wrappato in: bash -c 'pre_cmd && cmd_connessione'
    così il terminale mostra anche l'output del pre-comando.
    """
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
        else:  # Browser interno (default)
            return _build_sftp(profilo), "sftp_panel"
    elif proto == "ftp":
        mode = profilo.get("ftp_open_mode", "Browser interno")
        if mode.startswith("Browser esterno"):
            return _build_ftp(profilo, modalita="browser_ext"), "ftp_external"
        elif mode.startswith("Terminale interno"):
            return _wrap_pre(_build_ftp(profilo, modalita="term_int"), profilo), "embedded"
        elif mode.startswith("Terminale esterno"):
            return _wrap_pre(_build_ftp(profilo, modalita="term_ext"), profilo), "ftp_term_ext"
        else:  # Browser interno (default)
            return _build_ftp(profilo, modalita="browser_int"), "ftp_panel"
    elif proto == "rdp":
        mode = profilo.get("rdp_open_mode", "Finestra esterna")
        if mode.startswith("Pannello interno"):
            # cmd=None: RdpEmbedWidget costruisce il comando internamente
            return None, "rdp_embedded"
        return _build_rdp(profilo), "external"
    elif proto == "vnc":
        return _build_vnc(profilo), "external"
    elif proto == "ssh_tunnel":
        return _build_ssh_tunnel(profilo), "tunnel"
    elif proto == "serial":
        return _wrap_pre(_build_serial(profilo), profilo), "serial"
    else:
        return None, "embedded"


# ---------------------------------------------------------------------------
# Helper: wrap comando con pre_cmd locale
# ---------------------------------------------------------------------------

def _wrap_pre(cmd: Optional[str], profilo: dict) -> Optional[str]:
    """
    Se il profilo ha 'pre_cmd', avvolge il comando in:
        bash -c 'echo ">>> pre_cmd..."; pre_cmd && cmd_connessione'
    In questo modo il terminale mostra l'output del pre-comando prima
    di avviare la connessione.  Se pre_cmd esce con codice != 0, la
    connessione non parte e viene mostrato un messaggio di errore.
    """
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
# SSH
# ---------------------------------------------------------------------------

def _build_ssh(p: dict) -> str:
    host  = p.get("host", "")
    user  = p.get("user", "")
    port  = p.get("port", "22")
    pwd   = p.get("password", "")
    pkey  = p.get("private_key", "")
    x11   = p.get("x11", False)
    comp  = p.get("compression", False)
    ka    = p.get("keepalive", False)
    scmd  = p.get("startup_cmd", "")
    jump  = p.get("jump_host", "")
    juser = p.get("jump_user", "")
    jport = p.get("jump_port", "22")

    args = [f"-p {port}", "-o StrictHostKeyChecking=no",
            "-o ServerAliveInterval=15", "-o ServerAliveCountMax=3"]

    if pkey and os.path.exists(pkey):
        args.append(f"-i '{pkey}'")
    if x11:
        args.append("-X")
    if comp:
        args.append("-C")
    if ka:
        args.append("-o ServerAliveInterval=60 -o ServerAliveCountMax=3")
    if jump:
        ju = f"{juser}@" if juser else ""
        args.append(f"-J {ju}{jump}:{jport}")

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

    # comando base
    if pwd and not pkey:
        if shutil.which("sshpass"):
            base = f"sshpass -p '{_esc(pwd)}' ssh {args_str} {target}"
        else:
            # fallback: ssh chiederà la password interattivamente
            base = f"ssh {args_str} {target}"
    else:
        base = f"ssh {args_str} {target}"

    # comando di avvio remoto
    if scmd:
        base += f" -t '{_esc(scmd)}; exec $SHELL -l'"

    return base


# ---------------------------------------------------------------------------
# Telnet
# ---------------------------------------------------------------------------

def _build_telnet(p: dict) -> str:
    host = p.get("host", "")
    port = p.get("port", "23")
    user = p.get("user", "")

    if not shutil.which("telnet"):
        return f"bash -c 'echo \"telnet non trovato. Installa telnet.\"; sleep 5'"

    cmd = f"telnet {host} {port}"
    # alcuni server accettano -l per il login automatico
    if user:
        cmd = f"telnet -l {user} {host} {port}"
    return cmd


# ---------------------------------------------------------------------------
# SFTP (panel interno – paramiko)
# ---------------------------------------------------------------------------

def _build_sftp(p: dict) -> str:
    """Per SFTP il pannello laterale usa paramiko; qui restituiamo un cmd di info."""
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    return f"sftp://{user}@{host}:{port}"


# ---------------------------------------------------------------------------
# FTP / FTPS (browser interno via ftplib — comando usato solo come fallback CLI)
# ---------------------------------------------------------------------------

def _build_ftp(p: dict, modalita: str = "browser_int") -> str:
    """
    Costruisce il comando/URI FTP in base alla modalità scelta:
      browser_int  → URI ftp:// (usato da PCM per FtpWinScpWidget)
      browser_ext  → comando file manager (nautilus/thunar/dolphin) con URI ftp://
      term_int     → comando lftp/ftp per terminale interno (embedded xterm)
      term_ext     → comando terminale esterno con lftp/ftp
    """
    host   = p.get("host", "")
    port   = p.get("port", "21")
    user   = p.get("user", "")
    pwd    = p.get("password", "")
    tls    = p.get("ftp_tls", False)
    schema = "ftps" if tls else "ftp"

    if user:
        uri = f"{schema}://{user}@{host}:{port}"
    else:
        uri = f"{schema}://{host}:{port}"

    if modalita == "browser_ext":
        for fm in ("nautilus", "thunar", "dolphin", "nemo", "pcmanfm", "xdg-open"):
            if shutil.which(fm):
                return f"{fm} '{uri}'"
        return f"xdg-open '{uri}'"

    if modalita in ("term_int", "term_ext"):
        # lftp con -e "open URI" si connette e autentica in automatico,
        # poi cede il controllo alla shell interattiva di lftp.
        if shutil.which("lftp"):
            schema = "ftps" if tls else "ftp"
            if user and pwd:
                uri_cred = f"{schema}://{_esc(user)}:{_esc(pwd)}@{host}:{port}"
            elif user:
                uri_cred = f"{schema}://{_esc(user)}@{host}:{port}"
            else:
                uri_cred = f"{schema}://{host}:{port}"
            return f"lftp -e 'open {uri_cred}' {host}"
        elif shutil.which("ftp"):
            if user and pwd:
            # ftp non supporta password inline — avvisa e lascia prompt
                return f"bash -c 'printf \"open {host} {port}\\nuser {_esc(user)} {_esc(pwd)}\\nbinary\\n\" | ftp -n'"
            return f"ftp {host} {port}"
        else:
            return "bash -c 'echo \"lftp non trovato. Installa: sudo pacman -S lftp\"; sleep 5'"
    # browser_int (default): restituisce l'URI — PCM aprirà FtpWinScpWidget
    return uri


# ---------------------------------------------------------------------------
# SFTP esteso (browser esterno e CLI)
# ---------------------------------------------------------------------------

def _build_sftp_uri(p: dict, modalita: str = "browser_ext") -> str:
    """URI sftp:// per il file manager di sistema."""
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    if user:
        uri = f"sftp://{user}@{host}:{port}"
    else:
        uri = f"sftp://{host}:{port}"
    if modalita == "browser_ext":
        for fm in ("nautilus", "thunar", "dolphin", "nemo", "pcmanfm", "xdg-open"):
            if shutil.which(fm):
                return f"{fm} '{uri}'"
        return f"xdg-open '{uri}'"
    return uri


def _build_sftp_cli(p: dict) -> str:
    """
    Comando sftp CLI per terminale interno/esterno.
    Priorità autenticazione:
      1. Chiave privata  → sftp -i chiave user@host
      2. sshpass         → sshpass -p pwd sftp user@host
      3. lftp (fallback) → lftp -e 'open sftp://user:pwd@host:port' host
      4. sftp plain      → chiede password interattivamente
    """
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    pkey = p.get("private_key", "").strip()
    pwd  = p.get("password", "")

    args = [f"-P {port}", "-o StrictHostKeyChecking=no"]
    if pkey and os.path.exists(pkey):
        args.append(f"-i '{pkey}'")
    args_str = " ".join(args)
    target = f"{user}@{host}" if user else host

    if pkey and os.path.exists(pkey):
        # Chiave privata: sftp la usa direttamente, nessuna password necessaria
        return f"sftp {args_str} {target}"

    if pwd:
        if shutil.which("sshpass"):
            return f"sshpass -p '{_esc(pwd)}' sftp {args_str} {target}"
        elif shutil.which("lftp"):
            # lftp supporta sftp con credenziali inline
            uri_cred = f"sftp://{_esc(user)}:{_esc(pwd)}@{host}:{port}" if user else f"sftp://{host}:{port}"
            return f"lftp -e 'open {uri_cred}' {host}"

    # Fallback: sftp chiede la password interattivamente
    return f"sftp {args_str} {target}"


# ---------------------------------------------------------------------------
# RDP
# ---------------------------------------------------------------------------

def _build_rdp(p: dict) -> str:
    host   = p.get("host", "")
    port   = p.get("port", "3389")
    user   = p.get("user", "")
    pwd    = p.get("password", "")
    domain = p.get("rdp_domain", "").strip()
    client = p.get("rdp_client", "xfreerdp3")   # xfreerdp3 è il default attuale
    fs     = p.get("fullscreen", False)
    clips  = p.get("redirect_clipboard", True)
    drives = p.get("redirect_drives", False)

    if client in ("xfreerdp", "xfreerdp3"):
        args = [f"/v:{host}:{port}"]
        if user:
            args.append(f"/u:{user}")
        if domain:
            args.append(f"/d:{domain}")
        if pwd:
            args.append(f"/p:'{_esc(pwd)}'")
        args.append("/cert:ignore")
        if fs:
            args.append("/f")
        if clips:
            args.append("/clipboard")
        if drives:
            args.append("/drive:home,/home")
        return f"{client} {' '.join(args)}"

    elif client == "rdesktop":
        args = ["-a 16"]
        if user:
            args.append(f"-u {user}")
        if domain:
            args.append(f"-d {domain}")
        if pwd:
            args.append(f"-p '{_esc(pwd)}'")
        if fs:
            args.append("-f")
        return f"rdesktop {' '.join(args)} {host}:{port}"

    else:
        return f"{client} {host}:{port}"


# ---------------------------------------------------------------------------
# VNC
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# VNC
# ---------------------------------------------------------------------------

# Path noti di RealVNC Viewer su Linux
_REALVNC_PATHS = [
    "/usr/bin/realvnc-viewer",
    "/usr/bin/vncviewer-real",          # alcuni pacchetti AUR
    "/opt/realvnc/VNC-Viewer/vncviewer",
    "/opt/VNC/bin/vncviewer",
    "/snap/bin/realvnc-viewer",
]


def _build_vnc(p: dict) -> str:
    host   = p.get("host", "")
    port   = p.get("port", "5900")
    pwd    = p.get("password", "")
    client = p.get("vnc_client", "vncviewer")   # valore esatto dal combo

    # --- RealVNC Viewer ---
    if client == "realvnc-viewer":
        exe = _trova_realvnc()
        # RealVNC accetta  host::port  (doppio colon = porta diretta)
        cmd = f'"{exe}" {host}::{port}'
        return cmd

    # --- TigerVNC ---
    elif client == "tigervnc":
        exe = shutil.which("vncviewer") or "vncviewer"
        if pwd:
            return (
                f"bash -c '"
                f"TMP=$(mktemp); "
                f"printf \"%s\" \"{_esc(pwd)}\" | vncpasswd -f > \"$TMP\"; "
                f"{exe} -passwd \"$TMP\" {host}::{port}; "
                f"rm -f \"$TMP\"'"
            )
        return f"{exe} {host}::{port}"

    # --- Remmina ---
    elif client == "remmina":
        exe = shutil.which("remmina") or "remmina"
        return f"{exe} -c vnc://{host}:{port}"

    # --- KRDC ---
    elif client == "krdc":
        exe = shutil.which("krdc") or "krdc"
        return f"{exe} vnc://{host}:{port}"

    # --- vncviewer generico (default) ---
    else:
        # usa il client esattamente come scritto nel campo
        exe = shutil.which(client) or client
        return f"{exe} {host}::{port}"


def _trova_realvnc() -> str:
    """
    Cerca il binario di RealVNC Viewer nell'ordine:
    1. Il nome 'realvnc-viewer' nel PATH (symlink da pacchetti AUR/deb)
    2. Path noti di installazione
    3. Fallback: 'realvnc-viewer' così com'è (darà errore chiaro se mancante)
    """
    # Prima prova: nome esatto nel PATH
    found = shutil.which("realvnc-viewer")
    if found:
        return found

    # Seconda prova: path fissi
    for p in _REALVNC_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p

    # Ultima spiaggia: restituisce il nome e lascia che la shell dia errore leggibile
    return "realvnc-viewer"


# ---------------------------------------------------------------------------
# SSH Tunnel
# ---------------------------------------------------------------------------

def _build_ssh_tunnel(p: dict) -> str:
    host       = p.get("host", "")
    port       = p.get("port", "22")
    user       = p.get("user", "")
    pwd        = p.get("password", "")
    pkey       = p.get("private_key", "")
    ttype      = p.get("tunnel_type", "Proxy SOCKS (-D)")
    lport      = p.get("tunnel_local_port", "1080")
    rhost      = p.get("tunnel_remote_host", "")
    rport      = p.get("tunnel_remote_port", "")

    args = [f"-p {port}", "-N", "-o StrictHostKeyChecking=no",
            "-o ServerAliveInterval=15", "-o ServerAliveCountMax=3"]
    if pkey and os.path.exists(pkey):
        args.append(f"-i '{pkey}'")

    if ttype == "Proxy SOCKS (-D)":
        args.append(f"-D {lport}")
    elif ttype == "Locale (-L)" and rhost and rport:
        args.append(f"-L {lport}:{rhost}:{rport}")
    elif ttype == "Remoto (-R)" and rhost and rport:
        args.append(f"-R {lport}:{rhost}:{rport}")

    target = f"{user}@{host}" if user else host
    args_str = " ".join(args)

    if pwd and not pkey and shutil.which("sshpass"):
        return f"sshpass -p '{_esc(pwd)}' ssh {args_str} {target}"
    return f"ssh {args_str} {target}"


# ---------------------------------------------------------------------------
# Mosh
# ---------------------------------------------------------------------------

def _build_mosh(p: dict) -> str:
    host = p.get("host", "")
    port = p.get("port", "22")
    user = p.get("user", "")
    pkey = p.get("private_key", "")

    if not shutil.which("mosh"):
        return f"bash -c 'echo \"mosh non trovato. Installa mosh.\"; sleep 5'"

    args = [f"--ssh='ssh -p {port}'"]
    if pkey and os.path.exists(pkey):
        args.append(f"--ssh='ssh -p {port} -i {pkey}'")

    target = f"{user}@{host}" if user else host
    return f"mosh {' '.join(args)} {target}"


# ---------------------------------------------------------------------------
# Seriale (minicom / picocom / screen)
# ---------------------------------------------------------------------------

def _build_serial(p: dict) -> str:
    device = p.get("device", "/dev/ttyUSB0")
    baud   = p.get("baud", "115200")

    if shutil.which("picocom"):
        return f"picocom -b {baud} {device}"
    elif shutil.which("minicom"):
        return f"minicom -b {baud} -D {device}"
    elif shutil.which("screen"):
        return f"screen {device} {baud}"
    else:
        return f"bash -c 'echo \"Nessun client seriale trovato (picocom/minicom/screen).\"; sleep 5'"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    """Escape semplice per singoli apici in shell."""
    return s.replace("'", "'\\''")


def check_dipendenze() -> dict:
    """Controlla la disponibilità degli strumenti necessari."""
    tools = {
        "xterm":       shutil.which("xterm") is not None,
        "ssh":         shutil.which("ssh") is not None,
        "sshpass":     shutil.which("sshpass") is not None,
        "xfreerdp3":   shutil.which("xfreerdp3") is not None,
        "vncviewer":   shutil.which("vncviewer") is not None,
        "mosh":        shutil.which("mosh") is not None,
        "telnet":      shutil.which("telnet") is not None,
        "xdotool":     shutil.which("xdotool") is not None,
        "xwininfo":    shutil.which("xwininfo") is not None,
        "picocom":     shutil.which("picocom") is not None,
        "remmina":     shutil.which("remmina") is not None,
    }
    try:
        import paramiko
        tools["paramiko"] = True
    except ImportError:
        tools["paramiko"] = False
    return tools
