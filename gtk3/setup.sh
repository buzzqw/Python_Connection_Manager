#!/usr/bin/env bash
# setup.sh — Installazione dipendenze PCM (Python Connection Manager) GTK3
# Supporta: Debian/Ubuntu, Arch Linux, openSUSE, Fedora/RHEL
#
# Uso:
#   bash setup.sh           # installa tutto (dipendenze sistema + pip)
#   bash setup.sh --check   # verifica senza installare
#   bash setup.sh --pip     # solo dipendenze pip (già in venv/utente)

set -euo pipefail

# ── Colori ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC}  $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "  ${RED}✗${NC}  $*"; }
hdr()  { echo -e "\n${BOLD}${BLUE}── $* ──────────────────────────────────────${NC}"; }

MODE="full"
[[ "${1:-}" == "--check" ]] && MODE="check"
[[ "${1:-}" == "--pip"   ]] && MODE="pip"

# ── Rileva distribuzione ──────────────────────────────────────────────────
detect_distro() {
    if   command -v apt-get  &>/dev/null; then echo "debian"
    elif command -v pacman   &>/dev/null; then echo "arch"
    elif command -v zypper   &>/dev/null; then echo "suse"
    elif command -v dnf      &>/dev/null; then echo "fedora"
    elif command -v yum      &>/dev/null; then echo "rhel"
    else echo "unknown"
    fi
}

DISTRO=$(detect_distro)

# ── Pacchetti per distribuzione ───────────────────────────────────────────
#
# LEGENDA DIPENDENZE:
#   [RICHIESTO]   — PCM non parte senza questo
#   [Raccomandato]— funzionalità importanti (SSH, VNC, ecc.)
#   [Opzionale]   — funzionalità aggiuntive
#
declare -A PKG_DEBIAN PKG_ARCH PKG_SUSE PKG_FEDORA

# ── Python + GObject (RICHIESTO) ──────────────────────────────────────────
PKG_DEBIAN[python]="python3 python3-pip python3-gi python3-gi-cairo gir1.2-gtk-3.0"
PKG_ARCH[python]="python python-pip python-gobject gtk3"
PKG_SUSE[python]="python3 python3-pip python3-gobject typelib-1_0-Gtk-3_0"
PKG_FEDORA[python]="python3 python3-pip python3-gobject gtk3"

# ── VTE terminale embedded (RICHIESTO) ────────────────────────────────────
PKG_DEBIAN[vte]="gir1.2-vte-2.91"
PKG_ARCH[vte]="vte3"
PKG_SUSE[vte]="typelib-1_0-Vte-2.91"
PKG_FEDORA[vte]="vte291"

# ── Pixbuf / GdkPixbuf (RICHIESTO) ───────────────────────────────────────
PKG_DEBIAN[pixbuf]="gir1.2-gdkpixbuf-2.0"
PKG_ARCH[pixbuf]="gdk-pixbuf2"
PKG_SUSE[pixbuf]="typelib-1_0-GdkPixbuf-2_0"
PKG_FEDORA[pixbuf]="gdk-pixbuf2"

# ── VNC integrato gtk-vnc (Raccomandato) ─────────────────────────────────
PKG_DEBIAN[gtkvnc]="gir1.2-gtkvnc-2.0"
PKG_ARCH[gtkknc]="gtk-vnc"
PKG_SUSE[gtkknc]="typelib-1_0-GtkVnc-2_0"
PKG_FEDORA[gtkknc]="gtk-vnc2"

# ── WebKit2 per noVNC (Opzionale) ─────────────────────────────────────────
PKG_DEBIAN[webkit]="gir1.2-webkit2-4.1"
PKG_ARCH[webkit]="webkit2gtk"
PKG_SUSE[webkit]="typelib-1_0-WebKit2-4_1"
PKG_FEDORA[webkit]="webkit2gtk4.1"

# ── SSH / SFTP / Mosh (Raccomandato) ─────────────────────────────────────
PKG_DEBIAN[ssh]="openssh-client mosh"
PKG_ARCH[ssh]="openssh mosh"
PKG_SUSE[ssh]="openssh mosh"
PKG_FEDORA[ssh]="openssh-clients mosh"

# ── Telnet (Opzionale) ────────────────────────────────────────────────────
PKG_DEBIAN[telnet]="telnet"
PKG_ARCH[telnet]="inetutils"
PKG_SUSE[telnet]="telnet"
PKG_FEDORA[telnet]="telnet"

# ── RDP client (Raccomandato) ─────────────────────────────────────────────
PKG_DEBIAN[rdp]="freerdp3-x11"
PKG_ARCH[rdp]="freerdp"
PKG_SUSE[rdp]="freerdp"
PKG_FEDORA[rdp]="freerdp"

# ── VNC client esterno (Raccomandato) ─────────────────────────────────────
PKG_DEBIAN[vncviewer]="tigervnc-viewer"
PKG_ARCH[vncviewer]="tigervnc"
PKG_SUSE[vncviewer]="tigervnc"
PKG_FEDORA[vncviewer]="tigervnc"

# ── Seriale (Opzionale) ───────────────────────────────────────────────────
PKG_DEBIAN[serial]="minicom"
PKG_ARCH[serial]="minicom"
PKG_SUSE[serial]="minicom"
PKG_FEDORA[serial]="minicom"

# ── xdotool per embedding RDP (Opzionale) ────────────────────────────────
PKG_DEBIAN[xdotool]="xdotool"
PKG_ARCH[xdotool]="xdotool"
PKG_SUSE[xdotool]="xdotool"
PKG_FEDORA[xdotool]="xdotool"

# ── Wake-on-LAN (Opzionale) ───────────────────────────────────────────────
PKG_DEBIAN[wol]="wakeonlan"
PKG_ARCH[wol]="wol"
PKG_SUSE[wol]="wol"
PKG_FEDORA[wol]="wol"

# ── xdg-utils per aprire la guida (Raccomandato) ─────────────────────────
PKG_DEBIAN[xdg]="xdg-utils"
PKG_ARCH[xdg]="xdg-utils"
PKG_SUSE[xdg]="xdg-utils"
PKG_FEDORA[xdg]="xdg-utils"

# ── pip packages (RICHIESTO) ──────────────────────────────────────────────
PIP_PACKAGES=(
    "cryptography>=41.0"
    "paramiko>=3.0"
    "pyftpdlib>=1.5"
)

# ── Funzioni installazione ────────────────────────────────────────────────

install_debian() {
    local pkgs=()
    for key in python vte pixbuf gtkknc webkit ssh telnet rdp vncviewer serial xdotool wol xdg; do
        local p="${PKG_DEBIAN[$key]:-}"
        [[ -n "$p" ]] && pkgs+=($p)
    done
    echo -e "  Pacchetti: ${pkgs[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${pkgs[@]}"
}

install_arch() {
    local pkgs=()
    for key in python vte pixbuf gtkknc webkit ssh telnet rdp vncviewer serial xdotool wol xdg; do
        local p="${PKG_ARCH[$key]:-}"
        [[ -n "$p" ]] && pkgs+=($p)
    done
    echo -e "  Pacchetti: ${pkgs[*]}"
    sudo pacman -Sy --noconfirm --needed "${pkgs[@]}"
}

install_suse() {
    local pkgs=()
    for key in python vte pixbuf gtkknc webkit ssh telnet rdp vncviewer serial xdotool wol xdg; do
        local p="${PKG_SUSE[$key]:-}"
        [[ -n "$p" ]] && pkgs+=($p)
    done
    echo -e "  Pacchetti: ${pkgs[*]}"
    sudo zypper install -y "${pkgs[@]}"
}

install_fedora() {
    local pkgs=()
    for key in python vte pixbuf gtkknc webkit ssh telnet rdp vncviewer serial xdotool wol xdg; do
        local p="${PKG_FEDORA[$key]:-}"
        [[ -n "$p" ]] && pkgs+=($p)
    done
    echo -e "  Pacchetti: ${pkgs[*]}"
    sudo dnf install -y "${pkgs[@]}"
}

install_pip() {
    hdr "Dipendenze Python (pip)"
    # Preferisce pip3 in venv o --user
    local pip_cmd="pip3"
    command -v pip3 &>/dev/null || pip_cmd="pip"

    # Rileva se siamo in un venv
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        echo "  Ambiente virtuale attivo: $VIRTUAL_ENV"
        $pip_cmd install --quiet "${PIP_PACKAGES[@]}"
    else
        echo "  Installazione in modalità --user (no venv rilevato)"
        $pip_cmd install --quiet --user "${PIP_PACKAGES[@]}"
    fi

    for pkg in "${PIP_PACKAGES[@]}"; do
        local name="${pkg%%[>=<]*}"
        if python3 -c "import ${name//-/_}" &>/dev/null 2>&1 || \
           python3 -c "import ${name,,}" &>/dev/null 2>&1; then
            ok "$pkg"
        else
            warn "$pkg (verifica manualmente)"
        fi
    done
}

# ── Verifica finale ────────────────────────────────────────────────────────

check_python_modules() {
    hdr "Moduli Python"
    local modules=(
        "gi:PyGObject (GTK)"
        "cryptography:cryptography"
        "paramiko:paramiko"
        "pyftpdlib:pyftpdlib"
    )
    local ok_count=0 fail_count=0
    for entry in "${modules[@]}"; do
        local mod="${entry%%:*}"
        local desc="${entry##*:}"
        if python3 -c "import $mod" &>/dev/null 2>&1; then
            ok "$desc"
            ((ok_count++))
        else
            err "$desc  →  pip install ${desc}"
            ((fail_count++))
        fi
    done
    return $fail_count
}

check_gi_typelibs() {
    hdr "GObject typelibs"
    local libs=(
        "Gtk 3.0:GTK3 (RICHIESTO)"
        "Vte 2.91:VTE terminale (RICHIESTO)"
        "GdkPixbuf 2.0:GdkPixbuf (RICHIESTO)"
        "GtkVnc 2.0:gtk-vnc viewer (Raccomandato)"
        "WebKit2 4.1:WebKit2 (Opzionale)"
    )
    for entry in "${libs[@]}"; do
        local lib="${entry%%:*}"
        local desc="${entry##*:}"
        local ns="${lib%% *}"
        local ver="${lib##* }"
        if python3 -c "
import gi
gi.require_version('$ns', '$ver')
from gi.repository import $ns
" &>/dev/null 2>&1; then
            ok "$desc"
        else
            if [[ "$desc" == *"RICHIESTO"* ]]; then
                err "$desc"
            else
                warn "$desc  (non trovato — funzionalità limitata)"
            fi
        fi
    done
}

check_system_tools() {
    hdr "Strumenti di sistema"
    local tools=(
        "ssh:SSH client (RICHIESTO)"
        "sftp:SFTP client (RICHIESTO)"
        "xdg-open:xdg-utils — apri guida (Raccomandato)"
        "xfreerdp3:FreeRDP 3.x — RDP (Raccomandato)"
        "xfreerdp:FreeRDP 2.x — RDP (alternativa)"
        "vncviewer:VNC viewer esterno (Raccomandato)"
        "mosh:Mosh (Opzionale)"
        "telnet:Telnet (Opzionale)"
        "minicom:Minicom seriale (Opzionale)"
        "xdotool:xdotool RDP embedding (Opzionale)"
        "wakeonlan:Wake-on-LAN (Opzionale)"
    )
    for entry in "${tools[@]}"; do
        local cmd="${entry%%:*}"
        local desc="${entry##*:}"
        if command -v "$cmd" &>/dev/null; then
            ok "$cmd  →  $(command -v $cmd)"
        else
            if [[ "$desc" == *"RICHIESTO"* ]]; then
                err "$cmd  ($desc)"
            else
                warn "$cmd  ($desc)"
            fi
        fi
    done
}

check_python_version() {
    hdr "Versione Python"
    local ver
    ver=$(python3 --version 2>&1 | awk '{print $2}')
    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
        ok "Python $ver (>= 3.11 richiesto)"
    elif [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
        warn "Python $ver (3.10 — compatibile ma 3.11+ raccomandato)"
    else
        err "Python $ver — richiesto >= 3.10"
        exit 1
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}PCM — Python Connection Manager (GTK3)${NC}"
echo -e "${BOLD}Setup dipendenze${NC}"
echo ""

if [[ "$MODE" == "check" ]]; then
    hdr "Modalità: solo verifica"
    check_python_version
    check_python_modules
    check_gi_typelibs
    check_system_tools
    echo ""
    echo -e "${BOLD}Verifica completata.${NC}"
    exit 0
fi

if [[ "$MODE" == "pip" ]]; then
    install_pip
    exit 0
fi

# ── Installazione completa ────────────────────────────────────────────────

check_python_version

hdr "Dipendenze di sistema  ($DISTRO)"

case "$DISTRO" in
    debian)  install_debian  ;;
    arch)    install_arch    ;;
    suse)    install_suse    ;;
    fedora|rhel) install_fedora ;;
    *)
        err "Distribuzione non riconosciuta: $DISTRO"
        echo "  Installa manualmente:"
        echo "  - python3-gi, gir1.2-gtk-3.0, gir1.2-vte-2.91"
        echo "  - gir1.2-gtkvnc-2.0 (Raccomandato)"
        echo "  - openssh-client, freerdp, tigervnc-viewer"
        exit 1
        ;;
esac

install_pip

# ── Verifica finale ────────────────────────────────────────────────────────
hdr "Verifica installazione"
check_gi_typelibs
check_system_tools

# ── Permessi seriale ──────────────────────────────────────────────────────
hdr "Permessi seriale"
if groups | grep -qE "dialout|uucp|lock"; then
    ok "Utente già nel gruppo seriale"
else
    warn "Aggiungi l'utente al gruppo seriale per usare le porte COM:"
    case "$DISTRO" in
        debian|ubuntu) echo "    sudo usermod -aG dialout \$USER" ;;
        arch)          echo "    sudo usermod -aG uucp \$USER" ;;
        suse|fedora)   echo "    sudo usermod -aG dialout \$USER" ;;
    esac
    echo "    (richiede logout/login per avere effetto)"
fi

# ── Fine ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}=== Installazione completata ===${NC}"
echo ""
echo "  Avvia PCM con:"
echo "    cd $(dirname "$(realpath "$0")")"
echo "    python3 PCM.py"
echo ""
