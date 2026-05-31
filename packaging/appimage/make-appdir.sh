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

# ── Bundle PyInstaller ────────────────────────────────────────────────────────
cp -r "${SRC}/." "${APPDIR}/"

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

# Installa icone nelle directory hicolor se disponibili
for size in 16 32 48 64 128 256; do
    src="gtk3/icons/pcm_icon.png"
    [[ -f "$src" ]] && cp "$src" \
        "${APPDIR}/usr/share/icons/hicolor/${size}x${size}/apps/pcm.png"
done

# ── AppRun ────────────────────────────────────────────────────────────────────
# Punto d'ingresso per l'AppImage. Configura le variabili d'ambiente
# necessarie a GTK3/GObject Introspection e lancia il binario PyInstaller.
cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"

# PyInstaller 6+ mette i file interni in _internal/; build precedenti usano root.
if [[ -d "${HERE}/_internal" ]]; then
    INT="${HERE}/_internal"
else
    INT="${HERE}"
fi

# ── GObject Introspection — typelib ───────────────────────────────────────────
# I file .typelib di sistema (Gtk-3.0, Vte-2.91, …) sono stati copiati in
# gi/repository/ dal processo di build. GI li cerca in GI_TYPELIB_PATH.
# Anteponiamo il percorso bundled; quello di sistema rimane come fallback.
export GI_TYPELIB_PATH="${INT}/gi/repository:${GI_TYPELIB_PATH:-}"

# ── GDK Pixbuf loaders ────────────────────────────────────────────────────────
# Se PyInstaller ha bundlato i loaders pixbuf, puntiamo al file cache.
if [[ -f "${INT}/gdk-pixbuf-2.0/2.10.0/loaders.cache" ]]; then
    export GDK_PIXBUF_MODULE_FILE="${INT}/gdk-pixbuf-2.0/2.10.0/loaders.cache"
    export GDK_PIXBUF_MODULEDIR="${INT}/gdk-pixbuf-2.0/2.10.0/loaders"
fi

# ── GIO — nessun modulo di sistema ────────────────────────────────────────────
# Impedisce a GIO di caricare moduli di sistema (es. libgvfsdbus.so) che
# potrebbero dipendere da versioni GLib diverse da quella bundled.
export GIO_MODULE_DIR="${HERE}/gio-modules-empty"
mkdir -p "${GIO_MODULE_DIR}"

# ── GTK — backend e tema ──────────────────────────────────────────────────────
# GDK_BACKEND=x11 garantisce compatibilità massima (Wayland fallback nativo).
# Non forziamo il tema: usiamo quello del desktop dell'utente.
export GDK_BACKEND="${GDK_BACKEND:-x11}"

# ── Percorso librerie condivise ───────────────────────────────────────────────
# Le .so bundled da PyInstaller (gi, cryptography, …) stanno in INT/.
# Non aggiungiamo libgtk-3 né libvte: vengono da sistema e ci aspettiamo
# che siano presenti su qualsiasi desktop GTK3.
export LD_LIBRARY_PATH="${INT}:${LD_LIBRARY_PATH:-}"

exec "${HERE}/pcm" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

echo "=== AppDir pronto: ${APPDIR} ==="
echo "    Dimensione: $(du -sh "${APPDIR}" | cut -f1)"
