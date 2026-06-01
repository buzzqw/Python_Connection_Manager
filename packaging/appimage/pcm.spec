# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec per PCM (GTK3) — Python Connection Manager.

Genera un bundle --onedir che include:
  - Sorgenti PCM (gtk3/)
  - Dipendenze pip: cryptography, paramiko, pyftpdlib
  - Binding gi/PyGObject (typelib GObject Introspection raccolti dal sistema)

Requisiti sul sistema di build:
  - python3-gi (PyGObject)
  - libgtk-3-dev, libvte-2.91-dev (header + typelib)
  - pip: pyinstaller, pyinstaller-hooks-contrib, cryptography, paramiko, pyftpdlib

Uso:
  python3 -m PyInstaller packaging/appimage/pcm.spec --noconfirm
"""

import os
import glob
from PyInstaller.utils.hooks import collect_all

ROOT     = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
GTK3_SRC = os.path.join(ROOT, 'gtk3')

# ── Dipendenze pip puro-Python ────────────────────────────────────────────────
datas       = []
binaries    = []
hiddenimports = []

for pkg in ('cryptography', 'paramiko', 'pyftpdlib', 'bcrypt', 'nacl', 'cffi'):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

# ── gi / PyGObject ────────────────────────────────────────────────────────────
gi_d, gi_b, gi_h = collect_all('gi')
datas += gi_d; binaries += gi_b; hiddenimports += gi_h

# ── Typelib GObject Introspection — raccolta manuale dal sistema ───────────────
# pyinstaller-hooks-contrib raccoglie gi, ma i .typelib sono file di sistema
# non nel package Python: li aggiungiamo esplicitamente nella dest gi/repository.
TYPELIB_DIRS = [
    '/usr/lib/girepository-1.0',
    '/usr/lib/x86_64-linux-gnu/girepository-1.0',
    '/usr/lib/aarch64-linux-gnu/girepository-1.0',
    '/usr/lib/arm-linux-gnueabihf/girepository-1.0',
    '/usr/local/lib/girepository-1.0',
]
TYPELIBS_NEEDED = [
    'Gtk-3.0', 'Gdk-3.0', 'GdkX11-3.0', 'GdkPixbuf-2.0',
    'GLib-2.0', 'GObject-2.0', 'Gio-2.0', 'GModule-2.0',
    'Vte-2.91',
    'Pango-1.0', 'PangoCairo-1.0',
    'cairo-1.0',
    'Atk-1.0',
    'HarfBuzz-0.0',
    'xlib-2.0',
]

for tl_name in TYPELIBS_NEEDED:
    fname = f'{tl_name}.typelib'
    for tl_dir in TYPELIB_DIRS:
        fpath = os.path.join(tl_dir, fname)
        if os.path.exists(fpath):
            datas.append((fpath, 'gi/repository'))
            break

# ── Risorse PCM ───────────────────────────────────────────────────────────────
datas.append((os.path.join(GTK3_SRC, 'icons'), 'icons'))
for pattern in ('*.html',):
    for f in glob.glob(os.path.join(GTK3_SRC, pattern)):
        datas.append((f, '.'))

# ── Hidden imports gi ─────────────────────────────────────────────────────────
hiddenimports += [
    'gi.repository.Gtk',
    'gi.repository.Gdk',
    'gi.repository.GdkX11',
    'gi.repository.GdkPixbuf',
    'gi.repository.GLib',
    'gi.repository.GObject',
    'gi.repository.Gio',
    'gi.repository.GModule',
    'gi.repository.Vte',
    'gi.repository.Pango',
    'gi.repository.PangoCairo',
    'gi.repository.cairo',
    'gi.repository.Atk',
]

# ── Moduli PCM (importati dinamicamente da PCM.py) ───────────────────────────
hiddenimports += [
    'session_panel', 'session_dialog', 'session_command',
    'config_manager', 'settings_dialog', 'terminal_widget',
    'sftp_browser', 'winscp_widget', 'themes', 'translations',
    'tunnel_manager', 'rdp_widget', 'vnc_widget', 'crypto_manager',
    'importer', 'ftp_server_dialog', 'panel_monitor', 'sysmon_widget',
    'log_viewer', 'variables_dialog', 'deps_dialog',
    'keepassxc_manager', 'crypto_manager_dialog',
]

a = Analysis(
    [os.path.join(GTK3_SRC, 'PCM.py')],
    pathex=[GTK3_SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={
        'gi': {
            'module-versions': {
                'Gtk':        '3.0',
                'Gdk':        '3.0',
                'GdkPixbuf':  '2.0',
                'Vte':        '2.91',
                'Pango':      '1.0',
                'GLib':       '2.0',
                'GObject':    '2.0',
                'Gio':        '2.0',
                'Atk':        '1.0',
            },
            # Lista vuota = non raccogliere icon theme e GTK theme di sistema.
            # PCM usa solo le proprie icone (gtk3/icons/); quelle di sistema
            # sono già presenti su qualsiasi desktop Linux e non vanno bundlate.
            'icons':  [],
            'themes': [],
        }
    },
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'wx', 'PySide2', 'PySide6'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pcm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pcm',
)
