#!/usr/bin/env bash
# setup.sh — PCM (Python Connection Manager) — Setup unificato
#
# Uso:
#   bash setup.sh           # installazione / aggiornamento guidato
#   bash setup.sh --check   # verifica senza installare
#   bash setup.sh --deps    # installa/aggiorna solo le dipendenze
#
# Variante unica: GTK3 + PyGObject

set -euo pipefail

# ── Colori ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC}  $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "  ${RED}✗${NC}  $*"; }
hdr()  { echo -e "\n${BOLD}${BLUE}── $* ──────────────────────────────────────${NC}"; }
ask()  { echo -e "  ${CYAN}?${NC}  $*"; }

MODE="full"
[[ "${1:-}" == "--check" ]] && MODE="check"
[[ "${1:-}" == "--deps" ]] && MODE="deps"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLED_MARKER="${PROJECT_DIR}/.pcm_installed"

# ── Rileva distribuzione ──────────────────────────────────────────────────
detect_distro() {
    if   [[ "$(uname -s)" == "FreeBSD" ]]; then echo "freebsd"
    elif command -v zypper   &>/dev/null; then echo "opensuse"
    elif command -v apt-get  &>/dev/null; then echo "debian"
    elif command -v pacman   &>/dev/null; then echo "arch"
    elif command -v dnf      &>/dev/null; then echo "fedora"
    else echo "unknown"
    fi
}

DISTRO=$(detect_distro)
OS=$(uname -s)

# ── Banner ────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${BLUE}║   PCM — Python Connection Manager        ║${NC}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════╝${NC}"
echo -e "  Sistema rilevato: ${BOLD}${DISTRO}${NC}"

# ── Controllo se già installato → offri aggiornamento ─────────────────────
if [[ -f "$INSTALLED_MARKER" && "$MODE" == "full" ]]; then
    INSTALLED_VERSION=$(cat "$INSTALLED_MARKER" 2>/dev/null || echo "sconosciuta")
    if [[ "$INSTALLED_VERSION" != "gtk3" ]]; then
        warn "Installazione PyQt6 rilevata. La variante PyQt6 non è più distribuita."
        warn "L'installazione passerà a GTK3."
        INSTALLED_VERSION="gtk3"
    fi
    echo
    echo -e "  ${GREEN}✓${NC}  PCM risulta già installato (versione: ${BOLD}${INSTALLED_VERSION}${NC})"
    echo
    ask "Cosa vuoi fare?"
    echo "    1) Scarica aggiornamenti (git pull)"
    echo "    2) Reinstalla da zero"
    echo "    3) Esci"
    echo
    read -rp "  Scelta [1/2/3]: " UPDATE_CHOICE
    case "${UPDATE_CHOICE:-1}" in
        1)
            hdr "Aggiornamento in corso"
            if git -C "$PROJECT_DIR" pull --ff-only; then
                ok "Aggiornamento completato con successo."
            else
                warn "git pull non riuscito. Verifica manualmente lo stato del repository."
            fi
            echo
            # Le nuove versioni possono richiedere nuove dipendenze: rilancia
            # lo script aggiornato in modalita' --deps.
            read -rp "  Aggiornare anche le dipendenze? [S/n]: " DEPS_CHOICE || DEPS_CHOICE="n"
            if [[ ! "${DEPS_CHOICE:-S}" =~ ^[nN]$ ]]; then
                exec bash "$PROJECT_DIR/setup.sh" --deps
            fi
            echo -e "  ${GREEN}Aggiornamento terminato.${NC}"
            exit 0
            ;;
        2)
            echo "  Reinstallazione in corso..."
            ;;
        3|*)
            echo "  Uscita."
            exit 0
            ;;
    esac
fi

# --check: leggi il marker se presente, migra da pyqt6 se necessario
if [[ "$MODE" == "check" ]]; then
    VARIANT=$(cat "$INSTALLED_MARKER" 2>/dev/null || echo "gtk3")
    if [[ "$VARIANT" != "gtk3" ]]; then
        warn "La variante PyQt6 non è più distribuita. L'installazione passerà a GTK3."
        VARIANT="gtk3"
    fi
else
    VARIANT="gtk3"
fi

# ── Configurazione pacchetti per distro ────────────────────────────────────
USE_VENV=false
# OPT_PKGS: pacchetti facoltativi (es. GtkSource per l'evidenziazione
# sintassi nell'editor SFTP). Installati a parte: se mancano non bloccano.
OPT_PKGS=""

if [[ "$DISTRO" == "debian" ]]; then
    SYS_PKGS="python3 python3-venv python3-gi python3-gi-cairo curl libglib2.0-dev gir1.2-gtk-3.0 gir1.2-vte-2.91 gir1.2-gtk-vnc-2.0 openssh-client mosh freerdp3-x11 tigervnc-viewer xdotool xdg-utils telnet lftp picocom"
    OPT_PKGS="gir1.2-gtksource-3.0"
    PIP_PACKAGES=("cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5" "pyopenssl>=23.0" "pynacl>=1.5")
    USE_VENV=true
elif [[ "$DISTRO" == "fedora" ]]; then
    SYS_PKGS="python3 python3-devel python3-gobject curl gtk3 vte291 gtk-vnc2 openssh-clients mosh freerdp tigervnc xdotool xdg-utils telnet lftp picocom"
    OPT_PKGS="gtksourceview3"
    PIP_PACKAGES=("cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5" "pyopenssl>=23.0" "pynacl>=1.5")
    USE_VENV=true
elif [[ "$DISTRO" == "arch" ]]; then
    SYS_PKGS="python python-gobject curl gtk3 vte3 gtk-vnc openssh mosh freerdp tigervnc xdotool xdg-utils inetutils lftp picocom python-cryptography python-paramiko python-pyftpdlib python-pyopenssl python-pynacl"
    OPT_PKGS="gtksourceview3"
    PIP_PACKAGES=()
    USE_VENV=false
elif [[ "$DISTRO" == "freebsd" ]]; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')" 2>/dev/null || echo "311")
    SYS_PKGS="bash python3 curl py${PY_VER}-pygobject gtk3 vte3 gtk-vnc mosh freerdp3 tigervnc-viewer xdotool xdg-utils lftp picocom py${PY_VER}-cryptography py${PY_VER}-paramiko py${PY_VER}-pyftpdlib py${PY_VER}-openssl py${PY_VER}-pynacl"
    OPT_PKGS="gtksourceview3"
    PIP_PACKAGES=()
    USE_VENV=false
elif [[ "$DISTRO" == "opensuse" ]]; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')" 2>/dev/null || echo "313")
    SYS_PKGS="python${PY_VER} python${PY_VER}-pip python${PY_VER}-virtualenv python${PY_VER}-gobject python${PY_VER}-gobject-cairo curl typelib-1_0-Gtk-3_0 typelib-1_0-Vte-2_91 typelib-1_0-GtkVnc-2_0 gtk3 openssh mosh freerdp tigervnc xdotool xdg-utils telnet lftp picocom"
    SYS_PKGS="$SYS_PKGS python${PY_VER}-cryptography python${PY_VER}-paramiko python${PY_VER}-pyftpdlib python${PY_VER}-pyOpenSSL python${PY_VER}-PyNaCl"
    OPT_PKGS="typelib-1_0-GtkSource-3_0"
    PIP_PACKAGES=()
    USE_VENV=false
else
    SYS_PKGS=""
    PIP_PACKAGES=("cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5" "pyopenssl>=23.0" "pynacl>=1.5")
    USE_VENV=false
fi
VARIANT_DIR="${PROJECT_DIR}/gtk3"
CHECK_CMD_PY='import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk'
CHECK_LABEL="GTK3 / GObject Introspection"

# ── Funzioni ──────────────────────────────────────────────────────────────

install_system_deps() {
    hdr "Dipendenze di sistema ($DISTRO)"
    if [[ -z "$SYS_PKGS" ]]; then
        warn "Distribuzione non riconosciuta. Installa dipendenze di sistema a mano."
        return
    fi
    case "$DISTRO" in
        debian)   sudo apt-get update -qq && sudo apt-get install -y $SYS_PKGS ;;
        fedora)   sudo dnf install -y $SYS_PKGS ;;
        arch)     sudo pacman -Sy --noconfirm --needed $SYS_PKGS ;;
        opensuse) sudo zypper install -y $SYS_PKGS ;;
        freebsd)  sudo pkg update && sudo pkg install -y $SYS_PKGS ;;
    esac

    if [[ -n "$OPT_PKGS" ]]; then
        echo "  Pacchetti facoltativi: $OPT_PKGS"
        local rc=0
        case "$DISTRO" in
            debian)   sudo apt-get install -y $OPT_PKGS || rc=$? ;;
            fedora)   sudo dnf install -y $OPT_PKGS || rc=$? ;;
            arch)     sudo pacman -S --noconfirm --needed $OPT_PKGS || rc=$? ;;
            opensuse) sudo zypper install -y $OPT_PKGS || rc=$? ;;
            freebsd)  sudo pkg install -y $OPT_PKGS || rc=$? ;;
        esac
        if [[ $rc -ne 0 ]]; then
            warn "Pacchetti facoltativi non installati ($OPT_PKGS): l'editor SFTP userà testo semplice."
        fi
    fi
}

setup_python_env() {
    if [[ "$USE_VENV" == true ]]; then
        hdr "Ambiente virtuale (.venv)"
        VENV_DIR="${VARIANT_DIR}/.venv"
        if [[ ! -d "$VENV_DIR" ]]; then
            python3 -m venv --system-site-packages "$VENV_DIR"
            ok "Ambiente .venv creato in ${VENV_DIR}"
        else
            ok "Ambiente .venv esistente: ${VENV_DIR}"
        fi

        if [[ ${#PIP_PACKAGES[@]} -gt 0 ]]; then
            echo "  Installazione moduli Python nel venv..."
            "$VENV_DIR/bin/pip" install --quiet "${PIP_PACKAGES[@]}"
        fi

        PYTHON_CMD="${VENV_DIR}/bin/python3"
    else
        hdr "Ambiente Python (sistema)"
        ok "Pacchetti gestiti nativamente da $DISTRO"
        PYTHON_CMD="python3"
    fi
}

create_launcher() {
    hdr "Creazione script launcher"

    LAUNCHER_SCRIPT="${PROJECT_DIR}/pcm"
    cat > "$LAUNCHER_SCRIPT" <<LAUNCHER
#!/usr/bin/env bash
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD="${PYTHON_CMD}"
exec "\$PYTHON_CMD" "\$SCRIPT_DIR/gtk3/PCM.py" "\$@"
LAUNCHER
    chmod +x "$LAUNCHER_SCRIPT"
    ok "Script '${LAUNCHER_SCRIPT}' creato"

    # Lanciatore .desktop su Linux
    if [[ "$OS" == "Linux" ]]; then
        ICON_PATH=""
        for _try_icon in \
            "${VARIANT_DIR}/icons/pcm_icon.png" \
            "${VARIANT_DIR}/icons/computer.png"; do
            if [[ -f "$_try_icon" ]]; then
                ICON_PATH="$_try_icon"
                break
            fi
        done
        [[ -z "$ICON_PATH" ]] && ICON_PATH="network-server"

        mkdir -p "${HOME}/.local/share/applications"
        DESKTOP_FILE="${HOME}/.local/share/applications/pcm.desktop"
        cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=PCM
Comment=Python Connection Manager — SSH, RDP, VNC, SFTP, FTP, Telnet, Serial
Exec=${PYTHON_CMD} ${VARIANT_DIR}/PCM.py
Icon=${ICON_PATH}
Terminal=false
Categories=Network;RemoteAccess;System;
Keywords=ssh;rdp;vnc;sftp;ftp;telnet;terminal;connection;
EOF
        chmod +x "$DESKTOP_FILE"
        ok "Lanciatore desktop creato: $DESKTOP_FILE"
    fi
}

check_status() {
    hdr "Verifica finale ambiente (GTK3)"

    local PYTHON_CHK="${PYTHON_CMD:-python3}"
    [[ "$USE_VENV" == true && -d "${VARIANT_DIR}/.venv" ]] && PYTHON_CHK="${VARIANT_DIR}/.venv/bin/python3"

    local mod
    for mod in cryptography paramiko pyftpdlib; do
        if $PYTHON_CHK -c "import $mod" &>/dev/null; then ok "Python: $mod"
        else err "Python: $mod mancante"
        fi
    done
    if $PYTHON_CHK -c "import nacl" &>/dev/null; then ok "Python: pynacl"
    else warn "Python: pynacl mancante (integrazione KeePassXC non disponibile)"
    fi
    if $PYTHON_CHK -c "import OpenSSL" &>/dev/null; then ok "Python: pyopenssl"
    else warn "Python: pyopenssl mancante (FTPS nel server FTP locale non disponibile)"
    fi
    if $PYTHON_CHK -c 'import gi; gi.require_version("GtkSource","3.0"); from gi.repository import GtkSource' &>/dev/null; then
        ok "GtkSource 3 (evidenziazione sintassi editor SFTP)"
    else
        warn "GtkSource 3 non trovato (facoltativo: l'editor SFTP userà testo semplice)"
    fi

    if $PYTHON_CHK -c "$CHECK_CMD_PY" &>/dev/null; then
        ok "${CHECK_LABEL} accessibile"
    else
        err "${CHECK_LABEL} non accessibile da Python"
    fi

    # Strumenti di sistema
    echo
    echo "  Strumenti di sistema:"
    for tool in ssh xdotool; do
        if command -v "$tool" &>/dev/null; then ok "$tool"
        else warn "$tool: non trovato"
        fi
    done
    for tool in xfreerdp3 xfreerdp rdesktop mosh telnet lftp picocom xtigervncviewer vncviewer; do
        if command -v "$tool" &>/dev/null; then ok "$tool"
        else echo -e "    ${NC}$tool: non installato${NC}"
        fi
    done
}

# ── Main ──────────────────────────────────────────────────────────────────

if [[ "$MODE" == "check" ]]; then
    PYTHON_CMD="python3"
    [[ -d "${VARIANT_DIR}/.venv" ]] && PYTHON_CMD="${VARIANT_DIR}/.venv/bin/python3"
    check_status
    exit 0
fi

if [[ "$MODE" == "deps" ]]; then
    install_system_deps
    setup_python_env
    check_status
    hdr "Dipendenze aggiornate"
    exit 0
fi

install_system_deps
setup_python_env
create_launcher

# ── Man page ──────────────────────────────────────────────────────────────
if [[ "$OS" == "Linux" ]]; then
    hdr "Man page (man pcm)"
    MAN_DIR="/usr/local/share/man/man1"
    MAN_SRC="${PROJECT_DIR}/gtk3/pcm.1.md"
    MAN_GZ="${PROJECT_DIR}/gtk3/pcm.1.gz"
    if command -v pandoc &>/dev/null && [[ -f "$MAN_SRC" ]]; then
        pandoc "$MAN_SRC" -s -t man | gzip -9 > /tmp/pcm.1.gz
        sudo install -Dm644 /tmp/pcm.1.gz "${MAN_DIR}/pcm.1.gz"
        rm -f /tmp/pcm.1.gz
        sudo mandb --quiet 2>/dev/null || true
        ok "Man page installata → ${MAN_DIR}/pcm.1.gz (usa: man pcm)"
    elif [[ -f "$MAN_GZ" ]]; then
        sudo install -Dm644 "$MAN_GZ" "${MAN_DIR}/pcm.1.gz"
        sudo mandb --quiet 2>/dev/null || true
        ok "Man page installata → ${MAN_DIR}/pcm.1.gz (usa: man pcm)"
    else
        warn "Man page non disponibile (pandoc non trovato e pcm.1.gz assente — opzionale)"
    fi
fi

check_status

# Salva il marker di installazione
echo "gtk3" > "$INSTALLED_MARKER"

hdr "Installazione completata"
echo -e "  Versione installata: ${BOLD}GTK3${NC}"
echo -e "  Per avviare PCM esegui:  ${CYAN}${BOLD}./pcm${NC}"
if [[ "$OS" == "Linux" ]]; then
    echo "  Oppure cercalo nel menu applicazioni."
fi
echo
