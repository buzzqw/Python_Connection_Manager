#!/usr/bin/env bash
# ============================================================
#  install_deps.sh — Installa le dipendenze per il build
#  PCM (Python Connection Manager) — Linux Build System
# ============================================================
#  Uso:
#    bash install_deps.sh
# ============================================================

set -euo pipefail

# ── Colori ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[AVVISO]${NC} $*"; }
err()  { echo -e "${RED}[ERRORE]${NC} $*" >&2; }

echo ""
echo "============================================================"
echo -e " ${CYAN}PCM — Installazione dipendenze Linux (GTK3)${NC}"
echo " Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# ── Controlla Python ──────────────────────────────────────────
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    err "Python 3 non trovato nel PATH."
    echo "   Installa Python 3.10+ con il tuo package manager:"
    echo "     Debian/Ubuntu : sudo apt install python3 python3-pip"
    echo "     Fedora/RHEL   : sudo dnf install python3 python3-pip"
    echo "     Arch          : sudo pacman -S python python-pip"
    exit 1
fi
ok "Python: $($PYTHON_CMD --version)"

# ── Aggiorna pip ──────────────────────────────────────────────
info "[1/3] Aggiorno pip..."
$PYTHON_CMD -m pip install --upgrade pip
ok "pip aggiornato."

# ── Dipendenze Python via pip ─────────────────────────────────
info "[2/3] Installo dipendenze Python (pip)..."
$PYTHON_CMD -m pip install \
    "cryptography>=41.0" \
    "paramiko>=3.0" \
    "pyftpdlib>=1.5"
ok "Dipendenze Python installate."

# ── Dipendenze di sistema (GTK3, VTE, PyGObject) ──────────────
info "[3/3] Verifica dipendenze di sistema GTK3..."
echo ""
warn "Le librerie GTK3/VTE vanno installate con il package manager di sistema."
echo ""
echo "  Debian / Ubuntu / Linux Mint:"
echo "    sudo apt install \\"
echo "        python3-gi python3-gi-cairo \\"
echo "        gir1.2-gtk-3.0 gir1.2-vte-2.91 \\"
echo "        gir1.2-webkit2-4.1 gir1.2-gtk-vnc-2.0 \\"
echo "        gir1.2-gdkpixbuf-2.0 \\"
echo "        openssh-client freerdp3-x11 tigervnc-viewer \\"
echo "        mosh xdotool xdg-utils wakeonlan"
echo ""
echo "  Fedora / RHEL:"
echo "    sudo dnf install \\"
echo "        python3-gobject gtk3 vte291 \\"
echo "        webkit2gtk4.1 gtk-vnc2 \\"
echo "        openssh-clients mosh freerdp tigervnc \\"
echo "        xdotool xdg-utils wol"
echo ""
echo "  Arch Linux:"
echo "    sudo pacman -Sy --needed \\"
echo "        python-gobject gtk3 vte3 \\"
echo "        gtk-vnc webkit2gtk \\"
echo "        openssh mosh freerdp tigervnc \\"
echo "        xdotool xdg-utils wol \\"
echo "        python-cryptography python-paramiko python-pyftpdlib"
echo ""
echo "  openSUSE:"
echo "    sudo zypper install \\"
echo "        python3-gobject typelib-1_0-Gtk-3_0 \\"
echo "        typelib-1_0-Vte-2.91 typelib-1_0-GtkVnc-2_0 \\"
echo "        openssh freerdp tigervnc xdotool xdg-utils"
echo "    pip install --user cryptography paramiko pyftpdlib"
echo ""

# Verifica veloce PyGObject
if $PYTHON_CMD -c "import gi" &>/dev/null 2>&1; then
    ok "PyGObject (gi) già disponibile."
else
    warn "PyGObject (gi) NON trovato — installa i pacchetti di sistema indicati sopra."
fi

echo ""
echo "============================================================"
echo -e " ${GREEN}Installazione dipendenze Python completata!${NC}"
echo "============================================================"
echo ""
echo "  Prossimo passo: bash build.sh"
echo ""
