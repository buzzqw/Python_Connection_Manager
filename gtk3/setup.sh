#!/usr/bin/env bash
# setup.sh — Installazione dipendenze PCM con UV e .venv
#
# Uso:
#   bash setup.sh           # installa tutto (sistema + uv + venv)
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
    if   command -v apt-get  &>/dev/null; then echo "debian"
    elif command -v pacman   &>/dev/null; then echo "arch"
    elif command -v zypper   &>/dev/null; then echo "suse"
    elif command -v dnf      &>/dev/null; then echo "fedora"
    else echo "unknown"
    fi
}

DISTRO=$(detect_distro)

# ── Configurazione Pacchetti ──────────────────────────────────────────────
declare -A PKG
if [[ "$DISTRO" == "debian" ]]; then
    PKG[sys]="python3 python3-venv curl libglib2.0-dev gir1.2-gtk-3.0 gir1.2-vte-2.91 gir1.2-webkit2-4.1 gir1.2-gtk-vnc-2.0 openssh-client mosh freerdp3-x11 tigervnc-viewer xdotool wakeonlan xdg-utils"
elif [[ "$DISTRO" == "arch" ]]; then
    PKG[sys]="python curl gtk3 vte3 webkit2gtk gtk-vnc openssh mosh freerdp tigervnc xdotool wol xdg-utils"
elif [[ "$DISTRO" == "fedora" ]]; then
    PKG[sys]="python3 python3-devel curl gtk3 vte291 webkit2gtk4.1 gtk-vnc2 openssh-clients mosh freerdp tigervnc xdotool wol xdg-utils"
fi

PIP_PACKAGES=("cryptography>=41.0" "paramiko>=3.0" "pyftpdlib>=1.5")

# ── Funzioni ──────────────────────────────────────────────────────────────

install_system_deps() {
    hdr "Dipendenze di sistema ($DISTRO)"
    case "$DISTRO" in
        debian) sudo apt-get update -qq && sudo apt-get install -y ${PKG[sys]} ;;
        arch)   sudo pacman -Sy --noconfirm --needed ${PKG[sys]} ;;
        fedora) sudo dnf install -y ${PKG[sys]} ;;
    esac
}

install_uv() {
    hdr "Verifica UV"
    if command -v uv &>/dev/null; then
        ok "uv è già installato: $(uv --version)"
    else
        warn "uv non trovato. Installazione in corso..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Aggiunge temporaneamente uv al path per la sessione corrente
        export PATH="$HOME/.cargo/bin:$PATH"
    fi
}

setup_venv() {
    hdr "Creazione Ambiente Virtuale (.venv) con UV"
    if [[ ! -d ".venv" ]]; then
        uv venv --system-site-packages
        ok "Ambiente .venv creato (con accesso ai pacchetti di sistema)"
    else
        ok ".venv già esistente"
    fi

    echo "  Installazione pacchetti Python nel venv..."
    uv pip install "${PIP_PACKAGES[@]}"

    # Installa anche nel Python di sistema per "python3 PCM.py"
    hdr "Installazione pacchetti nel Python di sistema"
    if command -v pip3 &>/dev/null; then
        pip3 install --break-system-packages --quiet "${PIP_PACKAGES[@]}" \
            && ok "Pacchetti installati nel Python di sistema" \
            || warn "Installazione sistema fallita (non critico se usi il venv)"
    else
        warn "pip3 non trovato, salto installazione di sistema"
    fi

    # Crea script launcher che usa il venv
    hdr "Creazione script launcher"
    cat > pcm <<'LAUNCHER'
#!/usr/bin/env bash
# Launcher PCM: attiva il venv e lancia PCM.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/PCM.py" "$@"
LAUNCHER
    chmod +x pcm
    ok "Script './pcm' creato"
}

check_status() {
    hdr "Verifica finale"
    if .venv/bin/python3 -c "import cryptography, paramiko, pyftpdlib" &>/dev/null; then
        ok "Moduli Python installati correttamente nel venv"
    else
        err "Alcuni moduli Python mancano nel venv"
    fi

    if .venv/bin/python3 -c "import gi; gi.require_version('Gtk', '3.0')" &>/dev/null; then
        ok "GObject Introspection (GTK3) accessibile dal venv"
    else
        warn "GTK3 non accessibile dal venv direttamente."
        echo "  Tentativo di ri-creare il venv con accesso ai pacchetti di sistema..."
        uv venv --system-site-packages --allow-existing
        uv pip install "${PIP_PACKAGES[@]}"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────

echo -e "\n${BOLD}PCM Setup (UV Edition)${NC}"

if [[ "$MODE" == "check" ]]; then
    [[ -d ".venv" ]] && check_status || err ".venv non trovato"
    exit 0
fi

install_system_deps
install_uv
setup_venv
check_status

hdr "Completato"
echo "  Per avviare PCM usando l'ambiente virtuale:"
echo -e "  ${CYAN}${BOLD}./pcm${NC}             (usa il venv automaticamente)"
  echo -e "  ${CYAN}./.venv/bin/python3 PCM.py${NC}   (alternativa esplicita)"
echo ""
