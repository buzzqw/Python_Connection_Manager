#!/bin/bash
# build-appimage.sh — Costruisce l'AppImage di PCM (GTK3) in locale.
#
# Uso:
#   cd <root-del-progetto>          # es. ~/Dropbox/PCM/
#   bash packaging/appimage/build-appimage.sh [VERSIONE] [OPZIONI]
#
# Esempi:
#   bash packaging/appimage/build-appimage.sh
#   bash packaging/appimage/build-appimage.sh 2.1.0
#   bash packaging/appimage/build-appimage.sh 2.1.0 --skip-deps
#   bash packaging/appimage/build-appimage.sh 2.1.0 --skip-pyinstaller
#
# Opzioni:
#   --skip-deps          Non reinstalla le dipendenze Python nel venv
#   --skip-pyinstaller   Salta PyInstaller (usa dist/pcm/ già esistente)
#
# Requisiti di sistema:
#   - python3 (con python3-venv)
#   - python3-gi, gir1.2-gtk-3.0, gir1.2-vte-2.91  (PyGObject + typelib)
#   - libgtk-3-dev, libvte-2.91-dev                  (header per compilare gi)
#   - fuse o fuse2 per eseguire/testare l'AppImage
#   appimagetool viene scaricato automaticamente se non trovato nel PATH.
#
# Note:
#   Le dipendenze Python (cryptography, paramiko, pyftpdlib, pyinstaller)
#   vengono installate in un virtualenv isolato (.venv-build/) per evitare
#   il blocco PEP 668 degli ambienti "externally-managed".
#   PyGObject (gi) NON viene installato nel venv: si usa quello di sistema
#   perché richiede le librerie di sviluppo GTK3 per la compilazione.

set -euo pipefail

# ── Colori ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()  { echo -e "${CYAN}ℹ  ${RESET}$*"; }
ok()    { echo -e "${GREEN}✔  ${RESET}$*"; }
warn()  { echo -e "${YELLOW}⚠  ${RESET}$*" >&2; }
err()   { echo -e "${RED}✘  ${RESET}$*" >&2; exit 1; }
step()  { echo -e "\n${BOLD}══ $* ══${RESET}"; }

# ── Argomenti ──────────────────────────────────────────────────────────────────
SKIP_DEPS=false
SKIP_PYINSTALLER=false
VERSION_ARG=""

for arg in "$@"; do
    case "$arg" in
        --skip-deps)         SKIP_DEPS=true ;;
        --skip-pyinstaller)  SKIP_PYINSTALLER=true ;;
        -h|--help)
            grep '^#' "$0" | head -30 | sed 's/^# \?//'
            exit 0
            ;;
        --*)  warn "Opzione sconosciuta: $arg" ;;
        *)    [[ -z "$VERSION_ARG" ]] && VERSION_ARG="$arg" ;;
    esac
done

# ── Posizionamento nella root del progetto ─────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT}"
info "Root progetto: ${ROOT}"

# ── Rileva versione ────────────────────────────────────────────────────────────
if [[ -n "$VERSION_ARG" ]]; then
    APP_VERSION="$VERSION_ARG"
else
    # Numero di commit progressivo — unica sorgente di verità
    APP_VERSION=$(git rev-list --count HEAD 2>/dev/null || true)
    if [[ -z "$APP_VERSION" ]]; then
        err "Impossibile determinare il numero di commit (non sei in un repo git?)."
    fi
fi

ARCH="$(uname -m)"
APPIMAGE_NAME="PCM-${APP_VERSION}-${ARCH}.AppImage"
info "Versione: ${APP_VERSION}  |  Arch: ${ARCH}"
info "Output:   ${ROOT}/dist/${APPIMAGE_NAME}"

# ── 1. Verifica python3 ────────────────────────────────────────────────────────
step "Verifica ambiente Python"
command -v python3 >/dev/null 2>&1 || err "python3 non trovato nel PATH."
ok "python3: $(python3 --version)"

# Verifica che gi (PyGObject) di sistema sia disponibile — è richiesto da PCM
# e non viene installato nel venv (necessita di libgtk-3-dev per compilare).
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" \
    2>/dev/null || {
    err "PyGObject/GTK3 non disponibile sul sistema.
Installa con:
  Debian/Ubuntu:  sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91
  Fedora:         sudo dnf install python3-gobject gtk3
  Arch:           sudo pacman -S python-gobject gtk3 vte3"
}
ok "PyGObject GTK3 disponibile."

python3 -c "import gi; gi.require_version('Vte', '2.91'); from gi.repository import Vte" \
    2>/dev/null || warn "VTE 2.91 non trovato — l'AppImage non potrà usare il terminale embedded."

# ── 2. Virtualenv isolato ─────────────────────────────────────────────────────
VENV_DIR="${ROOT}/.venv-build"
if [[ "${SKIP_DEPS}" = false ]]; then
    step "Preparazione virtualenv (.venv-build/)"
    # --system-site-packages: eredita gi/PyGObject dal sistema (non installabile via pip)
    python3 -m venv --system-site-packages "${VENV_DIR}" || \
        err "python3 -m venv fallito. Installa python3-venv: sudo apt install python3-venv"
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    pip install --quiet --upgrade pip
    pip install --quiet cryptography paramiko pyftpdlib
    pip install --quiet pyinstaller pyinstaller-hooks-contrib
    ok "Dipendenze installate nel venv."
else
    info "Installazione dipendenze saltata (--skip-deps)."
    if [[ -f "${VENV_DIR}/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "${VENV_DIR}/bin/activate"
        info "Venv esistente attivato: ${VENV_DIR}"
    else
        warn "Nessun .venv-build/ trovato: si usa il Python di sistema."
    fi
fi

python3 -m PyInstaller --version >/dev/null 2>&1 || \
    err "pyinstaller non trovato. Rimuovi --skip-deps per reinstallare."

# ── 3. PyInstaller ────────────────────────────────────────────────────────────
if [[ "${SKIP_PYINSTALLER}" = false ]]; then
    step "Build PyInstaller (--onedir)"
    rm -rf build/ dist/pcm/ dist/pcm.AppDir/
    python3 -m PyInstaller packaging/appimage/pcm.spec --noconfirm
    ok "PyInstaller completato: dist/pcm/"
else
    info "PyInstaller saltato (--skip-pyinstaller)."
    [[ -d "dist/pcm" ]] || err "dist/pcm/ non trovato. Rimuovi --skip-pyinstaller."
fi

# ── 4. Assembla AppDir ────────────────────────────────────────────────────────
step "Assemblaggio AppDir"
bash packaging/appimage/make-appdir.sh
ok "AppDir pronto: dist/pcm.AppDir/"

# ── 5. Cerca / scarica appimagetool ───────────────────────────────────────────
step "Ricerca appimagetool"
APPIMAGETOOL=""
if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGETOOL="appimagetool"
    ok "appimagetool trovato nel PATH: $(command -v appimagetool)"
else
    for candidate in \
        "${ROOT}/packaging/appimage/appimagetool-${ARCH}.AppImage" \
        "${ROOT}/packaging/appimagetool-${ARCH}.AppImage" \
        "${ROOT}/appimagetool-${ARCH}.AppImage" \
        "${ROOT}/packaging/appimage/appimagetool.AppImage" \
        "${ROOT}/appimagetool.AppImage"
    do
        if [[ -x "$candidate" ]]; then
            APPIMAGETOOL="$candidate"
            ok "appimagetool trovato: $candidate"
            break
        fi
    done
fi

if [[ -z "${APPIMAGETOOL}" ]]; then
    warn "appimagetool non trovato. Scaricamento in corso..."
    APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    APPIMAGETOOL_DEST="${ROOT}/packaging/appimage/appimagetool-${ARCH}.AppImage"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "${APPIMAGETOOL_DEST}" "${APPIMAGETOOL_URL}"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "${APPIMAGETOOL_DEST}" "${APPIMAGETOOL_URL}"
    else
        err "curl e wget non disponibili. Scarica manualmente appimagetool da:\n  ${APPIMAGETOOL_URL}\ne salvalo in packaging/appimage/."
    fi
    chmod +x "${APPIMAGETOOL_DEST}"
    APPIMAGETOOL="${APPIMAGETOOL_DEST}"
    ok "appimagetool scaricato: ${APPIMAGETOOL_DEST}"
fi

# ── 6. Crea AppImage ──────────────────────────────────────────────────────────
step "Creazione AppImage"
OUTPUT_PATH="${ROOT}/dist/${APPIMAGE_NAME}"
export ARCH

if ! ( fusermount --version >/dev/null 2>&1 || fusermount3 --version >/dev/null 2>&1 ); then
    warn "FUSE non disponibile: uso --appimage-extract-and-run."
    APPIMAGE_EXTRACT_AND_RUN=1 "${APPIMAGETOOL}" \
        "${ROOT}/dist/pcm.AppDir" "${OUTPUT_PATH}" 2>&1
else
    "${APPIMAGETOOL}" \
        "${ROOT}/dist/pcm.AppDir" "${OUTPUT_PATH}" 2>&1
fi

# ── 7. Riepilogo ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  AppImage creata con successo!${RESET}"
echo -e "${BOLD}  File: ${OUTPUT_PATH}${RESET}"
echo -e "  Dimensione: $(du -sh "${OUTPUT_PATH}" | cut -f1)"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════${RESET}"
echo ""
info "Per testare l'AppImage:"
echo "    chmod +x ${OUTPUT_PATH}"
echo "    ${OUTPUT_PATH}"
echo ""
info "Nota GTK3: il sistema di destinazione deve avere libgtk-3 e libvte-2.91."
echo "    Debian/Ubuntu: sudo apt install libgtk-3-0 libvte-2.91-0"
