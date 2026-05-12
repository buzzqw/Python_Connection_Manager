"""
sftp_browser.py - Pannello SFTP laterale per PCM (GTK3)

Usa Gtk.TreeView + paramiko.
I thread bloccanti usano GLib.idle_add() per aggiornare la UI
in modo Wayland-safe (dal thread principale).
"""

import os
import stat
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf, Pango

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False

from translations import t

_HERE  = os.path.dirname(os.path.abspath(__file__))
_ICONS = os.path.join(_HERE, "icons")


def _pb(name: str, size: int = 16) -> GdkPixbuf.Pixbuf | None:
    path = os.path.join(_ICONS, name)
    if os.path.isfile(path):
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
        except Exception:
            pass
    return None


class SftpBrowserWidget(Gtk.Box):
    """Browser SFTP laterale stile MobaXterm (GTK3)."""

    def __init__(self, profilo: dict, parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_size_request(240, -1)
        self._profilo = profilo
        self._sftp    = None
        self._ssh     = None
        self._cwd     = "/"
        self._init_ui()

        self.connect("destroy", lambda w: self.chiudi())

        if PARAMIKO_OK:
            threading.Thread(target=self._connetti, daemon=True).start()
        else:
            GLib.idle_add(self._set_status, "paramiko non installato")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        # Barra indirizzo
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        nav_box.set_margin_start(4)
        nav_box.set_margin_end(4)
        nav_box.set_margin_top(4)

        self._path_entry = Gtk.Entry()
        self._path_entry.set_text("/")
        self._path_entry.set_hexpand(True)
        self._path_entry.connect("activate", lambda e: self._naviga(e.get_text()))

        btn_up = Gtk.Button()
        btn_up.add(Gtk.Image.new_from_icon_name("go-up-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        btn_up.set_tooltip_text("Su")
        btn_up.connect("clicked", lambda b: self._naviga_su())

        btn_ref = Gtk.Button()
        btn_ref.add(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        btn_ref.set_tooltip_text(t("sftp.refresh"))
        btn_ref.connect("clicked", lambda b: self._naviga(self._cwd))

        nav_box.pack_start(self._path_entry, True, True, 0)
        nav_box.pack_start(btn_up,  False, False, 0)
        nav_box.pack_start(btn_ref, False, False, 0)
        self.pack_start(nav_box, False, False, 0)

        # Toolbar operazioni
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        tb.set_margin_start(4)
        tb.set_margin_end(4)
        tb.set_margin_top(2)
        tb.set_margin_bottom(2)

        for label, cb in [
            (t("sftp.upload"),   self._on_upload),
            (t("sftp.download"), self._on_download),
            (t("sftp.mkdir"),    self._on_mkdir),
            (t("sftp.delete"),   self._on_delete),
        ]:
            btn = Gtk.Button(label=label)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.connect("clicked", lambda b, c=cb: c())
            tb.pack_start(btn, False, False, 0)

        self.pack_start(tb, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 0)

        # Lista file: icona, nome, dimensione, permessi
        self._store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str, bool)
        # cols: pixbuf, nome, size_str, perms, is_dir

        self._view = Gtk.TreeView(model=self._store)
        self._view.set_headers_visible(True)

        col_name = Gtk.TreeViewColumn(t("sftp.col_name"))
        cell_pb  = Gtk.CellRendererPixbuf()
        cell_txt = Gtk.CellRendererText()
        cell_txt.set_property("ellipsize", Pango.EllipsizeMode.END)
        col_name.pack_start(cell_pb,  False)
        col_name.pack_start(cell_txt, True)
        col_name.add_attribute(cell_pb,  "pixbuf", 0)
        col_name.add_attribute(cell_txt, "text",   1)
        col_name.set_expand(True)
        col_name.set_resizable(True)
        self._view.append_column(col_name)

        for i, h in enumerate([t("sftp.col_size"), t("sftp.col_perms")], start=2):
            cell = Gtk.CellRendererText()
            col  = Gtk.TreeViewColumn(h, cell, text=i)
            col.set_resizable(True)
            col.set_min_width(50)
            self._view.append_column(col)

        self._view.connect("row-activated", self._on_row_activated)
        self._view.connect("button-press-event", self._on_button_press)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._view)
        self.pack_start(scroll, True, True, 0)

        # Statusbar
        self._status_lbl = Gtk.Label(label=t("sftp.loading"))
        self._status_lbl.set_xalign(0.0)
        self._status_lbl.set_margin_start(6)
        self._status_lbl.set_margin_top(2)
        self._status_lbl.set_margin_bottom(2)
        self.pack_start(self._status_lbl, False, False, 0)

    # ------------------------------------------------------------------
    # Connessione SSH/SFTP
    # ------------------------------------------------------------------

    def _connetti(self):
        try:
            host = self._profilo.get("host", "")
            port = int(self._profilo.get("port", 22))
            user = self._profilo.get("user", "")
            pwd  = self._profilo.get("password", "")
            pkey = self._profilo.get("private_key", "")

            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            kwargs = {"hostname": host, "port": port, "username": user, "timeout": 10}
            if pkey and os.path.isfile(pkey):
                kwargs["key_filename"] = pkey
            elif pwd:
                kwargs["password"] = pwd

            self._ssh.connect(**kwargs)
            self._sftp = self._ssh.open_sftp()

            # Home directory
            _, stdout, _ = self._ssh.exec_command("echo $HOME")
            home = stdout.read().decode().strip() or "/"
            self._cwd = home

            GLib.idle_add(self._naviga_ui, home)
        except Exception as e:
            GLib.idle_add(self._set_status, t("sftp.err_connect").format(e=e))

    # ------------------------------------------------------------------
    # Navigazione
    # ------------------------------------------------------------------

    def _naviga(self, path: str):
        if not self._sftp:
            return
        threading.Thread(
            target=self._list_dir,
            args=(path,),
            daemon=True
        ).start()

    def _naviga_su(self):
        parent = str(Path(self._cwd).parent)
        self._naviga(parent)

    def _naviga_ui(self, path: str):
        """Chiamato sul thread principale tramite GLib.idle_add."""
        self._path_entry.set_text(path)
        self._naviga(path)

    def _list_dir(self, path: str):
        try:
            entries = self._sftp.listdir_attr(path)
            self._cwd = path
            GLib.idle_add(self._popola_lista, entries)
        except Exception as e:
            GLib.idle_add(self._set_status, t("sftp.err_connect").format(e=e))

    def _popola_lista(self, entries):
        self._store.clear()
        folder_pb = _pb("folder.png", 16)
        file_pb   = _pb("file.png", 16)

        # Prima le cartelle, poi i file
        dirs  = [e for e in entries if stat.S_ISDIR(e.st_mode)]
        files = [e for e in entries if not stat.S_ISDIR(e.st_mode)]

        for e in sorted(dirs,  key=lambda x: x.filename.lower()):
            self._store.append([folder_pb, e.filename, "", self._perms(e.st_mode), True])
        for e in sorted(files, key=lambda x: x.filename.lower()):
            size = self._fmt_size(e.st_size)
            self._store.append([file_pb, e.filename, size, self._perms(e.st_mode), False])

        self._path_entry.set_text(self._cwd)
        self._set_status(t("sftp.n_items").format(n=len(entries)))

    @staticmethod
    def _perms(mode: int) -> str:
        chars = "rwxrwxrwx"
        bits  = [0o400,0o200,0o100,0o040,0o020,0o010,0o004,0o002,0o001]
        return "".join(c if mode & b else "-" for c, b in zip(chars, bits))

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ("B","KB","MB","GB"):
            if n < 1024:
                return f"{n:.0f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def _set_status(self, msg: str):
        self._status_lbl.set_text(msg)

    # ------------------------------------------------------------------
    # Interazioni
    # ------------------------------------------------------------------

    def _on_row_activated(self, view, path, column):
        it = self._store.get_iter(path)
        if it is None:
            return
        is_dir = self._store.get_value(it, 4)
        nome   = self._store.get_value(it, 1)
        if is_dir:
            import posixpath
            self._naviga(posixpath.join(self._cwd, nome))

    def _on_button_press(self, view, event):
        if event.button != 3:
            return False
        info = view.get_path_at_pos(int(event.x), int(event.y))
        if not info:
            return False
        path, _, _, _ = info
        it = self._store.get_iter(path)
        if it is None:
            return False
        nome = self._store.get_value(it, 1)
        menu = Gtk.Menu()

        def _mi(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: cb(nome))
            menu.append(mi)

        _mi(t("sftp.download"), lambda n: self._on_download(nome=n))
        _mi(t("sftp.rename"),   self._on_rename)
        _mi(t("sftp.delete"),   lambda n: self._on_delete(nome=n))

        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    # ------------------------------------------------------------------
    # Operazioni file
    # ------------------------------------------------------------------

    def _on_upload(self):
        if not self._sftp:
            return
        dlg = Gtk.FileChooserDialog(
            title=t("sftp.upload_title"),
            parent=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons(t("sftp.btn_cancel"), Gtk.ResponseType.CANCEL, t("sftp.btn_upload"), Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            local  = dlg.get_filename()
            remote = self._cwd + "/" + os.path.basename(local)
            threading.Thread(
                target=self._upload_file, args=(local, remote), daemon=True
            ).start()
        dlg.destroy()

    def _upload_file(self, local: str, remote: str):
        try:
            self._sftp.put(local, remote)
            GLib.idle_add(self._naviga, self._cwd)
        except Exception as e:
            GLib.idle_add(self._set_status, t("sftp.upload_err") + f": {e}")

    def _on_download(self, nome: str | None = None):
        if not self._sftp:
            return
        if nome is None:
            sel = self._view.get_selection()
            model, it = sel.get_selected()
            if it is None:
                return
            nome = model.get_value(it, 1)

        dlg = Gtk.FileChooserDialog(
            title=t("sftp.download_title"),
            parent=self.get_toplevel(),
            action=Gtk.FileChooserAction.SAVE
        )
        dlg.set_current_name(nome)
        dlg.add_buttons(t("sftp.btn_cancel"), Gtk.ResponseType.CANCEL, t("sftp.btn_save"), Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            local  = dlg.get_filename()
            remote = self._cwd + "/" + nome
            threading.Thread(
                target=self._download_file, args=(remote, local), daemon=True
            ).start()
        dlg.destroy()

    def _download_file(self, remote: str, local: str):
        try:
            self._sftp.get(remote, local)
            GLib.idle_add(self._set_status, t("sftp.download_done"))
        except Exception as e:
            GLib.idle_add(self._set_status, t("sftp.err_delete").replace("Errore eliminazione", "Download errore") + f": {e}")

    def _on_mkdir(self):
        if not self._sftp:
            return
        dlg = Gtk.Dialog(
            title=t("sftp.mkdir_title"),
            transient_for=self.get_toplevel(),
            modal=True
        )
        area = dlg.get_content_area()
        entry = Gtk.Entry()
        entry.set_placeholder_text(t("sftp.mkdir_ph"))
        entry.set_margin_start(12)
        entry.set_margin_end(12)
        entry.set_margin_top(8)
        entry.set_margin_bottom(8)
        area.add(entry)
        dlg.add_buttons(t("sftp.btn_cancel"), Gtk.ResponseType.CANCEL, t("sftp.btn_create"), Gtk.ResponseType.OK)
        dlg.show_all()
        if dlg.run() == Gtk.ResponseType.OK:
            nome = entry.get_text().strip()
            if nome:
                try:
                    self._sftp.mkdir(self._cwd + "/" + nome)
                    self._naviga(self._cwd)
                except Exception as e:
                    self._set_status(t("sftp.err_connect").format(e=e))
        dlg.destroy()

    def _on_delete(self, nome: str | None = None):
        if not self._sftp:
            return
        if nome is None:
            sel = self._view.get_selection()
            model, it = sel.get_selected()
            if it is None:
                return
            nome = model.get_value(it, 1)

        confirm = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=t("sftp.delete_confirm").format(name=nome)
        )
        if confirm.run() == Gtk.ResponseType.YES:
            try:
                path = self._cwd + "/" + nome
                self._sftp.remove(path)
                self._naviga(self._cwd)
            except Exception as e:
                self._set_status(t("sftp.err_delete").format(e=e))
        confirm.destroy()

    def _on_rename(self, nome: str):
        if not self._sftp:
            return
        dlg = Gtk.Dialog(
            title=t("sftp.rename_title"),
            transient_for=self.get_toplevel(),
            modal=True
        )
        area = dlg.get_content_area()
        entry = Gtk.Entry()
        entry.set_text(nome)
        entry.set_margin_start(12); entry.set_margin_end(12)
        entry.set_margin_top(8);   entry.set_margin_bottom(8)
        area.add(entry)
        dlg.add_buttons(t("sftp.btn_cancel"), Gtk.ResponseType.CANCEL, t("sftp.btn_rename"), Gtk.ResponseType.OK)
        dlg.show_all()
        if dlg.run() == Gtk.ResponseType.OK:
            nuovo = entry.get_text().strip()
            if nuovo and nuovo != nome:
                try:
                    self._sftp.rename(
                        self._cwd + "/" + nome,
                        self._cwd + "/" + nuovo
                    )
                    self._naviga(self._cwd)
                except Exception as e:
                    self._set_status(t("sftp.err_rename").format(e=e))
        dlg.destroy()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def chiudi(self):
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
