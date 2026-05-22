#!/usr/bin/env bash
# setup.sh — PCM (Python Connection Manager) — Setup unificato
#
# Uso:
#   bash setup.sh           # installazione / aggiornamento guidato
#   bash setup.sh --check   # verifica senza installare
#
# Versioni supportate:
#   gtk3   → versione attiva (GTK3 + PyGObject)
#   pyqt6  → versione in sola manutenzione (PyQt6)

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

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLED_MARKER="${PROJECT_DIR}/.pcm_installed"

# ── Rileva distribuzione ──────────────────────────────────────────────────
detect_distro() {
    if   [[ "$(uname -s)" == "FreeBSD" ]]; then echo "freebsd"
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
if [[ -f "$INSTALLED_MARKER" ]]; then
    INSTALLED_VERSION=$(cat "$INSTALLED_MARKER" 2>/dev/null || echo "sconosciuta")
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

# ── Scelta versione ───────────────────────────────────────────────────────
if [[ "$MODE" != "check" ]]; then
    echo
    echo -e "  ${BOLD}Quale versione di PCM vuoi installare?${NC}"
    echo
    echo -e "    ${GREEN}1) GTK3${NC}  — versione attiva, supportata e raccomandata"
    echo -e "       (PyGObject + GTK3, terminale VTE embedded, gtk-vnc nativo)"
    echo
    echo -e "    ${YELLOW}2) PyQt6${NC} — versione in sola manutenzione"
    echo -e "       (PyQt6 + QtWebEngine; non riceve nuove funzionalità)"
    echo
    read -rp "  Scelta [1/2, default=1]: " VERSION_CHOICE
    VERSION_CHOICE="${VERSION_CHOICE:-1}"

    case "$VERSION_CHOICE" in
        1) VARIANT="gtk3"  ;;
        2) VARIANT="pyqt6" ;;
        *)
            warn "Scelta non valida, uso GTK3 per default."
            VARIANT="gtk3"
            ;;
    esac
else
    # In modalità --check legge il marker se presente, altrimenti usa gtk3
    VARIANT=$(cat "$INSTALLED_MARKER" 2>/dev/null || echo "gtk3")
fi

echo
echo -e "  Versione selezionata: ${BOLD}${VARIANT}${NC}"

# ── Configurazione pacchetti per variante e distro ────────────────────────
USE_UV=false

if [[ "$VARIANT" == "gtk3" ]]; then
    # ── GTK3 ──
    if [[ "$DISTRO" == "debian" ]]; then
        SYS_PKGS="python3 python3-venv curl libglib2.0-dev gir1.2-gtk-3.0 gir1.2-vte-2.91 gir1.2-gtk-vnc-2.0 openssh-client mosh freerdp3-x11 tigervnc-viewer xdotool wakeonlan xdg-utils"
        PIP_PACKAGES=("cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5")
        USE_UV=true
    elif [[ "$DISTRO" == "fedora" ]]; then
        SYS_PKGS="python3 python3-devel curl gtk3 vte291 gtk-vnc2 openssh-clients mosh freerdp tigervnc xdotool wol xdg-utils"
        PIP_PACKAGES=("cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5")
        USE_UV=true
    elif [[ "$DISTRO" == "arch" ]]; then
        SYS_PKGS="python curl gtk3 vte3 gtk-vnc openssh mosh freerdp tigervnc xdotool wol xdg-utils python-cryptography python-paramiko python-pyftpdlib"
        PIP_PACKAGES=()
        USE_UV=false
    elif [[ "$DISTRO" == "freebsd" ]]; then
        PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')" 2>/dev/null || echo "311")
        SYS_PKGS="bash python3 curl py${PY_VER}-pygobject gtk3 vte3 gtk-vnc mosh freerdp3 tigervnc-viewer xdotool wakeonlan xdg-utils py${PY_VER}-cryptography py${PY_VER}-paramiko py${PY_VER}-pyftpdlib"
        PIP_PACKAGES=()
        USE_UV=false
    else
        SYS_PKGS=""
        PIP_PACKAGES=("cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5")
        USE_UV=false
    fi
    VARIANT_DIR="${PROJECT_DIR}/gtk3"
    CHECK_CMD_PY='import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk'
    CHECK_LABEL="GTK3 / GObject Introspection"

else
    # ── PyQt6 ──
    warn "Stai installando la versione PyQt6, che è in sola manutenzione."
    warn "Per nuove funzionalità usa la versione GTK3."
    echo
    if [[ "$DISTRO" == "debian" ]]; then
        SYS_PKGS="python3 python3-venv curl openssh-client mosh freerdp3-x11 tigervnc-viewer novnc websockify xdotool wakeonlan xdg-utils telnet"
        PIP_PACKAGES=("PyQt6>=6.0.0" "PyQt6-WebEngine" "cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5")
        USE_UV=true
    elif [[ "$DISTRO" == "fedora" ]]; then
        SYS_PKGS="python3 python3-devel curl openssh-clients mosh freerdp tigervnc novnc python3-websockify xdotool wol xdg-utils telnet"
        PIP_PACKAGES=("PyQt6>=6.0.0" "PyQt6-WebEngine" "cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5")
        USE_UV=true
    elif [[ "$DISTRO" == "arch" ]]; then
        SYS_PKGS="python curl openssh mosh freerdp tigervnc novnc python-websockify xdotool wol xdg-utils inetutils python-pyqt6 python-pyqt6-webengine python-cryptography python-paramiko python-pyftpdlib"
        PIP_PACKAGES=()
        USE_UV=false
    elif [[ "$DISTRO" == "freebsd" ]]; then
        PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')" 2>/dev/null || echo "311")
        SYS_PKGS="bash python3 curl mosh freerdp3 tigervnc-viewer novnc py${PY_VER}-websockify xdotool wakeonlan xdg-utils py${PY_VER}-qt6-pyqt py${PY_VER}-qt6-webengine py${PY_VER}-cryptography py${PY_VER}-paramiko py${PY_VER}-pyftpdlib"
        PIP_PACKAGES=()
        USE_UV=false
    else
        SYS_PKGS=""
        PIP_PACKAGES=("PyQt6>=6.0.0" "PyQt6-WebEngine" "cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5")
        USE_UV=false
    fi
    VARIANT_DIR="${PROJECT_DIR}/pyqt6"
    CHECK_CMD_PY='from PyQt6.QtWidgets import QApplication'
    CHECK_LABEL="PyQt6"
fi

# ── Funzioni ──────────────────────────────────────────────────────────────

install_system_deps() {
    hdr "Dipendenze di sistema ($DISTRO)"
    if [[ -z "$SYS_PKGS" ]]; then
        warn "Distribuzione non riconosciuta. Installa dipendenze di sistema a mano."
        return
    fi
    case "$DISTRO" in
        debian)  sudo apt-get update -qq && sudo apt-get install -y $SYS_PKGS ;;
        fedora)  sudo dnf install -y $SYS_PKGS ;;
        arch)    sudo pacman -Sy --noconfirm --needed $SYS_PKGS ;;
        freebsd) sudo pkg update && sudo pkg install -y $SYS_PKGS ;;
    esac
}

setup_python_env() {
    if [[ "$USE_UV" == true ]]; then
        hdr "Verifica UV"
        if ! command -v uv &>/dev/null; then
            warn "uv non trovato. Installazione in corso..."
            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.cargo/bin:$PATH"
        else
            ok "uv è installato"
        fi

        hdr "Ambiente virtuale (.venv)"
        VENV_DIR="${VARIANT_DIR}/.venv"
        if [[ ! -d "$VENV_DIR" ]]; then
            uv venv --system-site-packages "$VENV_DIR"
            ok "Ambiente .venv creato in ${VENV_DIR}"
        else
            ok "Ambiente .venv esistente: ${VENV_DIR}"
        fi

        if [[ ${#PIP_PACKAGES[@]} -gt 0 ]]; then
            echo "  Installazione moduli Python nel venv..."
            uv pip install --python "$VENV_DIR/bin/python3" "${PIP_PACKAGES[@]}"
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
exec "\$PYTHON_CMD" "\$SCRIPT_DIR/${VARIANT}/PCM.py" "\$@"
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
    hdr "Verifica finale ambiente (${VARIANT})"

    local PYTHON_CHK="${PYTHON_CMD:-python3}"
    [[ "$USE_UV" == true && -d "${VARIANT_DIR}/.venv" ]] && PYTHON_CHK="${VARIANT_DIR}/.venv/bin/python3"

    if $PYTHON_CHK -c "import cryptography, paramiko, pyftpdlib" &>/dev/null; then
        ok "Moduli Python principali (cryptography, paramiko, pyftpdlib) trovati"
    else
        err "Alcuni moduli Python principali mancano"
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
    for tool in xfreerdp3 xfreerdp rdesktop mosh; do
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

install_system_deps
setup_python_env
create_launcher
check_status

# Salva il marker di installazione
echo "$VARIANT" > "$INSTALLED_MARKER"

hdr "Installazione completata"
echo -e "  Versione installata: ${BOLD}${VARIANT}${NC}"
echo -e "  Per avviare PCM esegui:  ${CYAN}${BOLD}./pcm${NC}"
if [[ "$OS" == "Linux" ]]; then
    echo "  Oppure cercalo nel menu applicazioni."
fi
echo
