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
from gi.repository import Gtk, GLib, GdkPixbuf, Pango, GObject

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False

from translations import t


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

CHUNK_SIZE = 32768  # 32 KB per chunk — permette controllo pausa/annulla

class TransferJob:
    def __init__(self, op, src, dst, size=0, nome=""):
        self.op         = op        # 'upload' | 'download'
        self.src        = src
        self.dst        = dst
        self.size       = size
        self.nome       = nome or os.path.basename(src)
        self.trasferito = 0
        self.stato      = t("winscp.status_wait")
        self.errore     = ""
        self.velocita   = 0
        self.t_inizio   = 0.0
        self.annulla    = False     # flag: interrompi trasferimento in corso


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
        for btn, tip in [(self.btn_su, t("winscp.tooltip_up")), (self.btn_home, t("winscp.tooltip_home")), (self.btn_ref, t("winscp.tooltip_refresh"))]:
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
        self._store = Gtk.ListStore(str, str, str, str, str, str, bool, str, GObject.TYPE_INT64)
        self._sorted = Gtk.TreeModelSort(model=self._store)
        self._view = Gtk.TreeView(model=self._sorted)
        self._view.set_headers_visible(True)
        self._view.set_headers_clickable(True)
        self._view.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        col_defs = [
            (t("winscp.col_name"),  C_NOME_D, True),
            (t("winscp.col_ext"),      C_EXT,    False),
            (t("winscp.col_size"),     C_SIZE,   False),
            (t("winscp.col_modified"), C_MTIME,  False),
            (t("winscp.col_attrs"),    C_ATTR,   False),
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
        dlg.add_buttons(t("sd.cancel"), Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
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
            _mi(t("winscp.ctx_ul_remote").format(n=len(sel)),
                lambda: ws._upload_selezione() if ws else None)
            _mi(t("winscp.queue_add").format(n=len(sel)),
                lambda: ws._accoda_upload(sel) if ws else None)
        menu.append(Gtk.SeparatorMenuItem())
        _mi(t("winscp.new_folder"), self._nuova_cartella)
        if sel and not sel[0]["is_dir"]:
            _mi(t("winscp.ctx_delete"), lambda: self._elimina(sel))
        menu.append(Gtk.SeparatorMenuItem())
        _mi(t("winscp.ctx_refresh"), self.aggiorna)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _nuova_cartella(self):
        nome = self._chiedi_nome(t("winscp.new_folder"))
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
            _mi(t("winscp.ctx_dl_local").format(n=len(sel)),
                lambda: ws._download_selezione() if ws else None)
            _mi(t("winscp.queue_add").format(n=len(sel)),
                lambda: ws._accoda_download(sel) if ws else None)
        menu.append(Gtk.SeparatorMenuItem())
        _mi(t("winscp.new_folder"), self._nuova_cartella)
        if sel:
            _mi(t("winscp.rename"), lambda: self._rinomina(sel[0]))
            _mi(t("winscp.ctx_delete"),  lambda: self._elimina(sel))
        menu.append(Gtk.SeparatorMenuItem())
        _mi(t("winscp.ctx_refresh"), self.aggiorna)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _nuova_cartella(self):
        nome = self._chiedi_nome(t("winscp.new_folder_remote"))
        if nome:
            try:
                self._sftp.mkdir(self.path.rstrip("/") + "/" + nome)
                self.aggiorna()
            except Exception as e:
                self._errore_ui(str(e))

    def _rinomina(self, v: dict):
        nuovo = self._chiedi_nome(t("winscp.rename"), default=v["nome"])
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
        # Header + toolbar coda
        hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hdr_box.set_margin_start(4); hdr_box.set_margin_end(4)
        hdr_box.set_margin_top(2);   hdr_box.set_margin_bottom(2)

        hdr = Gtk.Label(label=f"  {t('winscp.queue_title')}")
        hdr.set_xalign(0.0)
        hdr.get_style_context().add_class("section-header")
        hdr.set_hexpand(True)
        hdr_box.pack_start(hdr, True, True, 0)

        self._btn_pausa = Gtk.Button(label=t("winscp.btn_pause"))
        self._btn_pausa.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_pausa.set_tooltip_text(t("winscp.transfer_running"))
        self._btn_pausa.connect("clicked", self._on_pausa_riprendi)
        hdr_box.pack_start(self._btn_pausa, False, False, 0)

        btn_annulla = Gtk.Button(label=t("winscp.btn_cancel"))
        btn_annulla.set_relief(Gtk.ReliefStyle.NONE)
        btn_annulla.set_tooltip_text(t("winscp.tooltip_cancel_all"))
        btn_annulla.connect("clicked", self._on_annulla)
        hdr_box.pack_start(btn_annulla, False, False, 0)

        btn_pulisci = Gtk.Button(label=t("winscp.btn_clear"))
        btn_pulisci.set_relief(Gtk.ReliefStyle.NONE)
        btn_pulisci.set_tooltip_text(t("winscp.tooltip_clear_queue"))
        btn_pulisci.connect("clicked", self._on_pulisci)
        hdr_box.pack_start(btn_pulisci, False, False, 0)

        self.pack_start(hdr_box, False, False, 0)
        self._in_pausa = False

        # Store: icona, op, src, dst, trasferito, velocità, pct(int)
        self._store = Gtk.ListStore(str, str, str, str, str, str, int)
        self._view  = Gtk.TreeView(model=self._store)
        self._view.set_headers_visible(True)

        headers = ["", t("winscp.col_op"), t("winscp.col_src"), t("winscp.col_dst"), t("winscp.col_transferred"), t("winscp.col_speed")]
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
        col_pb  = Gtk.TreeViewColumn(t("winscp.col_pct"), cell_pb, value=6)
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
                            job.src, job.dst, "—", t("winscp.status_wait_lbl"), 0])
        return len(self._jobs) - 1

    def aggiorna_progress(self, idx: int, tx: int, tot: int):
        if idx >= len(self._store):
            return
        pct = int(tx * 100 / tot) if tot > 0 else 0
        it  = self._store.get_iter_from_string(str(idx))
        if it is None:
            return
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
        it = self._store.get_iter_from_string(str(idx))
        if it is None:
            return
        self._store.set_value(it, 5, "✓ OK" if ok else f"✖ {msg}")
        self._store.set_value(it, 6, 100 if ok else 0)


    def _on_pausa_riprendi(self, btn):
        self._in_pausa = not self._in_pausa
        self._btn_pausa.set_label(t("winscp.btn_resume") if self._in_pausa else t("winscp.btn_pause"))

    def _on_annulla(self, btn):
        """Annulla il job in corso e tutti quelli in attesa."""
        stato_in_corso  = t("winscp.status_running")
        stato_in_attesa = t("winscp.status_wait")
        stato_annullato = t("winscp.status_cancelled")
        for i, job in enumerate(self._jobs):
            if job.stato in (stato_in_corso, stato_in_attesa):
                job.annulla = True
                job.stato   = stato_annullato
                it = self._store.get_iter_from_string(str(i))
                if it:
                    self._store.set_value(it, 5, f"✖ {stato_annullato}")

    def _on_pulisci(self, btn):
        """Rimuove dalla coda tutti i job non in esecuzione (completati, errore, annullati, in attesa)."""
        stato_running = t("winscp.status_running")
        to_remove = [i for i, job in enumerate(self._jobs)
                     if job.stato != stato_running]
        for i in reversed(to_remove):
            it = self._store.get_iter_from_string(str(i))
            if it:
                self._store.remove(it)
            self._jobs.pop(i)

    def is_in_pausa(self) -> bool:
        return self._in_pausa


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
        self._sftp_transfer = None  # Connessione SFTP separata per i trasferimenti
        self._ssh     = None
        self._ssh_transfer = None   # Connessione SSH separata per i trasferimenti
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
            (t("winscp.btn_upload"),        t("winscp.tooltip_upload"),        self._upload_selezione),
            (t("winscp.btn_download"),      t("winscp.tooltip_download"),      self._download_selezione),
            (t("winscp.tooltip_btn_start"), t("winscp.tooltip_start_all"),     self._avvia_coda),
            (t("winscp.btn_delete"),        t("winscp.tooltip_delete"),        self._elimina_selezione),
            (t("winscp.btn_refresh"),       t("winscp.tooltip_refresh_both"),  self._aggiorna_tutto),
            (t("winscp.btn_clear"),         t("winscp.tooltip_clear_queue"),   self._pulisci_coda),
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
        self._loading_lbl = Gtk.Label(label=t("winscp.connecting"))
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

            # Connessione principale per navigazione
            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            kw = {"hostname": host, "port": port, "username": user, "timeout": 15}
            if pkey and os.path.isfile(pkey):
                kw["key_filename"] = pkey
            elif pwd:
                kw["password"] = pwd

            self._ssh.connect(**kw)
            self._sftp = self._ssh.open_sftp()

            # Connessione separata per trasferimenti
            self._ssh_transfer = paramiko.SSHClient()
            self._ssh_transfer.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh_transfer.connect(**kw)
            self._sftp_transfer = self._ssh_transfer.open_sftp()

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

    def _accoda_download(self, sel: list):
        """Aggiunge i file selezionati dal pannello remoto alla coda senza avviarli."""
        if not self._sftp or not self._remote_panel:
            return
        n = 0
        for v in sel:
            if not v["is_dir"]:
                lpath = os.path.join(self._local_panel.path, v["nome"])
                self._coda.aggiungi_in_attesa(
                    TransferJob("download", v["path"], lpath,
                                size=v["size"], nome=v["nome"]))
                n += 1

    def _accoda_upload(self, sel: list):
        """Aggiunge i file selezionati dal pannello locale alla coda senza avviarli."""
        if not self._sftp or not self._remote_panel:
            return
        n = 0
        for v in sel:
            if not v["is_dir"]:
                rpath = self._remote_panel.path.rstrip("/") + "/" + v["nome"]
                self._coda.aggiungi_in_attesa(
                    TransferJob("upload", v["path"], rpath,
                                size=v["size"], nome=v["nome"]))
                n += 1

    def _avvia_coda(self):
        """Avvia tutti i job in attesa nella coda (chiamato dal pulsante ▶)."""
        self._avvia_coda_se_idle()

    def _pulisci_coda(self):
        self._coda.pulisci()

    def _avvia_coda_se_idle(self):
        """Avvia il worker solo se non è già in esecuzione."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        stato_attesa = t("winscp.status_wait")
        jobs_in_attesa = [(i, j) for i, j in enumerate(self._coda._jobs)
                          if j.stato == stato_attesa]
        if not jobs_in_attesa:
            return

        def run():
            _annullato = t("winscp.status_cancelled")
            for idx, job in jobs_in_attesa:
                while self._coda.is_in_pausa():
                    time.sleep(0.3)
                if job.annulla or job.stato == _annullato:
                    continue
                job.stato = t("winscp.status_running")
                job.t_inizio = time.time()
                try:
                    self._trasferisci_chunk(job, idx)
                    if job.annulla:
                        job.stato = _annullato
                        GLib.idle_add(self._coda.segna_completato, idx, False, _annullato)
                    else:
                        job.stato = t("winscp.status_done")
                        GLib.idle_add(self._coda.segna_completato, idx, True, "")
                except Exception as e:
                    job.stato = t("winscp.status_err")
                    job.errore = str(e)
                    GLib.idle_add(self._coda.segna_completato, idx, False, str(e))

            GLib.idle_add(self._aggiorna_tutto)

        self._worker_thread = threading.Thread(target=run, daemon=True)
        self._worker_thread.start()

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
            _annullato = t("winscp.status_cancelled")
            for job, idx in zip(jobs, idxs):
                while self._coda.is_in_pausa():
                    time.sleep(0.3)
                if job.annulla or job.stato == _annullato:
                    continue
                job.stato = t("winscp.status_running")
                job.t_inizio = time.time()
                try:
                    self._trasferisci_chunk(job, idx)
                    if job.annulla:
                        job.stato = _annullato
                        GLib.idle_add(self._coda.segna_completato, idx, False, _annullato)
                    else:
                        job.stato = t("winscp.status_done")
                        GLib.idle_add(self._coda.segna_completato, idx, True, "")
                except Exception as e:
                    job.stato = t("winscp.status_err")
                    job.errore = str(e)
                    GLib.idle_add(self._coda.segna_completato, idx, False, str(e))

            GLib.idle_add(self._aggiorna_tutto)

        self._worker_thread = threading.Thread(target=run, daemon=True)
        self._worker_thread.start()

    # ------------------------------------------------------------------
    # Trasferimento a chunk (permette pausa/annulla)
    # ------------------------------------------------------------------

    def _trasferisci_chunk(self, job: TransferJob, idx: int):
        """
        Trasferisce un file a chunk di CHUNK_SIZE byte.
        Controlla job.annulla e _coda.is_in_pausa() ad ogni chunk,
        permettendo interruzione e pausa reali durante il trasferimento.
        Usa la connessione SFTP separata per i trasferimenti.
        """
        if job.op == "download":
            remote_f = self._sftp_transfer.open(job.src, "rb")
            try:
                with open(job.dst, "wb") as local_f:
                    tx = 0
                    while True:
                        # Pausa: aspetta senza consumare CPU
                        while self._coda.is_in_pausa():
                            time.sleep(0.3)
                        if job.annulla:
                            return
                        chunk = remote_f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        local_f.write(chunk)
                        tx += len(chunk)
                        job.trasferito = tx
                        dt = time.time() - job.t_inizio
                        job.velocita = int(tx / dt) if dt > 0 else 0
                        GLib.idle_add(self._coda.aggiorna_progress, idx, tx, job.size or tx)
            finally:
                remote_f.close()
        else:  # upload
            size = os.path.getsize(job.src)
            if not job.size:
                job.size = size
            with open(job.src, "rb") as local_f:
                remote_f = self._sftp_transfer.open(job.dst, "wb")
                try:
                    tx = 0
                    while True:
                        while self._coda.is_in_pausa():
                            time.sleep(0.3)
                        if job.annulla:
                            return
                        chunk = local_f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        remote_f.write(chunk)
                        tx += len(chunk)
                        job.trasferito = tx
                        dt = time.time() - job.t_inizio
                        job.velocita = int(tx / dt) if dt > 0 else 0
                        GLib.idle_add(self._coda.aggiorna_progress, idx, tx, job.size or tx)
                finally:
                    remote_f.close()

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
# FTP — importazioni (stdlib)
# ---------------------------------------------------------------------------

import ftplib

# ---------------------------------------------------------------------------
# CodaWidget — metodi aggiuntivi per FTP (in-attesa, pulisci)
# ---------------------------------------------------------------------------
# Estendiamo CodaWidget aggiungendo i metodi che servono al flusso FTP
# dove i job vengono prima accodati come "in attesa" e poi avviati
# tutti insieme da _avvia_coda().

def _coda_aggiungi_in_attesa(self, job: TransferJob) -> int:
    """Aggiunge un job come «in attesa» (non ancora avviato). Ritorna idx."""
    self._jobs.append(job)
    icona = "⬆" if job.op == "upload" else "⬇"
    self._store.append([icona, job.op.capitalize(),
                        job.src, job.dst, "—", t("winscp.status_wait_lbl"), 0])
    return len(self._jobs) - 1


def _coda_prendi_jobs_in_attesa(self) -> list:
    """Restituisce la lista di (idx, job) in stato 'In attesa' e la svuota
    impostando lo stato a 'In corso' (così non vengono riletti)."""
    result = []
    for i, job in enumerate(self._jobs):
        if job.stato == t("winscp.status_wait"):
            result.append((i, job))
    return result


def _coda_n_in_attesa(self) -> int:
    return sum(1 for j in self._jobs if j.stato == t("winscp.status_wait"))


def _coda_pulisci(self):
    """Rimuove dalla coda tutti i job non in esecuzione."""
    stato_running = t("winscp.status_running")
    to_remove = [i for i, j in enumerate(self._jobs) if j.stato != stato_running]
    for i in reversed(to_remove):
        it = self._store.get_iter_from_string(str(i))
        if it:
            self._store.remove(it)
        self._jobs.pop(i)


# Patching dinamico su CodaWidget (evita modificare la classe originale)
CodaWidget.aggiungi_in_attesa    = _coda_aggiungi_in_attesa
CodaWidget.prendi_jobs_in_attesa = _coda_prendi_jobs_in_attesa
CodaWidget.n_in_attesa           = _coda_n_in_attesa
CodaWidget.pulisci               = _coda_pulisci


# ---------------------------------------------------------------------------
# FtpTransferWorker — thread trasferimenti FTP
# ---------------------------------------------------------------------------

class FtpTransferWorker(threading.Thread):
    """
    Worker thread per trasferimenti FTP.
    Usa GLib.idle_add per tutti gli update UI — nessun segnale GObject.
    """

    def __init__(self, ftp_factory, callback_progress, callback_done, callback_tutti_finiti):
        super().__init__(daemon=True)
        self._ftp_factory           = ftp_factory
        self._cb_progress           = callback_progress
        self._cb_done               = callback_done
        self._cb_tutti_finiti       = callback_tutti_finiti
        self._jobs: list[tuple]     = []   # lista di (idx, TransferJob)
        self._stop                  = False

    def aggiungi(self, idx: int, job: TransferJob):
        self._jobs.append((idx, job))

    def stop(self):
        self._stop = True

    def run(self):
        try:
            ftp = self._ftp_factory()
        except Exception as e:
            GLib.idle_add(self._cb_tutti_finiti)
            return

        _annullato = t("winscp.status_cancelled")
        for idx, job in self._jobs:
            if self._stop or job.annulla:
                GLib.idle_add(self._cb_done, idx, False, _annullato)
                continue

            job.stato    = t("winscp.status_running")
            job.t_inizio = time.time()
            ok  = True
            msg = ""
            try:
                if job.op == "download":
                    self._scarica(ftp, job, idx)
                else:
                    self._carica(ftp, job, idx)

                if job.annulla:
                    ok, msg = False, _annullato
                    job.stato = _annullato
                else:
                    job.stato = t("winscp.status_done")
            except Exception as e:
                ok, msg   = False, str(e)
                job.stato = t("winscp.status_err")
                job.errore = msg

            GLib.idle_add(self._cb_done, idx, ok, msg)

        try:
            ftp.quit()
        except Exception:
            pass

        GLib.idle_add(self._cb_tutti_finiti)

    # ------------------------------------------------------------------
    # Trasferimento chunk-based
    # ------------------------------------------------------------------

    def _scarica(self, ftp: ftplib.FTP, job: TransferJob, idx: int):
        """Download: RETR → file locale, a blocchi di CHUNK_SIZE."""
        os.makedirs(os.path.dirname(job.dst) or ".", exist_ok=True)
        tx = [0]

        def _cb(chunk):
            if self._stop or job.annulla:
                raise ftplib.error_reply("annullato")
            with open(job.dst, "ab") as f:
                f.write(chunk)
            tx[0] += len(chunk)
            job.trasferito = tx[0]
            dt = time.time() - job.t_inizio
            job.velocita = int(tx[0] / dt) if dt > 0 else 0
            GLib.idle_add(self._cb_progress, idx, tx[0], job.size or tx[0])

        # Assicura file vuoto prima di partire
        open(job.dst, "wb").close()
        ftp.retrbinary(f"RETR {job.src}", _cb, blocksize=CHUNK_SIZE)

    def _carica(self, ftp: ftplib.FTP, job: TransferJob, idx: int):
        """Upload: STOR → server FTP, a blocchi di CHUNK_SIZE."""
        size = job.size or os.path.getsize(job.src)
        job.size = size
        tx = [0]

        class _ChunkReader:
            """File-like wrapper che conta i byte e aggiorna il progresso."""
            def __init__(inner_self, fp):
                inner_self._fp = fp

            def read(inner_self, n=-1):
                if self._stop or job.annulla:
                    return b""
                chunk = inner_self._fp.read(n if n > 0 else CHUNK_SIZE)
                if chunk:
                    tx[0] += len(chunk)
                    job.trasferito = tx[0]
                    dt = time.time() - job.t_inizio
                    job.velocita = int(tx[0] / dt) if dt > 0 else 0
                    GLib.idle_add(self._cb_progress, idx, tx[0], size)
                return chunk

        with open(job.src, "rb") as fp:
            ftp.storbinary(f"STOR {job.dst}", _ChunkReader(fp), blocksize=CHUNK_SIZE)


# ---------------------------------------------------------------------------
# FtpRemotePanel — pannello remoto FTP (eredita da FilePanel)
# ---------------------------------------------------------------------------

class FtpRemotePanel(FilePanel):
    """Pannello remoto FTP con navigazione MLSD/LIST/NLST e menu contestuale."""

    def __init__(self, ftp: ftplib.FTP):
        super().__init__("🌐  Remoto FTP")
        self._ftp = ftp
        try:
            home = ftp.pwd()
        except Exception:
            home = "/"
        self.naviga(home)

    # ------------------------------------------------------------------
    # Navigazione
    # ------------------------------------------------------------------

    def naviga(self, path: str):
        self.path = path
        self.path_entry.set_text(path)
        threading.Thread(target=self._list_thread, args=(path,), daemon=True).start()

    def _vai_home(self):
        try:
            home = self._ftp.pwd()
        except Exception:
            home = "/"
        self.naviga(home)

    def _list_thread(self, path: str):
        try:
            voci = self._lista_directory(path)
            GLib.idle_add(self._popola, voci)
        except Exception as e:
            GLib.idle_add(self._status.set_text, f"  ✖ {e}")

    def _lista_directory(self, path: str) -> list:
        """Prova MLSD → LIST raw → NLST. Ritorna lista voci."""
        parent = str(Path(path).parent) if path != "/" else "/"
        voci = [{"nome": "..", "is_dir": True, "path": parent,
                  "size": 0, "mtime": "", "attr": ""}]

        # --- Tentativo 1: MLSD (RFC 3659) ---
        try:
            entries = list(self._ftp.mlsd(path, facts=["type", "size", "modify", "perm"]))
            dirs, files = [], []
            for nome, facts in entries:
                if nome in (".", ".."):
                    continue
                is_dir = facts.get("type", "file").lower() in ("dir", "cdir", "pdir")
                size   = int(facts.get("size", 0) or 0)
                mtime  = ""
                raw_m  = facts.get("modify", "")
                if len(raw_m) >= 12:
                    try:
                        mtime = datetime.strptime(raw_m[:14], "%Y%m%d%H%M%S").strftime("%d.%m.%Y %H:%M:%S")
                    except ValueError:
                        pass
                entry = {
                    "nome":   nome,
                    "is_dir": is_dir,
                    "path":   path.rstrip("/") + "/" + nome,
                    "size":   0 if is_dir else size,
                    "mtime":  mtime,
                    "attr":   facts.get("perm", ""),
                }
                (dirs if is_dir else files).append(entry)
            dirs.sort(key=lambda v: v["nome"].lower())
            files.sort(key=lambda v: v["nome"].lower())
            return voci + dirs + files
        except ftplib.error_perm:
            pass  # server non supporta MLSD
        except Exception:
            pass

        # --- Tentativo 2: LIST raw ---
        try:
            righe = []
            self._ftp.retrlines(f"LIST {path}", righe.append)
            dirs, files = [], []
            for riga in righe:
                v = self._parse_list_line(riga, path)
                if v:
                    (dirs if v["is_dir"] else files).append(v)
            dirs.sort(key=lambda v: v["nome"].lower())
            files.sort(key=lambda v: v["nome"].lower())
            return voci + dirs + files
        except Exception:
            pass

        # --- Tentativo 3: NLST (solo nomi) ---
        try:
            nomi = []
            self._ftp.retrlines(f"NLST {path}", nomi.append)
            entries = []
            for nome in nomi:
                nome = nome.strip().split("/")[-1]
                if nome in (".", ".."):
                    continue
                entries.append({
                    "nome":   nome,
                    "is_dir": False,
                    "path":   path.rstrip("/") + "/" + nome,
                    "size":   0,
                    "mtime":  "",
                    "attr":   "",
                })
            return voci + entries
        except Exception:
            pass

        return voci  # fallback vuoto

    @staticmethod
    def _parse_list_line(riga: str, base_path: str) -> dict | None:
        """
        Parsing robusto di una riga LIST Unix-style.
        Formato: perms link user group size month day time/year name
        Esempio: drwxr-xr-x 2 user group 4096 Jan  1 12:00 dirname
        """
        try:
            riga = riga.encode("latin-1", errors="replace").decode("utf-8", errors="replace")
        except Exception:
            pass

        parts = riga.split(None, 8)
        if len(parts) < 9:
            # Tentativo di parsing semplificato (solo nome)
            nome = riga.strip().split("/")[-1]
            if nome and nome not in (".", ".."):
                return {"nome": nome, "is_dir": False,
                        "path": base_path.rstrip("/") + "/" + nome,
                        "size": 0, "mtime": "", "attr": ""}
            return None

        perms  = parts[0]
        size   = int(parts[4]) if parts[4].isdigit() else 0
        nome   = parts[8].strip()

        # Gestisci symlink (nome -> target)
        if " -> " in nome:
            nome = nome.split(" -> ")[0].strip()
        if nome in (".", "..") or not nome:
            return None

        is_dir = perms.startswith("d")
        mtime  = " ".join(parts[5:8])

        return {
            "nome":   nome,
            "is_dir": is_dir,
            "path":   base_path.rstrip("/") + "/" + nome,
            "size":   0 if is_dir else size,
            "mtime":  mtime,
            "attr":   perms,
        }

    # ------------------------------------------------------------------
    # Menu contestuale
    # ------------------------------------------------------------------

    def _menu_contestuale(self, event):
        sel = self.selezione()
        menu = Gtk.Menu()

        def _mi(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: cb())
            menu.append(mi)

        if sel:
            ws = self._trova_winscp()
            _mi(t("winscp.ctx_dl_local").format(n=len(sel)),
                lambda: ws._download_selezione() if ws else None)
            _mi(t("winscp.queue_add").format(n=len(sel)),
                lambda: ws._accoda_download(sel) if ws else None)
        menu.append(Gtk.SeparatorMenuItem())
        _mi(t("winscp.new_folder"), self._nuova_cartella)
        if sel:
            _mi(t("winscp.rename"), lambda: self._rinomina(sel[0]))
            _mi(t("winscp.ctx_delete"), lambda: self._elimina(sel))
        menu.append(Gtk.SeparatorMenuItem())
        _mi(t("winscp.ctx_refresh"), self.aggiorna)

        menu.show_all()
        menu.popup_at_pointer(event)

    # ------------------------------------------------------------------
    # Operazioni FTP
    # ------------------------------------------------------------------

    def _nuova_cartella(self):
        nome = self._chiedi_nome(t("winscp.new_folder_remote"))
        if nome:
            try:
                self._ftp.mkd(self.path.rstrip("/") + "/" + nome)
                self.aggiorna()
            except Exception as e:
                self._errore_ui(str(e))

    def _rinomina(self, v: dict):
        nuovo = self._chiedi_nome(t("winscp.rename"), default=v["nome"])
        if nuovo and nuovo != v["nome"]:
            try:
                self._ftp.rename(v["path"], self.path.rstrip("/") + "/" + nuovo)
                self.aggiorna()
            except Exception as e:
                self._errore_ui(str(e))

    def _elimina(self, sel: list):
        nomi = ", ".join(v["nome"] for v in sel)
        if self._conferma(f"Eliminare dal remoto: {nomi}?"):
            for v in sel:
                try:
                    if v["is_dir"]:
                        self._rmdir_ricorsivo(v["path"])
                    else:
                        self._ftp.delete(v["path"])
                except Exception as e:
                    self._errore_ui(str(e))
            self.aggiorna()

    def _rmdir_ricorsivo(self, path: str):
        """Elimina ricorsivamente directory via LIST."""
        righe = []
        try:
            self._ftp.retrlines(f"LIST {path}", righe.append)
        except Exception:
            righe = []
        for riga in righe:
            v = self._parse_list_line(riga, path)
            if not v:
                continue
            if v["is_dir"]:
                self._rmdir_ricorsivo(v["path"])
            else:
                try:
                    self._ftp.delete(v["path"])
                except Exception:
                    pass
        try:
            self._ftp.rmd(path)
        except Exception:
            pass

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
# FtpWinScpWidget — widget principale dual-pane FTP
# ---------------------------------------------------------------------------

class FtpWinScpWidget(Gtk.Box):
    """
    Browser FTP dual-pane stile WinSCP (GTK3).
    Usa ftplib della stdlib. Connessione plain FTP o FTPS (ftp_tls=True).
    """

    def __init__(self, profilo: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._profilo      = profilo
        self._ftp          = None       # connessione navigazione
        self._worker       = None       # FtpTransferWorker attivo
        self._remote_panel = None

        self._init_ui()
        threading.Thread(target=self._connetti, daemon=True).start()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        # Toolbar
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_margin_start(8); tb.set_margin_end(8)
        tb.set_margin_top(6);   tb.set_margin_bottom(6)
        self.pack_start(tb, False, False, 0)

        for label, tip, cb in [
            (t("winscp.btn_upload"),      t("winscp.tooltip_upload"),        self._upload_selezione),
            (t("winscp.btn_download"),    t("winscp.tooltip_download"),      self._download_selezione),
            (t("winscp.tooltip_btn_start"), t("winscp.tooltip_start_all"),  self._avvia_coda),
            (t("winscp.btn_new_folder_r"), t("winscp.tooltip_new_folder"),  self._nuova_cartella_remota),
            (t("winscp.btn_delete"),      t("winscp.tooltip_delete"),        self._elimina_selezione),
            (t("winscp.btn_refresh"),     t("winscp.tooltip_refresh_both"),  self._aggiorna_tutto),
            (t("winscp.btn_clear"),       t("winscp.tooltip_clear_queue"),   self._pulisci_coda),
        ]:
            btn = Gtk.Button(label=label)
            btn.set_tooltip_text(tip)
            btn.connect("clicked", lambda b, c=cb: c())
            tb.pack_start(btn, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 0)

        # Spinner caricamento
        self._loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._loading_box.set_halign(Gtk.Align.CENTER)
        self._loading_box.set_valign(Gtk.Align.CENTER)
        self._loading_lbl     = Gtk.Label(label=t("winscp.connecting"))
        self._loading_spinner = Gtk.Spinner()
        self._loading_spinner.start()
        self._loading_box.pack_start(self._loading_spinner, False, False, 0)
        self._loading_box.pack_start(self._loading_lbl,     False, False, 0)
        self.pack_start(self._loading_box, True, True, 0)

        # Dual-pane (nascosto finché non connesso)
        self._dual_pane   = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._local_panel = LocalPanel()
        self._dual_pane.pack1(self._local_panel, True, True)
        self._dual_pane.set_no_show_all(True)
        self.pack_start(self._dual_pane, True, True, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep2, False, False, 0)

        # Coda trasferimenti
        self._coda = CodaWidget()
        self.pack_start(self._coda, False, False, 0)

    # ------------------------------------------------------------------
    # Connessione FTP
    # ------------------------------------------------------------------

    def _ftp_factory(self) -> ftplib.FTP:
        """Crea e restituisce una nuova connessione FTP (per il worker)."""
        host = self._profilo.get("host", "")
        port = int(self._profilo.get("port", 21))
        user = self._profilo.get("user", "anonymous")
        pwd  = self._profilo.get("password", "")
        tls  = self._profilo.get("ftp_tls", False)
        if tls:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, pwd)
        if tls:
            ftp.prot_p()
        return ftp

    def _connetti(self):
        try:
            self._ftp = self._ftp_factory()
            GLib.idle_add(self._on_connesso)
        except Exception as e:
            GLib.idle_add(self._mostra_errore_init, str(e))

    def _on_connesso(self):
        self._remote_panel = FtpRemotePanel(self._ftp)
        self._dual_pane.pack2(self._remote_panel, True, True)
        self._dual_pane.set_position(500)

        self._loading_box.hide()
        self._loading_spinner.stop()

        self._dual_pane.set_no_show_all(False)
        self._dual_pane.show_all()

    def _mostra_errore_init(self, msg: str):
        self._loading_spinner.stop()
        self._loading_lbl.set_text(f"✖ Errore FTP:\n{msg}")

    # ------------------------------------------------------------------
    # Operazioni toolbar
    # ------------------------------------------------------------------

    def _upload_selezione(self):
        if not self._ftp or not self._remote_panel:
            return
        sel = self._local_panel.selezione()
        if not sel:
            return
        jobs = []
        for v in sel:
            rpath = self._remote_panel.path.rstrip("/") + "/" + v["nome"]
            if v["is_dir"]:
                jobs += self._jobs_upload_dir_ftp(v["path"], rpath)
            else:
                jobs.append(TransferJob("upload", v["path"], rpath,
                                        size=v["size"], nome=v["nome"]))
        self._esegui_jobs(jobs)

    def _download_selezione(self):
        if not self._ftp or not self._remote_panel:
            return
        sel = self._remote_panel.selezione()
        if not sel:
            return
        jobs = []
        for v in sel:
            lpath = os.path.join(self._local_panel.path, v["nome"])
            if v["is_dir"]:
                jobs += self._jobs_download_dir_ftp(v["path"], lpath)
            else:
                jobs.append(TransferJob("download", v["path"], lpath,
                                        size=v["size"], nome=v["nome"]))
        self._esegui_jobs(jobs)

    def _accoda_upload(self, sel: list = None):
        """Aggiunge la selezione locale alla coda senza avviare il worker."""
        if not self._ftp or not self._remote_panel:
            return
        if sel is None:
            sel = self._local_panel.selezione()
        for v in sel:
            if not v["is_dir"]:
                rpath = self._remote_panel.path.rstrip("/") + "/" + v["nome"]
                job   = TransferJob("upload", v["path"], rpath,
                                    size=v["size"], nome=v["nome"])
                self._coda.aggiungi_in_attesa(job)

    def _accoda_download(self, sel: list = None):
        """Aggiunge la selezione remota alla coda senza avviare il worker."""
        if not self._ftp or not self._remote_panel:
            return
        if sel is None:
            sel = self._remote_panel.selezione()
        for v in sel:
            if not v["is_dir"]:
                lpath = os.path.join(self._local_panel.path, v["nome"])
                job   = TransferJob("download", v["path"], lpath,
                                    size=v["size"], nome=v["nome"])
                self._coda.aggiungi_in_attesa(job)

    def _avvia_coda(self):
        """Avvia il FtpTransferWorker con i job in attesa."""
        if self._worker and self._worker.is_alive():
            return
        jobs_in_attesa = self._coda.prendi_jobs_in_attesa()
        if not jobs_in_attesa:
            return
        self._worker = FtpTransferWorker(
            ftp_factory           = self._ftp_factory,
            callback_progress     = self._coda.aggiorna_progress,
            callback_done         = self._coda.segna_completato,
            callback_tutti_finiti = self._aggiorna_tutto,
        )
        for idx, job in jobs_in_attesa:
            self._worker.aggiungi(idx, job)
        self._worker.start()

    def _esegui_jobs(self, jobs: list):
        """Aggiunge jobs alla coda e avvia subito il worker."""
        if not jobs:
            return
        for job in jobs:
            self._coda.aggiungi_in_attesa(job)
        self._avvia_coda()

    def _nuova_cartella_remota(self):
        if self._remote_panel:
            self._remote_panel._nuova_cartella()

    def _elimina_selezione(self):
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

    def _pulisci_coda(self):
        self._coda.pulisci()

    # ------------------------------------------------------------------
    # Espansione ricorsiva cartelle
    # ------------------------------------------------------------------

    def _jobs_upload_dir_ftp(self, local_dir: str, remote_dir: str) -> list:
        """Espande una cartella locale in lista di TransferJob per FTP."""
        jobs = []
        try:
            self._ftp.mkd(remote_dir)
        except Exception:
            pass  # directory già esistente
        try:
            for entry in os.scandir(local_dir):
                rp = remote_dir.rstrip("/") + "/" + entry.name
                if entry.is_dir(follow_symlinks=False):
                    jobs += self._jobs_upload_dir_ftp(entry.path, rp)
                else:
                    sz = entry.stat().st_size
                    jobs.append(TransferJob("upload", entry.path, rp,
                                            size=sz, nome=entry.name))
        except (PermissionError, OSError):
            pass
        return jobs

    def _jobs_download_dir_ftp(self, remote_dir: str, local_dir: str) -> list:
        """Espande una cartella remota in lista di TransferJob via LIST."""
        jobs = []
        os.makedirs(local_dir, exist_ok=True)
        righe = []
        try:
            self._ftp.retrlines(f"LIST {remote_dir}", righe.append)
        except Exception:
            return jobs
        for riga in righe:
            v = FtpRemotePanel._parse_list_line(riga, remote_dir)
            if not v:
                continue
            lp = os.path.join(local_dir, v["nome"])
            if v["is_dir"]:
                jobs += self._jobs_download_dir_ftp(v["path"], lp)
            else:
                jobs.append(TransferJob("download", v["path"], lp,
                                        size=v["size"], nome=v["nome"]))
        return jobs

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def chiudi_processo(self):
        if self._worker and self._worker.is_alive():
            self._worker.stop()
        if self._ftp:
            try:
                self._ftp.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# apri_sessione_winscp / apri_sessione_ftp — factory per PCM.py
# ---------------------------------------------------------------------------

def apri_sessione_winscp(profilo: dict) -> WinScpWidget:
    return WinScpWidget(profilo)


def apri_sessione_ftp(profilo: dict) -> FtpWinScpWidget:
    return FtpWinScpWidget(profilo)
