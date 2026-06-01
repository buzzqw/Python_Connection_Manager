"""
sftp_editor.py — Editor file remoti SFTP per PCM (GTK3)

Modalità automatica:
  - Se in Settings è configurato un editor GUI (mousepad, gedit, kate, code…):
      scarica in file temp → apre l'editor esterno → al termine del processo
      ricarica il temp e ricarica le modifiche sul server se il file è cambiato.
  - Se l'editor configurato è un editor da terminale (nano, vim…) oppure non è
      configurato: usa il widget interno GtkSource.View / GtkTextView.
"""

import hashlib
import io
import os
import subprocess
import tempfile
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

try:
    gi.require_version("GtkSource", "3.0")
    from gi.repository import GtkSource
    _GTKSOURCE = True
except (ValueError, ImportError):
    _GTKSOURCE = False


# Editor che richiedono un terminale — non apribili come processo GUI standalone
_TERM_EDITORS = {
    "nano", "vi", "vim", "nvim", "neovim", "emacs", "pico",
    "micro", "mcedit", "joe", "jed", "ne", "mg", "ed",
}

# Mappa estensione → id linguaggio GtkSource
_EXT_LANG = {
    ".py": "python",    ".sh": "sh",      ".bash": "sh",    ".zsh": "sh",
    ".js": "js",        ".ts": "typescript", ".json": "json",
    ".yaml": "yaml",    ".yml": "yaml",   ".toml": "toml",
    ".xml": "xml",      ".html": "html",  ".css": "css",
    ".c": "c",          ".h": "c",        ".cpp": "cpp",    ".hpp": "cpp",
    ".rs": "rust",      ".go": "go",      ".rb": "ruby",
    ".sql": "sql",      ".md": "markdown",
    ".conf": "ini",     ".ini": "ini",    ".cfg": "ini",
    ".dockerfile": "dockerfile",
}


def _get_configured_editor() -> str:
    """
    Ritorna il comando editor da Settings, vuoto se non configurato o da terminale.
    Gestisce sia editor binari ("mousepad", "gedit") sia script Python
    ("python3 /path/to/main.py" per NotePadPQ e simili).
    """
    try:
        import config_manager
        ed = config_manager.load_settings().get("general", {}).get("default_editor", "").strip()
        if not ed:
            return ""
        parts = ed.split()
        # Caso "python3 /path/script.py": il binario è python3, non da terminale
        if parts[0] in ("python3", "python") and len(parts) >= 2:
            return ed
        binary = os.path.basename(parts[0])
        if binary and binary not in _TERM_EDITORS:
            return ed
    except Exception:
        pass
    return ""


def _file_hash(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).digest()
    except Exception:
        return b""


# ---------------------------------------------------------------------------
# Helpers view interna
# ---------------------------------------------------------------------------

def _make_view() -> tuple:
    """Ritorna (view, buffer). Usa GtkSource se disponibile."""
    if _GTKSOURCE:
        buf  = GtkSource.Buffer()
        sm   = GtkSource.StyleSchemeManager.get_default()
        for sid in ("oblivion", "dark", "classic"):
            scheme = sm.get_scheme(sid)
            if scheme:
                buf.set_style_scheme(scheme)
                break
        view = GtkSource.View.new_with_buffer(buf)
        view.set_show_line_numbers(True)
        view.set_auto_indent(True)
        view.set_tab_width(4)
        view.set_insert_spaces_instead_of_tabs(True)
        view.set_highlight_current_line(True)
    else:
        buf  = Gtk.TextBuffer()
        view = Gtk.TextView.new_with_buffer(buf)
    view.set_monospace(True)
    view.set_wrap_mode(Gtk.WrapMode.NONE)
    return view, buf


def _set_language(buf, remote_path: str):
    if not _GTKSOURCE:
        return
    _, ext = os.path.splitext(remote_path.lower())
    lang_id = _EXT_LANG.get(ext)
    if lang_id:
        lang = GtkSource.LanguageManager.get_default().get_language(lang_id)
        if lang:
            buf.set_language(lang)


# ---------------------------------------------------------------------------
# Widget principale
# ---------------------------------------------------------------------------

class SftpEditorWidget(Gtk.Box):
    """
    Tab editor file remoto SFTP.
        sftp        — paramiko.SFTPClient già aperto
        remote_path — percorso assoluto sul server
    """

    def __init__(self, sftp, remote_path: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._sftp        = sftp
        self._remote_path = remote_path
        self._modified    = False
        self._tmp_path    = None   # solo in modalità editor esterno
        self._ext_editor  = _get_configured_editor()

        self._build_ui()
        threading.Thread(target=self._load, daemon=True).start()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_margin_start(6); tb.set_margin_end(6)
        tb.set_margin_top(4);   tb.set_margin_bottom(4)

        lbl = Gtk.Label(label=self._remote_path)
        lbl.set_xalign(0.0)
        lbl.set_hexpand(True)
        lbl.set_ellipsize(Pango.EllipsizeMode.START)
        lbl.set_selectable(True)
        tb.pack_start(lbl, True, True, 0)

        if self._ext_editor:
            # Modalità editor esterno: bottone "Riapri" + info editor
            editor_name = os.path.basename(self._ext_editor.split()[0])
            lbl_ed = Gtk.Label()
            lbl_ed.set_markup(f"<small>Editor: <b>{editor_name}</b></small>")
            lbl_ed.set_margin_end(6)
            tb.pack_start(lbl_ed, False, False, 0)

            self._btn_reopen = Gtk.Button(label="↗ Riapri")
            self._btn_reopen.set_tooltip_text(f"Riapre il file in {editor_name}")
            self._btn_reopen.connect("clicked", self._on_reopen)
            self._btn_reopen.set_sensitive(False)
            tb.pack_start(self._btn_reopen, False, False, 0)
        else:
            # Modalità built-in: bottone "Salva"
            self._btn_save = Gtk.Button(label="💾 Salva")
            self._btn_save.connect("clicked", self._on_save)
            self._btn_save.set_sensitive(False)
            tb.pack_start(self._btn_save, False, False, 0)

        self.pack_start(tb, False, False, 0)
        self.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0
        )

        if self._ext_editor:
            # Area informativa (non editabile)
            self._info_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            self._info_area.set_valign(Gtk.Align.CENTER)
            self._info_area.set_halign(Gtk.Align.CENTER)
            self._info_area.set_vexpand(True)

            self._info_icon = Gtk.Label()
            self._info_icon.set_markup('<span font="32">📝</span>')
            self._info_lbl = Gtk.Label(label="Scaricamento in corso…")
            self._info_lbl.set_justify(Gtk.Justification.CENTER)

            self._info_area.pack_start(self._info_icon, False, False, 0)
            self._info_area.pack_start(self._info_lbl,  False, False, 0)
            self.pack_start(self._info_area, True, True, 0)
        else:
            self._view, self._buf = _make_view()
            _set_language(self._buf, self._remote_path)
            self._buf.connect("changed", self._on_changed)

            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.add(self._view)
            self.pack_start(scroll, True, True, 0)

        self._status = Gtk.Label(label="Caricamento…")
        self._status.set_xalign(0.0)
        self._status.set_margin_start(6)
        self._status.set_margin_top(2); self._status.set_margin_bottom(2)
        self.pack_start(self._status, False, False, 0)

    def _on_changed(self, _buf):
        self._modified = True
        self._btn_save.set_sensitive(True)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _load(self):
        try:
            if self._ext_editor:
                self._load_to_temp()
            else:
                self._load_to_buf()
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ Errore caricamento: {e}")

    def _load_to_buf(self):
        buf_io = io.BytesIO()
        self._sftp.getfo(self._remote_path, buf_io)
        content = buf_io.getvalue().decode("utf-8", errors="replace")
        GLib.idle_add(self._set_content_buf, content)

    def _load_to_temp(self):
        fname = os.path.basename(self._remote_path)
        # Mantieni l'estensione originale così l'editor rileva il tipo
        suffix = os.path.splitext(fname)[1] or ".txt"
        fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="pcm_sftp_")
        os.close(fd)
        self._sftp.get(self._remote_path, tmp)
        self._tmp_path = tmp
        GLib.idle_add(self._after_download)

    def _after_download(self):
        editor_name = os.path.basename(self._ext_editor.split()[0])
        self._info_lbl.set_text(
            f"File scaricato — si aprirà in {editor_name}.\n"
            "Al salvataggio nell'editor, le modifiche verranno caricate sul server."
        )
        self._btn_reopen.set_sensitive(True)
        self._set_status(f"✔ Pronto — {self._remote_path}")
        self._open_ext_editor()

    # ------------------------------------------------------------------
    # Editor esterno
    # ------------------------------------------------------------------

    def _open_ext_editor(self):
        if not self._tmp_path:
            return
        hash_before = _file_hash(self._tmp_path)
        cmd = self._ext_editor.split() + [self._tmp_path]
        try:
            proc = subprocess.Popen(cmd)
        except FileNotFoundError:
            GLib.idle_add(self._set_status,
                          f"✖ Editor non trovato: {self._ext_editor}")
            return

        GLib.idle_add(self._set_status,
                      f"✎ {os.path.basename(self._ext_editor.split()[0])} aperto…")

        def _watch():
            proc.wait()
            hash_after = _file_hash(self._tmp_path)
            if hash_after and hash_after != hash_before:
                GLib.idle_add(self._set_status, "⬆ Caricamento modifiche…")
                self._upload_from_temp()
            else:
                GLib.idle_add(self._set_status, "✔ Nessuna modifica")

        threading.Thread(target=_watch, daemon=True).start()

    def _on_reopen(self, _btn=None):
        if self._tmp_path and os.path.exists(self._tmp_path):
            threading.Thread(target=self._open_ext_editor, daemon=True).start()
        else:
            threading.Thread(target=self._reload_and_open, daemon=True).start()

    def _reload_and_open(self):
        GLib.idle_add(self._set_status, "Riscaricamento…")
        try:
            self._load_to_temp()
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ {e}")

    def _upload_from_temp(self):
        try:
            self._sftp.put(self._tmp_path, self._remote_path)
            GLib.idle_add(self._set_status, f"✔ Salvato: {self._remote_path}")
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ Errore upload: {e}")

    # ------------------------------------------------------------------
    # Modalità built-in: salvataggio
    # ------------------------------------------------------------------

    def _set_content_buf(self, text: str):
        self._buf.handler_block_by_func(self._on_changed)
        self._buf.set_text(text)
        self._buf.handler_unblock_by_func(self._on_changed)
        self._modified = False
        self._btn_save.set_sensitive(False)
        self._set_status(f"✔ {self._remote_path}")

    def _on_save(self, _btn=None):
        if not self._sftp:
            return
        start, end = self._buf.get_bounds()
        text = self._buf.get_text(start, end, False)
        self._btn_save.set_sensitive(False)
        self._set_status("Salvataggio…")
        threading.Thread(target=self._save_remote, args=(text,), daemon=True).start()

    def _save_remote(self, text: str):
        try:
            self._sftp.putfo(io.BytesIO(text.encode("utf-8")), self._remote_path)
            GLib.idle_add(self._set_status, f"✔ Salvato: {self._remote_path}")
            self._modified = False
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ Errore salvataggio: {e}")
            GLib.idle_add(self._btn_save.set_sensitive, True)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_tmp(self):
        if self._tmp_path:
            try:
                os.unlink(self._tmp_path)
            except Exception:
                pass
            self._tmp_path = None

    def _set_status(self, msg: str):
        self._status.set_text(msg)

    def grab_focus(self):
        if self._ext_editor:
            self._info_area.grab_focus()
        else:
            self._view.grab_focus()
