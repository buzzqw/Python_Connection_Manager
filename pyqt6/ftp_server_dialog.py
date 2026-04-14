"""
ftp_server_dialog.py — Server FTP locale per PCM.
Dipendenza: pyftpdlib  (pip install pyftpdlib)
"""

import os
import threading
import socket
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QTextEdit, QSplitter, QWidget, QTabWidget, QFileDialog,
    QMessageBox, QToolButton, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QTextCursor, QPalette

try:
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer
    PYFTPDLIB_OK = True
except ImportError:
    PYFTPDLIB_OK = False


# ============================================================================
# Segnali cross-thread
# ============================================================================

class _Segnali(QObject):
    log_riga = pyqtSignal(str)
    avviato  = pyqtSignal(str)
    errore   = pyqtSignal(str)
    fermato  = pyqtSignal()


# ============================================================================
# Server FTP in threading.Thread (non QThread — evita freeze UI)
# ============================================================================

class _ServerThread(threading.Thread):

    def __init__(self, config: dict, segnali: _Segnali):
        super().__init__(daemon=True)
        self.config  = config
        self.sig     = segnali
        self._server = None
        self._stop   = threading.Event()

    def run(self):
        if not PYFTPDLIB_OK:
            self.sig.errore.emit("pyftpdlib non installato.\nInstalla con: pip install pyftpdlib")
            return
        try:
            auth = DummyAuthorizer()
            for u in self.config["utenti"]:
                perm = _calcola_permessi(u)
                if u["tipo"] == "anonymous":
                    auth.add_anonymous(u["cartella"], perm=perm)
                else:
                    auth.add_user(u["nome"], u["password"], u["cartella"], perm=perm)

            sig = self.sig

            class Handler(FTPHandler):
                def on_connect(self):
                    sig.log_riga.emit(f"[+] Connessione da {self.remote_ip}:{self.remote_port}")
                def on_disconnect(self):
                    sig.log_riga.emit(f"[-] Disconnessione {self.remote_ip}")
                def on_login(self, username):
                    sig.log_riga.emit(f"[OK] Login: {username} da {self.remote_ip}")
                def on_login_failed(self, username, password):
                    sig.log_riga.emit(f"[ERR] Login fallito: {username} da {self.remote_ip}")
                def on_logout(self, username):
                    sig.log_riga.emit(f"[->] Logout: {username}")
                def on_file_sent(self, file):
                    sig.log_riga.emit(f"[DN] Inviato: {file}")
                def on_file_received(self, file):
                    sig.log_riga.emit(f"[UP] Ricevuto: {file}")

            Handler.authorizer = auth
            Handler.passive_ports = range(self.config["pasv_min"], self.config["pasv_max"] + 1)
            Handler.masquerade_address = self.config.get("masquerade") or None
            Handler.permit_foreign_addresses = True
            Handler.banner = "PCM FTP Server pronto."
            Handler.timeout = 300

            self._server = FTPServer(("0.0.0.0", self.config["porta"]), Handler)
            self._server.max_cons = 50

            ip = _ip_locale()
            self.sig.avviato.emit(f"{ip}:{self.config['porta']}")
            self.sig.log_riga.emit(
                f"[START] Server FTP avviato su 0.0.0.0:{self.config['porta']} "
                f"— raggiungibile come {ip}:{self.config['porta']}"
            )
            for u in self.config["utenti"]:
                nome = "anonymous" if u["tipo"] == "anonymous" else u["nome"]
                self.sig.log_riga.emit(
                    f"    Utente: {nome}  ->  {u['cartella']}  [perm: {_calcola_permessi(u)}]"
                )

            # Loop non-bloccante: ogni 0.5s controlla _stop
            while not self._stop.is_set():
                self._server.serve_forever(timeout=0.5, blocking=False)

        except Exception as e:
            self.sig.errore.emit(str(e))
        finally:
            try:
                if self._server:
                    self._server.close_all()
            except Exception:
                pass
            self.sig.fermato.emit()

    def ferma(self):
        self._stop.set()


# ============================================================================
# Dialog principale
# ============================================================================

class FtpServerDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server FTP locale — PCM")
        self.setMinimumSize(860, 700)
        self.resize(980, 820)
        self.setModal(False)

        self._server_thread: _ServerThread | None = None
        self._in_esecuzione = False
        self._dati_utenti: list[dict] = []
        self._caricamento = False   # blocca _toggle_anon durante reload campi

        self._sig = _Segnali()
        self._sig.log_riga.connect(self._log)
        self._sig.avviato.connect(self._on_avviato)
        self._sig.errore.connect(self._on_errore)
        self._sig.fermato.connect(self._on_fermato)

        self._init_ui()
        self._reset_campi()   # pannello destra abilitato e vuoto all'avvio

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        hdr = QLabel("  Server FTP locale")
        hdr.setStyleSheet("color:#4e7abc; font-size:14px; font-weight:bold; padding:8px;")
        root.addWidget(hdr)

        splitter = QSplitter(Qt.Orientation.Vertical)

        cfg = QWidget()
        cfg_lay = QVBoxLayout(cfg)
        cfg_lay.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_tab_utenti(),       "Utenti")
        self.tabs.addTab(self._build_tab_impostazioni(), "Impostazioni")
        cfg_lay.addWidget(self.tabs)
        splitter.addWidget(cfg)

        log_w = QWidget()
        log_lay = QVBoxLayout(log_w)
        log_lay.setContentsMargins(0, 0, 0, 0)
        log_lay.setSpacing(2)

        log_hdr = QLabel("  Log connessioni")
        log_hdr.setFixedHeight(22)
        log_hdr.setStyleSheet(
            "background:#f0f0f0; color:#555; font-size:11px; font-weight:bold;"
            "padding:0 6px; border-top:1px solid #ccc; border-bottom:1px solid #ccc;"
        )
        log_lay.addWidget(log_hdr)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Monospace", 10))
        self.log_view.setStyleSheet("background:#1e1e1e; color:#cccccc; border:none;")
        log_lay.addWidget(self.log_view)

        btn_pulisci = QPushButton("Pulisci log")
        btn_pulisci.setFixedHeight(22)
        btn_pulisci.clicked.connect(self.log_view.clear)
        log_lay.addWidget(btn_pulisci)

        splitter.addWidget(log_w)
        splitter.setSizes([460, 200])
        root.addWidget(splitter, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        bottom = QHBoxLayout()

        self.lbl_stato = QLabel("  Server fermo")
        self.lbl_stato.setStyleSheet("color:#888; font-size:12px; font-weight:bold; padding:4px;")
        bottom.addWidget(self.lbl_stato, 1)

        self.btn_avvia = QPushButton("Avvia server")
        self.btn_avvia.setFixedHeight(34)
        self.btn_avvia.setStyleSheet(self._css_btn_verde())
        self.btn_avvia.clicked.connect(self._toggle_server)
        bottom.addWidget(self.btn_avvia)

        btn_chiudi = QPushButton("Chiudi")
        btn_chiudi.setFixedHeight(34)
        btn_chiudi.clicked.connect(self._chiudi_dialog)
        bottom.addWidget(btn_chiudi)

        root.addLayout(bottom)

    # ------------------------------------------------------------------
    # Tab Utenti
    # ------------------------------------------------------------------

    def _build_tab_utenti(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setSpacing(8)

        # --- Sinistra: lista ---
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(QLabel("Utenti configurati:"))

        self.lista = QTableWidget(0, 2)
        self.lista.setHorizontalHeaderLabels(["Nome", "Tipo"])
        self.lista.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lista.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.lista.verticalHeader().setVisible(False)
        self.lista.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lista.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lista.setMaximumWidth(230)
        self.lista.itemSelectionChanged.connect(self._on_selezione)
        left.addWidget(self.lista, 1)

        btn_row = QHBoxLayout()
        btn_del = QPushButton("Rimuovi selezionato")
        btn_del.clicked.connect(self._rimuovi)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        left.addLayout(btn_row)
        layout.addLayout(left)

        # --- Destra: dettagli ---
        self._pannello = QWidget()
        right = QVBoxLayout(self._pannello)
        right.setSpacing(8)

        grp_id = QGroupBox("Identita'")
        id_lay = QFormLayout(grp_id)
        id_lay.setSpacing(8)
        self.chk_anon = QCheckBox("Utente anonimo (anonymous)")
        self.chk_anon.toggled.connect(self._toggle_anon)
        id_lay.addRow("", self.chk_anon)
        self.edit_nome = QLineEdit()
        self.edit_nome.setPlaceholderText("nome utente")
        self.edit_nome.textChanged.connect(self._aggiorna_dict_realtime)
        id_lay.addRow("Nome utente:", self.edit_nome)
        self.edit_pwd = QLineEdit()
        self.edit_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_pwd.setPlaceholderText("password")
        self.edit_pwd.textChanged.connect(self._aggiorna_dict_realtime)
        id_lay.addRow("Password:", self.edit_pwd)
        right.addWidget(grp_id)

        grp_dir = QGroupBox("Cartella radice")
        dir_lay = QHBoxLayout(grp_dir)
        self.edit_cartella = QLineEdit()
        self.edit_cartella.setText(os.path.expanduser("~"))
        self.edit_cartella.textChanged.connect(self._aggiorna_dict_realtime)
        btn_sf = QPushButton("...")
        btn_sf.setMaximumWidth(36)
        btn_sf.clicked.connect(self._sfoglia)
        dir_lay.addWidget(self.edit_cartella)
        dir_lay.addWidget(btn_sf)
        right.addWidget(grp_dir)

        grp_perm = QGroupBox("Permessi")
        perm_lay = QVBoxLayout(grp_perm)
        perm_lay.setSpacing(4)

        perm_lay.addWidget(QLabel("Preset rapidi:"))
        pre_row = QHBoxLayout()
        pre_row.setSpacing(6)
        for testo, slot in [("Sola lettura", self._pre_read),
                             ("Lettura + scrittura", self._pre_rw),
                             ("Tutto", self._pre_all)]:
            b = QPushButton(testo)
            b.setFixedHeight(26)
            pal = b.palette()
            pal.setColor(QPalette.ColorRole.Button,     QColor("#d0d0d0"))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor("#111111"))
            b.setPalette(pal)
            b.setAutoFillBackground(True)
            b.clicked.connect(slot)
            pre_row.addWidget(b)
        pre_row.addStretch()
        perm_lay.addLayout(pre_row)

        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
        perm_lay.addWidget(f)

        self.chk_leggi    = QCheckBox("Lettura file (scarica)")
        self.chk_scrivi   = QCheckBox("Scrittura file (carica)")
        self.chk_cancella = QCheckBox("Cancellazione file e cartelle")
        self.chk_mkdir    = QCheckBox("Crea cartelle")
        self.chk_list     = QCheckBox("Elenca contenuto cartelle")
        self.chk_rinomina = QCheckBox("Rinomina file e cartelle")
        for c in [self.chk_leggi, self.chk_scrivi, self.chk_cancella,
                  self.chk_mkdir, self.chk_list, self.chk_rinomina]:
            c.toggled.connect(self._aggiorna_dict_realtime)
            perm_lay.addWidget(c)
        right.addWidget(grp_perm)

        self.btn_salva = QPushButton("Aggiungi / Salva modifiche utente")
        self.btn_salva.setFixedHeight(32)
        self.btn_salva.setStyleSheet(
            "QPushButton{background:#4e7abc;color:#fff;border-radius:3px;"
            "font-size:12px;font-weight:bold;}"
            "QPushButton:hover{background:#5a8fd1;}"
        )
        self.btn_salva.clicked.connect(self._salva)
        right.addWidget(self.btn_salva)
        right.addStretch()

        layout.addWidget(self._pannello, 1)
        return w

    # ------------------------------------------------------------------
    # Tab Impostazioni
    # ------------------------------------------------------------------

    def _build_tab_impostazioni(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(10)
        lay.setContentsMargins(12, 15, 12, 10)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spin_porta = QSpinBox()
        self.spin_porta.setRange(1, 65535)
        self.spin_porta.setValue(2121)
        self.spin_porta.setMaximumWidth(90)
        lay.addRow("Porta FTP:", self.spin_porta)

        nota = QLabel("Porta 21 richiede root. Usa 2121 o altra porta > 1024.")
        nota.setStyleSheet("color:#888; font-size:10px;")
        lay.addRow("", nota)

        self.spin_pasv_min = QSpinBox()
        self.spin_pasv_min.setRange(1024, 65000)
        self.spin_pasv_min.setValue(60000)
        self.spin_pasv_min.setMaximumWidth(90)
        lay.addRow("Porte passive (min):", self.spin_pasv_min)

        self.spin_pasv_max = QSpinBox()
        self.spin_pasv_max.setRange(1025, 65535)
        self.spin_pasv_max.setValue(60100)
        self.spin_pasv_max.setMaximumWidth(90)
        lay.addRow("Porte passive (max):", self.spin_pasv_max)

        self.edit_masq = QLineEdit()
        self.edit_masq.setPlaceholderText("es. 1.2.3.4 (solo se dietro NAT con IP pubblico fisso)")
        lay.addRow("Masquerade IP:", self.edit_masq)

        info = QLabel(
            "<b>Come connettersi:</b><br>"
            "Da questa macchina: <tt>ftp://localhost:2121</tt><br>"
            "Da rete locale: <tt>ftp://&lt;tuo-IP&gt;:2121</tt>"
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#eef3fa;border:1px solid #b8cfe8;border-radius:4px;"
            "padding:8px;font-size:11px;color:#333;margin-top:8px;"
        )
        lay.addRow(info)
        return w

    # ------------------------------------------------------------------
    # Gestione utenti
    # ------------------------------------------------------------------

    def _reset_campi(self):
        """Pannello destra abilitato con valori di default.
        Deseleziona la lista: il prossimo click su Salva creera' un nuovo utente."""
        self.lista.clearSelection()
        self._pannello.setEnabled(True)
        self._caricamento = True
        self.chk_anon.setChecked(False)
        self._caricamento = False
        self.edit_nome.setEnabled(True)
        self.edit_pwd.setEnabled(True)
        self.edit_nome.clear()
        self.edit_pwd.clear()
        self.edit_cartella.setText(os.path.expanduser("~"))
        self.chk_leggi.setChecked(True)
        self.chk_scrivi.setChecked(False)
        self.chk_cancella.setChecked(False)
        self.chk_mkdir.setChecked(False)
        self.chk_list.setChecked(True)
        self.chk_rinomina.setChecked(False)

    def _aggiungi(self):
        """Aggiunge un nuovo slot vuoto e prepara i campi per la compilazione."""
        nuovo = {
            "tipo": "utente", "nome": "", "password": "",
            "cartella": os.path.expanduser("~"),
            "perm_leggi": True, "perm_scrivi": True,
            "perm_cancella": False, "perm_mkdir": True,
            "perm_list": True, "perm_rinomina": False,
        }
        self._dati_utenti.append(nuovo)
        nuovo_idx = len(self._dati_utenti) - 1

        # Aggiunge riga nella tabella bloccando _on_selezione
        sm = self.lista.selectionModel()
        sm.blockSignals(True)
        self.lista.insertRow(nuovo_idx)
        item_n = QTableWidgetItem("(nuovo utente)")
        item_n.setForeground(QColor("#aaa"))
        self.lista.setItem(nuovo_idx, 0, item_n)
        self.lista.setItem(nuovo_idx, 1, QTableWidgetItem("Utente"))
        self.lista.setCurrentCell(nuovo_idx, 0)
        sm.blockSignals(False)

        # Resetta i campi per il nuovo utente — il dict si aggiornerà in real-time
        self._pannello.setEnabled(True)
        self._caricamento = True
        self.chk_anon.setChecked(False)
        self._caricamento = False
        self.edit_nome.setEnabled(True)
        self.edit_pwd.setEnabled(True)
        self.edit_nome.clear()
        self.edit_pwd.clear()
        self.edit_cartella.setText(os.path.expanduser("~"))
        self.chk_leggi.setChecked(True)
        self.chk_scrivi.setChecked(True)
        self.chk_cancella.setChecked(False)
        self.chk_mkdir.setChecked(True)
        self.chk_list.setChecked(True)
        self.chk_rinomina.setChecked(False)
        self.edit_nome.setFocus()

    def _rimuovi(self):
        r = self.lista.currentRow()
        if r < 0:
            return
        del self._dati_utenti[r]
        if self._dati_utenti:
            self._rebuild(seleziona=max(0, r - 1))
        else:
            self._rebuild()
            self._reset_campi()

    def _on_selezione(self):
        r = self.lista.currentRow()
        if r < 0 or r >= len(self._dati_utenti):
            return
        u = self._dati_utenti[r]
        self._pannello.setEnabled(True)
        # Blocca il toggle per non disabilitare i campi durante il caricamento
        self._caricamento = True
        self.chk_anon.setChecked(u["tipo"] == "anonymous")
        self._caricamento = False
        is_anon = u["tipo"] == "anonymous"
        self.edit_nome.setEnabled(not is_anon)
        self.edit_pwd.setEnabled(not is_anon)
        self.edit_nome.setText("" if is_anon else u.get("nome", ""))
        self.edit_pwd.setText(u.get("password", ""))
        self.edit_cartella.setText(u.get("cartella", os.path.expanduser("~")))
        self.chk_leggi.setChecked(u.get("perm_leggi", True))
        self.chk_scrivi.setChecked(u.get("perm_scrivi", False))
        self.chk_cancella.setChecked(u.get("perm_cancella", False))
        self.chk_mkdir.setChecked(u.get("perm_mkdir", False))
        self.chk_list.setChecked(u.get("perm_list", True))
        self.chk_rinomina.setChecked(u.get("perm_rinomina", False))

    def _aggiorna_dict_realtime(self, *args):
        """Aggiorna il dict in tempo reale ad ogni modifica dei campi UI.
        Nessuna azione se non c'e' un utente selezionato o se siamo in caricamento."""
        if self._caricamento:
            return
        r = self.lista.currentRow()
        if r < 0 or r >= len(self._dati_utenti):
            return
        u = self._dati_utenti[r]
        u["tipo"]        = "anonymous" if self.chk_anon.isChecked() else "utente"
        u["nome"]        = "anonymous" if u["tipo"] == "anonymous"                            else self.edit_nome.text().strip()
        u["password"]    = self.edit_pwd.text()
        cartella         = self.edit_cartella.text().strip()
        if os.path.isdir(cartella):
            u["cartella"] = cartella
        u["perm_leggi"]    = self.chk_leggi.isChecked()
        u["perm_scrivi"]   = self.chk_scrivi.isChecked()
        u["perm_cancella"] = self.chk_cancella.isChecked()
        u["perm_mkdir"]    = self.chk_mkdir.isChecked()
        u["perm_list"]     = self.chk_list.isChecked()
        u["perm_rinomina"] = self.chk_rinomina.isChecked()
        # Aggiorna il nome nella lista in tempo reale
        nome_disp = u["nome"] if u["nome"] else "(nuovo utente)"
        colore    = QColor("#111") if u["nome"] else QColor("#aaa")
        item = self.lista.item(r, 0)
        if item:
            item.setText(nome_disp)
            item.setForeground(colore)

    def _toggle_anon(self, checked: bool):
        if self._caricamento:
            return
        self.edit_nome.setEnabled(not checked)
        self.edit_pwd.setEnabled(not checked)
        if checked:
            self.edit_nome.clear()

    def _leggi_campi_in_dict(self, row: int) -> bool:
        """Legge i campi UI e li salva nel dict. Restituisce False se cartella non valida."""
        if row < 0 or row >= len(self._dati_utenti):
            return False
        cartella = self.edit_cartella.text().strip()
        if not os.path.isdir(cartella):
            return False
        u = self._dati_utenti[row]
        u["tipo"]        = "anonymous" if self.chk_anon.isChecked() else "utente"
        u["nome"]        = "anonymous" if u["tipo"] == "anonymous" \
                           else self.edit_nome.text().strip()
        u["password"]    = self.edit_pwd.text()
        u["cartella"]    = cartella
        u["perm_leggi"]    = self.chk_leggi.isChecked()
        u["perm_scrivi"]   = self.chk_scrivi.isChecked()
        u["perm_cancella"] = self.chk_cancella.isChecked()
        u["perm_mkdir"]    = self.chk_mkdir.isChecked()
        u["perm_list"]     = self.chk_list.isChecked()
        u["perm_rinomina"] = self.chk_rinomina.isChecked()
        return True

    def _salva(self):
        """Aggiungi / Salva modifiche utente.
        - Nessuna riga selezionata → crea nuovo utente coi campi compilati
        - Riga selezionata → aggiorna quell'utente
        Il dict e' aggiornato in real-time, qui facciamo validazione + feedback.
        """
        # Validazione comune
        is_anon = self.chk_anon.isChecked()
        nome    = self.edit_nome.text().strip()
        cartella = self.edit_cartella.text().strip()

        if not is_anon and not nome:
            QMessageBox.warning(self, "Nome mancante",
                                "Inserisci un nome utente.")
            self.edit_nome.setFocus()
            return
        if not os.path.isdir(cartella):
            QMessageBox.warning(self, "Cartella non valida",
                                "Seleziona una cartella esistente.")
            self.edit_cartella.setFocus()
            return

        r = self.lista.currentRow()

        if r < 0 or r >= len(self._dati_utenti):
            # ── Nessuna selezione: CREA NUOVO utente ──────────────────
            nuovo = {
                "tipo":        "anonymous" if is_anon else "utente",
                "nome":        "anonymous" if is_anon else nome,
                "password":    self.edit_pwd.text(),
                "cartella":    cartella,
                "perm_leggi":    self.chk_leggi.isChecked(),
                "perm_scrivi":   self.chk_scrivi.isChecked(),
                "perm_cancella": self.chk_cancella.isChecked(),
                "perm_mkdir":    self.chk_mkdir.isChecked(),
                "perm_list":     self.chk_list.isChecked(),
                "perm_rinomina": self.chk_rinomina.isChecked(),
            }
            self._dati_utenti.append(nuovo)
            sm = self.lista.selectionModel()
            sm.blockSignals(True)
            self._rebuild(seleziona=len(self._dati_utenti) - 1)
            sm.blockSignals(False)
            self._flash(len(self._dati_utenti) - 1)
        else:
            # ── Riga selezionata: AGGIORNA utente esistente ────────────
            # Il dict è già aggiornato in real-time, rebuild e flash
            sm = self.lista.selectionModel()
            sm.blockSignals(True)
            self._rebuild(seleziona=r)
            sm.blockSignals(False)
            self._flash(r)

    def _rebuild(self, seleziona: int = -1):
        self.lista.setRowCount(0)
        for u in self._dati_utenti:
            r = self.lista.rowCount()
            self.lista.insertRow(r)
            if u["tipo"] == "anonymous":
                nd, nc = "anonymous", QColor("#555")
                td = "Anonimo"
            elif u.get("nome"):
                nd, nc = u["nome"], QColor("#111")
                td = "Utente"
            else:
                nd, nc = "(nuovo utente)", QColor("#aaa")
                td = "Utente"
            item_n = QTableWidgetItem(nd)
            item_n.setForeground(nc)
            self.lista.setItem(r, 0, item_n)
            self.lista.setItem(r, 1, QTableWidgetItem(td))
        if 0 <= seleziona < self.lista.rowCount():
            self.lista.setCurrentCell(seleziona, 0)

    def _flash(self, row: int):
        if row >= self.lista.rowCount():
            return
        c = QColor("#d4edda")
        for col in range(self.lista.columnCount()):
            item = self.lista.item(row, col)
            if item:
                item.setBackground(c)
        QTimer.singleShot(800, lambda: self._reset_flash(row))

    def _reset_flash(self, row: int):
        if row < self.lista.rowCount():
            for col in range(self.lista.columnCount()):
                item = self.lista.item(row, col)
                if item:
                    item.setBackground(QColor("transparent"))

    def _sfoglia(self):
        d = QFileDialog.getExistingDirectory(
            self, "Seleziona cartella radice FTP",
            self.edit_cartella.text() or os.path.expanduser("~")
        )
        if d:
            self.edit_cartella.setText(d)

    # ------------------------------------------------------------------
    # Preset permessi
    # ------------------------------------------------------------------

    def _pre_read(self):
        self.chk_leggi.setChecked(True);   self.chk_list.setChecked(True)
        self.chk_scrivi.setChecked(False);  self.chk_cancella.setChecked(False)
        self.chk_mkdir.setChecked(False);   self.chk_rinomina.setChecked(False)

    def _pre_rw(self):
        self.chk_leggi.setChecked(True);   self.chk_list.setChecked(True)
        self.chk_scrivi.setChecked(True);  self.chk_mkdir.setChecked(True)
        self.chk_cancella.setChecked(False); self.chk_rinomina.setChecked(False)

    def _pre_all(self):
        for c in [self.chk_leggi, self.chk_scrivi, self.chk_cancella,
                  self.chk_mkdir, self.chk_list, self.chk_rinomina]:
            c.setChecked(True)

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------

    def _toggle_server(self):
        if self._in_esecuzione:
            self._ferma()
        else:
            self._avvia()

    def _avvia(self):
        if not PYFTPDLIB_OK:
            QMessageBox.critical(self, "Dipendenza mancante",
                "pyftpdlib non e' installato.\n\n"
                "Installa con:  pip install pyftpdlib")
            return

        # Salva utente corrente
        # Validazione (il dict e' sempre aggiornato in real-time)
        if not self._dati_utenti:
            QMessageBox.warning(self, "Nessun utente",
                "Aggiungi almeno un utente prima di avviare il server.")
            return
        for i, u in enumerate(self._dati_utenti):
            if u["tipo"] == "utente" and not u.get("nome"):
                QMessageBox.warning(self, "Nome mancante",
                    f"L'utente #{i+1} non ha un nome.")
                self.lista.setCurrentCell(i, 0)
                self.edit_nome.setFocus()
                return
            if not os.path.isdir(u.get("cartella", "")):
                QMessageBox.warning(self, "Cartella non valida",
                    f"Cartella non valida per '{u.get('nome', '#'+str(i+1))}'.")
                self.lista.setCurrentCell(i, 0)
                return
        if self.spin_pasv_min.value() >= self.spin_pasv_max.value():
            QMessageBox.warning(self, "Porte passive",
                "Range porte passive non valido.")
            return

        config = {
            "porta":     self.spin_porta.value(),
            "pasv_min":  self.spin_pasv_min.value(),
            "pasv_max":  self.spin_pasv_max.value(),
            "masquerade": self.edit_masq.text().strip(),
            "utenti":    list(self._dati_utenti),
        }

        self._log(f"Avvio server FTP su porta {config['porta']}...")
        self._server_thread = _ServerThread(config, self._sig)
        self._server_thread.start()

        self.tabs.setEnabled(False)
        self.btn_avvia.setEnabled(False)
        self.btn_avvia.setText("Avvio in corso...")

    def _ferma(self):
        self._log("Arresto server in corso...")
        self.btn_avvia.setEnabled(False)
        if self._server_thread:
            self._server_thread.ferma()

    def _on_avviato(self, indirizzo: str):
        self._in_esecuzione = True
        self.lbl_stato.setText(f"  SERVER IN ESECUZIONE  —  ftp://{indirizzo}")
        self.lbl_stato.setStyleSheet(
            "color:#ffffff; font-size:12px; font-weight:bold; padding:6px 10px;"
            "background:#2d7a2d; border-radius:4px;"
        )
        self.btn_avvia.setText("FERMA SERVER")
        self.btn_avvia.setEnabled(True)
        self.btn_avvia.setStyleSheet(
            "QPushButton{background:#c0392b;color:#fff;border-radius:4px;"
            "font-size:13px;font-weight:bold;padding:0 16px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )

    def _on_fermato(self):
        self._in_esecuzione = False
        self._server_thread = None
        self.tabs.setEnabled(True)
        self.lbl_stato.setText("  Server fermo")
        self.lbl_stato.setStyleSheet("color:#888; font-size:12px; font-weight:bold; padding:4px;")
        self.btn_avvia.setText("Avvia server")
        self.btn_avvia.setEnabled(True)
        self.btn_avvia.setStyleSheet(self._css_btn_verde())
        self._log("Server FTP fermato.")

    def _on_errore(self, msg: str):
        self._log(f"ERRORE: {msg}")
        QMessageBox.critical(self, "Errore server FTP", msg)
        self._on_fermato()

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    def _log(self, testo: str):
        ts = datetime.now().strftime("%H:%M:%S")
        colore = "#cccccc"
        if "[OK]" in testo or "[START]" in testo:
            colore = "#4ec9b0"
        elif "[ERR]" in testo:
            colore = "#f48771"
        elif "[+]" in testo:
            colore = "#9cdcfe"
        elif "[-]" in testo or "[->]" in testo:
            colore = "#888888"
        elif "[UP]" in testo or "[DN]" in testo:
            colore = "#c3e88d"
        riga = f"<span style='color:#666;'>[{ts}]</span> <span style='color:{colore};'>{testo}</span>"
        self.log_view.append(riga)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _css_btn_verde():
        return (
            "QPushButton{background:#2d7a2d;color:#fff;border-radius:4px;"
            "font-size:13px;font-weight:bold;padding:0 16px;}"
            "QPushButton:hover{background:#3a9e3a;}"
            "QPushButton:disabled{background:#888;}"
        )

    def _chiudi_dialog(self):
        if self._in_esecuzione:
            if QMessageBox.question(
                self, "Server in esecuzione",
                "Il server FTP e' in esecuzione.\nVuoi fermarlo e chiudere?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return
            self._ferma()
            QTimer.singleShot(800, self.accept)
        else:
            self.accept()

    def closeEvent(self, event):
        if self._in_esecuzione:
            self._ferma()
        super().closeEvent(event)


# ============================================================================
# Utility globali
# ============================================================================

def _calcola_permessi(u: dict) -> str:
    p = ""
    if u.get("perm_list",     True):  p += "el"
    if u.get("perm_leggi",    True):  p += "r"
    if u.get("perm_scrivi",   False): p += "w"
    if u.get("perm_cancella", False): p += "d"
    if u.get("perm_mkdir",    False): p += "m"
    if u.get("perm_rinomina", False): p += "f"
    return p or "el"


def _ip_locale() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
