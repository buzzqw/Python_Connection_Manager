"""
sftp_browser.py - Pannello SFTP laterale stile MobaXterm (sidebar SSH browser)
Usa paramiko per navigare, scaricare e caricare file via SSH/SFTP.
"""

import os
import stat
import threading
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QMenu, QFileDialog, QMessageBox,
    QProgressDialog, QApplication, QToolButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QIcon, QFont

try:
    import paramiko
    import stat as stat_mod
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False


# ---------------------------------------------------------------------------
# Worker thread per operazioni SFTP bloccanti
# ---------------------------------------------------------------------------

class SftpWorker(QObject):
    finished = pyqtSignal(bool, str)   # successo, messaggio
    progress = pyqtSignal(int)         # percentuale 0-100

    def __init__(self, sftp, operazione, src, dst, size=0):
        super().__init__()
        self._sftp = sftp
        self._op = operazione   # 'get' o 'put'
        self._src = src
        self._dst = dst
        self._size = size
        self._trasferito = 0

    def run(self):
        try:
            def callback(tx, tot):
                self._trasferito = tx
                if tot > 0:
                    self.progress.emit(int(tx * 100 / tot))

            if self._op == "get":
                self._sftp.get(self._src, self._dst, callback=callback)
            else:
                self._sftp.put(self._src, self._dst, callback=callback)
            self.finished.emit(True, "OK")
        except Exception as e:
            self.finished.emit(False, str(e))


class FtpWorker(QObject):
    finished = pyqtSignal(bool, str)

    def __init__(self, ftp, operazione, src, dst):
        super().__init__()
        self._ftp = ftp
        self._op  = operazione   # 'get' o 'put'
        self._src = src
        self._dst = dst

    def run(self):
        try:
            if self._op == "get":
                with open(self._dst, "wb") as fp:
                    self._ftp.retrbinary(f"RETR {self._src}", fp.write)
            else:
                with open(self._src, "rb") as fp:
                    self._ftp.storbinary(f"STOR {self._dst}", fp)
            self.finished.emit(True, "OK")
        except Exception as e:
            self.finished.emit(False, str(e))


# ---------------------------------------------------------------------------
# Widget principale
# ---------------------------------------------------------------------------

class SftpBrowserWidget(QWidget):
    """
    Sidebar SFTP in stile MobaXterm:
    - albero di navigazione file/cartelle
    - toolbar con su/giù/refresh/home/upload/download
    - drag & drop (futuro)
    - menu contestuale tasto destro
    """

    richiesta_cd = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ssh = None
        self._sftp = None
        self._path_corrente = "/"
        self._cronologia = []
        self._connesso = False

        self._init_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QLabel("  🗂  Browser SFTP")
        hdr.setStyleSheet(
            "background:#f0f0f0; color:#4e7abc; font-size:12px; font-weight:bold; "
            "padding:6px; border-bottom:1px solid #ccc;"
        )
        layout.addWidget(hdr)

        # Toolbar di navigazione
        tb = QHBoxLayout()
        tb.setContentsMargins(4, 2, 4, 2)
        tb.setSpacing(2)

        self.btn_su    = self._mkbtn("⬆", "Cartella superiore", self._vai_su)
        self.btn_home  = self._mkbtn("🏠", "Home directory",     self._vai_home)
        self.btn_refresh = self._mkbtn("↺", "Aggiorna",          self._aggiorna)
        self.btn_upload  = self._mkbtn("⬆️", "Carica file",       self._carica_file)
        self.btn_dl      = self._mkbtn("⬇️", "Scarica file",      self._scarica_file)
        self.btn_mkdir   = self._mkbtn("📁+","Nuova cartella",    self._nuova_cartella)

        for b in [self.btn_su, self.btn_home, self.btn_refresh,
                  self.btn_upload, self.btn_dl, self.btn_mkdir]:
            tb.addWidget(b)
        tb.addStretch()
        layout.addLayout(tb)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#444;")
        layout.addWidget(sep)

        # Barra percorso
        self.path_edit = QLineEdit("/")
        self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet(
            "background:#ffffff; color:#1a5ca8; font-family:monospace; "
            "font-size:12px; border:none; border-bottom:1px solid #ccc; padding:3px 6px;"
        )
        layout.addWidget(self.path_edit)

        # Lista file
        self.lista = QListWidget()
        self.lista.setFont(QFont("Monospace", 11))
        self.lista.setStyleSheet(
            "QListWidget { background:#ffffff; color:#111111; border:none; }"
            "QListWidget::item { padding:3px 6px; }"
            "QListWidget::item:selected { background:#4e7abc; color:#fff; }"
            "QListWidget::item:hover:!selected { background:#e8eef5; }"
        )
        self.lista.itemDoubleClicked.connect(self._doppio_clic)
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_contestuale)
        layout.addWidget(self.lista, 1)

        # Status bar
        self.status = QLabel("  Non connesso")
        self.status.setStyleSheet(
            "background:#f0f0f0; color:#555555; font-size:11px; padding:3px 6px; border-top:1px solid #ccc;"
        )
        layout.addWidget(self.status)

        self._imposta_disconnesso()

    def _mkbtn(self, label, tooltip, slot):
        b = QToolButton()
        b.setText(label)
        b.setToolTip(tooltip)
        b.setFixedHeight(24)
        b.setStyleSheet(
            "QToolButton { background:transparent; color:#444444; border:none; "
            "font-size:13px; padding:0 3px; }"
            "QToolButton:hover { color:#fff; background:#4e7abc; border-radius:3px; }"
            "QToolButton:disabled { color:#aaaaaa; }"
        )
        b.clicked.connect(slot)
        return b

    # ------------------------------------------------------------------
    # Connessione / disconnessione
    # ------------------------------------------------------------------

    def connetti(self, host, port, user, pwd, pkey_path=""):
        if not PARAMIKO_OK:
            self._set_status("⚠ paramiko non installato: pip install paramiko")
            return

        self._disconnetti_silenzioso()
        self._set_status("⏳ Connessione in corso…")
        self.lista.clear()

        try:
            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            kw = dict(hostname=host, port=int(port), username=user, timeout=8)
            if pkey_path and os.path.exists(pkey_path):
                kw["key_filename"] = pkey_path
            elif pwd:
                kw["password"] = pwd

            self._ssh.connect(**kw)
            self._sftp = self._ssh.open_sftp()
            self._path_corrente = self._sftp.normalize(".")
            self._connesso = True
            self._carica_cartella(self._path_corrente)
            self._set_status(f"✔ {user}@{host}:{port}")
            self._imposta_connesso()

        except Exception as e:
            self._set_status(f"✖ Errore: {e}")
            self._imposta_disconnesso()

    def disconnetti(self):
        self._disconnetti_silenzioso()
        self._imposta_disconnesso()
        self.lista.clear()
        self.path_edit.setText("/")
        self._set_status("  Non connesso")

    def _disconnetti_silenzioso(self):
        try:
            if self._sftp:
                self._sftp.close()
            if self._ssh:
                self._ssh.close()
        except Exception:
            pass
        self._sftp = None
        self._ssh = None
        self._connesso = False

    # ------------------------------------------------------------------
    # Navigazione
    # ------------------------------------------------------------------

    def _carica_cartella(self, path):
        if not self._sftp:
            return
        try:
            voci = self._sftp.listdir_attr(path)
            self.lista.clear()

            # Prima le cartelle poi i file, ordine alfabetico
            cartelle = sorted(
                [v for v in voci if stat.S_ISDIR(v.st_mode)],
                key=lambda x: x.filename.lower()
            )
            file = sorted(
                [v for v in voci if not stat.S_ISDIR(v.st_mode)],
                key=lambda x: x.filename.lower()
            )

            # ".." per salire
            item_su = QListWidgetItem("📁  ..")
            item_su.setData(Qt.ItemDataRole.UserRole, "..")
            self.lista.addItem(item_su)

            for v in cartelle:
                item = QListWidgetItem(f"📁  {v.filename}")
                item.setData(Qt.ItemDataRole.UserRole, ("dir", v.filename))
                item.setForeground(QColor("#1a5ca8"))
                self.lista.addItem(item)

            for v in file:
                size_str = self._fmt_size(v.st_size)
                item = QListWidgetItem(f"📄  {v.filename}  ({size_str})")
                item.setData(Qt.ItemDataRole.UserRole, ("file", v.filename))
                self.lista.addItem(item)

            self._path_corrente = path
            self.path_edit.setText(path)
            self._cronologia.append(path)

        except Exception as e:
            self._set_status(f"✖ {e}")

    def _doppio_clic(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data == "..":
            self._vai_su()
        elif isinstance(data, tuple):
            tipo, nome = data
            if tipo == "dir":
                nuovo = self._path_corrente.rstrip("/") + "/" + nome
                self._carica_cartella(nuovo)
            elif tipo == "file":
                self._scarica_file_singolo(nome)

    def _vai_su(self):
        parent = str(Path(self._path_corrente).parent)
        if parent != self._path_corrente:
            self._carica_cartella(parent)

    def _vai_home(self):
        if self._sftp:
            try:
                home = self._sftp.normalize(".")
                self._carica_cartella(home)
            except Exception:
                pass

    def _aggiorna(self):
        if self._connesso:
            self._carica_cartella(self._path_corrente)

    # ------------------------------------------------------------------
    # Upload / Download
    # ------------------------------------------------------------------

    def _scarica_file(self):
        item = self.lista.currentItem()
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and data[0] == "file":
            self._scarica_file_singolo(data[1])

    def _scarica_file_singolo(self, nome):
        if not self._sftp:
            return
        dst, _ = QFileDialog.getSaveFileName(self, "Salva come", nome)
        if not dst:
            return
        src = self._path_corrente.rstrip("/") + "/" + nome
        try:
            size = self._sftp.stat(src).st_size or 0
        except Exception:
            size = 0

        progress = QProgressDialog(f"⬇ Download: {nome}", "Annulla", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)
        self._set_status(f"⬇ Download {nome}…")

        worker = SftpWorker(self._sftp, "get", src, dst, size)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(progress.setValue)
        worker.finished.connect(
            lambda ok, msg, n=nome, p=progress, t=thread:
                self._on_sftp_done(ok, msg, n, "Scaricato", p, t, refresh=False)
        )
        thread.start()

    def _carica_file(self):
        if not self._sftp:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Seleziona file da caricare")
        if files:
            self._carica_lista(list(files))

    def _carica_lista(self, files: list):
        if not files:
            self._aggiorna()
            return
        local_path = files[0]
        rimanenti  = files[1:]
        nome = os.path.basename(local_path)
        remote_path = self._path_corrente.rstrip("/") + "/" + nome

        progress = QProgressDialog(f"⬆ Upload: {nome}", "Annulla", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)
        self._set_status(f"⬆ Upload {nome}…")

        worker = SftpWorker(self._sftp, "put", local_path, remote_path)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(progress.setValue)
        worker.finished.connect(
            lambda ok, msg, n=nome, p=progress, t=thread, r=rimanenti:
                self._on_sftp_upload_done(ok, msg, n, p, t, r)
        )
        thread.start()

    def _on_sftp_upload_done(self, ok, msg, nome, progress, thread, rimanenti):
        progress.close()
        thread.quit()
        thread.wait()
        if ok:
            self._set_status(f"✔ Caricato: {nome}")
        else:
            QMessageBox.critical(self, "Errore upload", msg)
            self._set_status(f"✖ Errore: {msg}")
        self._carica_lista(rimanenti)

    def _on_sftp_done(self, ok, msg, nome, azione, progress, thread, refresh=False):
        progress.close()
        thread.quit()
        thread.wait()
        if ok:
            self._set_status(f"✔ {azione}: {nome}")
        else:
            QMessageBox.critical(self, f"Errore {azione.lower()}", msg)
            self._set_status(f"✖ Errore: {msg}")
        if refresh:
            self._aggiorna()

    # ------------------------------------------------------------------
    # Operazioni file
    # ------------------------------------------------------------------

    def _nuova_cartella(self):
        if not self._sftp:
            return
        from PyQt6.QtWidgets import QInputDialog
        nome, ok = QInputDialog.getText(self, "Nuova cartella", "Nome:")
        if ok and nome:
            path = self._path_corrente.rstrip("/") + "/" + nome
            try:
                self._sftp.mkdir(path)
                self._aggiorna()
            except Exception as e:
                QMessageBox.critical(self, "Errore", str(e))

    def _rinomina(self, nome_orig):
        if not self._sftp:
            return
        from PyQt6.QtWidgets import QInputDialog
        nuovo, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=nome_orig)
        if ok and nuovo and nuovo != nome_orig:
            src = self._path_corrente.rstrip("/") + "/" + nome_orig
            dst = self._path_corrente.rstrip("/") + "/" + nuovo
            try:
                self._sftp.rename(src, dst)
                self._aggiorna()
            except Exception as e:
                QMessageBox.critical(self, "Errore rinomina", str(e))

    def _elimina(self, nome, is_dir):
        if not self._sftp:
            return
        risposta = QMessageBox.question(
            self, "Elimina",
            f"Eliminare {'la cartella' if is_dir else 'il file'} '{nome}'?"
        )
        if risposta != QMessageBox.StandardButton.Yes:
            return
        path = self._path_corrente.rstrip("/") + "/" + nome
        try:
            if is_dir:
                self._sftp.rmdir(path)
            else:
                self._sftp.remove(path)
            self._aggiorna()
        except Exception as e:
            QMessageBox.critical(self, "Errore eliminazione", str(e))

    # ------------------------------------------------------------------
    # Menu contestuale
    # ------------------------------------------------------------------

    def _menu_contestuale(self, pos):
        item = self.lista.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #ccc; }"
            "QMenu::item:selected { background:#4e7abc; color:#fff; }"
        )

        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, tuple):
                tipo, nome = data
                is_dir = tipo == "dir"
                if not is_dir:
                    menu.addAction("⬇ Scarica", lambda: self._scarica_file_singolo(nome))
                menu.addAction("✏ Rinomina", lambda: self._rinomina(nome))
                menu.addAction("🗑 Elimina", lambda: self._elimina(nome, is_dir))
                menu.addSeparator()

        menu.addAction("⬆ Carica file", self._carica_file)
        menu.addAction("📁+ Nuova cartella", self._nuova_cartella)
        menu.addSeparator()
        menu.addAction("↺ Aggiorna", self._aggiorna)
        menu.exec(self.lista.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Stato UI
    # ------------------------------------------------------------------

    def _imposta_connesso(self):
        for b in [self.btn_su, self.btn_home, self.btn_refresh,
                  self.btn_upload, self.btn_dl, self.btn_mkdir]:
            b.setEnabled(True)

    def _imposta_disconnesso(self):
        for b in [self.btn_su, self.btn_home, self.btn_refresh,
                  self.btn_upload, self.btn_dl, self.btn_mkdir]:
            b.setEnabled(False)

    def _set_status(self, msg):
        self.status.setText(f"  {msg}")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# FTP Browser Widget (ftplib — stdlib, nessuna dipendenza esterna)
# ---------------------------------------------------------------------------

import ftplib
from PyQt6.QtGui import QColor


class FtpBrowserWidget(QWidget):
    """
    Sidebar FTP in stile SftpBrowserWidget.
    Usa ftplib (stdlib) — supporta FTP plain e FTPS (TLS esplicito).
    Funzionalità: navigazione, download, upload, nuova cartella, rinomina, elimina.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ftp: ftplib.FTP | None = None
        self._path_corrente = "/"
        self._cronologia: list[str] = []
        self._connesso = False
        self._init_ui()

    # ------------------------------------------------------------------
    # UI (identica a SftpBrowserWidget)
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QLabel("  🗂  Browser FTP")
        hdr.setStyleSheet(
            "background:#f0f0f0; color:#b87a00; font-size:12px; font-weight:bold; "
            "padding:6px; border-bottom:1px solid #ccc;"
        )
        layout.addWidget(hdr)

        tb = QHBoxLayout()
        tb.setContentsMargins(4, 2, 4, 2)
        tb.setSpacing(2)

        self.btn_su      = self._mkbtn("⬆",  "Cartella superiore", self._vai_su)
        self.btn_home    = self._mkbtn("🏠", "Home directory",      self._vai_home)
        self.btn_refresh = self._mkbtn("↺",  "Aggiorna",            self._aggiorna)
        self.btn_upload  = self._mkbtn("⬆️", "Carica file",          self._carica_file)
        self.btn_dl      = self._mkbtn("⬇️", "Scarica file",         self._scarica_file)
        self.btn_mkdir   = self._mkbtn("📁+","Nuova cartella",       self._nuova_cartella)

        for b in [self.btn_su, self.btn_home, self.btn_refresh,
                  self.btn_upload, self.btn_dl, self.btn_mkdir]:
            tb.addWidget(b)
        tb.addStretch()
        layout.addLayout(tb)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#ccc;")
        layout.addWidget(sep)

        self.path_edit = QLineEdit("/")
        self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet(
            "background:#ffffff; color:#b87a00; font-family:monospace; "
            "font-size:12px; border:none; border-bottom:1px solid #ccc; padding:3px 6px;"
        )
        layout.addWidget(self.path_edit)

        self.lista = QListWidget()
        self.lista.setFont(QFont("Monospace", 11))
        self.lista.setStyleSheet(
            "QListWidget { background:#ffffff; color:#111111; border:none; }"
            "QListWidget::item { padding:3px 6px; }"
            "QListWidget::item:selected { background:#b87a00; color:#fff; }"
            "QListWidget::item:hover:!selected { background:#fdf3e0; }"
        )
        self.lista.itemDoubleClicked.connect(self._doppio_clic)
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_contestuale)
        layout.addWidget(self.lista, 1)

        self.status = QLabel("  Non connesso")
        self.status.setStyleSheet(
            "background:#f0f0f0; color:#555555; font-size:11px; padding:3px 6px; border-top:1px solid #ccc;"
        )
        layout.addWidget(self.status)

        self._imposta_disconnesso()

    def _mkbtn(self, label, tooltip, slot):
        b = QToolButton()
        b.setText(label)
        b.setToolTip(tooltip)
        b.setFixedHeight(24)
        b.setStyleSheet(
            "QToolButton { background:transparent; color:#444444; border:none; "
            "font-size:13px; padding:0 3px; }"
            "QToolButton:hover { color:#fff; background:#b87a00; border-radius:3px; }"
            "QToolButton:disabled { color:#aaaaaa; }"
        )
        b.clicked.connect(slot)
        return b

    # ------------------------------------------------------------------
    # Connessione
    # ------------------------------------------------------------------

    def connetti(self, host: str, port: int | str, user: str, pwd: str,
                 tls: bool = False, passive: bool = True):
        """
        Apre la connessione FTP (o FTPS con TLS esplicito se tls=True).
        passive=True  → modalità passiva (PASV) — default, funziona dietro NAT.
        passive=False → modalità attiva (PORT) — solo reti senza firewall.
        """
        self._disconnetti_silenzioso()
        self._set_status("⏳ Connessione FTP in corso…")
        self.lista.clear()

        try:
            port = int(port) if port else (21 if not tls else 990)

            if tls:
                ftp = ftplib.FTP_TLS(timeout=10)
                ftp.connect(host, port)
                ftp.auth()          # negozia TLS
                ftp.prot_p()        # dati cifrati
            else:
                ftp = ftplib.FTP(timeout=10)
                ftp.connect(host, port)

            ftp.login(user or "anonymous", pwd or "")
            ftp.set_pasv(passive)

            self._ftp = ftp
            self._connesso = True
            self._path_corrente = self._ftp.pwd()
            self._carica_cartella(self._path_corrente)
            proto_str = "FTPS" if tls else "FTP"
            self._set_status(f"✔ {proto_str}  {user}@{host}:{port}")
            self._imposta_connesso()

        except Exception as e:
            self._set_status(f"✖ Errore FTP: {e}")
            self._imposta_disconnesso()

    def disconnetti(self):
        self._disconnetti_silenzioso()
        self._imposta_disconnesso()
        self.lista.clear()
        self.path_edit.setText("/")
        self._set_status("  Non connesso")

    def _disconnetti_silenzioso(self):
        try:
            if self._ftp:
                self._ftp.quit()
        except Exception:
            try:
                if self._ftp:
                    self._ftp.close()
            except Exception:
                pass
        self._ftp = None
        self._connesso = False

    # ------------------------------------------------------------------
    # Navigazione
    # ------------------------------------------------------------------

    def _carica_cartella(self, path: str):
        if not self._ftp:
            return
        try:
            self._ftp.cwd(path)
            self._path_corrente = self._ftp.pwd()
            self.path_edit.setText(self._path_corrente)

            # MLSD (RFC 3659) se disponibile, fallback LIST
            voci = []
            try:
                for nome, fatti in self._ftp.mlsd():
                    if nome in (".", ".."):
                        continue
                    tipo = fatti.get("type", "file")
                    size = int(fatti.get("size", 0))
                    voci.append((nome, tipo == "dir", size))
            except ftplib.error_perm:
                # Server non supporta MLSD → parse LIST grezzo
                righe: list[str] = []
                self._ftp.retrlines("LIST", righe.append)
                for riga in righe:
                    parti = riga.split(None, 8)
                    if len(parti) < 9:
                        continue
                    is_dir = riga.startswith("d")
                    nome = parti[8].strip()
                    if nome in (".", ".."):
                        continue
                    try:
                        size = int(parti[4])
                    except ValueError:
                        size = 0
                    voci.append((nome, is_dir, size))

            self.lista.clear()

            # ".." per salire
            item_su = QListWidgetItem("📁  ..")
            item_su.setData(Qt.ItemDataRole.UserRole, "..")
            self.lista.addItem(item_su)

            cartelle = sorted([(n, s) for n, d, s in voci if d],     key=lambda x: x[0].lower())
            file_voci = sorted([(n, s) for n, d, s in voci if not d], key=lambda x: x[0].lower())

            for nome, _ in cartelle:
                item = QListWidgetItem(f"📁  {nome}")
                item.setData(Qt.ItemDataRole.UserRole, ("dir", nome))
                item.setForeground(QColor("#b87a00"))
                self.lista.addItem(item)

            for nome, size in file_voci:
                item = QListWidgetItem(f"📄  {nome}  ({SftpBrowserWidget._fmt_size(size)})")
                item.setData(Qt.ItemDataRole.UserRole, ("file", nome))
                self.lista.addItem(item)

            self._cronologia.append(self._path_corrente)
            self._set_status(
                f"  {len(cartelle)} cartelle, {len(file_voci)} file — {self._path_corrente}"
            )

        except Exception as e:
            self._set_status(f"✖ {e}")

    def _doppio_clic(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data == "..":
            self._vai_su()
        elif isinstance(data, tuple):
            tipo, nome = data
            if tipo == "dir":
                nuovo = self._path_corrente.rstrip("/") + "/" + nome
                self._carica_cartella(nuovo)
            elif tipo == "file":
                self._scarica_file_singolo(nome)

    def _vai_su(self):
        from pathlib import Path
        parent = str(Path(self._path_corrente).parent)
        if parent != self._path_corrente:
            self._carica_cartella(parent)

    def _vai_home(self):
        if self._ftp:
            try:
                self._carica_cartella("/")
            except Exception:
                pass

    def _aggiorna(self):
        if self._connesso:
            self._carica_cartella(self._path_corrente)

    # ------------------------------------------------------------------
    # Upload / Download
    # ------------------------------------------------------------------

    def _scarica_file(self):
        item = self.lista.currentItem()
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and data[0] == "file":
            self._scarica_file_singolo(data[1])

    def _scarica_file_singolo(self, nome: str):
        if not self._ftp:
            return
        dst, _ = QFileDialog.getSaveFileName(self, "Salva come", nome)
        if not dst:
            return
        remote = self._path_corrente.rstrip("/") + "/" + nome
        self._set_status(f"⬇ Download {nome}…")

        worker = FtpWorker(self._ftp, "get", remote, dst)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            lambda ok, msg, n=nome, t=thread:
                self._on_ftp_done(ok, msg, n, "Scaricato", t, refresh=False)
        )
        thread.start()

    def _carica_file(self):
        if not self._ftp:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Seleziona file da caricare")
        if files:
            self._carica_ftp_lista(list(files))

    def _carica_ftp_lista(self, files: list):
        if not files:
            self._aggiorna()
            return
        local_path = files[0]
        rimanenti  = files[1:]
        nome   = os.path.basename(local_path)
        remote = self._path_corrente.rstrip("/") + "/" + nome
        self._set_status(f"⬆ Upload {nome}…")

        worker = FtpWorker(self._ftp, "put", local_path, remote)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            lambda ok, msg, n=nome, t=thread, r=rimanenti:
                self._on_ftp_upload_done(ok, msg, n, t, r)
        )
        thread.start()

    def _on_ftp_upload_done(self, ok, msg, nome, thread, rimanenti):
        thread.quit()
        thread.wait()
        if ok:
            self._set_status(f"✔ Caricato: {nome}")
        else:
            QMessageBox.critical(self, "Errore upload", msg)
            self._set_status(f"✖ Errore: {msg}")
        self._carica_ftp_lista(rimanenti)

    def _on_ftp_done(self, ok, msg, nome, azione, thread, refresh=False):
        thread.quit()
        thread.wait()
        if ok:
            self._set_status(f"✔ {azione}: {nome}")
        else:
            QMessageBox.critical(self, f"Errore {azione.lower()}", msg)
            self._set_status(f"✖ Errore: {msg}")
        if refresh:
            self._aggiorna()

    # ------------------------------------------------------------------
    # Operazioni file
    # ------------------------------------------------------------------

    def _nuova_cartella(self):
        if not self._ftp:
            return
        from PyQt6.QtWidgets import QInputDialog
        nome, ok = QInputDialog.getText(self, "Nuova cartella", "Nome:")
        if ok and nome:
            path = self._path_corrente.rstrip("/") + "/" + nome
            try:
                self._ftp.mkd(path)
                self._aggiorna()
            except Exception as e:
                QMessageBox.critical(self, "Errore", str(e))

    def _rinomina(self, nome_orig: str):
        if not self._ftp:
            return
        from PyQt6.QtWidgets import QInputDialog
        nuovo, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=nome_orig)
        if ok and nuovo and nuovo != nome_orig:
            src = self._path_corrente.rstrip("/") + "/" + nome_orig
            dst = self._path_corrente.rstrip("/") + "/" + nuovo
            try:
                self._ftp.rename(src, dst)
                self._aggiorna()
            except Exception as e:
                QMessageBox.critical(self, "Errore rinomina", str(e))

    def _elimina(self, nome: str, is_dir: bool):
        if not self._ftp:
            return
        risposta = QMessageBox.question(
            self, "Elimina",
            f"Eliminare {'la cartella' if is_dir else 'il file'} '{nome}'?"
        )
        if risposta != QMessageBox.StandardButton.Yes:
            return
        path = self._path_corrente.rstrip("/") + "/" + nome
        try:
            if is_dir:
                self._ftp.rmd(path)
            else:
                self._ftp.delete(path)
            self._aggiorna()
        except Exception as e:
            QMessageBox.critical(self, "Errore eliminazione", str(e))

    # ------------------------------------------------------------------
    # Menu contestuale
    # ------------------------------------------------------------------

    def _menu_contestuale(self, pos):
        item = self.lista.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #ccc; }"
            "QMenu::item:selected { background:#b87a00; color:#fff; }"
        )
        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, tuple):
                tipo, nome = data
                is_dir = tipo == "dir"
                if not is_dir:
                    menu.addAction("⬇ Scarica", lambda: self._scarica_file_singolo(nome))
                menu.addAction("✏ Rinomina", lambda: self._rinomina(nome))
                menu.addAction("🗑 Elimina", lambda: self._elimina(nome, is_dir))
                menu.addSeparator()
        menu.addAction("⬆ Carica file", self._carica_file)
        menu.addAction("📁+ Nuova cartella", self._nuova_cartella)
        menu.addSeparator()
        menu.addAction("↺ Aggiorna", self._aggiorna)
        menu.exec(self.lista.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Stato UI
    # ------------------------------------------------------------------

    def _imposta_connesso(self):
        for b in [self.btn_su, self.btn_home, self.btn_refresh,
                  self.btn_upload, self.btn_dl, self.btn_mkdir]:
            b.setEnabled(True)

    def _imposta_disconnesso(self):
        for b in [self.btn_su, self.btn_home, self.btn_refresh,
                  self.btn_upload, self.btn_dl, self.btn_mkdir]:
            b.setEnabled(False)

    def _set_status(self, msg: str):
        self.status.setText(f"  {msg}")
