#!/usr/bin/env bash
# ============================================================
#  build.sh — Pacchettizza PCM (GTK3) per Linux
#  PCM (Python Connection Manager) — Linux Build System
# ============================================================
#  Produce un archivio .tar.gz distribuibile contenente:
#    - tutti i sorgenti Python della variante GTK3
#    - le icone e le risorse statiche
#    - uno script launcher "pcm"
#    - un file .desktop per l'integrazione con il desktop
#
#  Uso:
#    bash build.sh              -> pacchettizza (chiede versione e opzioni)
#    bash build.sh 1.2.0        -> pacchettizza con versione specificata
#    bash build.sh 1.2.0 --zip  -> produce anche un archivio .zip
#    bash build.sh 1.2.0 --deb  -> produce anche un pacchetto .deb Debian
#    bash build.sh 1.2.0 --zip --deb -> tar.gz + zip + deb
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

# ── Percorsi ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GTK3_DIR="${PROJECT_ROOT}/gtk3"
DIST_DIR="${PROJECT_ROOT}/dist"

# ── Parsing argomenti ─────────────────────────────────────────
VERSION=""
MAKE_ZIP=false
MAKE_DEB=false

for arg in "$@"; do
    case "$arg" in
        --zip) MAKE_ZIP=true ;;
        --deb) MAKE_DEB=true ;;
        *)     [[ -z "$VERSION" ]] && VERSION="$arg" ;;
    esac
done

# ── Banner ────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo -e " ${CYAN}PCM — Linux Build (GTK3)${NC}"
echo " Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# ── Versione ──────────────────────────────────────────────────
if [[ -z "$VERSION" ]]; then
    # Prova a leggere dal README
    VERSION=$(python3 -c "
import re, pathlib
txt = pathlib.Path('${PROJECT_ROOT}/README.md').read_text()
m = re.search(r'[Vv]ersione[^\d]*(\d+\.\d+(?:\.\d+)?)', txt)
print(m.group(1) if m else '')
" 2>/dev/null || true)

    if [[ -z "$VERSION" ]]; then
        read -rp "   Versione PCM [1.0.0]: " VERSION
        VERSION="${VERSION:-1.0.0}"
    else
        echo -e "   Versione rilevata: ${CYAN}${VERSION}${NC}"
        read -rp "   Conferma o inserisci una diversa [${VERSION}]: " _v
        [[ -n "$_v" ]] && VERSION="$_v"
    fi
    echo ""
fi

PACKAGE_NAME="PCM_v${VERSION}_Linux_GTK3"

# ── Prompt opzioni (solo se non passate da CLI) ───────────────
if ! $MAKE_ZIP && [[ $# -eq 0 || ( $# -eq 1 && -n "$VERSION" ) ]]; then
    read -rp "   Vuoi produrre anche un archivio .zip? [s/N]: " _zip
    [[ "${_zip,,}" == "s" ]] && MAKE_ZIP=true
fi

if ! $MAKE_DEB && [[ $# -eq 0 || ( $# -eq 1 && -n "$VERSION" ) ]]; then
    read -rp "   Vuoi creare anche il pacchetto .deb per Debian/Ubuntu? [s/N]: " _deb
    [[ "${_deb,,}" == "s" ]] && MAKE_DEB=true
    echo ""
fi

echo -e " Versione  : ${CYAN}${VERSION}${NC}"
echo -e " tar.gz    : ${CYAN}sì${NC}"
$MAKE_ZIP && echo -e " zip       : ${CYAN}sì${NC}"
$MAKE_DEB && echo -e " .deb      : ${CYAN}sì${NC}"
echo ""

# ── Controlla che la cartella gtk3 esista ─────────────────────
if [[ ! -d "$GTK3_DIR" ]]; then
    err "Cartella gtk3/ non trovata in ${PROJECT_ROOT}"
    exit 1
fi

if [[ ! -f "${GTK3_DIR}/PCM.py" ]]; then
    err "File PCM.py non trovato in ${GTK3_DIR}"
    exit 1
fi

ok "Sorgenti trovati in ${GTK3_DIR}"

# ── Controllo Python ──────────────────────────────────────────
PYTHON_CMD=""
command -v python3 &>/dev/null && PYTHON_CMD="python3"
command -v python  &>/dev/null && [[ -z "$PYTHON_CMD" ]] && PYTHON_CMD="python"
if [[ -z "$PYTHON_CMD" ]]; then
    err "Python 3 non trovato nel PATH."
    exit 1
fi
ok "Python: $($PYTHON_CMD --version)"

# ── Pulizia build precedenti ──────────────────────────────────
info "Pulizia build precedenti..."
rm -rf "${DIST_DIR}/${PACKAGE_NAME}"
rm -f  "${DIST_DIR}/${PACKAGE_NAME}.tar.gz"
rm -f  "${DIST_DIR}/${PACKAGE_NAME}.zip"
rm -f  "${DIST_DIR}/pcm_${VERSION}_all.deb"
rm -rf "${DIST_DIR}/pcm_deb_staging"

# ── Crea struttura staging ────────────────────────────────────
STAGING="${DIST_DIR}/${PACKAGE_NAME}"
mkdir -p "${STAGING}"

info "Copia sorgenti Python..."
# Copia tutti i file .py
for f in "${GTK3_DIR}"/*.py; do
    cp "$f" "${STAGING}/"
done
ok "Sorgenti Python copiati."

info "Copia risorse statiche..."
# Icone
cp -r "${GTK3_DIR}/icons" "${STAGING}/icons"

# File HTML (help)
for f in "${GTK3_DIR}"/*.html; do
    [[ -e "$f" ]] && cp "$f" "${STAGING}/"
done

# connections.json di default (senza dati utente — solo se non esiste già)
# Si copia come template; al primo avvio PCM usa quello nella home utente
if [[ -f "${GTK3_DIR}/connections.json" ]]; then
    cp "${GTK3_DIR}/connections.json" "${STAGING}/connections.json.example"
fi

# pcm_settings.json di default (template)
if [[ -f "${GTK3_DIR}/pcm_settings.json" ]]; then
    cp "${GTK3_DIR}/pcm_settings.json" "${STAGING}/pcm_settings.json.example"
fi

# README e INSTALL
[[ -f "${GTK3_DIR}/README.md"  ]] && cp "${GTK3_DIR}/README.md"  "${STAGING}/"
[[ -f "${GTK3_DIR}/INSTALL.txt" ]] && cp "${GTK3_DIR}/INSTALL.txt" "${STAGING}/"
[[ -f "${GTK3_DIR}/requirements.txt" ]] && cp "${GTK3_DIR}/requirements.txt" "${STAGING}/"
[[ -f "${PROJECT_ROOT}/LICENSE" ]] && cp "${PROJECT_ROOT}/LICENSE" "${STAGING}/"

ok "Risorse copiate."

# ── Crea launcher "pcm" ───────────────────────────────────────
info "Creo script launcher..."
LAUNCHER="${STAGING}/pcm"
cat > "$LAUNCHER" << 'LAUNCHER_SCRIPT'
#!/usr/bin/env bash
# PCM — Python Connection Manager (GTK3)
# Launcher — avvia PCM.py dalla directory del pacchetto

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_CMD=""
command -v python3 &>/dev/null && PYTHON_CMD="python3"
command -v python  &>/dev/null && [[ -z "$PYTHON_CMD" ]] && PYTHON_CMD="python"

if [[ -z "$PYTHON_CMD" ]]; then
    echo "[ERRORE] Python 3 non trovato nel PATH." >&2
    exit 1
fi

exec "$PYTHON_CMD" "$SCRIPT_DIR/PCM.py" "$@"
LAUNCHER_SCRIPT
chmod +x "$LAUNCHER"
ok "Launcher 'pcm' creato."

# ── Crea file .desktop ────────────────────────────────────────
info "Creo file .desktop..."
DESKTOP="${STAGING}/pcm.desktop"
cat > "$DESKTOP" << DESKTOP_FILE
[Desktop Entry]
Type=Application
Name=PCM - Python Connection Manager
GenericName=Connection Manager
Comment=Connection manager for SSH, RDP, VNC, SFTP and more
Exec=bash -c 'cd "%F" && python3 PCM.py'
Icon=pcm_icon
Terminal=false
Categories=Network;RemoteAccess;GTK;
Keywords=ssh;rdp;vnc;sftp;mosh;tunnel;
StartupNotify=true
DESKTOP_FILE
ok "File .desktop creato."

# ── Crea LEGGIMI_INSTALLAZIONE.txt ────────────────────────────
info "Creo istruzioni rapide di installazione..."
cat > "${STAGING}/LEGGIMI_INSTALLAZIONE.txt" << INSTALL_TXT
PCM — Python Connection Manager v${VERSION} (GTK3)
======================================================

AVVIO RAPIDO
------------
  1. Estrai l'archivio in una cartella a tua scelta, es.:
       tar -xzf ${PACKAGE_NAME}.tar.gz -C ~/Applicazioni/

  2. Entra nella cartella:
       cd ~/Applicazioni/${PACKAGE_NAME}

  3. Installa le dipendenze di sistema (una volta sola):
       # Debian / Ubuntu
       sudo apt install python3-gi python3-gi-cairo \\
           gir1.2-gtk-3.0 gir1.2-vte-2.91 \\
           gir1.2-gtk-vnc-2.0 \\
           openssh-client freerdp3-x11 tigervnc-viewer \\
           mosh xdotool xdg-utils wakeonlan

       # Fedora
       sudo dnf install python3-gobject gtk3 vte291 \\
           gtk-vnc2 openssh-clients mosh freerdp

       # Arch
       sudo pacman -Sy python-gobject gtk3 vte3 gtk-vnc \\
           openssh mosh freerdp tigervnc xdotool

  4. Installa le dipendenze Python (una volta sola):
       pip install --user cryptography paramiko pyftpdlib

  5. Avvia PCM:
       bash pcm
       oppure: python3 PCM.py

INTEGRAZIONE DESKTOP (opzionale)
---------------------------------
  Copia il file pcm.desktop in ~/.local/share/applications/:
    cp pcm.desktop ~/.local/share/applications/
  Poi modifica la riga Exec= con il percorso assoluto di pcm.

LICENZA
-------
  European Union Public Licence (EUPL) v1.2 — vedi file LICENSE
INSTALL_TXT
ok "Istruzioni di installazione create."

# ── Crea archivio .tar.gz ─────────────────────────────────────
info "Creo archivio ${PACKAGE_NAME}.tar.gz..."
mkdir -p "$DIST_DIR"
cd "$DIST_DIR"
tar -czf "${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}/"
ok "Archivio tar.gz creato: dist/${PACKAGE_NAME}.tar.gz"

# ── Crea archivio .zip (opzionale) ────────────────────────────
if $MAKE_ZIP; then
    info "Creo archivio ${PACKAGE_NAME}.zip..."
    zip -r -q "${PACKAGE_NAME}.zip" "${PACKAGE_NAME}/"
    ok "Archivio zip creato: dist/${PACKAGE_NAME}.zip"
fi

# ── Crea pacchetto .deb Debian/Ubuntu (opzionale) ─────────────
if $MAKE_DEB; then
    info "Creo pacchetto .deb per Debian/Ubuntu..."

    if ! command -v dpkg-deb &>/dev/null; then
        warn "dpkg-deb non trovato — pacchetto .deb saltato."
        warn "Installa con: sudo apt install dpkg"
        MAKE_DEB=false
    else
        DEB_ROOT="${DIST_DIR}/pcm_deb_staging"
        DEB_INSTALL_DIR="${DEB_ROOT}/usr/lib/pcm"
        DEB_BIN_DIR="${DEB_ROOT}/usr/bin"
        DEB_DESKTOP_DIR="${DEB_ROOT}/usr/share/applications"
        DEB_ICONS_DIR="${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps"
        DEB_DOC_DIR="${DEB_ROOT}/usr/share/doc/pcm"

        mkdir -p "${DEB_INSTALL_DIR}" \
                 "${DEB_BIN_DIR}" \
                 "${DEB_DESKTOP_DIR}" \
                 "${DEB_ICONS_DIR}" \
                 "${DEB_DOC_DIR}" \
                 "${DEB_ROOT}/DEBIAN"

        # Copia sorgenti Python
        for f in "${GTK3_DIR}"/*.py; do
            cp "$f" "${DEB_INSTALL_DIR}/"
        done

        # Risorse
        cp -r "${GTK3_DIR}/icons" "${DEB_INSTALL_DIR}/icons"
        for f in "${GTK3_DIR}"/*.html; do
            [[ -e "$f" ]] && cp "$f" "${DEB_INSTALL_DIR}/"
        done
        [[ -f "${GTK3_DIR}/connections.json" ]] && \
            cp "${GTK3_DIR}/connections.json" "${DEB_INSTALL_DIR}/connections.json.example"
        [[ -f "${GTK3_DIR}/pcm_settings.json" ]] && \
            cp "${GTK3_DIR}/pcm_settings.json" "${DEB_INSTALL_DIR}/pcm_settings.json.example"

        # Documentazione
        [[ -f "${PROJECT_ROOT}/LICENSE" ]] && \
            cp "${PROJECT_ROOT}/LICENSE" "${DEB_DOC_DIR}/copyright"
        [[ -f "${GTK3_DIR}/INSTALL.txt" ]] && \
            cp "${GTK3_DIR}/INSTALL.txt" "${DEB_DOC_DIR}/"

        # Man page
        DEB_MAN_DIR="${DEB_ROOT}/usr/share/man/man1"
        mkdir -p "${DEB_MAN_DIR}"
        if command -v pandoc &>/dev/null && [[ -f "${GTK3_DIR}/pcm.1.md" ]]; then
            pandoc "${GTK3_DIR}/pcm.1.md" -s -t man | gzip -9 > "${DEB_MAN_DIR}/pcm.1.gz"
            ok "Man page generata da pcm.1.md"
        elif [[ -f "${GTK3_DIR}/pcm.1.gz" ]]; then
            cp "${GTK3_DIR}/pcm.1.gz" "${DEB_MAN_DIR}/pcm.1.gz"
            ok "Man page copiata da pcm.1.gz"
        else
            warn "Man page non disponibile (pandoc non trovato e pcm.1.gz assente)"
        fi

        # Icona principale
        if [[ -f "${GTK3_DIR}/icons/pcm_icon.png" ]]; then
            cp "${GTK3_DIR}/icons/pcm_icon.png" "${DEB_ICONS_DIR}/pcm.png"
        fi

        # Wrapper /usr/bin/pcm
        cat > "${DEB_BIN_DIR}/pcm" << 'WRAPPER'
#!/usr/bin/env bash
exec python3 /usr/lib/pcm/PCM.py "$@"
WRAPPER
        chmod 0755 "${DEB_BIN_DIR}/pcm"

        # File .desktop
        cat > "${DEB_DESKTOP_DIR}/pcm.desktop" << DFILE
[Desktop Entry]
Type=Application
Name=PCM - Python Connection Manager
GenericName=Connection Manager
Comment=Connection manager for SSH, RDP, VNC, SFTP and more
Exec=/usr/bin/pcm
Icon=pcm
Terminal=false
Categories=Network;RemoteAccess;GTK;
Keywords=ssh;rdp;vnc;sftp;mosh;tunnel;
StartupNotify=true
DFILE

        # Calcola dimensione installata (in KB)
        INSTALLED_SIZE=$(du -sk "${DEB_ROOT}/usr" | cut -f1)

        # DEBIAN/control
        cat > "${DEB_ROOT}/DEBIAN/control" << CONTROL
Package: pcm
Version: ${VERSION}
Architecture: all
Maintainer: Andres Zanzani <azanzani@gmail.com>
Installed-Size: ${INSTALLED_SIZE}
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-vte-2.91
Recommends: gir1.2-gtk-vnc-2.0, openssh-client, freerdp3-x11, tigervnc-viewer, mosh, xdotool, xdg-utils, wakeonlan, python3-cryptography, python3-paramiko, python3-pyftpdlib, python3-serial
Section: net
Priority: optional
Homepage: https://github.com/buzzqw/Python_Connection_Manager
Description: Python Connection Manager (GTK3)
 PCM è un connection manager ispirato a MobaXterm,
 sviluppato in Python con interfaccia GTK3.
 Supporta SSH, RDP, VNC, SFTP, Mosh, porte seriali,
 tunnel SSH grafici, server FTP locale e molto altro.
CONTROL

        # DEBIAN/postinst — aggiorna cache icone e .desktop
        cat > "${DEB_ROOT}/DEBIAN/postinst" << 'POSTINST'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache /usr/share/icons/hicolor || true
fi
if command -v mandb >/dev/null 2>&1; then
    mandb --quiet || true
fi
POSTINST
        chmod 0755 "${DEB_ROOT}/DEBIAN/postinst"

        # Permessi corretti per dpkg-deb
        find "${DEB_ROOT}" -type d -exec chmod 0755 {} \;
        find "${DEB_ROOT}/usr" -type f -exec chmod 0644 {} \;
        chmod 0755 "${DEB_BIN_DIR}/pcm"

        DEB_FILE="${DIST_DIR}/pcm_${VERSION}_all.deb"
        dpkg-deb --build --root-owner-group "${DEB_ROOT}" "${DEB_FILE}"
        rm -rf "${DEB_ROOT}"
        ok "Pacchetto .deb creato: dist/pcm_${VERSION}_all.deb"
    fi
fi

# ── Riepilogo dimensioni ──────────────────────────────────────
echo ""
echo "============================================================"
echo -e " ${GREEN}Build completata con successo!${NC}"
echo "============================================================"
echo ""
echo "  Artefatti in dist/:"
[[ -f "${DIST_DIR}/${PACKAGE_NAME}.tar.gz" ]] && \
    echo "    $(du -sh "${DIST_DIR}/${PACKAGE_NAME}.tar.gz" | cut -f1)  ${PACKAGE_NAME}.tar.gz"
[[ -f "${DIST_DIR}/${PACKAGE_NAME}.zip" ]] && \
    echo "    $(du -sh "${DIST_DIR}/${PACKAGE_NAME}.zip"    | cut -f1)  ${PACKAGE_NAME}.zip"
[[ -f "${DIST_DIR}/pcm_${VERSION}_all.deb" ]] && \
    echo "    $(du -sh "${DIST_DIR}/pcm_${VERSION}_all.deb" | cut -f1)  pcm_${VERSION}_all.deb"
echo "    $(du -sh "${STAGING}" | cut -f1)  ${PACKAGE_NAME}/ (staging)"
echo ""
echo "  Per installare (tar.gz):"
echo "    tar -xzf dist/${PACKAGE_NAME}.tar.gz -C ~/Applicazioni/"
echo "    bash ~/Applicazioni/${PACKAGE_NAME}/pcm"
if [[ -f "${DIST_DIR}/pcm_${VERSION}_all.deb" ]]; then
echo ""
echo "  Per installare (.deb):"
echo "    sudo dpkg -i dist/pcm_${VERSION}_all.deb"
echo "    sudo apt-get install -f   # risolve eventuali dipendenze mancanti"
fi
echo ""
echo "============================================================"
