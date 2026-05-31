#!/bin/bash
# make-appdir.sh — Assembla l'AppDir GTK3 da usare con appimagetool.
# Deve essere eseguito dalla root del progetto dopo "pyinstaller pcm.spec".
#
# Input:  dist/pcm/   (output --onedir di PyInstaller)
# Output: dist/pcm.AppDir/

set -euo pipefail

SRC="dist/pcm"
APPDIR="dist/pcm.AppDir"

if [[ ! -d "$SRC" ]]; then
    echo "ERRORE: $SRC non trovato. Esegui prima PyInstaller." >&2
    exit 1
fi

echo "=== Creazione AppDir in ${APPDIR} ==="

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/"{16x16,32x32,48x48,64x64,128x128,256x256}"/apps"
mkdir -p "${APPDIR}/lib"

# ── Bundle PyInstaller ────────────────────────────────────────────────────────
cp -r "${SRC}/." "${APPDIR}/"

# ── Bundle libvte-2.91 ────────────────────────────────────────────────────────
# Bundlata per coprire sistemi senza terminale GTK (KDE + Alacritty/Kitty/ecc.)
# libgtk-3 NON viene bundlata: presente su qualsiasi desktop GTK/GNOME/XFCE.
echo "  Ricerca libvte-2.91..."
LIBVTE_REAL=$(readlink -f /usr/lib/libvte-2.91.so.0 2>/dev/null || \
              readlink -f /usr/lib64/libvte-2.91.so.0 2>/dev/null || \
              ldconfig -p 2>/dev/null | awk '/libvte-2\.91\.so\.0 /{print $NF}' | head -1 || true)

if [[ -n "$LIBVTE_REAL" && -f "$LIBVTE_REAL" ]]; then
    cp "$LIBVTE_REAL" "${APPDIR}/lib/libvte-2.91.so.0"
    echo "  libvte bundlata: $LIBVTE_REAL ($(du -sh "$LIBVTE_REAL" | cut -f1))"
else
    echo "ATTENZIONE: libvte-2.91 non trovata sul sistema di build — non bundlata." >&2
fi

# ── Desktop entry ─────────────────────────────────────────────────────────────
cat > "${APPDIR}/pcm.desktop" << 'DFILE'
[Desktop Entry]
Type=Application
Name=PCM - Python Connection Manager
GenericName=Connection Manager
Comment=Connection manager for SSH, RDP, VNC, SFTP and more
Exec=pcm
Icon=pcm
Terminal=false
Categories=Network;RemoteAccess;GTK;
Keywords=ssh;rdp;vnc;sftp;mosh;tunnel;
StartupNotify=true
DFILE

# ── Icona root (richiesta da appimagetool) ────────────────────────────────────
cp gtk3/icons/pcm_icon.png "${APPDIR}/pcm.png"

for size in 16 32 48 64 128 256; do
    src="gtk3/icons/pcm_icon.png"
    [[ -f "$src" ]] && cp "$src" \
        "${APPDIR}/usr/share/icons/hicolor/${size}x${size}/apps/pcm.png"
done

# ── AppRun ────────────────────────────────────────────────────────────────────
cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"

# PyInstaller 6+ mette i file interni in _internal/; build precedenti usano root.
if [[ -d "${HERE}/_internal" ]]; then
    INT="${HERE}/_internal"
else
    INT="${HERE}"
fi

# ── Verifica librerie di sistema richieste ────────────────────────────────────
# libvte-2.91 è bundlata nell'AppImage (HERE/lib/).
# libgtk-3 deve essere presente sul sistema.
_missing=()

_has_lib() {
    # Cerca la libreria in ldconfig, poi nei path standard
    ldconfig -p 2>/dev/null | grep -q "$1" && return 0
    for d in /usr/lib /usr/lib64 /usr/lib/x86_64-linux-gnu \
              /usr/lib/aarch64-linux-gnu /usr/local/lib; do
        ls "${d}/${1}"* 2>/dev/null | head -1 | grep -q . && return 0
    done
    return 1
}

if ! _has_lib "libgtk-3.so"; then
    _missing+=("libgtk-3")
fi

if [[ ${#_missing[@]} -gt 0 ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  PCM — librerie di sistema mancanti                         ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    for lib in "${_missing[@]}"; do
        echo "║  ✗  $lib"
    done
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  Installa con il gestore pacchetti della tua distribuzione:  ║"
    echo "║                                                              ║"
    echo "║  Debian/Ubuntu:                                              ║"
    echo "║    sudo apt install libgtk-3-0                               ║"
    echo "║                                                              ║"
    echo "║  Fedora:                                                     ║"
    echo "║    sudo dnf install gtk3                                     ║"
    echo "║                                                              ║"
    echo "║  Arch Linux:                                                 ║"
    echo "║    sudo pacman -S gtk3                                       ║"
    echo "║                                                              ║"
    echo "║  openSUSE:                                                   ║"
    echo "║    sudo zypper install libgtk-3-0                            ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
fi

# ── GObject Introspection — typelib ───────────────────────────────────────────
export GI_TYPELIB_PATH="${INT}/gi/repository:${GI_TYPELIB_PATH:-}"

# ── GDK Pixbuf loaders ────────────────────────────────────────────────────────
if [[ -f "${INT}/gdk-pixbuf-2.0/2.10.0/loaders.cache" ]]; then
    export GDK_PIXBUF_MODULE_FILE="${INT}/gdk-pixbuf-2.0/2.10.0/loaders.cache"
    export GDK_PIXBUF_MODULEDIR="${INT}/gdk-pixbuf-2.0/2.10.0/loaders"
fi

# ── GIO — nessun modulo di sistema ────────────────────────────────────────────
export GIO_MODULE_DIR="${HERE}/gio-modules-empty"
mkdir -p "${GIO_MODULE_DIR}"

# ── GTK — backend ─────────────────────────────────────────────────────────────
export GDK_BACKEND="${GDK_BACKEND:-x11}"

# ── Percorso librerie condivise ───────────────────────────────────────────────
# HERE/lib/ contiene libvte-2.91 bundlata.
# INT/ contiene le .so Python (gi, cryptography, …) da PyInstaller.
export LD_LIBRARY_PATH="${HERE}/lib:${INT}:${LD_LIBRARY_PATH:-}"

exec "${HERE}/pcm" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

echo "=== AppDir pronto: ${APPDIR} ==="
echo "    Dimensione: $(du -sh "${APPDIR}" | cut -f1)"
