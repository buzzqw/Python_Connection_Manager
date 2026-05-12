#!/usr/bin/env bash
# setup.sh — Installazione dipendenze PCM (PyQt6 Multi-Strategy)
# Supporta: Debian/Ubuntu, Arch Linux, Fedora e FreeBSD 15
#
# Uso:
#   bash setup.sh           # installa tutto
#   bash setup.sh --check   # verifica senza installare

set -euo pipefail

# ── Colori ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC}  $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "  ${RED}✗${NC}  $*"; }
hdr()  { echo -e "\n${BOLD}${BLUE}── $* ──────────────────────────────────────${NC}"; }

MODE="full"
[[ "${1:-}" == "--check" ]] && MODE="check"

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

# ── Configurazione Pacchetti ──────────────────────────────────────────────
declare -A PKG

if [[ "$DISTRO" == "debian" ]]; then
    # Su Debian usiamo UV per PyQt6 e i moduli Python
    PKG[sys]="python3 python3-venv curl openssh-client mosh freerdp3-x11 tigervnc-viewer novnc websockify xdotool wakeonlan xdg-utils telnet"
    USE_UV=true
    
elif [[ "$DISTRO" == "fedora" ]]; then
    # Su Fedora usiamo UV
    PKG[sys]="python3 python3-devel curl openssh-clients mosh freerdp tigervnc novnc python3-websockify xdotool wol xdg-utils telnet"
    USE_UV=true

elif [[ "$DISTRO" == "arch" ]]; then
    # Su Arch Linux prendiamo tutto da pacman (PyQt6 e moduli)
    PKG[sys]="python curl openssh mosh freerdp tigervnc novnc python-websockify xdotool wol xdg-utils inetutils python-pyqt6 python-pyqt6-webengine python-cryptography python-paramiko python-pyftpdlib"
    USE_UV=false

elif [[ "$DISTRO" == "freebsd" ]]; then
    # Su FreeBSD facciamo fare tutto a pkg.
    # Nomi corretti per i binding PyQt6 su FreeBSD: py311-qt6-pyqt e py311-qt6-webengine
    PKG[sys]="bash python3 curl mosh freerdp3 tigervnc-viewer novnc py311-websockify xdotool wakeonlan xdg-utils py311-qt6-pyqt py311-qt6-webengine py311-cryptography py311-paramiko py311-pyftpdlib"
    USE_UV=false

else
    USE_UV=false
fi

# Pacchetti Python per gli ambienti in cui usiamo UV (Debian/Fedora)
PIP_PACKAGES=("PyQt6>=6.0.0" "PyQt6-WebEngine" "cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5")

# ── Funzioni ──────────────────────────────────────────────────────────────

install_system_deps() {
    hdr "Dipendenze di sistema ($DISTRO)"
    case "$DISTRO" in
        debian)  sudo apt-get update -qq && sudo apt-get install -y ${PKG[sys]} ;;
        fedora)  sudo dnf install -y ${PKG[sys]} ;;
        arch)    sudo pacman -Sy --noconfirm --needed ${PKG[sys]} ;;
        freebsd) sudo pkg update && sudo pkg install -y ${PKG[sys]} ;;
        unknown) warn "Distribuzione non riconosciuta. Installa dipendenze a mano." ;;
    esac
}

setup_env() {
    if [[ "$USE_UV" == true ]]; then
        # ── STRATEGIA UV (Debian / Fedora) ──
        hdr "Verifica UV"
        if ! command -v uv &>/dev/null; then
            warn "uv non trovato. Installazione in corso..."
            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.cargo/bin:$PATH"
        else
            ok "uv è installato"
        fi

        hdr "Creazione Ambiente Virtuale (.venv) con UV"
        if [[ ! -d ".venv" ]]; then
            uv venv --system-site-packages
            ok "Ambiente .venv creato"
        fi
        
        echo "  Installazione PyQt6 e moduli Python nel venv..."
        uv pip install "${PIP_PACKAGES[@]}"
        
        hdr "Creazione script launcher (Modalità VENV)"
        cat > pcm <<'LAUNCHER'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/PCM.py" "$@"
LAUNCHER

    else
        # ── STRATEGIA PURE SYSTEM (Arch / FreeBSD) ──
        hdr "Configurazione Ambiente (Pure System)"
        ok "Tutti i pacchetti (PyQt6 incluso) sono gestiti nativamente da $DISTRO"
        
        hdr "Creazione script launcher (Modalità System)"
        cat > pcm <<'LAUNCHER'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/PCM.py" "$@"
LAUNCHER
    fi

    chmod +x pcm
    ok "Script './pcm' creato"
}

check_status() {
    hdr "Verifica finale ambiente"
    
    # Sceglie quale python interrogare in base alla strategia
    local PYTHON_CMD="python3"
    [[ "$USE_UV" == true && -d ".venv" ]] && PYTHON_CMD="./.venv/bin/python3"

    if $PYTHON_CMD -c "import cryptography, paramiko, pyftpdlib" &>/dev/null; then
        ok "Moduli Python principali (cryptography, paramiko, pyftpdlib) trovati!"
    else
        err "Alcuni moduli Python principali mancano."
    fi

    if $PYTHON_CMD -c "from PyQt6.QtWidgets import QApplication" &>/dev/null; then
        ok "PyQt6 accessibile!"
    else
        err "PyQt6 non accessibile da Python."
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────

echo -e "\n${BOLD}PCM Setup (PyQt6 Edition)${NC}"

if [[ "$MODE" == "check" ]]; then
    check_status
    exit 0
fi

install_system_deps
setup_env
check_status

hdr "Completato"
echo "  Per avviare l'applicazione esegui:"
echo -e "  ${CYAN}${BOLD}./pcm${NC}"
echo ""
