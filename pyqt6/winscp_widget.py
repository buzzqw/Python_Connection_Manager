"""
winscp_widget.py — Finestra SFTP stile WinSCP per PCM.

Layout:
  ┌────────────────────────────────────────────────────────────┐
  │  Toolbar: Upload ▲  Download ▼  Sync  Delete  Properties  │
  ├───────────────────────┬────────────────────────────────────┤
  │  LOCALE               │  REMOTO                            │
  │  path bar + nav       │  path bar + nav                    │
  │  [tabella file]       │  [tabella file]                    │
  ├───────────────────────┴────────────────────────────────────┤
  │  Coda trasferimenti (Operation | Source | Dest | % | ETA)  │
  └────────────────────────────────────────────────────────────┘

Supporta:
  - navigazione locale e remota con doppio clic
  - upload (locale→remoto) e download (remoto→locale) con progress bar
  - trasferimento cartelle ricorsivo
  - coda trasferimenti con thread dedicato
  - rinomina, elimina, nuova cartella, proprietà (remoto)
  - drag & drop tra i due pannelli
  - barra stato con dimensioni selezione
"""

import os
import stat
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QLineEdit,
    QToolButton, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMenu, QMessageBox, QInputDialog, QProgressBar,
    QFrame, QStatusBar, QApplication, QFileDialog, QSizePolicy,
    QToolBar, QStyle
)
from PyQt6.QtCore import (
    Qt, QThread, QObject, pyqtSignal, QTimer, QMimeData, QSize
)
from PyQt6.QtGui import QFont, QColor, QDrag, QKeySequence, QAction

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False

from translations import t


def _fmt_size(n: int) -> str:
    """Formatta dimensione in byte in stringa leggibile."""
    if n is None:
        return ""
    n = int(n)
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n/1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n/1024**2:.1f} MB"
    return f"{n/1024**3:.2f} GB"


# ============================================================================
# Thread di trasferimento
# ============================================================================

class TransferJob:
    """Rappresenta un singolo job di trasferimento."""
    def __init__(self, op, src, dst, size=0, nome=""):
        self.op    = op      # 'upload' | 'download'
        self.src   = src
        self.dst   = dst
        self.size  = size
        self.nome  = nome or os.path.basename(src)
        self.trasferito = 0
        self.stato = t("winscp.status_wait")   # In attesa | In corso | Completato | Errore
        self.errore = ""
        self.velocita = 0
        self.t_inizio = 0.0


class TransferWorker(QObject):
    """Worker che esegue i trasferimenti SFTP in un thread separato."""

    job_iniziato   = pyqtSignal(int)           # indice job
    job_progress   = pyqtSignal(int, int, int) # indice, trasferito, totale
    job_finito     = pyqtSignal(int, bool, str) # indice, ok, msg
    tutti_finiti   = pyqtSignal()

    def __init__(self, sftp):
        super().__init__()
        self._sftp   = sftp
        self._jobs   = []
        self._stop   = False
        self._lock   = threading.Lock()

    def aggiungi(self, job: TransferJob) -> int:
        with self._lock:
            self._jobs.append(job)
            return len(self._jobs) - 1

    def stop(self):
        self._stop = True

    def run(self):
        for idx, job in enumerate(self._jobs):
            if self._stop:
                break
            job.stato   = t("winscp.status_running")
            job.t_inizio = time.time()
            self.job_iniziato.emit(idx)
            try:
                if job.op == "download":
                    self._download(idx, job)
                else:
                    self._upload(idx, job)
                job.stato = t("winscp.status_done")
                self.job_finito.emit(idx, True, "")
            except Exception as e:
                job.stato  = t("winscp.status_err")
                job.errore = str(e)
                self.job_finito.emit(idx, False, str(e))
        self.tutti_finiti.emit()

    def _download(self, idx, job):
        def cb(tx, tot):
            job.trasferito = tx
            dt = time.time() - job.t_inizio
            job.velocita = int(tx / dt) if dt > 0 else 0
            self.job_progress.emit(idx, tx, tot or job.size)
        self._sftp.get(job.src, job.dst, callback=cb)

    def _upload(self, idx, job):
        def cb(tx, tot):
            job.trasferito = tx
            dt = time.time() - job.t_inizio
            job.velocita = int(tx / dt) if dt > 0 else 0
            self.job_progress.emit(idx, tx, tot or job.size)
        self._sftp.put(job.src, job.dst, callback=cb)


# ============================================================================
# Pannello file (locale o remoto)
# ============================================================================

COL_NOME, COL_EXT, COL_SIZE, COL_DATA, COL_ATTR = 0, 1, 2, 3, 4
COLONNE = [t("winscp.col_name"), t("winscp.col_ext"), t("winscp.col_size"), t("winscp.col_modified"), t("winscp.col_attrs")]


class FilePanel(QWidget):
    """
    Singolo pannello file (locale o remoto).
    Emette segnali per navigazione e selezione.
    """

    navigato       = pyqtSignal(str)          # nuovo path
    selezione_cambiata = pyqtSignal(list)     # lista nomi selezionati

    def __init__(self, titolo="Locale", parent=None):
        super().__init__(parent)
        self.titolo    = titolo
        self.path      = ""
        self._voci     = []   # lista di dict con info file
        self._init_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header titolo
        hdr = QLabel(f"  {self.titolo}")
        hdr.setFixedHeight(24)
        hdr.setStyleSheet(
            "background:#f0f0f0; color:#4e7abc; font-weight:bold; "
            "font-size:12px; padding:0 6px; border-bottom:1px solid #ccc;"
        )
        layout.addWidget(hdr)

        # Barra navigazione
        nav = QHBoxLayout()
        nav.setContentsMargins(3, 2, 3, 2)
        nav.setSpacing(2)

        self.btn_su = QToolButton()
        self.btn_su.setText("⬆")
        self.btn_su.setToolTip(t("sftp.parent_folder"))
        self.btn_su.setFixedHeight(22)
        self.btn_su.clicked.connect(self.vai_su)
        self.btn_su.setStyleSheet(self._btn_stile())

        self.btn_home = QToolButton()
        self.btn_home.setText("🏠")
        self.btn_home.setToolTip(t("winscp.tooltip_home"))
        self.btn_home.setFixedHeight(22)
        self.btn_home.clicked.connect(self.vai_home)
        self.btn_home.setStyleSheet(self._btn_stile())

        self.btn_aggiorna = QToolButton()
        self.btn_aggiorna.setText("↺")
        self.btn_aggiorna.setToolTip(t("winscp.tooltip_refresh"))
        self.btn_aggiorna.setFixedHeight(22)
        self.btn_aggiorna.clicked.connect(self.aggiorna)
        self.btn_aggiorna.setStyleSheet(self._btn_stile())

        self.edit_path = QLineEdit()
        self.edit_path.setFixedHeight(22)
        self.edit_path.setStyleSheet(
            "background:#ffffff; color:#4e7abc; font-family:monospace; "
            "font-size:11px; border:1px solid #ccc; padding:0 4px;"
        )
        self.edit_path.returnPressed.connect(
            lambda: self.naviga(self.edit_path.text().strip())
        )

        nav.addWidget(self.btn_su)
        nav.addWidget(self.btn_home)
        nav.addWidget(self.btn_aggiorna)
        nav.addWidget(self.edit_path, 1)
        layout.addLayout(nav)

        # Tabella file
        self.tabella = QTableWidget(0, len(COLONNE))
        self.tabella.setHorizontalHeaderLabels(COLONNE)
        self.tabella.horizontalHeader().setSectionResizeMode(COL_NOME, QHeaderView.ResizeMode.Stretch)
        self.tabella.horizontalHeader().setSectionResizeMode(COL_EXT,  QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(COL_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(COL_DATA, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(COL_ATTR, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.verticalHeader().setDefaultSectionSize(20)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabella.setAlternatingRowColors(True)
        self.tabella.setSortingEnabled(True)
        self.tabella.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; "
            "  gridline-color:#dddddd; border:none; font-size:12px; }"
            "QTableWidget::item { padding:1px 4px; color:#111111; }"
            "QTableWidget::item:selected { background:#4e7abc; color:#ffffff; }"
            "QTableWidget::item:selected:active { background:#4e7abc; color:#ffffff; }"
            "QTableWidget::item:selected:!active { background:#b0c4de; color:#ffffff; }"
            "QTableWidget::item:alternate { background:#f5f5f5; color:#111111; }"
            "QHeaderView::section { background:#e8e8e8; color:#333333; "
            "  border:1px solid #ccc; padding:3px; font-size:11px; }"
        )
        self.tabella.itemDoubleClicked.connect(self._doppio_clic)
        self.tabella.itemSelectionChanged.connect(self._selezione_cambiata)
        self.tabella.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabella.customContextMenuRequested.connect(self._menu_contestuale)

        # Drag & Drop
        self.tabella.setDragEnabled(True)
        self.tabella.setAcceptDrops(True)
        self.tabella.setDropIndicatorShown(True)
        self.tabella.dragEnterEvent   = self._drag_enter
        self.tabella.dragMoveEvent    = self._drag_move
        self.tabella.dropEvent        = self._drop_event

        layout.addWidget(self.tabella, 1)

        # Status bar locale al pannello
        self.lbl_status = QLabel()
        self.lbl_status.setFixedHeight(18)
        self.lbl_status.setStyleSheet(
            "background:#f0f0f0; color:#555555; font-size:10px; padding:0 6px; border-top:1px solid #ccc;"
        )
        layout.addWidget(self.lbl_status)

    # ------------------------------------------------------------------
    # Navigazione (da implementare nelle sottoclassi)
    # ------------------------------------------------------------------

    def naviga(self, path):
        raise NotImplementedError

    def aggiorna(self):
        self.naviga(self.path)

    def vai_su(self):
        parent = str(Path(self.path).parent)
        if parent != self.path:
            self.naviga(parent)

    def vai_home(self):
        self.naviga(os.path.expanduser("~"))

    # ------------------------------------------------------------------
    # Popolamento tabella
    # ------------------------------------------------------------------

    def _popola(self, voci: list):
        """voci: lista di dict {nome, is_dir, size, mtime, attr}"""
        self._voci = voci
        self.tabella.setSortingEnabled(False)
        self.tabella.setRowCount(0)

        for v in voci:
            r = self.tabella.rowCount()
            self.tabella.insertRow(r)
            nome = v["nome"]
            is_dir = v["is_dir"]

            # Colore directory
            col_nome = QTableWidgetItem(("📁 " if is_dir else "📄 ") + nome)
            col_nome.setData(Qt.ItemDataRole.UserRole, v)
            if is_dir:
                # Colore blu solo quando NON selezionato; la selezione usa lo stylesheet
                col_nome.setData(Qt.ItemDataRole.ForegroundRole, QColor("#1a5ca8"))

            ext = "" if is_dir else (Path(nome).suffix.lstrip(".") or "")
            col_ext  = QTableWidgetItem(ext)
            col_size = QTableWidgetItem("" if is_dir else self._fmt_size(v.get("size", 0)))
            col_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            col_data = QTableWidgetItem(v.get("mtime", ""))
            col_attr = QTableWidgetItem(v.get("attr", ""))

            # Dati numerici per sort corretto
            col_size.setData(Qt.ItemDataRole.UserRole + 1, v.get("size", 0))

            self.tabella.setItem(r, COL_NOME, col_nome)
            self.tabella.setItem(r, COL_EXT,  col_ext)
            self.tabella.setItem(r, COL_SIZE, col_size)
            self.tabella.setItem(r, COL_DATA, col_data)
            self.tabella.setItem(r, COL_ATTR, col_attr)

        self.tabella.setSortingEnabled(True)
        self.tabella.sortItems(COL_NOME, Qt.SortOrder.AscendingOrder)
        self._aggiorna_status()

    def _aggiorna_status(self):
        n = self.tabella.rowCount()
        self.lbl_status.setText(
            f"  {n} elementi  |  {self.path}"
        )

    # ------------------------------------------------------------------
    # Selezione
    # ------------------------------------------------------------------

    def selezione(self) -> list:
        """Restituisce lista di dict delle voci selezionate."""
        righe = set(i.row() for i in self.tabella.selectedItems())
        result = []
        for r in sorted(righe):
            item = self.tabella.item(r, COL_NOME)
            if item:
                v = item.data(Qt.ItemDataRole.UserRole)
                if v:
                    result.append(v)
        return result

    def _selezione_cambiata(self):
        self.selezione_cambiata.emit([v["nome"] for v in self.selezione()])

    # ------------------------------------------------------------------
    # Doppio clic
    # ------------------------------------------------------------------

    def _doppio_clic(self, item):
        v = self.tabella.item(item.row(), COL_NOME).data(Qt.ItemDataRole.UserRole)
        if not v:
            return
        if v["nome"] == "..":
            self.vai_su()
        elif v["is_dir"]:
            self.naviga(v["path"])

    # ------------------------------------------------------------------
    # Drag source: avvia drag dalla tabella con lista file selezionati
    # ------------------------------------------------------------------

    def _init_drag_source(self):
        """Attiva il pannello come sorgente drag."""
        self.tabella.setDragEnabled(True)
        self.tabella.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

    def _init_drop_target(self):
        """Attiva il pannello come destinazione drop."""
        self.tabella.setAcceptDrops(True)
        self.tabella.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.tabella.dragEnterEvent = self._drag_enter
        self.tabella.dragMoveEvent  = self._drag_move
        self.tabella.dropEvent      = self._drop_event

    def _start_drag(self):
        """Chiamato da mouseMoveEvent — avvia il drag con la selezione corrente."""
        sel = self.selezione()
        if not sel:
            return
        nomi = "\n".join(v["path"] for v in sel)
        mime = QMimeData()
        mime.setText(f"pcm_files:{self._panel_tipo()}\n{nomi}")
        drag = QDrag(self.tabella)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def _panel_tipo(self) -> str:
        return t("winscp.local_panel")  # override nelle sottoclassi

    # ------------------------------------------------------------------
    # Drag & Drop (overridati nelle sottoclassi)
    # ------------------------------------------------------------------

    def _drag_enter(self, ev):
        if ev.mimeData().hasText() and ev.mimeData().text().startswith("pcm_files:"):
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def _drag_move(self, ev):
        if ev.mimeData().hasText() and ev.mimeData().text().startswith("pcm_files:"):
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def _drop_event(self, ev):
        ev.ignore()   # override nelle sottoclassi

    # ------------------------------------------------------------------
    # Menu contestuale stub
    # ------------------------------------------------------------------

    def _menu_contestuale(self, pos):
        pass

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_size(n: int) -> str:
        if n is None:
            return ""
        if n < 1024:
            return f"{n} B"
        elif n < 1024 ** 2:
            return f"{n/1024:.1f} KB"
        elif n < 1024 ** 3:
            return f"{n/1024**2:.1f} MB"
        return f"{n/1024**3:.2f} GB"

    @staticmethod
    def _btn_stile():
        return (
            "QToolButton { background:transparent; color:#444444; border:none; "
            "font-size:13px; padding:0 3px; }"
            "QToolButton:hover { color:#fff; background:#4e7abc; border-radius:3px; }"
        )


# ============================================================================
# Pannello LOCALE
# ============================================================================

class LocalPanel(FilePanel):

    def __init__(self, parent=None):
        super().__init__("💻  Locale", parent)
        self._init_drag_source()
        self._init_drop_target()
        # Avvia drag su mouseMove con tasto sinistro premuto
        self.tabella.mouseMoveEvent = self._tabella_mouse_move
        self._drag_pos = None
        self.naviga(os.path.expanduser("~"))

    def _panel_tipo(self) -> str:
        return "locale"

    def _tabella_mouse_move(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton:
            if self._drag_pos is None:
                self._drag_pos = ev.pos()
            elif (ev.pos() - self._drag_pos).manhattanLength() > 20:
                self._drag_pos = None
                self._start_drag()
                return
        else:
            self._drag_pos = None
        QAbstractItemView.mouseMoveEvent(self.tabella, ev)

    def _drop_event(self, ev):
        """Drop sul pannello locale = download dal remoto."""
        txt = ev.mimeData().text() if ev.mimeData().hasText() else ""
        if not txt.startswith("pcm_files:remoto"):
            ev.ignore()
            return
        righe = txt.split("\n")[1:]
        paths_remoti = [r for r in righe if r.strip()]
        if paths_remoti:
            winscp = self._trova_winscp()
            if winscp:
                jobs = []
                for rpath in paths_remoti:
                    nome = os.path.basename(rpath)
                    lpath = os.path.join(self.path, nome)
                    jobs.append(TransferJob("download", rpath, lpath, nome=nome))
                winscp._esegui_jobs(jobs)
        ev.acceptProposedAction()

    def _trova_winscp(self):
        p = self.parent()
        while p:
            if hasattr(p, '_esegui_jobs'):
                return p
            p = p.parent() if hasattr(p, 'parent') else None
        return None

    def vai_home(self):
        self.naviga(os.path.expanduser("~"))

    def naviga(self, path: str):
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            return
        self.path = path
        self.edit_path.setText(path)
        voci = [{"nome": "..", "is_dir": True, "path": str(Path(path).parent),
                  "size": 0, "mtime": "", "attr": ""}]
        try:
            # follow_symlinks=False per evitare crash su symlink rotti
            raw = list(os.scandir(path))
        except (PermissionError, OSError):
            raw = []

        # Ordina: cartelle prima, poi file, alfabetico
        raw.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))

        for e in raw:
            try:
                # stat senza seguire symlink per evitare [Errno 2] su link rotti
                st = e.stat(follow_symlinks=False)
                is_dir = e.is_dir(follow_symlinks=False)
                # Se è un symlink valido, segui per la dimensione reale
                if e.is_symlink():
                    try:
                        st_real = e.stat(follow_symlinks=True)
                        is_dir  = os.path.isdir(e.path)
                        size    = 0 if is_dir else st_real.st_size
                        mtime   = datetime.fromtimestamp(st_real.st_mtime).strftime("%d.%m.%Y %H:%M:%S")
                    except OSError:
                        # Symlink rotto: mostra comunque il file con indicatore
                        size  = 0
                        mtime = datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M:%S")
                        e_nome = f"⚠ {e.name}"
                        voci.append({"nome": e_nome, "is_dir": False,
                                     "path": e.path, "size": 0, "mtime": mtime, "attr": "link?"})
                        continue
                else:
                    is_dir = e.is_dir()
                    size   = 0 if is_dir else st.st_size
                    mtime  = datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M:%S")

                voci.append({
                    "nome":   e.name,
                    "is_dir": is_dir,
                    "path":   e.path,
                    "size":   size,
                    "mtime":  mtime,
                    "attr":   self._attrs_locali(e),
                })
            except (PermissionError, OSError):
                voci.append({"nome": e.name, "is_dir": False,
                              "path": e.path, "size": 0, "mtime": "", "attr": "?"})
        self._popola(voci)
        self.navigato.emit(path)

    @staticmethod
    def _attrs_locali(entry) -> str:
        try:
            m = entry.stat().st_mode
            r = "r" if m & 0o444 else "-"
            w = "w" if m & 0o222 else "-"
            x = "x" if m & 0o111 else "-"
            return f"{r}{w}{x}"
        except Exception:
            return ""

    def _menu_contestuale(self, pos):
        sel = self.selezione()
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #ccc; }"
            "QMenu::item:selected { background:#4e7abc; color:#fff; }"
        )
        if sel:
            menu.addAction(f"⬆  Carica su remoto ({len(sel)} elementi)",
                           lambda: self.parent().parent()._upload_selezione())
        menu.addSeparator()
        menu.addAction(t("winscp.new_folder"), self._nuova_cartella_locale)
        if sel and not sel[0]["is_dir"]:
            menu.addAction(t("winscp.ctx_delete"), lambda: self._elimina_locale(sel))
        menu.addSeparator()
        menu.addAction(t("winscp.ctx_refresh"), self.aggiorna)
        menu.exec(self.tabella.mapToGlobal(pos))

    def _nuova_cartella_locale(self):
        nome, ok = QInputDialog.getText(self, t("winscp.new_folder"), t("winscp.field_name"))
        if ok and nome:
            try:
                os.makedirs(os.path.join(self.path, nome), exist_ok=True)
                self.aggiorna()
            except Exception as e:
                QMessageBox.critical(self, "Errore", str(e))

    def _elimina_locale(self, sel):
        nomi = ", ".join(v["nome"] for v in sel)
        if QMessageBox.question(self, t("winscp.dlg_delete"), t("winscp.dlg_delete_confirm").format(names=nomi)) \
                == QMessageBox.StandardButton.Yes:
            for v in sel:
                try:
                    if v["is_dir"]:
                        shutil.rmtree(v["path"])
                    else:
                        os.remove(v["path"])
                except Exception as e:
                    QMessageBox.critical(self, t("winscp.err_generic2"), str(e))
            self.aggiorna()


# ============================================================================
# Pannello REMOTO
# ============================================================================

class RemotePanel(FilePanel):

    def __init__(self, sftp, parent=None):
        super().__init__("🌐  Remoto", parent)
        self._sftp = sftp
        self._init_drag_source()
        self._init_drop_target()
        self.tabella.mouseMoveEvent = self._tabella_mouse_move
        self._drag_pos = None
        try:
            home = sftp.normalize(".")
        except Exception:
            home = "/"
        try:
            self.naviga(home)
        except Exception as e:
            self.lbl_status.setText(t("winscp.err_nav").format(e=e))

    def _panel_tipo(self) -> str:
        return "remoto"

    def _tabella_mouse_move(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton:
            if self._drag_pos is None:
                self._drag_pos = ev.pos()
            elif (ev.pos() - self._drag_pos).manhattanLength() > 20:
                self._drag_pos = None
                self._start_drag()
                return
        else:
            self._drag_pos = None
        QAbstractItemView.mouseMoveEvent(self.tabella, ev)

    def _drop_event(self, ev):
        """Drop sul pannello remoto = upload dal locale."""
        txt = ev.mimeData().text() if ev.mimeData().hasText() else ""
        if not txt.startswith("pcm_files:" + t("winscp.local_panel")):
            ev.ignore()
            return
        righe = txt.split("\n")[1:]
        paths_locali = [r for r in righe if r.strip()]
        if paths_locali:
            winscp = self._trova_winscp()
            if winscp:
                jobs = []
                for lpath in paths_locali:
                    nome = os.path.basename(lpath)
                    rpath = self.path.rstrip("/") + "/" + nome
                    size = os.path.getsize(lpath) if os.path.isfile(lpath) else 0
                    if os.path.isdir(lpath):
                        jobs += winscp._jobs_upload_dir(lpath, rpath)
                    else:
                        jobs.append(TransferJob("upload", lpath, rpath, size=size, nome=nome))
                winscp._esegui_jobs(jobs)
        ev.acceptProposedAction()

    def _trova_winscp(self):
        p = self.parent()
        while p:
            if hasattr(p, '_esegui_jobs'):
                return p
            p = p.parent() if hasattr(p, 'parent') else None
        return None

    def vai_home(self):
        try:
            home = self._sftp.normalize(".")
            self.naviga(home)
        except Exception:
            pass

    def naviga(self, path: str):
        try:
            self._sftp.chdir(path)
            self.path = self._sftp.getcwd() or path
        except Exception:
            self.path = path
        self.edit_path.setText(self.path)

        voci = [{"nome": "..", "is_dir": True,
                  "path": str(Path(self.path).parent), "size": 0, "mtime": "", "attr": ""}]
        try:
            entries = self._sftp.listdir_attr(self.path)
            dirs  = sorted([e for e in entries if stat.S_ISDIR(e.st_mode)],
                            key=lambda e: e.filename.lower())
            files = sorted([e for e in entries if not stat.S_ISDIR(e.st_mode)],
                            key=lambda e: e.filename.lower())
            for e in dirs + files:
                mtime = datetime.fromtimestamp(e.st_mtime).strftime("%d.%m.%Y %H:%M:%S") \
                        if e.st_mtime else ""
                attr = self._fmt_attr(e.st_mode)
                voci.append({
                    "nome":   e.filename,
                    "is_dir": stat.S_ISDIR(e.st_mode),
                    "path":   self.path.rstrip("/") + "/" + e.filename,
                    "size":   e.st_size or 0,
                    "mtime":  mtime,
                    "attr":   attr,
                })
        except Exception as e:
            self.lbl_status.setText(f"  ✖ {e}")
        self._popola(voci)
        self.navigato.emit(self.path)

    @staticmethod
    def _fmt_attr(mode) -> str:
        chars = ""
        for who in [(0o400, 0o200, 0o100), (0o040, 0o020, 0o010), (0o004, 0o002, 0o001)]:
            chars += "r" if mode & who[0] else "-"
            chars += "w" if mode & who[1] else "-"
            chars += "x" if mode & who[2] else "-"
        return chars

    def _menu_contestuale(self, pos):
        sel = self.selezione()
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #ccc; }"
            "QMenu::item:selected { background:#4e7abc; color:#fff; }"
        )
        if sel:
            menu.addAction(t("winscp.ctx_dl_local").format(n=len(sel)),
                           lambda: self.parent().parent()._download_selezione())
        menu.addSeparator()
        menu.addAction(t("winscp.new_folder"), self._nuova_cartella_remota)
        if sel:
            menu.addAction(t("winscp.ctx_rename"), lambda: self._rinomina(sel[0]))
            menu.addAction(t("winscp.ctx_delete"), lambda: self._elimina(sel))
        menu.addSeparator()
        menu.addAction(t("winscp.ctx_refresh"), self.aggiorna)
        menu.exec(self.tabella.mapToGlobal(pos))

    def _nuova_cartella_remota(self):
        nome, ok = QInputDialog.getText(self, t("winscp.new_folder"), t("winscp.field_name"))
        if ok and nome:
            try:
                self._sftp.mkdir(self.path.rstrip("/") + "/" + nome)
                self.aggiorna()
            except Exception as e:
                QMessageBox.critical(self, t("winscp.err_generic2"), str(e))

    def _rinomina(self, v):
        nuovo, ok = QInputDialog.getText(self, t("winscp.rename"), t("winscp.dlg_rename_input"), text=v["nome"])
        if ok and nuovo and nuovo != v["nome"]:
            src = v["path"]
            dst = self.path.rstrip("/") + "/" + nuovo
            try:
                self._sftp.rename(src, dst)
                self.aggiorna()
            except Exception as e:
                QMessageBox.critical(self, t("winscp.err_rename"), str(e))

    def _elimina(self, sel):
        nomi = ", ".join(v["nome"] for v in sel)
        if QMessageBox.question(self, t("winscp.dlg_delete_remote"), t("winscp.dlg_delete_confirm").format(names=nomi)) \
                != QMessageBox.StandardButton.Yes:
            return
        for v in sel:
            try:
                if v["is_dir"]:
                    self._rmdir_ricorsivo(v["path"])
                else:
                    self._sftp.remove(v["path"])
            except Exception as e:
                QMessageBox.critical(self, t("winscp.err_generic2"), str(e))
        self.aggiorna()

    def _rmdir_ricorsivo(self, path):
        for attr in self._sftp.listdir_attr(path):
            fp = path.rstrip("/") + "/" + attr.filename
            if stat.S_ISDIR(attr.st_mode):
                self._rmdir_ricorsivo(fp)
            else:
                self._sftp.remove(fp)
        self._sftp.rmdir(path)


# ============================================================================
# Coda trasferimenti
# ============================================================================

class CodaWidget(QWidget):
    """Tabella in basso con la coda dei trasferimenti."""

    COLONNE = ["", t("winscp.col_operation"), t("winscp.col_src"), t("winscp.col_dst"),
               t("winscp.col_transferred"), t("winscp.col_time_speed"), t("winscp.col_progress")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs = []
        self._jobs_in_attesa: list[TransferJob] = []   # accodati, non ancora avviati
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QLabel(f"  {t('winscp.queue_title')}")
        hdr.setFixedHeight(22)
        hdr.setStyleSheet(
            "background:#f0f0f0; color:#555555; font-size:11px; "
            "padding:0 6px; border-top:1px solid #ccc; border-bottom:1px solid #ccc;"
        )
        layout.addWidget(hdr)

        self.tabella = QTableWidget(0, len(self.COLONNE))
        self.tabella.setHorizontalHeaderLabels(self.COLONNE)
        self.tabella.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabella.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabella.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.verticalHeader().setDefaultSectionSize(20)
        self.tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabella.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#333333; gridline-color:#dddddd; "
            "border:none; font-size:11px; }"
            "QTableWidget::item:selected { background:#4e7abc; color:#fff; }"
            "QHeaderView::section { background:#e8e8e8; color:#333333; "
            "border:1px solid #ccc; padding:2px; font-size:10px; }"
        )
        self.tabella.setMaximumHeight(160)
        layout.addWidget(self.tabella)

    def aggiungi_job(self, job: TransferJob) -> int:
        self._jobs.append(job)
        r = self.tabella.rowCount()
        self.tabella.insertRow(r)
        icona = "⬆" if job.op == "upload" else "⬇"
        self.tabella.setItem(r, 0, QTableWidgetItem(icona))
        self.tabella.setItem(r, 1, QTableWidgetItem(job.op.capitalize()))
        self.tabella.setItem(r, 2, QTableWidgetItem(job.src))
        self.tabella.setItem(r, 3, QTableWidgetItem(job.dst))
        self.tabella.setItem(r, 4, QTableWidgetItem("—"))
        self.tabella.setItem(r, 5, QTableWidgetItem(t("winscp.status_wait_lbl")))

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(True)
        bar.setStyleSheet(
            "QProgressBar { border:1px solid #ccc; border-radius:2px; "
            "background:#f0f0f0; color:#111; text-align:center; font-size:10px; }"
            "QProgressBar::chunk { background:#4e7abc; }"
        )
        self.tabella.setCellWidget(r, 6, bar)
        return r

    def aggiorna_progress(self, idx: int, tx: int, tot: int):
        if idx >= self.tabella.rowCount():
            return
        pct = int(tx * 100 / tot) if tot > 0 else 0
        bar = self.tabella.cellWidget(idx, 6)
        if bar:
            bar.setValue(pct)
        self.tabella.item(idx, 4).setText(_fmt_size(tx))
        job = self._jobs[idx] if idx < len(self._jobs) else None
        if job and job.velocita > 0:
            eta = int((tot - tx) / job.velocita) if tot > tx else 0
            vel = _fmt_size(job.velocita) + "/s"
            self.tabella.item(idx, 5).setText(f"{vel}  ETA {eta}s")

    def segna_completato(self, idx: int, ok: bool, msg: str):
        if idx >= self.tabella.rowCount():
            return
        bar = self.tabella.cellWidget(idx, 6)
        if bar:
            bar.setValue(100 if ok else bar.value())
            if ok:
                bar.setStyleSheet(bar.styleSheet().replace("#4e7abc", "#2d7a2d"))
            else:
                bar.setStyleSheet(bar.styleSheet().replace("#4e7abc", "#7a2d2d"))
        stato = "✔ " + t("winscp.status_done") if ok else f"✖ {msg}"
        self.tabella.item(idx, 5).setText(stato)

    def aggiungi_in_attesa(self, job: TransferJob) -> int:
        """Aggiunge il job alla coda visuale in stato 'In attesa' senza avviarlo."""
        self._jobs_in_attesa.append(job)
        r = self.aggiungi_job(job)
        job._coda_idx = r   # salva indice nel job per recuperarlo in _esegui_jobs
        # Evidenzia in grigio chiaro per distinguerlo da quelli in esecuzione
        for col in range(len(self.COLONNE) - 1):
            item = self.tabella.item(r, col)
            if item:
                item.setForeground(QColor("#888888"))
        return r

    def prendi_jobs_in_attesa(self) -> list:
        """Restituisce e svuota la lista dei job accodati in attesa."""
        jobs = list(self._jobs_in_attesa)
        self._jobs_in_attesa.clear()
        return jobs

    def n_in_attesa(self) -> int:
        return len(self._jobs_in_attesa)

    def pulisci(self):
        self.tabella.setRowCount(0)
        self._jobs.clear()
        self._jobs_in_attesa.clear()


# ============================================================================
# Finestra WinSCP principale
# ============================================================================

class WinScpWidget(QWidget):
    """
    Finestra SFTP completa stile WinSCP.
    Da usare come tab nell'area principale di PCM.
    """

    def __init__(self, ssh_client, sftp_client, host="", user="", parent=None):
        super().__init__(parent)
        self._ssh  = ssh_client
        self._sftp = sftp_client
        self._host = host
        self._user = user
        self._transfer_thread = None
        self._worker = None
        self._job_indices = {}   # job_locale_idx -> riga coda

        self._init_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 1) Pannelli (referenziati dalla toolbar) ----
        self.panel_locale = LocalPanel(self)
        self.panel_remoto = RemotePanel(self._sftp, self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("QSplitter::handle { background:#cccccc; }")
        splitter.addWidget(self.panel_locale)
        splitter.addWidget(self.panel_remoto)
        splitter.setSizes([500, 500])

        # ---- 2) Coda (referenziata dalla toolbar) ----
        self.coda = CodaWidget(self)

        # ---- 3) Status bar (referenziata dalla toolbar) ----
        self.lbl_globale = QLabel(
            f"  🔐  Connesso: {self._user}@{self._host}  (SFTP)"
        )
        self.lbl_globale.setFixedHeight(18)
        self.lbl_globale.setStyleSheet(
            "background:#f0f0f0; color:#4e7abc; font-size:11px; "
            "padding:0 6px; border-top:1px solid #ccc;"
        )

        # ---- 4) Toolbar (per ultima, ora tutti gli attributi esistono) ----
        self._build_toolbar(root)

        # ---- 5) Aggiungi al layout nell'ordine visivo ----
        root.addWidget(splitter, 1)
        root.addWidget(self.coda)
        root.addWidget(self.lbl_globale)

    def _build_toolbar(self, root):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        HOVER_COLOR = "#4e7abc"
        tb.setStyleSheet(
            "QToolBar { background:#e8e8e8; border-bottom:1px solid #ccc; padding:2px; spacing:2px; }"
            f"QToolButton {{ color:#111111; background:transparent; border:1px solid transparent; "
            f"  border-radius:3px; padding:3px 8px; font-size:12px; }}"
            f"QToolButton:hover {{ background:{HOVER_COLOR}; color:#fff; border-color:{HOVER_COLOR}; }}"
            f"QToolButton:pressed {{ background:#2d5a8e; color:#fff; }}"
            f"QToolButton::menu-indicator {{ image: none; }}"
        )

        def _split_btn(label, tooltip_imm, tooltip_coda,
                        slot_imm, slot_coda, shortcut=None):
            """Crea un QToolButton con azione principale + menu 'Aggiungi in coda'."""
            btn = QToolButton()
            btn.setText(label)
            btn.setToolTip(tooltip_imm)
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            btn.clicked.connect(slot_imm)
            if shortcut:
                act = QAction(label, self)
                act.setShortcut(QKeySequence(shortcut))
                act.triggered.connect(slot_imm)
                self.addAction(act)
            menu = QMenu(btn)
            menu.setStyleSheet(
                "QMenu { background:#ffffff; color:#111; border:1px solid #ccc; }"
                f"QMenu::item:selected {{ background:{HOVER_COLOR}; color:#fff; }}"
            )
            act_imm  = menu.addAction(f"{label.strip()}  (esegui subito)")
            act_coda = menu.addAction(f"📋  Aggiungi in coda")
            act_imm.triggered.connect(slot_imm)
            act_coda.triggered.connect(slot_coda)
            btn.setMenu(menu)
            tb.addWidget(btn)
            return btn

        def _a(label, tooltip, slot, shortcut=None):
            a = QAction(label, self)
            a.setToolTip(tooltip)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            tb.addAction(a)
            return a

        _split_btn("⬆  Upload",
                   "Carica subito i file selezionati (locale → remoto)",
                   "Aggiungi upload alla coda senza avviare",
                   self._upload_selezione,
                   self._accoda_upload,
                   "F5")
        _split_btn("⬇  Download",
                   "Scarica subito i file selezionati (remoto → locale)",
                   "Aggiungi download alla coda senza avviare",
                   self._download_selezione,
                   self._accoda_download,
                   "F6")
        tb.addSeparator()
        # Bottone Avvia coda
        self._btn_avvia_coda = QToolButton()
        self._btn_avvia_coda.setText(t("winscp.tooltip_btn_start"))
        self._btn_avvia_coda.setToolTip(t("winscp.tooltip_start_all"))
        self._btn_avvia_coda.setStyleSheet(
            "QToolButton { color:#2d7a2d; font-weight:bold; background:transparent; "
            "border:1px solid #2d7a2d; border-radius:3px; padding:3px 8px; font-size:12px; }"
            "QToolButton:hover { background:#2d7a2d; color:#fff; }"
            "QToolButton:disabled { color:#aaa; border-color:#ccc; }"
        )
        self._btn_avvia_coda.clicked.connect(self._avvia_coda)
        tb.addWidget(self._btn_avvia_coda)
        tb.addSeparator()
        _a(t("winscp.new_folder_remote"), t("winscp.tooltip_new_folder"),
           lambda: self.panel_remoto._nuova_cartella_remota(), "F7")
        _a(t("winscp.ctx_delete"), t("winscp.tooltip_delete_remote"),
           lambda: self.panel_remoto._elimina(self.panel_remoto.selezione()))
        tb.addSeparator()
        _a(t("winscp.ctx_refresh"), t("winscp.tooltip_refresh_both"),
           self._aggiorna_tutto, "F2")
        tb.addSeparator()
        _a(t("winscp.btn_clear"), t("winscp.tooltip_clear_queue"), self.coda.pulisci)

        root.addWidget(tb)

    # ------------------------------------------------------------------
    # Trasferimenti
    # ------------------------------------------------------------------

    def _upload_selezione(self):
        """Carica i file selezionati dal pannello locale al pannello remoto."""
        sel = self.panel_locale.selezione()
        if not sel:
            QMessageBox.information(self, t("winscp.dlg_upload"), t("winscp.no_local_sel"))
            return
        dest_base = self.panel_remoto.path.rstrip("/")
        jobs = []
        for v in sel:
            if v["nome"] == "..":
                continue
            if v["is_dir"]:
                jobs += self._jobs_upload_dir(v["path"], dest_base + "/" + v["nome"])
            else:
                j = TransferJob(
                    op="upload", src=v["path"],
                    dst=dest_base + "/" + v["nome"],
                    size=v.get("size", 0), nome=v["nome"]
                )
                jobs.append(j)
        if jobs:
            self._esegui_jobs(jobs)

    def _download_selezione(self):
        """Scarica i file selezionati dal pannello remoto al pannello locale."""
        sel = self.panel_remoto.selezione()
        if not sel:
            QMessageBox.information(self, t("winscp.dlg_download"), t("winscp.no_remote_sel"))
            return
        dest_base = self.panel_locale.path
        jobs = []
        for v in sel:
            if v["nome"] == "..":
                continue
            if v["is_dir"]:
                jobs += self._jobs_download_dir(v["path"], os.path.join(dest_base, v["nome"]))
            else:
                j = TransferJob(
                    op="download", src=v["path"],
                    dst=os.path.join(dest_base, v["nome"]),
                    size=v.get("size", 0), nome=v["nome"]
                )
                jobs.append(j)
        if jobs:
            self._esegui_jobs(jobs)

    def _jobs_upload_dir(self, local_dir, remote_dir) -> list:
        """Genera jobs ricorsivi per upload di una cartella."""
        try:
            self._sftp.mkdir(remote_dir)
        except Exception:
            pass
        jobs = []
        try:
            for entry in os.scandir(local_dir):
                rpath = remote_dir + "/" + entry.name
                if entry.is_dir():
                    jobs += self._jobs_upload_dir(entry.path, rpath)
                else:
                    jobs.append(TransferJob(
                        op="upload", src=entry.path, dst=rpath,
                        size=entry.stat().st_size, nome=entry.name
                    ))
        except Exception:
            pass
        return jobs

    def _jobs_download_dir(self, remote_dir, local_dir) -> list:
        """Genera jobs ricorsivi per download di una cartella."""
        os.makedirs(local_dir, exist_ok=True)
        jobs = []
        try:
            for attr in self._sftp.listdir_attr(remote_dir):
                rpath = remote_dir.rstrip("/") + "/" + attr.filename
                lpath = os.path.join(local_dir, attr.filename)
                if stat.S_ISDIR(attr.st_mode):
                    jobs += self._jobs_download_dir(rpath, lpath)
                else:
                    jobs.append(TransferJob(
                        op="download", src=rpath, dst=lpath,
                        size=attr.st_size or 0, nome=attr.filename
                    ))
        except Exception:
            pass
        return jobs

    # ------------------------------------------------------------------
    # Accodamento senza avvio immediato
    # ------------------------------------------------------------------

    def _accoda_upload(self):
        """Aggiunge i file selezionati alla coda senza avviarla."""
        sel = self.panel_locale.selezione()
        if not sel:
            QMessageBox.information(self, t("winscp.dlg_queue"), t("winscp.no_local_sel"))
            return
        dest_base = self.panel_remoto.path.rstrip("/")
        jobs = []
        for v in sel:
            if v["nome"] == "..":
                continue
            if v["is_dir"]:
                jobs += self._jobs_upload_dir(v["path"], dest_base + "/" + v["nome"])
            else:
                jobs.append(TransferJob(
                    op="upload", src=v["path"],
                    dst=dest_base + "/" + v["nome"],
                    size=v.get("size", 0), nome=v["nome"]
                ))
        for job in jobs:
            self.coda.aggiungi_in_attesa(job)
        self._set_status(t("winscp.queue_count").format(n=len(jobs), m=self.coda.n_in_attesa()))

    def _accoda_download(self):
        """Aggiunge i file selezionati alla coda senza avviarla."""
        sel = self.panel_remoto.selezione()
        if not sel:
            QMessageBox.information(self, t("winscp.dlg_queue"), t("winscp.no_remote_sel"))
            return
        dest_base = self.panel_locale.path
        jobs = []
        for v in sel:
            if v["nome"] == "..":
                continue
            if v["is_dir"]:
                jobs += self._jobs_download_dir(v["path"], os.path.join(dest_base, v["nome"]))
            else:
                jobs.append(TransferJob(
                    op="download", src=v["path"],
                    dst=os.path.join(dest_base, v["nome"]),
                    size=v.get("size", 0), nome=v["nome"]
                ))
        for job in jobs:
            self.coda.aggiungi_in_attesa(job)
        self._set_status(t("winscp.queue_count").format(n=len(jobs), m=self.coda.n_in_attesa()))

    def _avvia_coda(self):
        """Avvia tutti i job in attesa nella coda."""
        jobs = self.coda.prendi_jobs_in_attesa()
        if not jobs:
            self._set_status(t("winscp.no_jobs"))
            return
        self._esegui_jobs(jobs, dalla_coda=True)

    def _esegui_jobs(self, jobs: list, dalla_coda: bool = False):
        """Aggiunge i jobs alla coda e avvia il thread di trasferimento."""
        if self._transfer_thread and self._transfer_thread.isRunning():
            QMessageBox.warning(self, t("winscp.transfer_running"), t("winscp.transfer_wait"))
            return

        self._worker = TransferWorker(self._sftp)
        idx_map = {}
        for job in jobs:
            job_idx  = self._worker.aggiungi(job)
            # Se viene dalla coda, il job è già nella tabella — non aggiungere di nuovo
            coda_idx = job._coda_idx if (dalla_coda and hasattr(job, "_coda_idx"))                        else self.coda.aggiungi_job(job)
            # Ripristina colore normale (era grigio "in attesa")
            for col in range(len(CodaWidget.COLONNE) - 1):
                item = self.coda.tabella.item(coda_idx, col)
                if item:
                    item.setForeground(QColor("#111111"))
            idx_map[job_idx] = coda_idx

        self._worker.job_progress.connect(
            lambda ji, tx, tot: self.coda.aggiorna_progress(idx_map.get(ji, ji), tx, tot)
        )
        self._worker.job_finito.connect(
            lambda ji, ok, msg: self._job_finito(idx_map.get(ji, ji), ok, msg)
        )
        self._worker.tutti_finiti.connect(self._tutti_finiti)

        self._transfer_thread = QThread()
        self._worker.moveToThread(self._transfer_thread)
        self._transfer_thread.started.connect(self._worker.run)
        self._transfer_thread.start()

        self._set_status(t("winscp.transferring").format(n=len(jobs)))

    def _job_finito(self, coda_idx, ok, msg):
        self.coda.segna_completato(coda_idx, ok, msg)

    def _tutti_finiti(self):
        # quit() segnala al thread di fermarsi, wait() attende max 3s
        if self._transfer_thread:
            self._transfer_thread.quit()
            self._transfer_thread.wait(3000)
            self._transfer_thread = None
        self._worker = None
        self._set_status("✔ Tutti i trasferimenti completati")
        # Aggiorna i pannelli nel main thread con un piccolo delay
        QTimer.singleShot(200, self.panel_locale.aggiorna)
        QTimer.singleShot(200, self.panel_remoto.aggiorna)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _aggiorna_tutto(self):
        self.panel_locale.aggiorna()
        self.panel_remoto.aggiorna()

    def _set_status(self, msg):
        self.lbl_globale.setText(f"  {msg}")

    def chiudi_connessione(self):
        """Da chiamare alla chiusura del tab."""
        if self._worker:
            self._worker.stop()
        if self._transfer_thread and self._transfer_thread.isRunning():
            self._transfer_thread.quit()
            self._transfer_thread.wait(2000)
        try:
            self._sftp.close()
        except Exception:
            pass
        try:
            self._ssh.close()
        except Exception:
            pass


# ============================================================================
# Factory: apre una sessione SFTP e restituisce il widget
# ============================================================================


# ============================================================================
# Helper condiviso: dialog credenziali con "Ricorda"
# ============================================================================

def _dialog_credenziali(parent, host: str, porto: int, proto_label: str,
                         user: str = "", pwd: str = "",
                         mostra_pkey: bool = False) -> "dict | None":
    """
    Mostra un dialog per raccogliere le credenziali mancanti.
    Restituisce un dict {user, pwd, pkey, ricorda} oppure None se annullato.
    I campi già valorizzati sono precompilati ma modificabili.

    mostra_pkey=True  → aggiunge il campo "Chiave privata" (per SFTP/SSH)
    """
    from PyQt6.QtWidgets import (QDialog, QFormLayout, QDialogButtonBox,
                                  QLineEdit, QLabel, QCheckBox, QHBoxLayout,
                                  QPushButton, QFileDialog)

    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Credenziali — {host}")
    dlg.setMinimumWidth(380)
    form = QFormLayout(dlg)
    form.setSpacing(10)
    form.setContentsMargins(14, 14, 14, 10)

    # Header colorato con protocollo
    COLORI = {
        "SFTP": "#4e7abc", "SSH": "#4e7abc",
        "FTP":  "#b87a00", "FTPS": "#b87a00",
        "RDP":  "#0078d4", "VNC":  "#e8a020",
        "Telnet": "#c9b458",
    }
    colore = COLORI.get(proto_label, "#555555")
    lbl_info = QLabel(f"<b>{proto_label}</b>  →  {host}:{porto}")
    lbl_info.setStyleSheet(f"color:{colore}; font-size:12px; padding:4px 0 8px 0;")
    form.addRow(lbl_info)

    edit_user = QLineEdit(user)
    edit_user.setPlaceholderText("nome utente")
    form.addRow("Utente:", edit_user)

    # Password con occhio
    pwd_row = QHBoxLayout()
    edit_pwd = QLineEdit(pwd)
    edit_pwd.setEchoMode(QLineEdit.EchoMode.Password)
    edit_pwd.setPlaceholderText("password")
    btn_eye = QPushButton("👁")
    btn_eye.setFixedWidth(30)
    btn_eye.setCheckable(True)
    btn_eye.setFlat(True)
    btn_eye.toggled.connect(lambda on: edit_pwd.setEchoMode(
        QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
    ))
    pwd_row.addWidget(edit_pwd)
    pwd_row.addWidget(btn_eye)
    form.addRow("Password:", pwd_row)

    # Chiave privata (solo per proto SSH-based)
    edit_pkey = None
    if mostra_pkey:
        pkey_row = QHBoxLayout()
        edit_pkey = QLineEdit()
        edit_pkey.setPlaceholderText("percorso chiave privata (opzionale)")
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(lambda: edit_pkey.setText(
            QFileDialog.getOpenFileName(dlg, "Seleziona chiave privata",
                                         os.path.expanduser("~/.ssh"))[0] or edit_pkey.text()
        ))
        pkey_row.addWidget(edit_pkey)
        pkey_row.addWidget(btn_browse)
        form.addRow("Chiave privata:", pkey_row)

    # Checkbox "Ricorda credenziali"
    chk_ricorda = QCheckBox("Ricorda credenziali nel profilo sessione")
    chk_ricorda.setChecked(False)
    chk_ricorda.setStyleSheet(
        "font-size:11px; color:#333333; margin-top:4px; spacing:6px;"
        "QCheckBox::indicator { width:15px; height:15px; border:2px solid #888888;"
        "  border-radius:3px; background:#ffffff; }"
        "QCheckBox::indicator:checked { background:#0078d4; border-color:#0057a8; }"
        "QCheckBox::indicator:hover { border-color:#0078d4; background:#e8f0fe; }"
    )
    form.addRow("", chk_ricorda)

    bbox = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    bbox.accepted.connect(dlg.accept)
    bbox.rejected.connect(dlg.reject)
    form.addRow(bbox)

    edit_pwd.returnPressed.connect(dlg.accept)
    # Focus sul primo campo vuoto
    if not user:
        edit_user.setFocus()
    else:
        edit_pwd.setFocus()

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    return {
        "user":     edit_user.text().strip(),
        "pwd":      edit_pwd.text(),
        "pkey":     edit_pkey.text().strip() if edit_pkey else "",
        "ricorda":  chk_ricorda.isChecked(),
    }

def _salva_credenziali_profilo(profilo: dict):
    """
    Salva user/password/private_key aggiornati nel profilo persistente (connections.json).
    Il profilo deve contenere il campo speciale '__nome__' impostato da PCM.
    Se manca, il salvataggio viene silenziosamente saltato.
    """
    try:
        import config_manager
        nome = profilo.get("__nome__", "")
        if not nome:
            return
        profili = config_manager.load_profiles()
        if nome in profili:
            for campo in ("user", "password", "private_key"):
                if campo in profilo:
                    profili[nome][campo] = profilo[campo]
            config_manager.save_profiles(profili)
    except Exception as e:
        print(f"[PCM] Salvataggio credenziali fallito: {e}")


def apri_sessione_winscp(profilo: dict, parent=None) -> "WinScpWidget | None":
    """
    Connette via paramiko e restituisce un WinScpWidget pronto.
    Se mancano credenziali, le chiede con un dialog (con opzione Ricorda).
    Restituisce None se paramiko non è disponibile, connessione fallisce o utente annulla.
    """
    if not PARAMIKO_OK:
        QMessageBox.critical(parent, "SFTP non disponibile",
                             "Installa paramiko:\n  pip install paramiko")
        return None

    host  = profilo.get("host", "")
    port  = int(profilo.get("port", 22))
    user  = profilo.get("user", "").strip()
    pwd   = profilo.get("password", "")
    pkey  = profilo.get("private_key", "").strip()

    # Chiedi credenziali se mancano (nessuna autenticazione configurata)
    if not user or (not pwd and not pkey):
        cred = _dialog_credenziali(parent, host, port, "SFTP",
                                    user=user, pwd=pwd, mostra_pkey=True)
        if cred is None:
            return None
        user = cred["user"]
        pwd  = cred["pwd"]
        pkey = cred["pkey"]
        if cred["ricorda"]:
            profilo["user"]        = user
            profilo["password"]    = pwd
            profilo["private_key"] = pkey
            _salva_credenziali_profilo(profilo)

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kw = dict(hostname=host, port=port, username=user, timeout=10)
        if pkey and os.path.exists(pkey):
            kw["key_filename"] = pkey
        elif pwd:
            kw["password"] = pwd
        ssh.connect(**kw)
        sftp = ssh.open_sftp()
        return WinScpWidget(ssh, sftp, host=host, user=user, parent=parent)
    except Exception as e:
        QMessageBox.critical(parent, "Errore connessione SFTP", str(e))
        return None


# ============================================================================
# FTP/FTPS stile WinSCP — pannello remoto FTP (ftplib, stdlib)
# ============================================================================

import ftplib


class FtpTransferWorker(QObject):
    """Worker FTP per trasferimenti in thread separato (ftplib)."""

    job_iniziato  = pyqtSignal(int)
    job_progress  = pyqtSignal(int, int, int)   # idx, trasferito, totale
    job_finito    = pyqtSignal(int, bool, str)
    tutti_finiti  = pyqtSignal()

    def __init__(self, ftp_factory):
        """
        ftp_factory: callable senza argomenti che restituisce una nuova ftplib.FTP
        connessa — necessario perché ftplib non supporta trasferimenti paralleli
        su una singola connessione.
        """
        super().__init__()
        self._factory = ftp_factory
        self._jobs: list[TransferJob] = []
        self._stop = False
        self._lock = threading.Lock()

    def aggiungi(self, job: TransferJob) -> int:
        with self._lock:
            self._jobs.append(job)
            return len(self._jobs) - 1

    def stop(self):
        self._stop = True

    def run(self):
        ftp = None
        try:
            ftp = self._factory()
        except Exception as e:
            for idx in range(len(self._jobs)):
                self.job_finito.emit(idx, False, f"Connessione fallita: {e}")
            self.tutti_finiti.emit()
            return

        for idx, job in enumerate(self._jobs):
            if self._stop:
                break
            job.stato    = t("winscp.status_running")
            job.t_inizio = time.time()
            self.job_iniziato.emit(idx)
            try:
                if job.op == "download":
                    self._download(ftp, idx, job)
                else:
                    self._upload(ftp, idx, job)
                job.stato = t("winscp.status_done")
                self.job_finito.emit(idx, True, "")
            except Exception as e:
                job.stato  = t("winscp.status_err")
                job.errore = str(e)
                self.job_finito.emit(idx, False, str(e))

        try:
            ftp.quit()
        except Exception:
            pass
        self.tutti_finiti.emit()

    def _download(self, ftp, idx, job):
        size = job.size or 0
        trasferito = [0]

        def callback(data):
            fp.write(data)
            trasferito[0] += len(data)
            dt = time.time() - job.t_inizio
            job.velocita = int(trasferito[0] / dt) if dt > 0 else 0
            job.trasferito = trasferito[0]
            self.job_progress.emit(idx, trasferito[0], size)

        os.makedirs(os.path.dirname(job.dst) or ".", exist_ok=True)
        with open(job.dst, "wb") as fp:
            ftp.retrbinary(f"RETR {job.src}", callback)

    def _upload(self, ftp, idx, job):
        size = os.path.getsize(job.src) if os.path.isfile(job.src) else 0
        trasferito = [0]

        def callback(data):
            trasferito[0] += len(data)
            dt = time.time() - job.t_inizio
            job.velocita = int(trasferito[0] / dt) if dt > 0 else 0
            job.trasferito = trasferito[0]
            self.job_progress.emit(idx, trasferito[0], size)

        # ftplib non ha callback nativo per storbinary — usiamo un wrapper
        with open(job.src, "rb") as fp:
            ftp.storbinary(f"STOR {job.dst}", fp, callback=callback)


class FtpRemotePanel(FilePanel):
    """Pannello remoto FTP — sostituisce RemotePanel per connessioni ftplib."""

    def __init__(self, ftp: "ftplib.FTP", parent=None):
        super().__init__("🌐  Remoto (FTP)", parent)
        self._ftp = ftp
        self._init_drag_source()
        self._init_drop_target()
        self.tabella.mouseMoveEvent = self._tabella_mouse_move
        self._drag_pos = None
        try:
            home = ftp.pwd()
        except Exception:
            home = "/"
        self.naviga(home)

    def _panel_tipo(self) -> str:
        return "remoto"

    def _tabella_mouse_move(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton:
            if self._drag_pos is None:
                self._drag_pos = ev.pos()
            elif (ev.pos() - self._drag_pos).manhattanLength() > 20:
                self._drag_pos = None
                self._start_drag()
                return
        else:
            self._drag_pos = None
        QAbstractItemView.mouseMoveEvent(self.tabella, ev)

    def _drop_event(self, ev):
        txt = ev.mimeData().text() if ev.mimeData().hasText() else ""
        if not txt.startswith("pcm_files:locale"):
            ev.ignore()
            return
        righe = txt.split("\n")[1:]
        paths_locali = [r for r in righe if r.strip()]
        if paths_locali:
            widget = self._trova_ftp_widget()
            if widget:
                jobs = []
                for lpath in paths_locali:
                    nome = os.path.basename(lpath)
                    rpath = self.path.rstrip("/") + "/" + nome
                    size = os.path.getsize(lpath) if os.path.isfile(lpath) else 0
                    if os.path.isdir(lpath):
                        jobs += widget._jobs_upload_dir_ftp(lpath, rpath)
                    else:
                        jobs.append(TransferJob("upload", lpath, rpath, size=size, nome=nome))
                widget._esegui_jobs(jobs)
        ev.acceptProposedAction()

    def _trova_ftp_widget(self):
        p = self.parent()
        while p:
            if isinstance(p, FtpWinScpWidget):
                return p
            p = p.parent() if hasattr(p, 'parent') else None
        return None

    def vai_home(self):
        try:
            self._ftp.cwd("/")
            self.naviga(self._ftp.pwd())
        except Exception:
            pass

    def naviga(self, path: str):
        try:
            self._ftp.cwd(path)
            self.path = self._ftp.pwd()
        except Exception:
            self.path = path
        self.edit_path.setText(self.path)

        voci = [{"nome": "..", "is_dir": True,
                  "path": str(Path(self.path).parent), "size": 0, "mtime": "", "attr": ""}]

        mlsd_ok = False
        try:
            # Prova MLSD (RFC 3659) — più affidabile ma può fallire su server
            # con encoding non-UTF-8 (NAS Synology, server legacy CP1252/Latin-1).
            # Catturiamo sia error_perm che UnicodeDecodeError e qualsiasi altro
            # problema di parsing, facendo fallback su LIST.
            entries_raw = list(self._ftp.mlsd(path=self.path))
            for nome, fatti in entries_raw:
                if nome in (".", ".."):
                    continue
                tipo   = fatti.get("type", "file")
                is_dir = tipo in ("dir", "cdir", "pdir")
                try:
                    size = int(fatti.get("size", 0)) if not is_dir else 0
                except (ValueError, TypeError):
                    size = 0
                mtime_raw = fatti.get("modify", "")
                mtime = ""
                if mtime_raw and len(mtime_raw) >= 14:
                    try:
                        from datetime import datetime as _dt
                        mtime = _dt.strptime(mtime_raw[:14], "%Y%m%d%H%M%S").strftime("%d.%m.%Y %H:%M:%S")
                    except ValueError:
                        mtime = mtime_raw
                voci.append({
                    "nome":   nome,
                    "is_dir": is_dir,
                    "path":   self.path.rstrip("/") + "/" + nome,
                    "size":   size,
                    "mtime":  mtime,
                    "attr":   fatti.get("perm", ""),
                })
            mlsd_ok = True
        except Exception:
            mlsd_ok = False

        if not mlsd_ok:
            # Fallback LIST grezzo — legge i byte raw e decodifica con
            # latin-1 (superset di CP1252), che non genera mai UnicodeDecodeError
            # poiché mappa 1:1 tutti i 256 valori possibili di un byte.
            righe_raw: list[bytes] = []
            try:
                self._ftp.retrbinary(
                    "LIST " + self.path,
                    lambda blk: righe_raw.extend(blk.split(b"\n"))
                )
            except Exception:
                # Ultimo fallback: NLST (solo nomi)
                try:
                    nomi = self._ftp.nlst(self.path)
                    for nome in nomi:
                        if nome in (".", ".."):
                            continue
                        voci.append({
                            "nome":   nome,
                            "is_dir": False,   # NLST non distingue
                            "path":   self.path.rstrip("/") + "/" + nome,
                            "size":   0, "mtime": "", "attr": "",
                        })
                except Exception as e:
                    self.lbl_status.setText(f"  ✖ Errore listaggio: {e}")

            for riga_b in righe_raw:
                # Decodifica latin-1 — non solleva mai eccezioni
                riga = riga_b.decode("latin-1", errors="replace").strip()
                if not riga:
                    continue
                parti = riga.split(None, 8)
                if len(parti) < 9:
                    continue
                nome = parti[8].strip()
                if nome in (".", ".."):
                    continue
                is_dir = riga.startswith("d")
                try:
                    size = int(parti[4])
                except ValueError:
                    size = 0
                mtime = " ".join(parti[5:8])
                voci.append({
                    "nome":   nome,
                    "is_dir": is_dir,
                    "path":   self.path.rstrip("/") + "/" + nome,
                    "size":   size,
                    "mtime":  mtime,
                    "attr":   parti[0],
                })

        # Ordina: cartelle prima, poi file, alfabetico (case-insensitive)
        cartelle = sorted([v for v in voci if v["is_dir"] and v["nome"] != ".."],
                          key=lambda x: x["nome"].lower())
        files_   = sorted([v for v in voci if not v["is_dir"]],
                          key=lambda x: x["nome"].lower())
        voci_ord = [voci[0]] + cartelle + files_

        self._popola(voci_ord)
        self.navigato.emit(self.path)

    def _menu_contestuale(self, pos):
        sel = self.selezione()
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #ccc; }"
            "QMenu::item:selected { background:#b87a00; color:#fff; }"
        )
        if sel:
            menu.addAction(t("winscp.ctx_dl_local").format(n=len(sel)),
                           lambda: self._trova_ftp_widget()._download_selezione()
                           if self._trova_ftp_widget() else None)
        menu.addSeparator()
        menu.addAction(t("winscp.ctx_mkdir_remote"), self._nuova_cartella_remota)
        if sel:
            menu.addAction(t("winscp.ctx_rename"), lambda: self._rinomina(sel[0]))
            menu.addAction(t("winscp.ctx_delete"),  lambda: self._elimina(sel))
        menu.addSeparator()
        menu.addAction(t("winscp.ctx_refresh"), self.aggiorna)
        menu.exec(self.tabella.mapToGlobal(pos))

    def _nuova_cartella_remota(self):
        nome, ok = QInputDialog.getText(self, t("winscp.new_folder"), t("winscp.field_name"))
        if ok and nome:
            path = self.path.rstrip("/") + "/" + nome
            try:
                self._ftp.mkd(path)
                self.aggiorna()
            except Exception as e:
                QMessageBox.critical(self, t("winscp.err_generic2"), str(e))

    def _rinomina(self, v):
        nuovo, ok = QInputDialog.getText(self, t("winscp.dlg_rename"), t("winscp.dlg_rename_input"), text=v["nome"])
        if ok and nuovo and nuovo != v["nome"]:
            src = v["path"]
            dst = self.path.rstrip("/") + "/" + nuovo
            try:
                self._ftp.rename(src, dst)
                self.aggiorna()
            except Exception as e:
                QMessageBox.critical(self, t("winscp.err_rename"), str(e))

    def _elimina(self, sel):
        nomi = ", ".join(v["nome"] for v in sel)
        if QMessageBox.question(self, t("winscp.dlg_delete"), t("winscp.dlg_delete_confirm").format(names=nomi)) \
                != QMessageBox.StandardButton.Yes:
            return
        for v in sel:
            try:
                if v["is_dir"]:
                    self._rmdir_ricorsivo(v["path"])
                else:
                    self._ftp.delete(v["path"])
            except Exception as e:
                QMessageBox.critical(self, t("winscp.err_generic2"), str(e))
        self.aggiorna()

    def _rmdir_ricorsivo(self, path):
        """Elimina ricorsivamente una cartella FTP."""
        try:
            righe_raw: list[bytes] = []
            self._ftp.retrbinary(
                "LIST " + path,
                lambda blk: righe_raw.extend(blk.split(b"\n"))
            )
            for riga_b in righe_raw:
                riga = riga_b.decode("latin-1", errors="replace").strip()
                if not riga:
                    continue
                parti = riga.split(None, 8)
                if len(parti) < 9:
                    continue
                nome  = parti[8].strip()
                if nome in (".", ".."):
                    continue
                fpath = path.rstrip("/") + "/" + nome
                if riga.startswith("d"):
                    self._rmdir_ricorsivo(fpath)
                else:
                    self._ftp.delete(fpath)
        except Exception:
            pass
        try:
            self._ftp.rmd(path)
        except Exception:
            pass


# ============================================================================
# FtpWinScpWidget — interfaccia FTP stile WinSCP
# ============================================================================

class FtpWinScpWidget(QWidget):
    """
    Interfaccia FTP/FTPS completa stile WinSCP.
    Sostituisce WinScpWidget per connessioni FTP (ftplib, stdlib).
    Da usare come tab nell'area principale di PCM.
    """

    def __init__(self, ftp: "ftplib.FTP", ftp_factory, host="", user="",
                 tls=False, parent=None):
        super().__init__(parent)
        self._ftp          = ftp
        self._ftp_factory  = ftp_factory   # callable → nuova connessione FTP per i trasferimenti
        self._host         = host
        self._user         = user
        self._tls          = tls
        self._transfer_thread = None
        self._worker: FtpTransferWorker | None = None

        self._init_ui()

    # ------------------------------------------------------------------
    # UI — identica a WinScpWidget tranne i colori (arancione FTP)
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.panel_locale = LocalPanel(self)
        self.panel_remoto = FtpRemotePanel(self._ftp, self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("QSplitter::handle { background:#cccccc; }")
        splitter.addWidget(self.panel_locale)
        splitter.addWidget(self.panel_remoto)
        splitter.setSizes([500, 500])

        self.coda = CodaWidget(self)

        proto_str = "FTPS" if self._tls else "FTP"
        self.lbl_globale = QLabel(
            f"  🗂  Connesso: {self._user}@{self._host}  ({proto_str})"
        )
        self.lbl_globale.setFixedHeight(18)
        self.lbl_globale.setStyleSheet(
            "background:#f0f0f0; color:#b87a00; font-size:11px; "
            "padding:0 6px; border-top:1px solid #ccc;"
        )

        self._build_toolbar(root)

        root.addWidget(splitter, 1)
        root.addWidget(self.coda)
        root.addWidget(self.lbl_globale)

    def _build_toolbar(self, root):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        HOVER_COLOR = "#b87a00"
        tb.setStyleSheet(
            "QToolBar { background:#e8e8e8; border-bottom:1px solid #ccc; padding:2px; spacing:2px; }"
            f"QToolButton {{ color:#111111; background:transparent; border:1px solid transparent; "
            f"  border-radius:3px; padding:3px 8px; font-size:12px; }}"
            f"QToolButton:hover {{ background:{HOVER_COLOR}; color:#fff; border-color:{HOVER_COLOR}; }}"
            f"QToolButton:pressed {{ background:#8a5a00; color:#fff; }}"
            f"QToolButton::menu-indicator {{ image: none; }}"
        )

        def _split_btn(label, tooltip_imm, tooltip_coda,
                        slot_imm, slot_coda, shortcut=None):
            btn = QToolButton()
            btn.setText(label)
            btn.setToolTip(tooltip_imm)
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            btn.clicked.connect(slot_imm)
            if shortcut:
                act = QAction(label, self)
                act.setShortcut(QKeySequence(shortcut))
                act.triggered.connect(slot_imm)
                self.addAction(act)
            menu = QMenu(btn)
            menu.setStyleSheet(
                "QMenu { background:#ffffff; color:#111; border:1px solid #ccc; }"
                f"QMenu::item:selected {{ background:{HOVER_COLOR}; color:#fff; }}"
            )
            act_imm  = menu.addAction(f"{label.strip()}  (esegui subito)")
            act_coda = menu.addAction("📋  Aggiungi in coda")
            act_imm.triggered.connect(slot_imm)
            act_coda.triggered.connect(slot_coda)
            btn.setMenu(menu)
            tb.addWidget(btn)
            return btn

        def _a(label, tooltip, slot, shortcut=None):
            a = QAction(label, self)
            a.setToolTip(tooltip)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            tb.addAction(a)
            return a

        _split_btn("⬆  Upload",
                   "Carica subito i file selezionati (locale → remoto)",
                   "Aggiungi upload alla coda senza avviare",
                   self._upload_selezione,
                   self._accoda_upload,
                   "F5")
        _split_btn("⬇  Download",
                   "Scarica subito i file selezionati (remoto → locale)",
                   "Aggiungi download alla coda senza avviare",
                   self._download_selezione,
                   self._accoda_download,
                   "F6")
        tb.addSeparator()
        self._btn_avvia_coda = QToolButton()
        self._btn_avvia_coda.setText(t("winscp.tooltip_btn_start"))
        self._btn_avvia_coda.setToolTip(t("winscp.tooltip_start_all"))
        self._btn_avvia_coda.setStyleSheet(
            "QToolButton { color:#2d7a2d; font-weight:bold; background:transparent; "
            "border:1px solid #2d7a2d; border-radius:3px; padding:3px 8px; font-size:12px; }"
            "QToolButton:hover { background:#2d7a2d; color:#fff; }"
            "QToolButton:disabled { color:#aaa; border-color:#ccc; }"
        )
        self._btn_avvia_coda.clicked.connect(self._avvia_coda)
        tb.addWidget(self._btn_avvia_coda)
        tb.addSeparator()
        _a(t("winscp.ctx_mkdir_remote"), t("winscp.tooltip_new_folder"),
           lambda: self.panel_remoto._nuova_cartella_remota(), "F7")
        _a(t("winscp.ctx_delete"), t("winscp.tooltip_delete_remote"),
           lambda: self.panel_remoto._elimina(self.panel_remoto.selezione()))
        tb.addSeparator()
        _a(t("winscp.ctx_refresh"), t("winscp.tooltip_refresh_both"), self._aggiorna_tutto, "F2")
        tb.addSeparator()
        _a(t("winscp.btn_clear"), t("winscp.tooltip_clear_queue"), self.coda.pulisci)

        root.addWidget(tb)

    # ------------------------------------------------------------------
    # Trasferimenti
    # ------------------------------------------------------------------

    def _upload_selezione(self):
        sel = self.panel_locale.selezione()
        if not sel:
            QMessageBox.information(self, t("winscp.dlg_upload"), t("winscp.no_local_sel"))
            return
        dest_base = self.panel_remoto.path.rstrip("/")
        jobs = []
        for v in sel:
            if v["nome"] == "..":
                continue
            if v["is_dir"]:
                jobs += self._jobs_upload_dir_ftp(v["path"], dest_base + "/" + v["nome"])
            else:
                j = TransferJob(
                    op="upload", src=v["path"],
                    dst=dest_base + "/" + v["nome"],
                    size=v.get("size", 0), nome=v["nome"]
                )
                jobs.append(j)
        if jobs:
            self._esegui_jobs(jobs)

    def _download_selezione(self):
        sel = self.panel_remoto.selezione()
        if not sel:
            QMessageBox.information(self, t("winscp.dlg_download"), t("winscp.no_remote_sel"))
            return
        dest_base = self.panel_locale.path
        jobs = []
        for v in sel:
            if v["nome"] == "..":
                continue
            if v["is_dir"]:
                jobs += self._jobs_download_dir_ftp(v["path"], os.path.join(dest_base, v["nome"]))
            else:
                j = TransferJob(
                    op="download", src=v["path"],
                    dst=os.path.join(dest_base, v["nome"]),
                    size=v.get("size", 0), nome=v["nome"]
                )
                jobs.append(j)
        if jobs:
            self._esegui_jobs(jobs)

    def _jobs_upload_dir_ftp(self, local_dir, remote_dir) -> list:
        try:
            self._ftp.mkd(remote_dir)
        except Exception:
            pass
        jobs = []
        try:
            for entry in os.scandir(local_dir):
                rpath = remote_dir + "/" + entry.name
                if entry.is_dir():
                    jobs += self._jobs_upload_dir_ftp(entry.path, rpath)
                else:
                    jobs.append(TransferJob(
                        op="upload", src=entry.path, dst=rpath,
                        size=entry.stat().st_size, nome=entry.name
                    ))
        except Exception:
            pass
        return jobs

    def _jobs_download_dir_ftp(self, remote_dir, local_dir) -> list:
        os.makedirs(local_dir, exist_ok=True)
        jobs = []
        try:
            righe_raw: list[bytes] = []
            self._ftp.retrbinary(
                "LIST " + remote_dir,
                lambda blk: righe_raw.extend(blk.split(b"\n"))
            )
            for riga_b in righe_raw:
                riga = riga_b.decode("latin-1", errors="replace").strip()
                if not riga:
                    continue
                parti = riga.split(None, 8)
                if len(parti) < 9:
                    continue
                nome  = parti[8].strip()
                if nome in (".", ".."):
                    continue
                rpath = remote_dir.rstrip("/") + "/" + nome
                lpath = os.path.join(local_dir, nome)
                if riga.startswith("d"):
                    jobs += self._jobs_download_dir_ftp(rpath, lpath)
                else:
                    try:
                        size = int(parti[4])
                    except ValueError:
                        size = 0
                    jobs.append(TransferJob(
                        op="download", src=rpath, dst=lpath,
                        size=size, nome=nome
                    ))
        except Exception:
            pass
        return jobs

    # ------------------------------------------------------------------
    # Accodamento senza avvio immediato
    # ------------------------------------------------------------------

    def _accoda_upload(self):
        sel = self.panel_locale.selezione()
        if not sel:
            QMessageBox.information(self, t("winscp.dlg_queue"), t("winscp.no_local_sel"))
            return
        dest_base = self.panel_remoto.path.rstrip("/")
        jobs = []
        for v in sel:
            if v["nome"] == "..":
                continue
            if v["is_dir"]:
                jobs += self._jobs_upload_dir_ftp(v["path"], dest_base + "/" + v["nome"])
            else:
                jobs.append(TransferJob(
                    op="upload", src=v["path"],
                    dst=dest_base + "/" + v["nome"],
                    size=v.get("size", 0), nome=v["nome"]
                ))
        for job in jobs:
            self.coda.aggiungi_in_attesa(job)
        self._set_status(t("winscp.queue_count").format(n=len(jobs), m=self.coda.n_in_attesa()))

    def _accoda_download(self):
        sel = self.panel_remoto.selezione()
        if not sel:
            QMessageBox.information(self, t("winscp.dlg_queue"), t("winscp.no_remote_sel"))
            return
        dest_base = self.panel_locale.path
        jobs = []
        for v in sel:
            if v["nome"] == "..":
                continue
            if v["is_dir"]:
                jobs += self._jobs_download_dir_ftp(v["path"], os.path.join(dest_base, v["nome"]))
            else:
                jobs.append(TransferJob(
                    op="download", src=v["path"],
                    dst=os.path.join(dest_base, v["nome"]),
                    size=v.get("size", 0), nome=v["nome"]
                ))
        for job in jobs:
            self.coda.aggiungi_in_attesa(job)
        self._set_status(t("winscp.queue_count").format(n=len(jobs), m=self.coda.n_in_attesa()))

    def _avvia_coda(self):
        jobs = self.coda.prendi_jobs_in_attesa()
        if not jobs:
            self._set_status(t("winscp.no_jobs"))
            return
        self._esegui_jobs(jobs, dalla_coda=True)

    def _esegui_jobs(self, jobs: list, dalla_coda: bool = False):
        if self._transfer_thread and self._transfer_thread.isRunning():
            QMessageBox.warning(self, t("winscp.transfer_running"), t("winscp.transfer_wait"))
            return

        self._worker = FtpTransferWorker(self._ftp_factory)
        idx_map = {}
        for job in jobs:
            job_idx  = self._worker.aggiungi(job)
            coda_idx = job._coda_idx if (dalla_coda and hasattr(job, "_coda_idx")) \
                       else self.coda.aggiungi_job(job)
            for col in range(len(CodaWidget.COLONNE) - 1):
                item = self.coda.tabella.item(coda_idx, col)
                if item:
                    item.setForeground(QColor("#111111"))
            idx_map[job_idx] = coda_idx

        self._worker.job_progress.connect(
            lambda ji, tx, tot: self.coda.aggiorna_progress(idx_map.get(ji, ji), tx, tot)
        )
        self._worker.job_finito.connect(
            lambda ji, ok, msg: self._job_finito(idx_map.get(ji, ji), ok, msg)
        )
        self._worker.tutti_finiti.connect(self._tutti_finiti)

        self._transfer_thread = QThread()
        self._worker.moveToThread(self._transfer_thread)
        self._transfer_thread.started.connect(self._worker.run)
        self._transfer_thread.start()

        self._set_status(t("winscp.transferring").format(n=len(jobs)))

    def _job_finito(self, coda_idx, ok, msg):
        self.coda.segna_completato(coda_idx, ok, msg)

    def _tutti_finiti(self):
        if self._transfer_thread:
            self._transfer_thread.quit()
            self._transfer_thread.wait(3000)
            self._transfer_thread = None
        self._worker = None
        self._set_status("✔ Tutti i trasferimenti completati")
        QTimer.singleShot(200, self.panel_locale.aggiorna)
        QTimer.singleShot(200, self.panel_remoto.aggiorna)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _aggiorna_tutto(self):
        self.panel_locale.aggiorna()
        self.panel_remoto.aggiorna()

    def _set_status(self, msg):
        self.lbl_globale.setText(f"  {msg}")

    def chiudi_connessione(self):
        if self._worker:
            self._worker.stop()
        if self._transfer_thread and self._transfer_thread.isRunning():
            self._transfer_thread.quit()
            self._transfer_thread.wait(2000)
        try:
            self._ftp.quit()
        except Exception:
            try:
                self._ftp.close()
            except Exception:
                pass


# ============================================================================
# Factory FTP — analoga ad apri_sessione_winscp
# ============================================================================

def apri_sessione_ftp(profilo: dict, parent=None) -> "FtpWinScpWidget | None":
    """
    Connette via ftplib e restituisce un FtpWinScpWidget pronto.
    Se mancano credenziali, le chiede con un dialog (con opzione Ricorda).
    Restituisce None se la connessione fallisce o l'utente annulla.
    """
    host    = profilo.get("host", "")
    port    = int(profilo.get("port", 21))
    tls     = profilo.get("ftp_tls", False)
    passive = profilo.get("ftp_passive", True)
    user    = profilo.get("user", "").strip()
    pwd     = profilo.get("password", "")

    proto_label = "FTPS" if tls else "FTP"

    # Chiedi credenziali se mancano utente o password
    if not user or not pwd:
        cred = _dialog_credenziali(parent, host, port, proto_label,
                                    user=user, pwd=pwd, mostra_pkey=False)
        if cred is None:
            return None
        user = cred["user"] or "anonymous"
        pwd  = cred["pwd"]
        if cred["ricorda"]:
            profilo["user"]     = user
            profilo["password"] = pwd
            _salva_credenziali_profilo(profilo)

    def _crea_connessione():
        """Crea e restituisce una nuova connessione FTP autenticata."""
        if tls:
            ftp = ftplib.FTP_TLS(timeout=10)
            ftp.connect(host, port)
            ftp.auth()
            ftp.prot_p()
        else:
            ftp = ftplib.FTP(timeout=10)
            ftp.connect(host, port)
        # Imposta encoding latin-1: superset di CP1252, compatibile con server
        # Synology e NAS legacy che non usano UTF-8 per i nomi file.
        # Per MLSD usiamo retrbinary + decodifica manuale, quindi questo
        # encoding vale solo per i comandi di controllo (PWD, CWD, ecc.).
        ftp.encoding = "latin-1"
        ftp.login(user, pwd)
        ftp.set_pasv(passive)
        return ftp

    try:
        ftp = _crea_connessione()
        return FtpWinScpWidget(
            ftp, _crea_connessione,
            host=host, user=user, tls=tls, parent=parent
        )
    except Exception as e:
        QMessageBox.critical(parent, "Errore connessione FTP", str(e))
        return None
