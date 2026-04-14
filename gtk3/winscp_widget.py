"""
winscp_widget.py — Browser SFTP dual-pane stile WinSCP per PCM (GTK3)

Layout:
  ┌────────────────────────────────────────────────────────────┐
  │  Toolbar: Upload ▲  Download ▼  Sincronizza  Elimina       │
  ├───────────────────────┬────────────────────────────────────┤
  │  LOCALE               │  REMOTO                            │
  │  path bar + nav       │  path bar + nav                    │
  │  [TreeView file]      │  [TreeView file]                   │
  ├───────────────────────┴────────────────────────────────────┤
  │  Coda trasferimenti (Op | Src | Dst | % | Velocità)        │
  └────────────────────────────────────────────────────────────┘

Thread GTK-safe: tutti gli aggiornamenti UI via GLib.idle_add().
"""

import os
import stat
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf, Pango

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _fmt_size(n) -> str:
    if n is None:
        return ""
    n = int(n)
    if n < 1024:        return f"{n} B"
    if n < 1024**2:     return f"{n/1024:.1f} KB"
    if n < 1024**3:     return f"{n/1024**2:.1f} MB"
    return f"{n/1024**3:.2f} GB"


def _fmt_attr(mode: int) -> str:
    chars = ""
    for r, w, x in [(0o400,0o200,0o100),(0o040,0o020,0o010),(0o004,0o002,0o001)]:
        chars += "r" if mode & r else "-"
        chars += "w" if mode & w else "-"
        chars += "x" if mode & x else "-"
    return chars


# ---------------------------------------------------------------------------
# TransferJob — un singolo elemento di coda
# ---------------------------------------------------------------------------

class TransferJob:
    def __init__(self, op, src, dst, size=0, nome=""):
        self.op         = op        # 'upload' | 'download'
        self.src        = src
        self.dst        = dst
        self.size       = size
        self.nome       = nome or os.path.basename(src)
        self.trasferito = 0
        self.stato      = "In attesa"
        self.errore     = ""
        self.velocita   = 0
        self.t_inizio   = 0.0


# ---------------------------------------------------------------------------
# Pannello file (base) — Gtk.TreeView
# ---------------------------------------------------------------------------

# Colonne store: nome_display, nome_raw, ext, size_str, mtime, attr, is_dir, path, size_int
C_NOME_D, C_NOME, C_EXT, C_SIZE, C_MTIME, C_ATTR, C_ISDIR, C_PATH, C_SIZE_INT = range(9)


class FilePanel(Gtk.Box):
    """
    Singolo pannello file (locale o remoto).
    Emette segnali GObject per navigazione.
    """

    def __init__(self, titolo: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.titolo = titolo
        self.path   = ""
        self._init_ui()

    def _init_ui(self):
        # Header
        hdr = Gtk.Label(label=f"  {self.titolo}")
        hdr.set_xalign(0.0)
        hdr.get_style_context().add_class("section-header")
        self.pack_start(hdr, False, False, 0)

        # Barra navigazione
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        nav.set_margin_start(4)
        nav.set_margin_end(4)
        nav.set_margin_top(2)
        nav.set_margin_bottom(2)

        self.btn_su   = Gtk.Button(label="⬆")
        self.btn_home = Gtk.Button(label="🏠")
        self.btn_ref  = Gtk.Button(label="↺")
        for btn, tip in [(self.btn_su,"Su"),(self.btn_home,"Home"),(self.btn_ref,"Aggiorna")]:
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_tooltip_text(tip)
            nav.pack_start(btn, False, False, 0)

        self.path_entry = Gtk.Entry()
        self.path_entry.set_hexpand(True)
        self.path_entry.connect("activate", lambda e: self.naviga(e.get_text().strip()))
        nav.pack_start(self.path_entry, True, True, 0)

        self.pack_start(nav, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 0)

        # TreeView
        # Store: nome_display, nome_raw, ext, size, mtime, attr, is_dir, path, size_int
        self._store = Gtk.ListStore(str, str, str, str, str, str, bool, str, int)
        self._sorted = Gtk.TreeModelSort(model=self._store)
        self._view = Gtk.TreeView(model=self._sorted)
        self._view.set_headers_visible(True)
        self._view.set_headers_clickable(True)
        self._view.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        col_defs = [
            ("Nome",        C_NOME_D, True),
            ("Ext",         C_EXT,    False),
            ("Dimensione",  C_SIZE,   False),
            ("Modificato",  C_MTIME,  False),
            ("Attributi",   C_ATTR,   False),
        ]
        sort_cols = [C_NOME, C_EXT, C_SIZE_INT, C_MTIME, C_ATTR]

        for i, (h, data_col, expand) in enumerate(col_defs):
            cell = Gtk.CellRendererText()
            cell.set_property("ellipsize", Pango.EllipsizeMode.END)
            col = Gtk.TreeViewColumn(h, cell, text=data_col)
            col.set_resizable(True)
            col.set_expand(expand)
            col.set_sort_column_id(sort_cols[i])
            self._view.append_column(col)

        self._view.connect("row-activated",       self._on_row_activated)
        self._view.connect("button-press-event",  self._on_button_press)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add(self._view)
        self.pack_start(scroll, True, True, 0)

        # Status
        self._status = Gtk.Label(label="")
        self._status.set_xalign(0.0)
        self._status.set_margin_start(6)
        self.pack_start(self._status, False, False, 0)

        # Connetti bottoni nav
        self.btn_su.connect("clicked",   lambda b: self._vai_su())
        self.btn_home.connect("clicked", lambda b: self._vai_home())
        self.btn_ref.connect("clicked",  lambda b: self.aggiorna())

    # ------------------------------------------------------------------
    # Navigazione (da implementare nelle sottoclassi)
    # ------------------------------------------------------------------

    def naviga(self, path: str):
        raise NotImplementedError

    def aggiorna(self):
        self.naviga(self.path)

    def _vai_su(self):
        parent = str(Path(self.path).parent)
        if parent != self.path:
            self.naviga(parent)

    def _vai_home(self):
        self.naviga(os.path.expanduser("~"))

    # ------------------------------------------------------------------
    # Popolamento
    # ------------------------------------------------------------------

    def _popola(self, voci: list):
        """voci: lista di dict {nome, is_dir, path, size, mtime, attr}"""
        self._store.clear()
        for v in voci:
            nome   = v["nome"]
            is_dir = v.get("is_dir", False)
            icona  = "📁 " if is_dir else "📄 "
            ext    = "" if is_dir else (Path(nome).suffix.lstrip(".") or "")
            size_s = "" if is_dir else _fmt_size(v.get("size", 0))
            self._store.append([
                icona + nome,
                nome,
                ext,
                size_s,
                v.get("mtime", ""),
                v.get("attr", ""),
                is_dir,
                v.get("path", ""),
                v.get("size", 0) or 0,
            ])
        self._status.set_text(f"  {len(voci)} elementi  |  {self.path}")

    # ------------------------------------------------------------------
    # Selezione
    # ------------------------------------------------------------------

    def selezione(self) -> list:
        """Lista di dict per le righe selezionate."""
        sel = self._view.get_selection()
        model, paths = sel.get_selected_rows()
        result = []
        for p in paths:
            it = model.get_iter(p)
            result.append({
                "nome":   model.get_value(it, C_NOME),
                "is_dir": model.get_value(it, C_ISDIR),
                "path":   model.get_value(it, C_PATH),
                "size":   model.get_value(it, C_SIZE_INT),
            })
        return result

    # ------------------------------------------------------------------
    # Interazioni
    # ------------------------------------------------------------------

    def _on_row_activated(self, view, path, column):
        it = self._sorted.get_iter(path)
        if it is None:
            return
        nome   = self._sorted.get_value(it, C_NOME)
        is_dir = self._sorted.get_value(it, C_ISDIR)
        fpath  = self._sorted.get_value(it, C_PATH)
        if nome == "..":
            self._vai_su()
        elif is_dir:
            self.naviga(fpath)

    def _on_button_press(self, view, event):
        if event.button != 3:
            return False
        info = view.get_path_at_pos(int(event.x), int(event.y))
        if info:
            path, col, _, _ = info
            sel = view.get_selection()
            if not sel.path_is_selected(path):
                sel.unselect_all()
                sel.select_path(path)
        self._menu_contestuale(event)
        return True

    def _menu_contestuale(self, event):
        pass  # override nelle sottoclassi

    # ------------------------------------------------------------------
    # Helper dialog
    # ------------------------------------------------------------------

    def _chiedi_nome(self, titolo: str, default: str = "") -> str | None:
        dlg = Gtk.Dialog(
            title=titolo,
            transient_for=self.get_toplevel(),
            modal=True
        )
        entry = Gtk.Entry()
        entry.set_text(default)
        entry.set_margin_start(12); entry.set_margin_end(12)
        entry.set_margin_top(8);   entry.set_margin_bottom(8)
        dlg.get_content_area().add(entry)
        dlg.add_buttons("Annulla", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        dlg.show_all()
        resp = dlg.run()
        result = entry.get_text().strip() if resp == Gtk.ResponseType.OK else None
        dlg.destroy()
        return result

    def _conferma(self, msg: str) -> bool:
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO, text=msg
        )
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    def _trova_winscp(self):
        """Risale la gerarchia widget per trovare il WinScpWidget padre."""
        w = self.get_parent()
        while w:
            if hasattr(w, "_esegui_jobs"):
                return w
            w = w.get_parent()
        return None


# ---------------------------------------------------------------------------
# Pannello LOCALE
# ---------------------------------------------------------------------------

class LocalPanel(FilePanel):

    def __init__(self):
        super().__init__("💻  Locale")
        self.naviga(os.path.expanduser("~"))

    def naviga(self, path: str):
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            return
        self.path = path
        self.path_entry.set_text(path)

        voci = [{"nome": "..", "is_dir": True,
                  "path": str(Path(path).parent), "size": 0, "mtime": "", "attr": ""}]
        try:
            raw = list(os.scandir(path))
        except (PermissionError, OSError):
            raw = []

        raw.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))

        for e in raw:
            try:
                st = e.stat(follow_symlinks=False)
                is_dir = e.is_dir(follow_symlinks=False)
                if e.is_symlink():
                    try:
                        st = e.stat(follow_symlinks=True)
                        is_dir = os.path.isdir(e.path)
                    except OSError:
                        voci.append({"nome": f"⚠ {e.name}", "is_dir": False,
                                     "path": e.path, "size": 0, "mtime": "", "attr": "link?"})
                        continue
                size  = 0 if is_dir else st.st_size
                mtime = datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M:%S")
                m     = st.st_mode
                attr  = ("r" if m & 0o444 else "-") + ("w" if m & 0o222 else "-") + ("x" if m & 0o111 else "-")
                voci.append({"nome": e.name, "is_dir": is_dir,
                              "path": e.path, "size": size, "mtime": mtime, "attr": attr})
            except (PermissionError, OSError):
                voci.append({"nome": e.name, "is_dir": False,
                              "path": e.path, "size": 0, "mtime": "", "attr": "?"})
        self._popola(voci)

    def _menu_contestuale(self, event):
        sel = self.selezione()
        menu = Gtk.Menu()

        def _mi(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: cb())
            menu.append(mi)

        if sel:
            ws = self._trova_winscp()
            _mi(f"⬆  Carica su remoto ({len(sel)} elementi)",
                lambda: ws._upload_selezione() if ws else None)
        menu.append(Gtk.SeparatorMenuItem())
        _mi("📁+  Nuova cartella", self._nuova_cartella)
        if sel and not sel[0]["is_dir"]:
            _mi("🗑  Elimina", lambda: self._elimina(sel))
        menu.append(Gtk.SeparatorMenuItem())
        _mi("↺  Aggiorna", self.aggiorna)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _nuova_cartella(self):
        nome = self._chiedi_nome("Nuova cartella")
        if nome:
            try:
                os.makedirs(os.path.join(self.path, nome), exist_ok=True)
                self.aggiorna()
            except Exception as e:
                self._errore(str(e))

    def _elimina(self, sel: list):
        nomi = ", ".join(v["nome"] for v in sel)
        if self._conferma(f"Eliminare: {nomi}?"):
            for v in sel:
                try:
                    if v["is_dir"]: shutil.rmtree(v["path"])
                    else:           os.remove(v["path"])
                except Exception as e:
                    self._errore(str(e))
            self.aggiorna()

    def _errore(self, msg: str):
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=msg
        )
        dlg.run()
        dlg.destroy()


# ---------------------------------------------------------------------------
# Pannello REMOTO
# ---------------------------------------------------------------------------

class RemotePanel(FilePanel):

    def __init__(self, sftp):
        super().__init__("🌐  Remoto")
        self._sftp = sftp
        try:
            home = sftp.normalize(".")
        except Exception:
            home = "/"
        self.naviga(home)

    def naviga(self, path: str):
        self.path = path
        self.path_entry.set_text(path)
        threading.Thread(target=self._list_thread, args=(path,), daemon=True).start()

    def _list_thread(self, path: str):
        try:
            entries = self._sftp.listdir_attr(path)
            voci = [{"nome": "..", "is_dir": True,
                     "path": str(Path(path).parent), "size": 0, "mtime": "", "attr": ""}]
            dirs  = sorted([e for e in entries if stat.S_ISDIR(e.st_mode)],
                            key=lambda e: e.filename.lower())
            files = sorted([e for e in entries if not stat.S_ISDIR(e.st_mode)],
                            key=lambda e: e.filename.lower())
            for e in dirs + files:
                mtime = datetime.fromtimestamp(e.st_mtime).strftime("%d.%m.%Y %H:%M:%S") \
                        if e.st_mtime else ""
                voci.append({
                    "nome":   e.filename,
                    "is_dir": stat.S_ISDIR(e.st_mode),
                    "path":   path.rstrip("/") + "/" + e.filename,
                    "size":   e.st_size or 0,
                    "mtime":  mtime,
                    "attr":   _fmt_attr(e.st_mode),
                })
            GLib.idle_add(self._popola, voci)
        except Exception as e:
            GLib.idle_add(self._status.set_text, f"  ✖ {e}")

    def _vai_home(self):
        try:
            home = self._sftp.normalize(".")
        except Exception:
            home = "/"
        self.naviga(home)

    def _menu_contestuale(self, event):
        sel = self.selezione()
        menu = Gtk.Menu()

        def _mi(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: cb())
            menu.append(mi)

        if sel:
            ws = self._trova_winscp()
            _mi(f"⬇  Scarica in locale ({len(sel)} elementi)",
                lambda: ws._download_selezione() if ws else None)
        menu.append(Gtk.SeparatorMenuItem())
        _mi("📁+  Nuova cartella", self._nuova_cartella)
        if sel:
            _mi("✏  Rinomina", lambda: self._rinomina(sel[0]))
            _mi("🗑  Elimina",  lambda: self._elimina(sel))
        menu.append(Gtk.SeparatorMenuItem())
        _mi("↺  Aggiorna", self.aggiorna)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _nuova_cartella(self):
        nome = self._chiedi_nome("Nuova cartella remota")
        if nome:
            try:
                self._sftp.mkdir(self.path.rstrip("/") + "/" + nome)
                self.aggiorna()
            except Exception as e:
                self._errore_ui(str(e))

    def _rinomina(self, v: dict):
        nuovo = self._chiedi_nome("Rinomina", default=v["nome"])
        if nuovo and nuovo != v["nome"]:
            try:
                self._sftp.rename(v["path"], self.path.rstrip("/") + "/" + nuovo)
                self.aggiorna()
            except Exception as e:
                self._errore_ui(str(e))

    def _elimina(self, sel: list):
        nomi = ", ".join(v["nome"] for v in sel)
        if self._conferma(f"Eliminare dal remoto: {nomi}?"):
            for v in sel:
                try:
                    if v["is_dir"]: self._rmdir_ricorsivo(v["path"])
                    else:           self._sftp.remove(v["path"])
                except Exception as e:
                    self._errore_ui(str(e))
            self.aggiorna()

    def _rmdir_ricorsivo(self, path: str):
        for attr in self._sftp.listdir_attr(path):
            fp = path.rstrip("/") + "/" + attr.filename
            if stat.S_ISDIR(attr.st_mode):
                self._rmdir_ricorsivo(fp)
            else:
                self._sftp.remove(fp)
        self._sftp.rmdir(path)

    def _errore_ui(self, msg: str):
        GLib.idle_add(self._mostra_errore, msg)

    def _mostra_errore(self, msg: str):
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=msg
        )
        dlg.run()
        dlg.destroy()


# ---------------------------------------------------------------------------
# Coda trasferimenti
# ---------------------------------------------------------------------------

class CodaWidget(Gtk.Box):
    """Pannello inferiore con la lista dei trasferimenti."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._jobs: list[TransferJob] = []
        self._init_ui()

    def _init_ui(self):
        hdr = Gtk.Label(label="  📋  Coda trasferimenti")
        hdr.set_xalign(0.0)
        hdr.get_style_context().add_class("section-header")
        self.pack_start(hdr, False, False, 0)

        # Store: icona, op, src, dst, trasferito, velocità, pct(int)
        self._store = Gtk.ListStore(str, str, str, str, str, str, int)
        self._view  = Gtk.TreeView(model=self._store)
        self._view.set_headers_visible(True)

        headers = ["", "Op.", "Sorgente", "Destinazione", "Trasferito", "Velocità"]
        widths  = [24,  60,    0,           0,              80,           100]
        expand  = [False, False, True, True, False, False]

        for i, (h, w, ex) in enumerate(zip(headers, widths, expand)):
            cell = Gtk.CellRendererText()
            cell.set_property("ellipsize", Pango.EllipsizeMode.END)
            col = Gtk.TreeViewColumn(h, cell, text=i)
            col.set_resizable(True)
            col.set_expand(ex)
            if w:
                col.set_min_width(w)
            self._view.append_column(col)

        # Colonna progress bar
        cell_pb = Gtk.CellRendererProgress()
        col_pb  = Gtk.TreeViewColumn("%", cell_pb, value=6)
        col_pb.set_min_width(80)
        self._view.append_column(col_pb)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(110)
        scroll.set_max_content_height(130)
        scroll.add(self._view)
        self.pack_start(scroll, False, False, 0)

    def aggiungi_job(self, job: TransferJob) -> int:
        self._jobs.append(job)
        icona = "⬆" if job.op == "upload" else "⬇"
        self._store.append([icona, job.op.capitalize(),
                            job.src, job.dst, "—", "In attesa", 0])
        return len(self._jobs) - 1

    def aggiorna_progress(self, idx: int, tx: int, tot: int):
        if idx >= len(self._store):
            return
        pct = int(tx * 100 / tot) if tot > 0 else 0
        it  = self._store.get_iter(idx)
        job = self._jobs[idx] if idx < len(self._jobs) else None
        self._store.set_value(it, 4, _fmt_size(tx))
        self._store.set_value(it, 6, pct)
        if job and job.velocita > 0:
            eta = int((tot - tx) / job.velocita) if tot > tx else 0
            vel = f"{_fmt_size(job.velocita)}/s  ETA {eta}s"
            self._store.set_value(it, 5, vel)

    def segna_completato(self, idx: int, ok: bool, msg: str):
        if idx >= len(self._store):
            return
        it = self._store.get_iter(idx)
        self._store.set_value(it, 5, "✓ OK" if ok else f"✖ {msg}")
        self._store.set_value(it, 6, 100 if ok else 0)


# ---------------------------------------------------------------------------
# WinScpWidget — widget principale dual-pane
# ---------------------------------------------------------------------------

class WinScpWidget(Gtk.Box):
    """
    Browser SFTP dual-pane stile WinSCP (GTK3).
    Riceve un profilo sessione SSH e apre la connessione SFTP.
    """

    def __init__(self, profilo: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._profilo = profilo
        self._sftp    = None
        self._ssh     = None
        self._worker_thread = None

        self._init_ui()

        if PARAMIKO_OK:
            threading.Thread(target=self._connetti, daemon=True).start()
        else:
            GLib.idle_add(self._mostra_errore_init, "paramiko non installato.\npip install paramiko")

    def _init_ui(self):
        # --- Toolbar ---
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_margin_start(8)
        tb.set_margin_end(8)
        tb.set_margin_top(6)
        tb.set_margin_bottom(6)
        self.pack_start(tb, False, False, 0)

        for label, tip, cb in [
            ("⬆ Upload",   "Carica locale→remoto", self._upload_selezione),
            ("⬇ Download", "Scarica remoto→locale", self._download_selezione),
            ("🗑 Elimina",  "Elimina selezione",    self._elimina_selezione),
            ("↺ Aggiorna", "Aggiorna entrambi",    self._aggiorna_tutto),
        ]:
            btn = Gtk.Button(label=label)
            btn.set_tooltip_text(tip)
            btn.connect("clicked", lambda b, c=cb: c())
            tb.pack_start(btn, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 0)

        # --- Pannello caricamento (mostrato finché SFTP non è pronto) ---
        self._loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._loading_box.set_halign(Gtk.Align.CENTER)
        self._loading_box.set_valign(Gtk.Align.CENTER)
        self._loading_lbl = Gtk.Label(label="Connessione in corso…")
        self._loading_spinner = Gtk.Spinner()
        self._loading_spinner.start()
        self._loading_box.pack_start(self._loading_spinner, False, False, 0)
        self._loading_box.pack_start(self._loading_lbl, False, False, 0)
        self.pack_start(self._loading_box, True, True, 0)

        # --- Dual-pane (nascosto finché non connesso) ---
        self._dual_pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._local_panel  = LocalPanel()
        self._remote_panel = None  # creato dopo connessione

        self._dual_pane.pack1(self._local_panel, True, True)
        self._dual_pane.set_no_show_all(True)

        self.pack_start(self._dual_pane, True, True, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep2, False, False, 0)

        # --- Coda trasferimenti ---
        self._coda = CodaWidget()
        self.pack_start(self._coda, False, False, 0)

    # ------------------------------------------------------------------
    # Connessione SFTP
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

            kw = {"hostname": host, "port": port, "username": user, "timeout": 15}
            if pkey and os.path.isfile(pkey):
                kw["key_filename"] = pkey
            elif pwd:
                kw["password"] = pwd

            self._ssh.connect(**kw)
            self._sftp = self._ssh.open_sftp()

            GLib.idle_add(self._on_connesso)
        except Exception as e:
            GLib.idle_add(self._mostra_errore_init, str(e))

    def _on_connesso(self):
        """Chiamato sul thread principale dopo connessione riuscita."""
        self._remote_panel = RemotePanel(self._sftp)
        self._dual_pane.pack2(self._remote_panel, True, True)
        self._dual_pane.set_position(500)

        self._loading_box.hide()
        self._loading_spinner.stop()

        self._dual_pane.set_no_show_all(False)
        self._dual_pane.show_all()

    def _mostra_errore_init(self, msg: str):
        self._loading_spinner.stop()
        self._loading_lbl.set_text(f"✖ Errore connessione:\n{msg}")

    # ------------------------------------------------------------------
    # Operazioni toolbar
    # ------------------------------------------------------------------

    def _upload_selezione(self):
        if not self._sftp or not self._remote_panel:
            return
        sel = self._local_panel.selezione()
        if not sel:
            return
        jobs = []
        for v in sel:
            rpath = self._remote_panel.path.rstrip("/") + "/" + v["nome"]
            if v["is_dir"]:
                jobs += self._jobs_upload_dir(v["path"], rpath)
            else:
                jobs.append(TransferJob("upload", v["path"], rpath,
                                        size=v["size"], nome=v["nome"]))
        self._esegui_jobs(jobs)

    def _download_selezione(self):
        if not self._sftp or not self._remote_panel:
            return
        sel = self._remote_panel.selezione()
        if not sel:
            return
        jobs = []
        for v in sel:
            lpath = os.path.join(self._local_panel.path, v["nome"])
            if not v["is_dir"]:
                jobs.append(TransferJob("download", v["path"], lpath,
                                        size=v["size"], nome=v["nome"]))
        self._esegui_jobs(jobs)

    def _elimina_selezione(self):
        """Elimina la selezione nel pannello attivo (tenta remoto, poi locale)."""
        if self._remote_panel:
            sel = self._remote_panel.selezione()
            if sel:
                self._remote_panel._elimina(sel)
                return
        sel = self._local_panel.selezione()
        if sel:
            self._local_panel._elimina(sel)

    def _aggiorna_tutto(self):
        self._local_panel.aggiorna()
        if self._remote_panel:
            self._remote_panel.aggiorna()

    # ------------------------------------------------------------------
    # Esecuzione job in thread
    # ------------------------------------------------------------------

    def _jobs_upload_dir(self, local_dir: str, remote_dir: str) -> list:
        """Espande una cartella locale in lista di TransferJob ricorsivi."""
        jobs = []
        try:
            self._sftp.mkdir(remote_dir)
        except Exception:
            pass
        for entry in os.scandir(local_dir):
            rp = remote_dir.rstrip("/") + "/" + entry.name
            if entry.is_dir(follow_symlinks=False):
                jobs += self._jobs_upload_dir(entry.path, rp)
            else:
                sz = entry.stat().st_size
                jobs.append(TransferJob("upload", entry.path, rp,
                                        size=sz, nome=entry.name))
        return jobs

    def _esegui_jobs(self, jobs: list):
        if not jobs:
            return
        idxs = [self._coda.aggiungi_job(j) for j in jobs]

        def run():
            for job, idx in zip(jobs, idxs):
                job.stato = "In corso"
                job.t_inizio = time.time()
                try:
                    def cb(tx, tot, j=job, i=idx):
                        j.trasferito = tx
                        dt = time.time() - j.t_inizio
                        j.velocita = int(tx / dt) if dt > 0 else 0
                        GLib.idle_add(self._coda.aggiorna_progress, i, tx, tot or j.size)

                    if job.op == "download":
                        self._sftp.get(job.src, job.dst, callback=cb)
                    else:
                        self._sftp.put(job.src, job.dst, callback=cb)

                    job.stato = "Completato"
                    GLib.idle_add(self._coda.segna_completato, idx, True, "")
                except Exception as e:
                    job.stato = "Errore"
                    job.errore = str(e)
                    GLib.idle_add(self._coda.segna_completato, idx, False, str(e))

            # Aggiorna pannelli dopo tutti i job
            GLib.idle_add(self._aggiorna_tutto)

        self._worker_thread = threading.Thread(target=run, daemon=True)
        self._worker_thread.start()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def chiudi_processo(self):
        if self._sftp:
            try: self._sftp.close()
            except Exception: pass
        if self._ssh:
            try: self._ssh.close()
            except Exception: pass


# ---------------------------------------------------------------------------
# FtpWinScpWidget — variante FTP (solo browser locale + connessione FTP)
# ---------------------------------------------------------------------------

class FtpWinScpWidget(Gtk.Box):
    """
    Browser FTP semplificato. Usa ftplib della stdlib.
    Layout: pannello locale | pannello remoto FTP.
    """

    def __init__(self, profilo: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._profilo = profilo
        self._ftp     = None
        self._cwd     = "/"

        self._init_ui()
        threading.Thread(target=self._connetti, daemon=True).start()

    def _init_ui(self):
        lbl = Gtk.Label(label="  📂  Browser FTP")
        lbl.set_xalign(0.0)
        lbl.get_style_context().add_class("section-header")
        self.pack_start(lbl, False, False, 0)

        self._status = Gtk.Label(label="Connessione FTP in corso…")
        self._status.set_margin_start(12)
        self._status.set_margin_top(20)
        self.pack_start(self._status, True, True, 0)

    def _connetti(self):
        import ftplib
        host = self._profilo.get("host", "")
        port = int(self._profilo.get("port", 21))
        user = self._profilo.get("user", "anonymous")
        pwd  = self._profilo.get("password", "")
        tls  = self._profilo.get("ftp_tls", False)

        try:
            if tls:
                self._ftp = ftplib.FTP_TLS()
            else:
                self._ftp = ftplib.FTP()
            self._ftp.connect(host, port, timeout=15)
            self._ftp.login(user, pwd)
            if tls:
                self._ftp.prot_p()
            GLib.idle_add(self._on_connesso)
        except Exception as e:
            GLib.idle_add(lambda: self._status.set_text(f"✖ Errore FTP: {e}"))

    def _on_connesso(self):
        self._status.set_text(f"✓ Connesso a {self._profilo.get('host','')} (FTP)")

    def chiudi_processo(self):
        if self._ftp:
            try: self._ftp.quit()
            except Exception: pass


# ---------------------------------------------------------------------------
# apri_sessione_winscp / apri_sessione_ftp — factory per PCM.py
# ---------------------------------------------------------------------------

def apri_sessione_winscp(profilo: dict) -> WinScpWidget:
    return WinScpWidget(profilo)


def apri_sessione_ftp(profilo: dict) -> FtpWinScpWidget:
    return FtpWinScpWidget(profilo)
