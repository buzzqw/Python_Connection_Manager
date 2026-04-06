"""
session_dialog.py - Dialog di creazione/modifica sessioni PCM
Supporta tutti i protocolli con tab specifici per le impostazioni avanzate.
"""

import os
import shutil
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QWidget, QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QDialogButtonBox, QFileDialog, QSpinBox, QGroupBox, QGridLayout,
    QTextEdit, QSizePolicy, QFrame, QToolButton,
    QMessageBox, QListWidget, QListWidgetItem, QInputDialog, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette
from PyQt6.QtWidgets import QScrollArea

from themes import TERMINAL_THEMES

# ---------------------------------------------------------------------------
# Percorso assoluto cartella icons (risolve il problema CWD)
# ---------------------------------------------------------------------------

_HERE      = os.path.dirname(os.path.abspath(__file__))
_ICONS_DIR = os.path.join(_HERE, "icons")
_ICON_CACHE: dict = {}


def _icon(filename: str) -> QIcon:
    """Carica SVG/PNG con percorso assoluto; restituisce QIcon vuota se mancante."""
    if filename in _ICON_CACHE:
        return _ICON_CACHE[filename]
    path = os.path.join(_ICONS_DIR, filename)
    ico  = QIcon(path) if os.path.isfile(path) else QIcon()
    _ICON_CACHE[filename] = ico
    return ico


PROTOCOLLI = ["ssh", "telnet", "sftp", "ftp", "rdp", "vnc", "ssh_tunnel", "mosh", "serial"]

PROTO_LABEL = {
    "ssh":        "SSH",
    "telnet":     "Telnet",
    "sftp":       "SFTP",
    "ftp":        "FTP / FTPS",
    "rdp":        "RDP",
    "vnc":        "VNC",
    "ssh_tunnel": "SSH Tunnel",
    "mosh":       "Mosh",
    "serial":     "Seriale",
}

PROTO_ICON = {
    "ssh":        "ssh.png",
    "telnet":     "network.png",
    "sftp":       "folder.png",
    "ftp":        "folder.png",
    "rdp":        "monitor.png",
    "vnc":        "vnc.png",
    "ssh_tunnel": "tunnel.png",
    "mosh":       "flash.png",
    "serial":     "cable.png",
}


class SessionDialog(QDialog):
    """
    Dialog per creare o modificare una sessione.
    Adatta i campi visibili al protocollo selezionato.
    """

    def __init__(self, parent=None, nome="", dati=None):
        super().__init__(parent)
        self._nome_originale = nome
        self._dati_originali = dati or {}

        self.setWindowTitle("Nuova sessione" if not nome else f"Modifica: {nome}")
        self.setMinimumSize(720, 600)
        self.resize(770, 660)
        self.setModal(True)

        # ── Palette chiara (sovrascrive tema dark globale) ──────────────
        p = QPalette()
        p.setColor(QPalette.ColorRole.Window,          QColor("#f5f5f5"))
        p.setColor(QPalette.ColorRole.WindowText,      QColor("#111111"))
        p.setColor(QPalette.ColorRole.Base,            QColor("#ffffff"))
        p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#ececec"))
        p.setColor(QPalette.ColorRole.Text,            QColor("#111111"))
        p.setColor(QPalette.ColorRole.Button,          QColor("#e0e0e0"))
        p.setColor(QPalette.ColorRole.ButtonText,      QColor("#111111"))
        p.setColor(QPalette.ColorRole.Highlight,       QColor("#0078d4"))
        p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(p)
        self.setStyleSheet(
            "QDialog, QWidget { background:#f5f5f5; color:#111111; }"
            "QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {"
            "  background:#ffffff; color:#111111; border:1px solid #aaaaaa;"
            "  border-radius:3px; padding:2px 4px; }"
            "QComboBox QAbstractItemView {"
            "  background:#ffffff; color:#111111; min-width:200px; }"
            "QLabel { color:#111111; }"
            "QCheckBox { color:#111111; spacing:6px; }"
            "QCheckBox::indicator { width:15px; height:15px;"
            "  border:2px solid #aaaaaa; border-radius:3px; background:#ffffff; }"
            "QCheckBox::indicator:hover { border-color:#0078d4; background:#e8f0fe; }"
            "QCheckBox::indicator:checked { background:#0078d4; border-color:#0057a8; }"
            "QCheckBox::indicator:checked:hover { background:#006cbf; }"
            "QGroupBox { color:#333333; border:1px solid #cccccc; border-radius:4px;"
            "  margin-top:6px; padding-top:8px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; color:#333333; }"
            "QTabWidget::pane { border:1px solid #cccccc; }"
            "QTabBar::tab { background:#e0e0e0; color:#333333; padding:5px 12px;"
            "  border:1px solid #cccccc; border-bottom:none;"
            "  border-radius:3px 3px 0 0; }"
            "QTabBar::tab:selected { background:#ffffff; color:#111111; font-weight:bold; }"
            "QTabBar::tab:hover { background:#d0d0d0; }"
            "QPushButton { background:#e0e0e0; color:#111111; border:1px solid #aaaaaa;"
            "  border-radius:3px; padding:4px 12px; }"
            "QPushButton:hover { background:#c8c8c8; }"
            "QPushButton:pressed { background:#b0b0b0; }"
            "QScrollArea { border:none; background:#f5f5f5; }"
        )
        # ────────────────────────────────────────────────────────────────

        self._init_ui()
        if nome and dati:
            self._popola(nome, dati)

    # ------------------------------------------------------------------
    # UI principale
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # --- Nome sessione + protocollo ---
        top = QFormLayout()
        top.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        top.setSpacing(8)

        self.edit_nome = QLineEdit()
        self.edit_nome.setPlaceholderText("es. Server produzione")
        lbl_nome = QLabel("Nome sessione:")
        lbl_nome.setMinimumWidth(115)  # <-- Forza la larghezza
        top.addRow(lbl_nome, self.edit_nome)

        self.combo_gruppo = QComboBox()
        self.combo_gruppo.setEditable(True)
        self.combo_gruppo.setPlaceholderText("es. Lavoro, Casa (vuoto = radice)")
        self._carica_gruppi_esistenti()
        lbl_gruppo = QLabel("Gruppo:")
        lbl_gruppo.setMinimumWidth(115)
        top.addRow(lbl_gruppo, self.combo_gruppo)

        self.combo_proto = QComboBox()
        self.combo_proto.setMinimumWidth(200)
        for k, v in PROTO_LABEL.items():
            self.combo_proto.addItem(_icon(PROTO_ICON.get(k, "terminal.png")), v, k)
        self.combo_proto.currentIndexChanged.connect(self._aggiorna_tab)
        lbl_proto = QLabel("Protocollo:")
        lbl_proto.setMinimumWidth(115) # <-- Forza la larghezza
        top.addRow(lbl_proto, self.combo_proto)

        root.addLayout(top)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#555;")
        root.addWidget(sep)

        # --- Tab avanzate ---
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # Tab Connessione: avvolto in QScrollArea per evitare troncature
        # quando i GroupBox specifici per protocollo sono grandi
        self._scroll_conn = QScrollArea()
        self._scroll_conn.setWidgetResizable(True)
        self._scroll_conn.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tab_conn = QWidget()
        self._scroll_conn.setWidget(self.tab_conn)
        self.tabs.addTab(self._scroll_conn, _icon("connection.png"), "Connessione")
        self._build_tab_connessione()

        # Tab: Autenticazione
        self.tab_auth = QWidget()
        self.tabs.addTab(self.tab_auth, _icon("key.png"), "Autenticazione")
        self._build_tab_autenticazione()

        # Tab: Terminale
        self.tab_term = QWidget()
        self.tabs.addTab(self.tab_term, _icon("terminal.png"), "Terminale")
        self._build_tab_terminale()

        # Tab: Avanzate
        self.tab_adv = QWidget()
        self.tabs.addTab(self.tab_adv, _icon("settings.png"), "⚙ Avanzate")
        self._build_tab_avanzate()

        # Tab: Note
        self.tab_note = QWidget()
        self.tabs.addTab(self.tab_note, _icon("notes.png"), "📝 Note")
        self._build_tab_note()

        # Tab: Macro
        self.tab_macro = QWidget()
        self.tabs.addTab(self.tab_macro, _icon("flash.png"), "⚡ Macro")
        self._build_tab_macro()

        # --- Pulsanti OK / Annulla ---
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._valida_e_accetta)
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)

        self._aggiorna_tab()

    # ------------------------------------------------------------------
    # Tab Connessione
    # ------------------------------------------------------------------
    
    def _carica_gruppi_esistenti(self):
        """Legge i profili salvati e popola la tendina con i gruppi esistenti."""
        import config_manager
        profili = config_manager.load_profiles()
        gruppi = set()
        for dati in profili.values():
            g = dati.get("group", "").strip()
            if g:
                gruppi.add(g)
        self.combo_gruppo.addItems(sorted(list(gruppi)))
        self.combo_gruppo.setCurrentText("")

    # ------------------------------------------------------------------
    # Tab Connessione
    # ------------------------------------------------------------------

    

    def _build_tab_connessione(self):
        layout = QFormLayout(self.tab_conn)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 15, 12, 10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.edit_host = QLineEdit()
        self.edit_host.setPlaceholderText("hostname o IP")
        lbl_host = QLabel("Host:")
        lbl_host.setMinimumWidth(115) # <-- Stessa larghezza fissa di sopra
        layout.addRow(lbl_host, self.edit_host)

        self.edit_port = QLineEdit()
        self.edit_port.setMaximumWidth(80)
        lbl_port = QLabel("Porta:")
        lbl_port.setMinimumWidth(115)
        layout.addRow(lbl_port, self.edit_port)

        self.edit_user = QLineEdit()
        self.edit_user.setPlaceholderText("nome utente")
        lbl_user = QLabel("Utente:")
        lbl_user.setMinimumWidth(115)
        layout.addRow(lbl_user, self.edit_user)

        # --- Campi specifici RDP ---
        self.grp_rdp = QGroupBox("Opzioni RDP")
        rdp_layout = QFormLayout(self.grp_rdp)
        self.combo_rdp_client = QComboBox()
        self.combo_rdp_client.addItems(["xfreerdp3", "xfreerdp", "rdesktop"])
        rdp_layout.addRow("Client RDP:", self.combo_rdp_client)
        self.chk_rdp_fs = QCheckBox("Schermo intero")
        self.chk_rdp_fs.setChecked(True)
        rdp_layout.addRow("", self.chk_rdp_fs)
        self.chk_rdp_clip = QCheckBox("Condividi clipboard")
        self.chk_rdp_clip.setChecked(True)
        rdp_layout.addRow("", self.chk_rdp_clip)
        self.chk_rdp_drives = QCheckBox("Condividi cartelle locali")
        rdp_layout.addRow("", self.chk_rdp_drives)
        layout.addRow(self.grp_rdp)

        # --- Campi specifici VNC ---
        self.grp_vnc = QGroupBox("Opzioni VNC")
        vnc_layout = QFormLayout(self.grp_vnc)
        
        # AGGIUNTA OPZIONE VNC INTEGRATO
        self.chk_vnc_internal = QCheckBox("Integra VNC in una scheda di PCM")
        self.chk_vnc_internal.setChecked(True)
        vnc_layout.addRow("", self.chk_vnc_internal)

        self.combo_vnc_client = QComboBox()
        self.combo_vnc_client.addItems(["vncviewer", "realvnc-viewer", "tigervnc", "remmina", "krdc"])
        vnc_layout.addRow("Client VNC esterno:", self.combo_vnc_client)
        self.combo_vnc_color = QComboBox()
        self.combo_vnc_color.addItems(["Truecolor (32 bpp)", "Highcolor (16 bpp)", "256 colori"])
        vnc_layout.addRow("Profondità colore:", self.combo_vnc_color)
        self.combo_vnc_quality = QComboBox()
        self.combo_vnc_quality.addItems(["Auto", "Alta", "Buona", "Bassa"])
        vnc_layout.addRow("Qualità:", self.combo_vnc_quality)
        layout.addRow(self.grp_vnc)

        # --- Campi specifici FTP ---
        self.grp_ftp = QGroupBox("Opzioni FTP / FTPS")
        ftp_layout = QFormLayout(self.grp_ftp)

        self.chk_ftp_tls = QCheckBox("Usa FTPS (TLS esplicito — porta 21, AUTH TLS)")
        self.chk_ftp_tls.toggled.connect(self._aggiorna_porta_ftp)
        ftp_layout.addRow("", self.chk_ftp_tls)
        self.chk_ftp_passive = QCheckBox("Modalità passiva (PASV) — consigliata dietro NAT/firewall")
        self.chk_ftp_passive.setChecked(True)
        ftp_layout.addRow("", self.chk_ftp_passive)
        lbl_ftp_note = QLabel(
            "<b>FTP plain</b>: porta 21, nessuna cifratura (dati in chiaro).<br>"
            "<b>FTPS</b>: TLS esplicito sulla porta 21 — diverso da SFTP (che usa SSH).<br>"
            "La modalità di apertura si configura nel tab <b>Avanzate</b>."
        )
        lbl_ftp_note.setWordWrap(True)
        lbl_ftp_note.setStyleSheet(
            "background:#fef9e7; border:1px solid #f0c050; border-radius:4px; "
            "padding:6px; font-size:11px; color:#555; margin-top:4px;"
        )
        ftp_layout.addRow(lbl_ftp_note)
        layout.addRow(self.grp_ftp)

        # --- Campi specifici Tunnel ---
        self.grp_tunnel = QGroupBox("Configurazione Tunnel SSH")
        t_layout = QFormLayout(self.grp_tunnel)
        self.combo_tunnel_type = QComboBox()
        self.combo_tunnel_type.addItems(["Proxy SOCKS (-D)", "Locale (-L)", "Remoto (-R)"])
        self.combo_tunnel_type.currentTextChanged.connect(self._aggiorna_tunnel_fields)
        t_layout.addRow("Tipo:", self.combo_tunnel_type)
        self.edit_tunnel_lport = QLineEdit("1080")
        self.edit_tunnel_lport.setMaximumWidth(80)
        t_layout.addRow("Porta locale:", self.edit_tunnel_lport)
        self.edit_tunnel_rhost = QLineEdit()
        self.edit_tunnel_rhost.setPlaceholderText("host destinazione (per -L/-R)")
        t_layout.addRow("Host remoto:", self.edit_tunnel_rhost)
        self.edit_tunnel_rport = QLineEdit()
        self.edit_tunnel_rport.setMaximumWidth(80)
        self.edit_tunnel_rport.setPlaceholderText("porta dest.")
        t_layout.addRow("Porta remota:", self.edit_tunnel_rport)
        layout.addRow(self.grp_tunnel)

        # --- Campi specifici Seriale ---
        self.grp_serial = QGroupBox("Configurazione Seriale")
        ser_layout = QFormLayout(self.grp_serial)
        self.edit_serial_dev = QLineEdit("/dev/ttyUSB0")
        ser_layout.addRow("Dispositivo:", self.edit_serial_dev)
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600","19200","38400","57600","115200","230400","460800","921600"])
        self.combo_baud.setCurrentText("115200")
        ser_layout.addRow("Baud rate:", self.combo_baud)
        self.combo_data_bits = QComboBox()
        self.combo_data_bits.addItems(["5","6","7","8"])
        self.combo_data_bits.setCurrentText("8")
        ser_layout.addRow("Data bits:", self.combo_data_bits)
        self.combo_parity = QComboBox()
        self.combo_parity.addItems(["None","Even","Odd","Mark","Space"])
        ser_layout.addRow("Parità:", self.combo_parity)
        self.combo_stop_bits = QComboBox()
        self.combo_stop_bits.addItems(["1","2"])
        ser_layout.addRow("Stop bits:", self.combo_stop_bits)
        layout.addRow(self.grp_serial)

        # --- Wake-on-LAN ---
        self.grp_wol = QGroupBox("Wake-on-LAN")
        wol_layout = QFormLayout(self.grp_wol)
        self.chk_wol = QCheckBox("Invia magic packet prima di connettersi")
        self.chk_wol.setToolTip(
            "Invia un magic packet UDP (porta 9) all'indirizzo MAC indicato\n"
            "e attende che l'host risponda al ping prima di aprire la sessione."
        )
        wol_layout.addRow("", self.chk_wol)
        self.edit_wol_mac = QLineEdit()
        self.edit_wol_mac.setPlaceholderText("es. AA:BB:CC:DD:EE:FF")
        self.edit_wol_mac.setMaximumWidth(180)
        wol_layout.addRow("Indirizzo MAC:", self.edit_wol_mac)
        self.spin_wol_wait = QSpinBox()
        self.spin_wol_wait.setRange(1, 120)
        self.spin_wol_wait.setValue(20)
        self.spin_wol_wait.setSuffix(" s")
        self.spin_wol_wait.setMaximumWidth(80)
        self.spin_wol_wait.setToolTip("Secondi massimi di attesa che l'host risponda al ping dopo il WoL.")
        wol_layout.addRow("Attesa risposta:", self.spin_wol_wait)
        layout.addRow(self.grp_wol)

    # ------------------------------------------------------------------
    # Tab Autenticazione
    # ------------------------------------------------------------------

    def _build_tab_autenticazione(self):
        layout = QFormLayout(self.tab_auth)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Creiamo il campo di testo per la password
        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_password.setPlaceholderText("lascia vuoto per chiave privata o prompt")
        
        # Creiamo il bottoncino con l'occhietto
        self.btn_mostra_pwd = QToolButton()
        self.btn_mostra_pwd.setText("👁")
        self.btn_mostra_pwd.setCheckable(True)
        self.btn_mostra_pwd.setToolTip("Mostra/Nascondi password")
        
        # Logica: se lo clicco, mostra il testo normale, se lo rilascio torna a password
        self.btn_mostra_pwd.toggled.connect(
            lambda checked: self.edit_password.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        
        # Mettiamo il campo di testo e il bottone sulla stessa riga
        pwd_row = QHBoxLayout()
        pwd_row.setContentsMargins(0, 0, 0, 0)
        pwd_row.addWidget(self.edit_password)
        pwd_row.addWidget(self.btn_mostra_pwd)
        
        # Aggiungiamo la riga completa al layout
        layout.addRow("Password:", pwd_row)

        pkey_row = QHBoxLayout()
        self.edit_pkey = QLineEdit()
        self.edit_pkey.setPlaceholderText("percorso chiave privata (es. ~/.ssh/id_ed25519)")
        self.btn_pkey_browse = QPushButton("...")
        self.btn_pkey_browse.setMaximumWidth(30)
        self.btn_pkey_browse.clicked.connect(self._sfoglia_chiave)
        pkey_row.addWidget(self.edit_pkey)
        pkey_row.addWidget(self.btn_pkey_browse)
        layout.addRow("Chiave privata:", pkey_row)

        # Gestione chiavi SSH
        self.grp_chiavi = QGroupBox("🔑  Gestione chiavi SSH")
        chiavi_layout = QVBoxLayout(self.grp_chiavi)
        chiavi_layout.setSpacing(6)

        # Riga 1: chiavi esistenti
        riga_esistenti = QHBoxLayout()
        lbl_chiavi = QLabel("Chiavi in ~/.ssh:")
        lbl_chiavi.setMinimumWidth(110)
        self.combo_chiavi = QComboBox()
        self.combo_chiavi.setToolTip("Chiavi trovate in ~/.ssh")
        self.combo_chiavi.currentTextChanged.connect(self._chiave_selezionata)
        btn_ricarica = QPushButton("↺")
        btn_ricarica.setMaximumWidth(28)
        btn_ricarica.setToolTip("Ricarica lista chiavi")
        btn_ricarica.clicked.connect(self._carica_chiavi_esistenti)
        riga_esistenti.addWidget(lbl_chiavi)
        riga_esistenti.addWidget(self.combo_chiavi, 1)
        riga_esistenti.addWidget(btn_ricarica)
        chiavi_layout.addLayout(riga_esistenti)

        # Riga 2: genera nuova chiave
        riga_genera = QHBoxLayout()
        lbl_tipo = QLabel("Genera nuova:")
        lbl_tipo.setMinimumWidth(110)
        self.combo_key_type = QComboBox()
        self.combo_key_type.addItems(["ed25519  (consigliata)", "rsa 4096", "ecdsa 521"])
        self.edit_key_comment = QLineEdit()
        self.edit_key_comment.setPlaceholderText("commento (es. andres@debminis)")
        self.edit_key_comment.setText(f"{os.environ.get('USER', 'user')}@{__import__('socket').gethostname()}")
        btn_genera = QPushButton("⚙  Genera")
        btn_genera.setToolTip("Genera una nuova coppia di chiavi SSH")
        btn_genera.clicked.connect(self._genera_chiave)
        riga_genera.addWidget(lbl_tipo)
        riga_genera.addWidget(self.combo_key_type, 1)
        riga_genera.addWidget(self.edit_key_comment)
        riga_genera.addWidget(btn_genera)
        chiavi_layout.addLayout(riga_genera)

        # Riga 3: copia chiave pubblica sul server
        riga_copia = QHBoxLayout()
        self.btn_copia_server = QPushButton("📤  Copia chiave pubblica sul server")
        self.btn_copia_server.setToolTip(
            "Esegue ssh-copy-id per copiare la chiave pubblica sul server remoto\n"
            "Richiede la password del server (una sola volta)"
        )
        self.btn_copia_server.clicked.connect(self._copia_chiave_server)
        self.btn_copia_server.setStyleSheet(
            "QPushButton { background:#2d5a8e; color:#fff; border-radius:3px; padding:4px 12px; }"
            "QPushButton:hover { background:#4e7abc; }"
        )
        riga_copia.addWidget(self.btn_copia_server)

        # Pulsante mostra chiave pubblica
        self.btn_mostra_pub = QPushButton("👁  Mostra pubblica")
        self.btn_mostra_pub.setToolTip("Mostra il contenuto della chiave pubblica (da copiare manualmente)")
        self.btn_mostra_pub.clicked.connect(self._mostra_chiave_pubblica)
        riga_copia.addWidget(self.btn_mostra_pub)
        chiavi_layout.addLayout(riga_copia)

        layout.addRow(self.grp_chiavi)
        self._carica_chiavi_esistenti()

        # Jump host
        self.grp_jump = QGroupBox("Jump Host (Bastion)")
        jlayout = QFormLayout(self.grp_jump)

        lbl_jump_info = QLabel(
            "<b>A cosa serve:</b> un Jump Host (o Bastion) è un server intermedio "
            "che fa da ponte verso macchine non raggiungibili direttamente.<br>"
            "Es: <tt>PC → gateway.azienda.it → server-interno</tt><br><br>"
            "<b>Come funziona:</b> PCM si connette prima al Jump Host, poi da lì "
            "apre automaticamente la connessione al server finale — tutto in modo "
            "trasparente con un solo tab. Equivale a <tt>ssh -J gateway host</tt>."
        )
        lbl_jump_info.setWordWrap(True)
        lbl_jump_info.setStyleSheet(
            "background:#eef3fa; border:1px solid #b8cfe8; border-radius:4px; "
            "padding:8px; font-size:11px; color:#333; margin-bottom:4px;"
        )
        jlayout.addRow(lbl_jump_info)

        self.edit_jump_host = QLineEdit()
        self.edit_jump_host.setPlaceholderText("gateway.esempio.it")
        jlayout.addRow("Jump host:", self.edit_jump_host)
        self.edit_jump_user = QLineEdit()
        self.edit_jump_user.setPlaceholderText("utente sul gateway (vuoto = stesso utente)")
        jlayout.addRow("Utente jump:", self.edit_jump_user)
        self.edit_jump_port = QLineEdit("22")
        self.edit_jump_port.setMaximumWidth(80)
        jlayout.addRow("Porta jump:", self.edit_jump_port)
        layout.addRow(self.grp_jump)

    def _carica_chiavi_esistenti(self):
        """Scansiona ~/.ssh e popola il combo con le chiavi private trovate."""
        self.combo_chiavi.clear()
        self.combo_chiavi.addItem("(nessuna — usa password)")
        ssh_dir = os.path.expanduser("~/.ssh")
        if not os.path.isdir(ssh_dir):
            return
        # Cerca file di chiave privata (non .pub, non known_hosts, non config)
        esclusi = {".pub", "known_hosts", "authorized_keys", "config"}
        try:
            for f in sorted(os.listdir(ssh_dir)):
                path = os.path.join(ssh_dir, f)
                if os.path.isfile(path) and not any(f.endswith(e) or f == e for e in esclusi):
                    # Verifica che sia una chiave privata leggendo la prima riga
                    try:
                        with open(path, "r", errors="ignore") as fh:
                            prima = fh.readline().strip()
                        if "PRIVATE KEY" in prima or prima.startswith("-----BEGIN"):
                            self.combo_chiavi.addItem(f"~/.ssh/{f}", path)
                    except Exception:
                        pass
        except Exception:
            pass

    def _chiave_selezionata(self, testo: str):
        """Quando si seleziona una chiave dal combo, la imposta nel campo chiave privata."""
        path = self.combo_chiavi.currentData()
        if path:
            self.edit_pkey.setText(path)
        elif testo == "(nessuna — usa password)":
            self.edit_pkey.clear()

    def _genera_chiave(self):
        """Genera una nuova coppia di chiavi SSH con ssh-keygen."""
        import shutil, subprocess
        from PyQt6.QtWidgets import QInputDialog

        if not shutil.which("ssh-keygen"):
            QMessageBox.critical(self, "Errore", "ssh-keygen non trovato nel PATH.")
            return

        tipo_raw = self.combo_key_type.currentText()
        if "ed25519" in tipo_raw:
            tipo, bits = "ed25519", None
        elif "rsa" in tipo_raw:
            tipo, bits = "rsa", "4096"
        else:
            tipo, bits = "ecdsa", "521"

        commento = self.edit_key_comment.text().strip() or "pcm-key"
        ssh_dir = os.path.expanduser("~/.ssh")
        os.makedirs(ssh_dir, mode=0o700, exist_ok=True)

        nome_default = f"id_{tipo}_pcm"
        nome, ok = QInputDialog.getText(
            self, "Nome file chiave",
            f"Nome del file chiave (in ~/.ssh/):",
            text=nome_default
        )
        if not ok or not nome.strip():
            return
        nome = nome.strip()
        percorso = os.path.join(ssh_dir, nome)

        if os.path.exists(percorso):
            risposta = QMessageBox.question(
                self, "File esistente",
                f"Il file '{percorso}' esiste già. Sovrascrivere?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if risposta != QMessageBox.StandardButton.Yes:
                return

        # Opzionale: passphrase
        passphrase, ok2 = QInputDialog.getText(
            self, "Passphrase (opzionale)",
            "Passphrase per la chiave (lascia vuoto per nessuna):",
            QLineEdit.EchoMode.Password
        )
        if not ok2:
            return

        cmd = ["ssh-keygen", "-t", tipo, "-f", percorso, "-C", commento, "-N", passphrase or ""]
        if bits:
            cmd += ["-b", bits]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                self.edit_pkey.setText(percorso)
                self._carica_chiavi_esistenti()
                # Seleziona la chiave appena creata
                for i in range(self.combo_chiavi.count()):
                    if self.combo_chiavi.itemData(i) == percorso:
                        self.combo_chiavi.setCurrentIndex(i)
                        break
                QMessageBox.information(
                    self, "Chiave generata",
                    f"✅ Coppia di chiavi creata:\n\n"
                    f"  Privata: {percorso}\n"
                    f"  Pubblica: {percorso}.pub\n\n"
                    f"Usa 'Copia chiave pubblica sul server' per installarla sul server remoto."
                )
            else:
                QMessageBox.critical(self, "Errore ssh-keygen", result.stderr)
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "Timeout", "ssh-keygen ha impiegato troppo. Riprova.")
        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))

    def _copia_chiave_server(self):
        """Guida l'utente a copiare la chiave pubblica sul server con ssh-copy-id."""
        import shutil, subprocess
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QDialogButtonBox

        pkey = self.edit_pkey.text().strip()
        host = self.edit_host.text().strip()
        user = self.edit_user.text().strip()
        port = self.edit_port.text().strip() or "22"

        if not shutil.which("ssh-copy-id"):
            QMessageBox.critical(self, "Errore", "ssh-copy-id non trovato nel PATH.")
            return

        if not pkey:
            QMessageBox.warning(self, "Chiave mancante",
                                "Seleziona o genera prima una chiave privata.")
            return
        pub_path = pkey + ".pub"
        if not os.path.exists(pub_path):
            QMessageBox.warning(self, "Chiave pubblica mancante",
                                f"Non trovato il file:\n{pub_path}\n\nGenera prima la coppia di chiavi.")
            return
        if not host:
            QMessageBox.warning(self, "Host mancante",
                                "Inserisci l'indirizzo del server nel campo Host.")
            return

        target = f"{user}@{host}" if user else host
        cmd = f"ssh-copy-id -i '{pub_path}' -p {port} {target}"

        # Dialog di guida
        dlg = QDialog(self)
        dlg.setWindowTitle("📤 Copia chiave pubblica sul server")
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)

        from PyQt6.QtWidgets import QLabel as _QLabel
        info = _QLabel(
            f"<b>Operazione:</b> copia la chiave pubblica su <tt>{target}:{port}</tt><br><br>"
            f"<b>Chiave pubblica:</b> <tt>{pub_path}</tt><br><br>"
            f"Verrà eseguito in un terminale:<br>"
            f"<tt style='background:#f0f0f0; padding:4px'>{cmd}</tt><br><br>"
            f"<b>Ti verrà chiesta la password del server una sola volta.</b><br>"
            f"Dopo, potrai connetterti senza password usando questa chiave."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding:8px;")
        lay.addWidget(info)

        # Mostra il contenuto della chiave pubblica
        try:
            with open(pub_path) as f:
                pub_content = f.read().strip()
        except Exception:
            pub_content = "(impossibile leggere il file)"

        txt_pub = QTextEdit()
        txt_pub.setReadOnly(True)
        txt_pub.setPlainText(pub_content)
        txt_pub.setFixedHeight(60)
        txt_pub.setStyleSheet("font-family:monospace; font-size:10px; background:#f8f8f8;")
        lay.addWidget(_QLabel("Contenuto chiave pubblica (authorized_keys):"))
        lay.addWidget(txt_pub)

        bbox = QDialogButtonBox()
        btn_esegui = bbox.addButton("▶  Esegui ssh-copy-id", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_manuale = bbox.addButton("📋  Copia testo pubblica", QDialogButtonBox.ButtonRole.ActionRole)
        btn_annulla = bbox.addButton("Annulla", QDialogButtonBox.ButtonRole.RejectRole)
        lay.addWidget(bbox)

        def esegui():
            dlg.accept()
            # Avvia ssh-copy-id in un xterm visibile così l'utente può digitare la password
            import shutil as _sh
            xterm = _sh.which("xterm") or "xterm"
            cmd_xterm = (
                f"{xterm} -title 'PCM — ssh-copy-id' "
                f"-e bash -c '{cmd}; echo; echo \"Premi Invio per chiudere...\"; read'"
            )
            subprocess.Popen(cmd_xterm, shell=True)

        def copia_testo():
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(pub_content)
            QMessageBox.information(dlg, "Copiato",
                "Chiave pubblica copiata negli appunti.\n\n"
                "Incollala nel file ~/.ssh/authorized_keys del server remoto.")

        btn_esegui.clicked.connect(esegui)
        btn_manuale.clicked.connect(copia_testo)
        btn_annulla.clicked.connect(dlg.reject)
        dlg.exec()

    def _mostra_chiave_pubblica(self):
        """Mostra il contenuto della chiave pubblica selezionata."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel as _QLabel
        pkey = self.edit_pkey.text().strip()
        if not pkey:
            QMessageBox.warning(self, "Nessuna chiave", "Seleziona prima una chiave privata.")
            return
        pub_path = pkey + ".pub"
        if not os.path.exists(pub_path):
            QMessageBox.warning(self, "Non trovata",
                                f"File non trovato:\n{pub_path}")
            return
        try:
            with open(pub_path) as f:
                contenuto = f.read().strip()
        except Exception as e:
            QMessageBox.critical(self, "Errore lettura", str(e))
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Chiave pubblica — {os.path.basename(pub_path)}")
        dlg.setMinimumWidth(600)
        lay = QVBoxLayout(dlg)
        lay.addWidget(_QLabel(f"<b>{pub_path}</b>"))
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(contenuto)
        txt.setStyleSheet("font-family:monospace; font-size:11px;")
        lay.addWidget(txt)
        btn_row = QHBoxLayout()
        btn_copia = QPushButton("📋  Copia negli appunti")
        btn_ok = QPushButton("Chiudi")
        btn_copia.clicked.connect(lambda: (
            __import__('PyQt6.QtWidgets', fromlist=['QApplication']).QApplication.clipboard().setText(contenuto),
            btn_copia.setText("✅  Copiato!")
        ))
        btn_ok.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_copia)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)
        dlg.exec()

    def _sfoglia_chiave(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona chiave privata",
            os.path.expanduser("~/.ssh"), "Tutti i file (*)"
        )
        if path:
            self.edit_pkey.setText(path)

    # ------------------------------------------------------------------
    # Tab Terminale
    # ------------------------------------------------------------------

    def _build_tab_terminale(self):
        layout = QFormLayout(self.tab_term)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.combo_tema = QComboBox()
        for t in TERMINAL_THEMES.keys():
            self.combo_tema.addItem(t)
        layout.addRow("Tema:", self.combo_tema)

        self.combo_font = QComboBox()
        self.combo_font.addItems([
            "Monospace", "DejaVu Sans Mono", "Hack", "JetBrains Mono",
            "Fira Code", "Source Code Pro", "Inconsolata", "Terminus",
            "Noto Mono", "Roboto Mono"
        ])
        layout.addRow("Font:", self.combo_font)

        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(6, 32)
        self.spin_font_size.setValue(11)
        self.spin_font_size.setMaximumWidth(60)
        layout.addRow("Dimensione font:", self.spin_font_size)

        self.edit_startup_cmd = QLineEdit()
        self.edit_startup_cmd.setPlaceholderText("es. cd /var/log && tail -f syslog")
        layout.addRow("Comando avvio:", self.edit_startup_cmd)

        self.edit_pre_cmd = QLineEdit()
        self.edit_pre_cmd.setPlaceholderText(
            "es. wg-quick up vpn0  oppure  openfortivpn --config=/etc/vpn.conf"
        )
        lbl_pre = QLabel("Cmd locale pre-connessione:")
        lbl_pre.setToolTip(
            "Comando shell locale eseguito PRIMA di aprire la connessione remota.\n"
            "Utile per attivare una VPN, montare un volume, ecc.\n"
            "La connessione parte solo se il comando esce con codice 0."
        )
        layout.addRow(lbl_pre, self.edit_pre_cmd)

        self.spin_pre_cmd_timeout = QSpinBox()
        self.spin_pre_cmd_timeout.setRange(0, 120)
        self.spin_pre_cmd_timeout.setValue(15)
        self.spin_pre_cmd_timeout.setSuffix(" s  (0 = nessun timeout)")
        self.spin_pre_cmd_timeout.setMaximumWidth(170)
        self.spin_pre_cmd_timeout.setToolTip(
            "Secondi di attesa massima per il completamento del comando locale.\n"
            "Se scade, la connessione viene annullata."
        )
        layout.addRow("Timeout pre-cmd:", self.spin_pre_cmd_timeout)

        self.chk_sftp_browser = QCheckBox("Apri browser SFTP laterale dopo la connessione SSH")
        self.chk_sftp_browser.setChecked(True)
        layout.addRow("", self.chk_sftp_browser)

        self.chk_log = QCheckBox("Registra output su file")
        layout.addRow("", self.chk_log)

        log_row = QHBoxLayout()
        self.edit_log_dir = QLineEdit("/tmp/pcm_logs")
        self.btn_log_browse = QPushButton("...")
        self.btn_log_browse.setMaximumWidth(30)
        self.btn_log_browse.clicked.connect(self._sfoglia_log_dir)
        log_row.addWidget(self.edit_log_dir)
        log_row.addWidget(self.btn_log_browse)
        layout.addRow("Cartella log:", log_row)

    def _sfoglia_log_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Cartella log")
        if d:
            self.edit_log_dir.setText(d)

    # ------------------------------------------------------------------
    # Tab Avanzate
    # ------------------------------------------------------------------

    def _build_tab_avanzate(self):
        layout = QFormLayout(self.tab_adv)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # SSH avanzate
        self.grp_ssh_adv = QGroupBox("Opzioni SSH")
        ssh_layout = QFormLayout(self.grp_ssh_adv)
        self.chk_x11 = QCheckBox("X11 Forwarding (-X)")
        ssh_layout.addRow("", self.chk_x11)
        self.chk_compression = QCheckBox("Compressione (-C)")
        ssh_layout.addRow("", self.chk_compression)
        self.chk_keepalive = QCheckBox("Keepalive (ServerAliveInterval=60)")
        ssh_layout.addRow("", self.chk_keepalive)
        self.chk_strict_host = QCheckBox("Strict Host Key Checking")
        ssh_layout.addRow("", self.chk_strict_host)
        layout.addRow(self.grp_ssh_adv)

        # ── Modalità apertura SSH ────────────────────────────────────────
        self.grp_ssh_open = QGroupBox("Modalità apertura SSH")
        ssh_open_layout = QFormLayout(self.grp_ssh_open)
        self.combo_ssh_open = QComboBox()
        self.combo_ssh_open.addItems([
            "Terminale interno",
            "Terminale esterno",
        ])
        self.combo_ssh_open.setToolTip(
            "Terminale interno: xterm embedded dentro PCM\n"
            "Terminale esterno: apre il terminale scelto in una finestra separata"
        )
        ssh_open_layout.addRow("Apri con:", self.combo_ssh_open)
        layout.addRow(self.grp_ssh_open)

        # ── Modalità apertura SFTP ───────────────────────────────────────
        self.grp_sftp_open = QGroupBox("Modalità apertura SFTP")
        sftp_open_layout = QFormLayout(self.grp_sftp_open)
        self.combo_sftp_open = QComboBox()
        self.combo_sftp_open.addItems([
            "Browser interno",
            "Browser esterno (Nemo / Thunar / Dolphin)",
            "Terminale interno (sftp CLI embedded)",
            "Terminale esterno (sftp CLI in finestra separata)",
        ])
        self.combo_sftp_open.setToolTip(
            "Browser interno: interfaccia WinSCP integrata in PCM\n"
            "Browser esterno: apre il file manager di sistema con URI sftp://\n"
            "Terminale interno: client sftp CLI in xterm dentro PCM\n"
            "Terminale esterno: client sftp CLI in finestra separata"
        )
        sftp_open_layout.addRow("Apri con:", self.combo_sftp_open)
        layout.addRow(self.grp_sftp_open)

        # ── Modalità apertura FTP ────────────────────────────────────────
        self.grp_ftp_open = QGroupBox("Modalità apertura FTP")
        ftp_open_layout = QFormLayout(self.grp_ftp_open)
        self.combo_ftp_open = QComboBox()
        self.combo_ftp_open.addItems([
            "Browser interno",
            "Browser esterno (Nemo / Thunar / Dolphin)",
            "Terminale interno (lftp embedded)",
            "Terminale esterno (lftp in finestra separata)",
        ])
        self.combo_ftp_open.setToolTip(
            "Browser interno: interfaccia WinSCP integrata in PCM\n"
            "Browser esterno: apre il file manager di sistema con URI ftp://\n"
            "Terminale interno: lftp/ftp in xterm dentro PCM\n"
            "Terminale esterno: lftp/ftp in finestra terminale separata"
        )
        ftp_open_layout.addRow("Apri con:", self.combo_ftp_open)
        layout.addRow(self.grp_ftp_open)

        # ── Selettore terminale (SSH/SFTP/FTP terminale esterno / Telnet / Mosh / Serial) ──
        self.grp_term_ext = QGroupBox("Terminale")
        te_layout = QFormLayout(self.grp_term_ext)
        self.combo_term_ext = QComboBox()
        self.combo_term_ext.setEditable(True)
        self.combo_term_ext.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_term_ext.addItems([
            "Terminale Interno", "xterm", "xfce4-terminal",
            "gnome-terminal", "konsole", "alacritty", "kitty", "terminator",
            "wezterm", "foot", "tilix", "st"
        ])
        self.combo_term_ext.setToolTip(
            "Terminale Interno: xterm embedded in PCM\n"
            "Qualsiasi altro valore: apre una finestra separata"
        )
        te_layout.addRow("Terminale:", self.combo_term_ext)
        layout.addRow(self.grp_term_ext)

    # ------------------------------------------------------------------
    # Tab Note
    # ------------------------------------------------------------------

    def _build_tab_note(self):
        layout = QVBoxLayout(self.tab_note)
        self.edit_notes = QTextEdit()
        self.edit_notes.setPlaceholderText("Note libere su questa sessione…")
        layout.addWidget(self.edit_notes)

    # ------------------------------------------------------------------
    # Tab Macro
    # ------------------------------------------------------------------

    def _build_tab_macro(self):
        layout = QVBoxLayout(self.tab_macro)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        lbl_info = QLabel(
            "Le macro sono comandi inviati al terminale con un clic dal pannello sessioni.<br>"
            "Ogni macro ha un <b>nome</b> (etichetta nel menu) e un <b>comando</b> da eseguire."
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet(
            "background:#f0f6ff; border:1px solid #b0c8e8; border-radius:4px; "
            "padding:6px; font-size:11px; color:#335;"
        )
        layout.addWidget(lbl_info)

        # Lista macro
        self._lista_macro = QListWidget()
        self._lista_macro.setAlternatingRowColors(True)
        self._lista_macro.setStyleSheet(
            "QListWidget { background:#ffffff; color:#111111; border:1px solid #ccc; }"
            "QListWidget::item:selected { background:#4e7abc; color:#ffffff; }"
            "QListWidget::item:alternate { background:#f7f7f7; }"
        )
        layout.addWidget(self._lista_macro, 1)

        # Campi modifica
        form = QWidget()
        fl = QFormLayout(form)
        fl.setSpacing(6)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._edit_macro_nome = QLineEdit()
        self._edit_macro_nome.setPlaceholderText("es. Stato servizi")
        fl.addRow("Nome:", self._edit_macro_nome)
        self._edit_macro_cmd = QLineEdit()
        self._edit_macro_cmd.setPlaceholderText("es. systemctl status nginx")
        fl.addRow("Comando:", self._edit_macro_cmd)
        layout.addWidget(form)

        # Pulsanti
        btn_row = QHBoxLayout()
        btn_add = QPushButton("➕  Aggiungi")
        btn_add.clicked.connect(self._macro_aggiungi)
        btn_mod = QPushButton("✏  Aggiorna")
        btn_mod.clicked.connect(self._macro_aggiorna)
        btn_del = QPushButton("🗑  Elimina")
        btn_del.clicked.connect(self._macro_elimina)
        btn_up  = QPushButton("▲")
        btn_up.setMaximumWidth(32)
        btn_up.clicked.connect(self._macro_su)
        btn_dn  = QPushButton("▼")
        btn_dn.setMaximumWidth(32)
        btn_dn.clicked.connect(self._macro_giu)
        for b in (btn_add, btn_mod, btn_del, btn_up, btn_dn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._lista_macro.currentItemChanged.connect(self._macro_selezionata)

    def _macro_selezionata(self, item):
        if item is None:
            return
        dati = item.data(Qt.ItemDataRole.UserRole)
        if dati:
            self._edit_macro_nome.setText(dati.get("nome", ""))
            self._edit_macro_cmd.setText(dati.get("cmd", ""))

    def _macro_aggiungi(self):
        nome = self._edit_macro_nome.text().strip()
        cmd  = self._edit_macro_cmd.text().strip()
        if not nome or not cmd:
            QMessageBox.warning(self, "Macro", "Inserisci nome e comando.")
            return
        item = QListWidgetItem(f"[{nome}]  →  {cmd}")
        item.setData(Qt.ItemDataRole.UserRole, {"nome": nome, "cmd": cmd})
        self._lista_macro.addItem(item)
        self._edit_macro_nome.clear()
        self._edit_macro_cmd.clear()

    def _macro_aggiorna(self):
        item = self._lista_macro.currentItem()
        if not item:
            return
        nome = self._edit_macro_nome.text().strip()
        cmd  = self._edit_macro_cmd.text().strip()
        if not nome or not cmd:
            QMessageBox.warning(self, "Macro", "Inserisci nome e comando.")
            return
        item.setText(f"[{nome}]  →  {cmd}")
        item.setData(Qt.ItemDataRole.UserRole, {"nome": nome, "cmd": cmd})

    def _macro_elimina(self):
        row = self._lista_macro.currentRow()
        if row >= 0:
            self._lista_macro.takeItem(row)

    def _macro_su(self):
        row = self._lista_macro.currentRow()
        if row > 0:
            item = self._lista_macro.takeItem(row)
            self._lista_macro.insertItem(row - 1, item)
            self._lista_macro.setCurrentRow(row - 1)

    def _macro_giu(self):
        row = self._lista_macro.currentRow()
        if row < self._lista_macro.count() - 1:
            item = self._lista_macro.takeItem(row)
            self._lista_macro.insertItem(row + 1, item)
            self._lista_macro.setCurrentRow(row + 1)

    # ------------------------------------------------------------------
    # Visibilità campi per protocollo
    # ------------------------------------------------------------------

    def _aggiorna_tab(self):
        proto = self.combo_proto.currentData()

        # Porta di default per protocollo
        default_ports = {
            "ssh": "22", "telnet": "23", "sftp": "22", "ftp": "21",
            "rdp": "3389", "vnc": "5900", "ssh_tunnel": "22",
            "mosh": "22", "serial": ""
        }
        porta_corrente = self.edit_port.text().strip()
        proto_prec = getattr(self, "_proto_precedente", None)
        porta_default_prec = default_ports.get(proto_prec, "") if proto_prec else ""
        if not porta_corrente or porta_corrente == porta_default_prec:
            self.edit_port.setText(default_ports.get(proto, "22"))
        self._proto_precedente = proto

        # Gruppi specifici
        self.grp_rdp.setVisible(proto == "rdp")
        self.grp_vnc.setVisible(proto == "vnc")
        self.grp_ftp.setVisible(proto == "ftp")
        self.grp_tunnel.setVisible(proto == "ssh_tunnel")
        self.grp_serial.setVisible(proto == "serial")
        self.grp_jump.setVisible(proto in ("ssh", "sftp", "mosh"))
        self.grp_ssh_adv.setVisible(proto in ("ssh", "sftp", "mosh", "ssh_tunnel"))
        # Gruppi modalità apertura — uno solo visibile per volta
        self.grp_ssh_open.setVisible(proto in ("ssh", "mosh"))
        self.grp_sftp_open.setVisible(proto == "sftp")
        self.grp_ftp_open.setVisible(proto == "ftp")

        # Selettore terminale: visibile per tutti i proto che usano un terminale
        # (incluso "Terminale esterno" per SSH/SFTP/FTP, sempre per Telnet/Serial/Mosh)
        self.grp_term_ext.setVisible(proto in (
            "ssh", "mosh", "sftp", "ftp", "telnet", "serial", "ssh_tunnel"
        ))

        # Nel tab autenticazione: chiave privata e gestione chiavi SSH solo per proto SSH-based
        _ssh_like = proto in ("ssh", "sftp", "mosh", "ssh_tunnel")
        self.edit_pkey.setVisible(_ssh_like)
        self.btn_pkey_browse.setVisible(_ssh_like)
        self.grp_chiavi.setVisible(_ssh_like)
        # Etichetta "Chiave privata:" — la troviamo tramite il layout
        _auth_layout = self.tab_auth.layout()
        if _auth_layout:
            for i in range(_auth_layout.rowCount()):
                lbl = _auth_layout.itemAt(i, _auth_layout.ItemRole.LabelRole)
                if lbl and lbl.widget() and lbl.widget().text() == "Chiave privata:":
                    lbl.widget().setVisible(_ssh_like)
                    break

        # WoL: visibile solo per protocolli di rete (non seriale, non tunnel)
        self.grp_wol.setVisible(proto in ("ssh", "mosh", "rdp", "vnc", "telnet"))

        # Mostra/nascondi tab terminale
        show_term = proto in ("ssh", "telnet", "mosh", "serial", "ssh_tunnel")
        self.tabs.setTabVisible(
            self.tabs.indexOf(self.tab_term), show_term
        )

        # Port/user non visibili per serial; user non visibile per vnc
        self.edit_port.setEnabled(proto != "serial")
        self.edit_user.setEnabled(proto not in ("serial", "vnc"))

        # Placeholder password contestuale al protocollo
        _placeholder_pwd = {
            "ssh":        "lascia vuoto per chiave privata o prompt interattivo",
            "sftp":       "lascia vuoto per chiave privata o prompt interattivo",
            "mosh":       "lascia vuoto per chiave privata o prompt interattivo",
            "ftp":        "password FTP (lascia vuoto per anonymous)",
            "telnet":     "lascia vuoto per prompt interattivo",
            "rdp":        "password Windows",
            "vnc":        "password VNC",
            "ssh_tunnel": "lascia vuoto per chiave privata",
        }
        self.edit_password.setPlaceholderText(
            _placeholder_pwd.get(proto, "password")
        )

    def _aggiorna_porta_ftp(self, tls_attivo: bool):
        """Se si attiva FTPS implicit (porta 990) aggiorna la porta; tornando a plain rimette 21."""
        # FTPS esplicito usa comunque porta 21; implicit usa 990.
        # Qui gestiamo solo la convenzione più comune (esplicito = 21).
        # Se l'utente ha già modificato la porta manualmente, non sovrascriviamo.
        porta_corrente = self.edit_port.text().strip()
        if tls_attivo and porta_corrente == "21":
            pass   # FTPS esplicito rimane su 21 — ok
        elif not tls_attivo and porta_corrente == "990":
            self.edit_port.setText("21")

    def _aggiorna_tunnel_fields(self):
        t = self.combo_tunnel_type.currentText()
        show_remote = t in ("Locale (-L)", "Remoto (-R)")
        self.edit_tunnel_rhost.setEnabled(show_remote)
        self.edit_tunnel_rport.setEnabled(show_remote)

    # ------------------------------------------------------------------
    # Popola dati esistenti
    # ------------------------------------------------------------------

    def _popola(self, nome, dati):
        self.edit_nome.setText(nome)
        self.combo_gruppo.setCurrentText(dati.get("group", ""))

        proto = dati.get("protocol", "ssh")
        idx = next((i for i in range(self.combo_proto.count())
                    if self.combo_proto.itemData(i) == proto), 0)
        self.combo_proto.setCurrentIndex(idx)

        self.edit_host.setText(dati.get("host", ""))
        self.edit_port.setText(str(dati.get("port", "")))
        self.edit_user.setText(dati.get("user", ""))
        self.edit_password.setText(dati.get("password", ""))
        self.edit_pkey.setText(dati.get("private_key", ""))

        # Jump
        self.edit_jump_host.setText(dati.get("jump_host", ""))
        self.edit_jump_user.setText(dati.get("jump_user", ""))
        self.edit_jump_port.setText(str(dati.get("jump_port", "22")))

        # Terminale
        tema = dati.get("term_theme", "Scuro (Default)")
        idx_t = self.combo_tema.findText(tema)
        if idx_t >= 0:
            self.combo_tema.setCurrentIndex(idx_t)

        font = dati.get("term_font", "Monospace")
        idx_f = self.combo_font.findText(font)
        if idx_f >= 0:
            self.combo_font.setCurrentIndex(idx_f)

        try:
            self.spin_font_size.setValue(int(dati.get("term_size", 11)))
        except Exception:
            pass

        self.edit_startup_cmd.setText(dati.get("startup_cmd", ""))
        self.chk_sftp_browser.setChecked(dati.get("sftp_browser", True))
        self.chk_log.setChecked(dati.get("log_output", False))
        self.edit_log_dir.setText(dati.get("log_dir", "/tmp/pcm_logs"))

        # SSH avanzate
        self.chk_x11.setChecked(dati.get("x11", False))
        self.chk_compression.setChecked(dati.get("compression", False))
        self.chk_keepalive.setChecked(dati.get("keepalive", False))
        self.chk_strict_host.setChecked(dati.get("strict_host", False))

        # RDP
        rdp_c = dati.get("rdp_client", "xfreerdp")
        idx_r = self.combo_rdp_client.findText(rdp_c)
        if idx_r >= 0:
            self.combo_rdp_client.setCurrentIndex(idx_r)
        self.chk_rdp_fs.setChecked(dati.get("fullscreen", True))
        self.chk_rdp_clip.setChecked(dati.get("redirect_clipboard", True))
        self.chk_rdp_drives.setChecked(dati.get("redirect_drives", False))

        # VNC
        self.chk_vnc_internal.setChecked(dati.get("vnc_internal", True))

        # SSH modalità apertura
        ssh_open = dati.get("ssh_open_mode", "Terminale interno")
        idx_so = self.combo_ssh_open.findText(ssh_open, Qt.MatchFlag.MatchStartsWith)
        if idx_so >= 0:
            self.combo_ssh_open.setCurrentIndex(idx_so)

        # SFTP modalità apertura
        sftp_open = dati.get("sftp_open_mode", "Browser interno")
        idx_sfo = self.combo_sftp_open.findText(sftp_open, Qt.MatchFlag.MatchStartsWith)
        if idx_sfo >= 0:
            self.combo_sftp_open.setCurrentIndex(idx_sfo)

        # FTP
        self.chk_ftp_tls.setChecked(dati.get("ftp_tls", False))
        self.chk_ftp_passive.setChecked(dati.get("ftp_passive", True))
        ftp_open = dati.get("ftp_open_mode", "Browser interno")
        idx_fo = self.combo_ftp_open.findText(ftp_open, Qt.MatchFlag.MatchStartsWith)
        if idx_fo >= 0:
            self.combo_ftp_open.setCurrentIndex(idx_fo)
        
        vnc_c = dati.get("vnc_client", "vncviewer")
        idx_v = self.combo_vnc_client.findText(vnc_c)
        if idx_v >= 0:
            self.combo_vnc_client.setCurrentIndex(idx_v)

        # Tunnel
        tt = dati.get("tunnel_type", "Proxy SOCKS (-D)")
        idx_tt = self.combo_tunnel_type.findText(tt)
        if idx_tt >= 0:
            self.combo_tunnel_type.setCurrentIndex(idx_tt)
        self.edit_tunnel_lport.setText(str(dati.get("tunnel_local_port", "1080")))
        self.edit_tunnel_rhost.setText(dati.get("tunnel_remote_host", ""))
        self.edit_tunnel_rport.setText(str(dati.get("tunnel_remote_port", "")))

        # WoL
        self.chk_wol.setChecked(dati.get("wol_enabled", False))
        self.edit_wol_mac.setText(dati.get("wol_mac", ""))
        self.spin_wol_wait.setValue(int(dati.get("wol_wait", 20)))

        # Seriale
        self.edit_serial_dev.setText(dati.get("device", "/dev/ttyUSB0"))
        baud = str(dati.get("baud", "115200"))
        idx_b = self.combo_baud.findText(baud)
        if idx_b >= 0:
            self.combo_baud.setCurrentIndex(idx_b)

        # Terminale esterno
        te = dati.get("terminal_type", "Terminale Interno")
        idx_te = self.combo_term_ext.findText(te)
        if idx_te >= 0:
            self.combo_term_ext.setCurrentIndex(idx_te)

        # Pre-cmd locale
        self.edit_pre_cmd.setText(dati.get("pre_cmd", ""))
        self.spin_pre_cmd_timeout.setValue(int(dati.get("pre_cmd_timeout", 15)))

        # Macro
        self._lista_macro.clear()
        for m in dati.get("macros", []):
            nome = m.get("nome", "")
            cmd  = m.get("cmd", "")
            if nome or cmd:
                item = __import__("PyQt6.QtWidgets", fromlist=["QListWidgetItem"]).QListWidgetItem(
                    f"[{nome}]  →  {cmd}"
                )
                item.setData(__import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ItemDataRole.UserRole,
                             {"nome": nome, "cmd": cmd})
                self._lista_macro.addItem(item)

        # Note
        self.edit_notes.setPlainText(dati.get("notes", ""))

    # ------------------------------------------------------------------
    # Validazione e raccolta dati
    # ------------------------------------------------------------------

    def _valida_e_accetta(self):
        nome = self.edit_nome.text().strip()
        if not nome:
            self.edit_nome.setFocus()
            self.edit_nome.setStyleSheet("border:1px solid red;")
            return
        proto = self.combo_proto.currentData()
        if proto != "serial" and not self.edit_host.text().strip():
            self.edit_host.setFocus()
            self.edit_host.setStyleSheet("border:1px solid red;")
            return
        self.accept()

    def get_data(self):
        """Restituisce (nome, dizionario_dati)."""
        proto = self.combo_proto.currentData()
        d = {
            "protocol":       proto,
            "group":          self.combo_gruppo.currentText().strip(),
            "host":           self.edit_host.text().strip(),
            "port":           self.edit_port.text().strip(),
            "user":           self.edit_user.text().strip(),
            "password":       self.edit_password.text(),
            "private_key":    self.edit_pkey.text().strip(),
            "jump_host":      self.edit_jump_host.text().strip(),
            "jump_user":      self.edit_jump_user.text().strip(),
            "jump_port":      self.edit_jump_port.text().strip(),
            "term_theme":     self.combo_tema.currentText(),
            "term_font":      self.combo_font.currentText(),
            "term_size":      self.spin_font_size.value(),
            "startup_cmd":    self.edit_startup_cmd.text().strip(),
            "sftp_browser":   self.chk_sftp_browser.isChecked(),
            "log_output":     self.chk_log.isChecked(),
            "log_dir":        self.edit_log_dir.text().strip(),
            "x11":            self.chk_x11.isChecked(),
            "compression":    self.chk_compression.isChecked(),
            "keepalive":      self.chk_keepalive.isChecked(),
            "strict_host":    self.chk_strict_host.isChecked(),
            "rdp_client":     self.combo_rdp_client.currentText(),
            "fullscreen":     self.chk_rdp_fs.isChecked(),
            "redirect_clipboard": self.chk_rdp_clip.isChecked(),
            "redirect_drives": self.chk_rdp_drives.isChecked(),
            "vnc_internal":   self.chk_vnc_internal.isChecked(), 
            "vnc_client":     self.combo_vnc_client.currentText(),
            "vnc_color":      self.combo_vnc_color.currentText(),
            "vnc_quality":    self.combo_vnc_quality.currentText(),
            "ssh_open_mode":  self.combo_ssh_open.currentText(),
            "sftp_open_mode": self.combo_sftp_open.currentText(),
            "ftp_open_mode":  self.combo_ftp_open.currentText(),
            "ftp_tls":        self.chk_ftp_tls.isChecked(),
            "ftp_passive":    self.chk_ftp_passive.isChecked(),
            "tunnel_type":    self.combo_tunnel_type.currentText(),
            "tunnel_local_port": self.edit_tunnel_lport.text().strip(),
            "tunnel_remote_host": self.edit_tunnel_rhost.text().strip(),
            "tunnel_remote_port": self.edit_tunnel_rport.text().strip(),
            "device":         self.edit_serial_dev.text().strip(),
            "baud":           self.combo_baud.currentText(),
            "data_bits":      self.combo_data_bits.currentText(),
            "parity":         self.combo_parity.currentText(),
            "stop_bits":      self.combo_stop_bits.currentText(),
            "terminal_type":  self.combo_term_ext.currentText(),
            "notes":          self.edit_notes.toPlainText(),
            "wol_enabled":    self.chk_wol.isChecked(),
            "wol_mac":        self.edit_wol_mac.text().strip(),
            "wol_wait":       self.spin_wol_wait.value(),
            "pre_cmd":        self.edit_pre_cmd.text().strip(),
            "pre_cmd_timeout": self.spin_pre_cmd_timeout.value(),
            "macros":         [
                self._lista_macro.item(i).data(
                    __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ItemDataRole.UserRole
                )
                for i in range(self._lista_macro.count())
            ],
        }
        return self.edit_nome.text().strip(), d
