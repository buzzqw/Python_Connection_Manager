#!/usr/bin/env bash
# =============================================================================
#  PCM — Python Connection Manager
#  Script di installazione dipendenze sistema + ambiente Python via uv
#
#  Supporta: Debian/Ubuntu/Mint, Fedora/RHEL/CentOS, Arch/Manjaro
#  Utilizzo: bash setup.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[PCM]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()   { echo -e "${RED}[ERR]${NC}  $*" >&2; exit 1; }

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   PCM — Python Connection Manager  Setup         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ---------------------------------------------------------------------------
# Rileva distribuzione
# ---------------------------------------------------------------------------
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "${ID_LIKE:-$ID}"
    elif command -v pacman &>/dev/null; then
        echo "arch"
    elif command -v apt-get &>/dev/null; then
        echo "debian"
    elif command -v dnf &>/dev/null || command -v yum &>/dev/null; then
        echo "fedora"
    else
        echo "unknown"
    fi
}

DISTRO=$(detect_distro)
info "Distribuzione rilevata: $DISTRO"

# ---------------------------------------------------------------------------
# Installa dipendenze di sistema
# ---------------------------------------------------------------------------
# Nota: Python e le librerie PyQt6/paramiko vengono installate
# tramite uv nel virtualenv — NON servono pacchetti Qt/Python dal gestore
# di sistema. Qui installiamo solo gli strumenti esterni che PCM lancia
# come processi separati (xterm, ssh, ecc.).
# ---------------------------------------------------------------------------
install_sys_deps() {
    info "Installazione strumenti di sistema necessari a PCM..."

    case "$DISTRO" in
        *debian*|*ubuntu*|*mint*)
            sudo apt-get update -qq
            sudo apt-get install -y \
                python3 curl git \
                xterm xdotool x11-utils \
                openssh-client sshpass \
                xfreerdp2-x11 \
                lftp \
                libxcb-cursor0 libxkbcommon-x11-0 \
                libqt6svg6 \
                2>/dev/null || true
            ;;

        *fedora*|*rhel*|*centos*|*rocky*|*alma*)
            local PKG="dnf"
            command -v dnf &>/dev/null || PKG="yum"
            sudo $PKG install -y \
                python3 curl git \
                xterm xdotool xorg-x11-utils \
                openssh-clients sshpass \
                freerdp \
                lftp \
                qt6-qtsvg \
                2>/dev/null || true
            ;;

        *arch*|*manjaro*|*endeavour*)
            sudo pacman -Sy --noconfirm \
                python curl git \
                xterm xdotool xorg-xwininfo \
                openssh sshpass \
                freerdp \
                lftp \
                qt6-svg \
                2>/dev/null || true
            ;;

        *)
            warn "Distribuzione non riconosciuta. Installa manualmente:"
            warn "  python3, curl, git, xterm, xdotool, openssh-client, sshpass, xfreerdp"
            ;;
    esac

    # Strumenti opzionali (non installati automaticamente):
    #   remmina   — client RDP/VNC alternativo a xfreerdp
    #   mosh      — shell mobile (alternativa SSH su connessioni instabili)
    #   picocom   — client seriale (alternativa a minicom/screen)
    #   novnc     — per il VNC integrato nel browser di PCM
    info "Opzionali non installati: remmina, mosh, picocom, novnc."
    info "  Installali manualmente se vuoi usare queste funzionalità."
    info "  - lftp: client FTP/SFTP per terminale embedded (installato sopra se disponibile)"
    info "  - sshpass: login SSH con password senza prompt (consigliato)"

    ok "Strumenti di sistema installati"
}

# ---------------------------------------------------------------------------
# Installa uv (gestore ambienti Python ultra-rapido)
# ---------------------------------------------------------------------------
install_uv() {
    if command -v uv &>/dev/null; then
        ok "uv già installato: $(uv --version)"
        return
    fi
    info "Installazione uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Aggiungi al PATH della sessione corrente
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
    if command -v uv &>/dev/null; then
        ok "uv installato: $(uv --version)"
    else
        die "uv non trovato nel PATH dopo l'installazione. Riavvia il terminale e riprova."
    fi
}

# ---------------------------------------------------------------------------
# Crea ambiente virtuale Python e installa dipendenze Python
# ---------------------------------------------------------------------------
setup_venv() {
    info "Creazione ambiente virtuale Python con uv..."

    PCM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    VENV_DIR="$PCM_DIR/.venv"

    # Crea venv con Python 3.11+ (preferito per PyQt6)
    uv venv "$VENV_DIR" --python python3 2>/dev/null || \
    uv venv "$VENV_DIR" 2>/dev/null || \
    die "Impossibile creare il virtualenv. Verifica che Python 3 sia installato."

    ok "Virtualenv creato in $VENV_DIR"

    info "Installazione dipendenze Python (PyQt6, paramiko)..."
    uv pip install --python "$VENV_DIR/bin/python" \
        PyQt6 \
        PyQt6-WebEngine \
        paramiko \
        pyftpdlib \
        2>/dev/null || {
            warn "PyQt6-WebEngine non disponibile (VNC integrato non funzionerà)"
            uv pip install --python "$VENV_DIR/bin/python" \
                PyQt6 \
                paramiko \
                pyftpdlib
        }

    ok "Dipendenze Python installate"
}

# ---------------------------------------------------------------------------
# Crea lo script di avvio
# ---------------------------------------------------------------------------
create_launcher() {
    PCM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    LAUNCHER="$PCM_DIR/run_pcm.sh"

    cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
# Avvia PCM con il virtualenv corretto
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="\$SCRIPT_DIR"
exec "\$SCRIPT_DIR/.venv/bin/python" "\$SCRIPT_DIR/PCM.py" "\$@"
EOF
    chmod +x "$LAUNCHER"
    ok "Script di avvio creato: $LAUNCHER"

    # Crea .desktop opzionale
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_DIR/pcm.desktop" << EOF
[Desktop Entry]
Name=PCM — Python Connection Manager
Comment=Gestore sessioni remote multi-protocollo
Exec=$LAUNCHER
Icon=$PCM_DIR/pcm_icon.png
Terminal=false
Type=Application
Categories=Network;RemoteAccess;
Keywords=ssh;sftp;rdp;vnc;tunnel;
StartupWMClass=PCM
EOF
    ok "Voce menu applicazioni creata"
}

# ---------------------------------------------------------------------------
# Verifica finale
# ---------------------------------------------------------------------------
verify() {
    info "Verifica installazione..."
    PCM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PYTHON="$PCM_DIR/.venv/bin/python"

    "$PYTHON" -c "import PyQt6.QtWidgets; print('PyQt6 OK')" 2>/dev/null && ok "PyQt6 OK" || warn "PyQt6 non trovato"
    "$PYTHON" -c "import paramiko; print('paramiko OK')"     2>/dev/null && ok "paramiko OK" || warn "paramiko non trovato"
    "$PYTHON" -c "import pyftpdlib; print('pyftpdlib OK')"   2>/dev/null && ok "pyftpdlib OK"  || warn "pyftpdlib non trovato (server FTP locale non funzionerà)"

    # Verifica supporto SVG (icone)
    if "$PYTHON" -c "
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
import sys, tempfile, os
app = QApplication.instance() or QApplication(sys.argv)
svg = '<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 10 10\"><circle cx=\"5\" cy=\"5\" r=\"4\" fill=\"red\"/></svg>'
f = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
f.write(svg.encode()); f.close()
ok = not QIcon(f.name).pixmap(QSize(10,10)).isNull()
os.unlink(f.name)
sys.exit(0 if ok else 1)
" 2>/dev/null; then
        ok "SVG Qt6 OK (icone attive)"
    else
        warn "libqt6svg6 non trovato — icone SVG non disponibili"
        warn "  Installa con: sudo apt install libqt6svg6   (Debian/Ubuntu)"
        warn "                sudo pacman -S qt6-svg         (Arch)"
        warn "                sudo dnf install qt6-qtsvg     (Fedora)"
    fi

    command -v xterm    &>/dev/null && ok "xterm trovato"    || warn "xterm non trovato — installa manualmente"
    command -v ssh      &>/dev/null && ok "ssh trovato"      || warn "ssh non trovato"
    command -v sshpass  &>/dev/null && ok "sshpass trovato"  || warn "sshpass non trovato (login con password SSH limitato)"
    command -v xdotool  &>/dev/null && ok "xdotool trovato"  || warn "xdotool non trovato (multi-exec non funzionerà)"
    command -v lftp     &>/dev/null && ok "lftp trovato"     || warn "lftp non trovato (terminale FTP/SFTP embedded limitato)"
}

# ---------------------------------------------------------------------------
# Verifica icone PNG
# ---------------------------------------------------------------------------
setup_icons() {
    PCM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    ICONS_DIR="$PCM_DIR/icons"

    [ -d "$ICONS_DIR" ] || { warn "Cartella icons/ non trovata."; return; }

    local png_count
    png_count=$(find "$ICONS_DIR" -name "*.png" | wc -l)

    if [ "$png_count" -gt 0 ]; then
        ok "Icone PNG presenti: $png_count file in icons/"
    else
        warn "Nessun PNG trovato in icons/ — le icone non saranno visibili."
        warn "  Esegui: bash convert_icons.sh"
    fi

    [ -f "$ICONS_DIR/checkmark.png" ] && ok "checkmark.png presente" \
        || warn "checkmark.png mancante in icons/ — i checkbox non avranno la spunta"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    install_sys_deps
    install_uv
    setup_venv
    setup_icons
    create_launcher
    verify

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Installazione completata!                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Avvia PCM con:  ${YELLOW}./run_pcm.sh${NC}"
    echo -e "  Oppure dal menu applicazioni: ${YELLOW}PCM${NC}"
    echo ""
}

main "$@"
