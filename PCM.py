#!/usr/bin/env python3
"""
PCM - Python Connection Manager
Clone Linux di MobaXterm sviluppato in Python/PyQt6.

Moduli:
  PCM.py              - Finestra principale
  config_manager.py   - Gestione sessioni e impostazioni
  themes.py           - Temi e stylesheet
  terminal_widget.py  - Widget xterm embedded
  sftp_browser.py     - Browser SFTP laterale (paramiko)
  session_dialog.py   - Dialog creazione/modifica sessione
  session_command.py  - Costruzione comandi shell per protocollo
  session_panel.py    - Sidebar sessioni con albero
  tunnel_manager.py   - Gestore tunnel SSH grafici
  settings_dialog.py  - Impostazioni globali

Requisiti:
  PyQt6, paramiko, xterm, sshpass (opzionale), xdotool (opzionale)

Autore: lavoro scolastico - clone MobaXterm per Linux
"""

import sys
import os
import subprocess
import signal
import shutil
from functools import partial
from vnc_widget import VncWebWidget

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QTabBar, QToolBar, QStatusBar, QLabel,
    QLineEdit, QPushButton, QComboBox, QMessageBox, QMenu, QFrame,
    QSizePolicy, QToolButton, QDialog, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence

import config_manager
from themes import APP_STYLESHEET, TERMINAL_THEMES
from terminal_widget import TerminalWidget
from sftp_browser import SftpBrowserWidget
from session_dialog import SessionDialog
from session_command import build_command, check_dipendenze
from session_panel import SessionPanel
from tunnel_manager import TunnelManagerDialog
from ftp_server_dialog import FtpServerDialog
from settings_dialog import SettingsDialog
from winscp_widget import apri_sessione_winscp, WinScpWidget, apri_sessione_ftp, FtpWinScpWidget

# ---------------------------------------------------------------------------
# Helper icone PNG con percorso assoluto (indipendente dalla CWD)
# ---------------------------------------------------------------------------
_ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

def _qi(name: str) -> QIcon:
    """Carica icons/<name>.png con percorso assoluto."""
    path = os.path.join(_ICONS_DIR, name)
    return QIcon(path) if os.path.isfile(path) else QIcon()


# ==============================================================================
# Widget di benvenuto
# ==============================================================================

class WelcomeWidget(QWidget):
    """Schermata iniziale stile MobaXterm con scorciatoie rapide."""

    nuova_sessione   = pyqtSignal()
    terminale_locale = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._chiusura_tab_in_corso = False
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        titolo = QLabel("PCM — Python Connection Manager")
        titolo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titolo.setStyleSheet("color:#4e7abc; font-size:22px; font-weight:bold;")
        layout.addWidget(titolo)

        sottotitolo = QLabel("Python Connection Manager • Gestione sessioni remote multi-protocollo")
        sottotitolo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sottotitolo.setStyleSheet("color:#444444; font-size:13px;")
        layout.addWidget(sottotitolo)

        separatore = QFrame()
        separatore.setFrameShape(QFrame.Shape.HLine)
        separatore.setStyleSheet("color:#333; margin:10px 80px;")
        layout.addWidget(separatore)

        # Pulsanti rapidi
        pulsanti_layout = QHBoxLayout()
        pulsanti_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pulsanti_layout.setSpacing(16)

        btn_nuova = self._crea_pulsante_grande("➕\n\nNuova sessione\nremota", "#4e7abc")
        btn_nuova.clicked.connect(self.nuova_sessione.emit)

        btn_locale = self._crea_pulsante_grande("⌨\n\nTerminale\nlocale", "#2d7a2d")
        btn_locale.clicked.connect(self.terminale_locale.emit)

        for b in [btn_nuova, btn_locale]:
            pulsanti_layout.addWidget(b)

        layout.addLayout(pulsanti_layout)

        # Info dipendenze
        deps = check_dipendenze()
        mancanti = [k for k, v in deps.items() if not v and k not in ("paramiko",)]
        if mancanti:
            avviso = QLabel(f"⚠  Strumenti non trovati: {', '.join(mancanti)}")
            avviso.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avviso.setStyleSheet("color:#c9b458; font-size:11px; margin-top:20px;")
            layout.addWidget(avviso)

        # Footer
        footer = QLabel("Doppio clic su una sessione nella sidebar per connettersi  •  Ctrl+Alt+T = terminale locale")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color:#444; font-size:11px; margin-top:30px;")
        layout.addWidget(footer)

    def _crea_pulsante_grande(self, testo, colore):
        b = QPushButton(testo)
        b.setFixedSize(150, 120)
        b.setStyleSheet(
            f"QPushButton {{ background:{colore}; color:#fff; border-radius:8px; "
            f"font-size:13px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:#5a9fe0; }}"
            f"QPushButton:pressed {{ background:#2d5a8e; }}"
        )
        return b


# ==============================================================================
# Tab chiudibile personalizzato
# ==============================================================================

class TabBar(QTabBar):
    """
    TabBar con:
    - Tasto X su ogni tab
    - Tab riordinabili con drag dentro lo stesso pannello
    - Tasto destro: 'Sposta nell'altro pannello' / 'Chiudi'
    - Drag visivo: trascina il tab verso l'altro pannello
    """

    sposta_ad_altro  = pyqtSignal(int)
    esporta_replay   = pyqtSignal(int)   # indice tab da esportare

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self._drag_idx = -1
        self._drag_start = None
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_idx   = self.tabAt(event.pos())
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton
                and self._drag_start is not None
                and self._drag_idx >= 0):
            dist = (event.pos() - self._drag_start).manhattanLength()
            if dist > 25:
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(f"pcm_tab:{self._drag_idx}")
                drag.setMimeData(mime)
                drag.exec(Qt.DropAction.MoveAction)
                self._drag_idx   = -1
                self._drag_start = None
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        if event.button() == Qt.MouseButton.RightButton:
            idx = self.tabAt(event.pos())
            if idx >= 0:
                menu = QMenu(self)
                menu.addAction("⇄  Sposta nell'altro pannello",
                               lambda: self.sposta_ad_altro.emit(idx))
                menu.addSeparator()
                menu.addAction("📄  Esporta comandi.sh…",
                               lambda: self.esporta_replay.emit(idx))
                menu.addSeparator()
                menu.addAction("✖  Chiudi tab",
                               lambda: self.tabCloseRequested.emit(idx))
                menu.exec(event.globalPosition().toPoint())
                return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("pcm_tab:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Drop su questa TabBar: sposta il tab dalla barra sorgente a questa."""
        txt = event.mimeData().text()
        if not txt.startswith("pcm_tab:"):
            event.ignore()
            return
        try:
            src_idx = int(txt.split(":")[1])
        except ValueError:
            event.ignore()
            return
        src_bar = event.source()
        if src_bar is self:
            event.ignore()   # riordino interno, ci pensa Qt
            return
        # Sorgente è l'altra TabBar — emetti il segnale sulla barra sorgente
        src_bar.sposta_ad_altro.emit(src_idx)
        event.acceptProposedAction()


# ==============================================================================
# Finestra principale
# ==============================================================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PCM — Python Connection Manager")
        self.setMinimumSize(1000, 650)
        self.resize(1280, 780)

        self._settings = config_manager.load_settings()
        self._tunnel_dialog = None
        self._modalita_protetta = False
        self._processi_tunnel = {}
        self._chiusura_tab_in_corso = False
        self._profili_tab = {}   # id(widget) -> (nome, profilo)

        self._init_ui()
        self._setup_menu()
        self._setup_scorciatoie()
        self._setup_tray()
        self._aggiorna_status()

    # ------------------------------------------------------------------
    # Costruzione UI principale
    # ------------------------------------------------------------------

    def _init_ui(self):
        # --- Toolbar principale ---
        self._build_toolbar()

        # --- Quick Connect bar ---
        self._build_quickconnect()

        # --- Area centrale: splitter sidebar + tabs ---
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.qc_frame)   # quick connect

        self.splitter_main = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(self.splitter_main, 1)

        # --- Sidebar sinistra: tab Sessioni + SFTP ---
        self.left_tabs = QTabWidget()
        self.left_tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.left_tabs.setMinimumWidth(180)
        self.left_tabs.setStyleSheet(
            "QTabBar::tab { padding:8px 3px; font-size:10px; min-height:50px; }"
        )

        self.session_panel = SessionPanel()
        self.session_panel.sessione_aperta.connect(self._gestisci_apertura_sessione)
        self.session_panel.sessione_modifica.connect(self._modifica_sessione_da_panel)
        self.session_panel.sessione_eliminata.connect(lambda _: None)
        self.session_panel.nuova_sessione.connect(self._nuova_sessione)
        self.left_tabs.addTab(self.session_panel, _qi("computer.png"), "Sess.")
        
        self.sftp_browser = SftpBrowserWidget()
        self.left_tabs.addTab(self.sftp_browser, _qi("folder.png"), "SFTP")


        self.splitter_main.addWidget(self.left_tabs)

        # --- Area destra: splitter terminali (supporta split vero) ---
        self.tab_area = QWidget()
        tab_layout = QVBoxLayout(self.tab_area)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        # Splitter interno per split verticale/orizzontale dei terminali
        self.splitter_term = QSplitter(Qt.Orientation.Horizontal)
        self.splitter_term.setHandleWidth(4)
        tab_layout.addWidget(self.splitter_term)

        # Pannello primario (sempre presente)
        self._tabbar1 = TabBar()
        self._tabbar1.sposta_ad_altro.connect(lambda i: self._sposta_tab(self.tabs, self.tabs2, i))
        self._tabbar1.esporta_replay.connect(lambda i: self._esporta_replay_tab(self.tabs, i))
        self.tabs = QTabWidget()
        self.tabs.setTabBar(self._tabbar1)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.tabCloseRequested.connect(self._chiudi_tab)
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border:none; }"
            "QTabBar::tab { min-width:120px; padding:5px 12px; }"
        )
        self.splitter_term.addWidget(self.tabs)

        # Pannello secondario (usato per split — inizialmente nascosto)
        self._tabbar2 = TabBar()
        self._tabbar2.sposta_ad_altro.connect(lambda i: self._sposta_tab(self.tabs2, self.tabs, i))
        self._tabbar2.esporta_replay.connect(lambda i: self._esporta_replay_tab(self.tabs2, i))
        self.tabs2 = QTabWidget()
        self.tabs2.setTabBar(self._tabbar2)
        self.tabs2.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs2.tabCloseRequested.connect(lambda i: self._chiudi_tab2(i))
        self.tabs2.setStyleSheet(
            "QTabWidget::pane { border:none; }"
            "QTabBar::tab { min-width:120px; padding:5px 12px; }"
        )
        self.splitter_term.addWidget(self.tabs2)
        self.tabs2.hide()

        self.splitter_main.addWidget(self.tab_area)
        self.splitter_main.setSizes([280, 1000])
        self.splitter_main.setCollapsible(0, True)

        # Benvenuto iniziale
        self._welcome = WelcomeWidget()
        self._welcome.nuova_sessione.connect(self._nuova_sessione)
        self._welcome.terminale_locale.connect(self._terminale_locale)
        self.tabs.addTab(self._welcome, "🏠 Benvenuto")
        self.tabs.setTabsClosable(False)

        # --- Barra di stato ---
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.lbl_status = QLabel("  PCM pronto")
        self.lbl_connessioni = QLabel()
        self.statusbar.addWidget(self.lbl_status, 1)
        self.statusbar.addPermanentWidget(self.lbl_connessioni)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self):
        self.toolbar = QToolBar("Toolbar principale")
        self.toolbar.setIconSize(QSize(22, 22)) # Grandezza ideale per la toolbar
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(self.toolbar)

        # Modificata per accettare il percorso dell'icona (icon_path)
        def _azione(icon_path, label, tooltip, slot, shortcut=None):
            a = QAction(_qi(icon_path), label, self)
            a.setToolTip(tooltip)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(shortcut)
            self.toolbar.addAction(a)
            return a

        # Toolbar principale
        _azione("server.png",   "Sessione",     "Nuova sessione remota",  self._nuova_sessione, "Ctrl+Shift+N")
        _azione("terminal.png", "Locale",        "Terminale locale",       self._terminale_locale, "Ctrl+Alt+T")
        self.toolbar.addSeparator()
        _azione("tunnel.png",   "Tunnel",        "Gestione tunnel SSH",    self._apri_tunnel_manager)
        self.toolbar.addSeparator()
        _azione("settings.png", "Impostazioni",  "Impostazioni globali",   self._apri_impostazioni)

        self.toolbar.addSeparator()

        # Bottone split mode
        split_btn = QToolButton()
        split_btn.setText("Split")
        split_btn.setIcon(_qi("split.png")) # Aggiunta icona
        split_btn.setToolTip("Modalità split terminale")
        split_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        split_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon) # Mostra sia icona che testo
        
        split_menu = QMenu(split_btn)
        split_menu.addAction("Singolo", self._split_singolo)
        split_menu.addAction("Split verticale (2)", self._split_verticale)
        split_menu.addAction("Split orizzontale (2)", self._split_orizzontale)
        split_btn.setMenu(split_menu)
        self.toolbar.addWidget(split_btn)

        self.toolbar.addSeparator()

        # Info dipendenze mancanti nella toolbar
        deps = check_dipendenze()
        if not deps.get("xterm"):
            lbl_warn = QLabel("  ⚠ xterm mancante  ")
            lbl_warn.setStyleSheet("color:#c9b458; font-weight:bold;")
            self.toolbar.addWidget(lbl_warn)

    # ------------------------------------------------------------------
    # Quick Connect bar
    # ------------------------------------------------------------------

    def _build_quickconnect(self):
        self.qc_frame = QFrame()
        self.qc_frame.setFixedHeight(34)
        self.qc_frame.setStyleSheet(
            "QFrame { background:#f0f0f0; border-bottom:1px solid #444; }"
        )
        qc_layout = QHBoxLayout(self.qc_frame)
        qc_layout.setContentsMargins(8, 2, 8, 2)
        qc_layout.setSpacing(6)

        lbl = QLabel("Quick Connect:")
        lbl.setStyleSheet("color:#888; font-size:12px;")
        qc_layout.addWidget(lbl)

        self.combo_proto_qc = QComboBox()
        self.combo_proto_qc.addItems(["SSH", "Telnet", "SFTP", "FTP", "RDP", "VNC"])
        self.combo_proto_qc.setFixedWidth(80)
        self.combo_proto_qc.setStyleSheet("font-size:12px;")
        qc_layout.addWidget(self.combo_proto_qc)

        self.edit_qc = QLineEdit()
        self.edit_qc.setPlaceholderText("utente@host:porta  oppure  host")
        self.edit_qc.setStyleSheet(
            "background:#ffffff; color:#000000; border:1px solid #aaa; "
            "border-radius:3px; padding:2px 6px; font-family:monospace; font-size:12px;"
        )
        self.edit_qc.returnPressed.connect(self._esegui_quick_connect)
        qc_layout.addWidget(self.edit_qc, 1)

        btn_go = QPushButton("▶ Connetti")
        btn_go.setFixedHeight(24)
        btn_go.clicked.connect(self._esegui_quick_connect)
        btn_go.setStyleSheet(
            "QPushButton { background:#4e7abc; color:#fff; border-radius:3px; "
            "font-size:12px; padding:0 10px; font-weight:bold; }"
            "QPushButton:hover { background:#5a8fd1; }"
        )
        qc_layout.addWidget(btn_go)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _setup_menu(self):
        mb = self.menuBar()

        def _act(label, slot, shortcut=None):
            a = QAction(label, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            return a

        # File
        file_menu = mb.addMenu("File")
        file_menu.addAction(_act("➕ Nuova sessione",    self._nuova_sessione,    "Ctrl+Shift+N"))
        file_menu.addAction(_act("⌨ Terminale locale",  self._terminale_locale,  "Ctrl+Alt+T"))
        file_menu.addSeparator()
        file_menu.addAction(_act("📥 Importa sessioni…", self._importa_sessioni))
        file_menu.addAction(_act("📤 Esporta sessioni…", self._esporta_sessioni))
        file_menu.addSeparator()
        file_menu.addAction(_act("⚙ Impostazioni",      self._apri_impostazioni))
        file_menu.addSeparator()
        file_menu.addAction(_act("✖ Esci",              self.close,              "Alt+F4"))

        # Visualizza
        view_menu = mb.addMenu("Visualizza")
        view_menu.addAction(_act("📋 Mostra/Nascondi Sidebar",      self._toggle_sidebar,     "Ctrl+Shift+B"))
        view_menu.addAction(_act("🔀 Modalità Split verticale",     self._split_verticale,    "Ctrl+Alt+2"))
        view_menu.addAction(_act("🔀 Modalità Split orizzontale",   self._split_orizzontale,  "Ctrl+Alt+3"))
        view_menu.addAction(_act("⬜ Vista singola",                self._split_singolo,      "Ctrl+Alt+1"))

        # Strumenti
        tools_menu = mb.addMenu("Strumenti")
        tools_menu.addAction(_act("🔀 Gestione Tunnel SSH",   self._apri_tunnel_manager))
        tools_menu.addAction(_act("⚡ Multi-exec…",           self._apri_multi_exec,      "Ctrl+Shift+M"))
        tools_menu.addAction(_act("📦 Variabili globali…",    self._apri_variabili,       "Ctrl+Shift+V"))
        tools_menu.addSeparator()
        tools_menu.addAction(_act("🗄  Server FTP locale…",   self._apri_ftp_server,      "Ctrl+Shift+F"))
        tools_menu.addSeparator()

        # Sottomenu importazione da applicazioni esterne
        import_menu = tools_menu.addMenu("📥  Importa da applicazione esterna")
        import_menu.addAction(_act("🖥  Remmina…",
                                   lambda: self._importa_da_app("remmina")))
        import_menu.addAction(_act("🗂  Remote Desktop Manager (XML)…",
                                   lambda: self._importa_da_app("rdm_xml")))
        import_menu.addAction(_act("🗂  Remote Desktop Manager (JSON)…",
                                   lambda: self._importa_da_app("rdm_json")))
        tools_menu.addSeparator()

        # Modalità protetta (checkable)
        self._act_protetta = QAction("🔒 Modalità protetta (nascondi password)", self)
        self._act_protetta.setCheckable(True)
        self._act_protetta.setChecked(False)
        self._act_protetta.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self._act_protetta.toggled.connect(self._toggle_modalita_protetta)
        tools_menu.addAction(self._act_protetta)

        tools_menu.addSeparator()
        tools_menu.addAction(_act("📋 Verifica dipendenze",   self._mostra_dipendenze))

        # Aiuto
        help_menu = mb.addMenu("?")
        help_menu.addAction(_act("📖 Guida di PCM",       self._apri_guida,        "F1"))
        help_menu.addSeparator()
        help_menu.addAction(_act("ℹ  Informazioni su PCM", self._about))

    # ------------------------------------------------------------------
    # Scorciatoie da tastiera
    # ------------------------------------------------------------------

    def _setup_scorciatoie(self):
        sc = self._settings.get("shortcuts", {})

        def _shortcut(seq_str, slot):
            if seq_str:
                a = QAction(self)
                a.setShortcut(QKeySequence(seq_str))
                a.triggered.connect(slot)
                self.addAction(a)

        _shortcut(sc.get("new_terminal", "Ctrl+Alt+T"), self._terminale_locale)
        _shortcut(sc.get("close_tab", "Ctrl+Alt+Q"), self._chiudi_tab_corrente)
        _shortcut(sc.get("prev_tab", "Ctrl+Alt+Left"), self._tab_precedente)
        _shortcut(sc.get("next_tab", "Ctrl+Alt+Right"), self._tab_successivo)
        _shortcut(sc.get("new_session", "Ctrl+Shift+N"), self._nuova_sessione)
        _shortcut(sc.get("toggle_sidebar", "Ctrl+Shift+B"), self._toggle_sidebar)
        _shortcut(sc.get("fullscreen", "F11"), self._toggle_fullscreen)

    # ------------------------------------------------------------------
    # Gestione sessioni
    # ------------------------------------------------------------------

    def _nuova_sessione(self):
        dlg = SessionDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nome, dati = dlg.get_data()
            profili = config_manager.load_profiles()
            profili[nome] = dati
            config_manager.save_profiles(profili)
            self.session_panel.aggiorna()
            self._aggiorna_tray_sessioni()
            self._apri_sessione(nome, dati)

    def _modifica_sessione_da_panel(self, nome, dati):
        dlg = SessionDialog(self, nome, dati)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nuovo_nome, nuovi_dati = dlg.get_data()
            profili = config_manager.load_profiles()
            if nuovo_nome != nome and nome in profili:
                del profili[nome]
            profili[nuovo_nome] = nuovi_dati
            config_manager.save_profiles(profili)
            self.session_panel.aggiorna()

    def _apri_sessione(self, nome: str, profilo: dict):
        import copy
        profilo = copy.copy(profilo)
        profilo["__nome__"] = nome

        # --- Tracciamento ultime sessioni usate ---
        recenti = self._settings.setdefault("recent_sessions", [])
        if nome in recenti:
            recenti.remove(nome)
        recenti.insert(0, nome)
        self._settings["recent_sessions"] = recenti[:20]
        config_manager.save_settings(self._settings)
        self._aggiorna_tray_sessioni()

        proto = profilo.get("protocol", "ssh")

        # --- CORREZIONE LOGICA CREDENZIALI ---
        _proto_con_cred = ("ssh", "telnet", "mosh", "rdp", "vnc")
        if proto in _proto_con_cred:
            user = profilo.get("user", "").strip()
            pwd  = profilo.get("password", "")
            pkey = profilo.get("private_key", "").strip()
            
            # Determiniamo se servono davvero le credenziali
            # 1. Per SSH/Mosh: serve user E (password o chiave)
            if proto in ("ssh", "mosh"):
                need_cred = not user or (not pwd and not pkey)
            # 2. Per VNC: serve solo la password (l'utente spesso non esiste)
            elif proto == "vnc":
                need_cred = not pwd
            # 3. Per altri (RDP/Telnet): servono user e password
            else:
                need_cred = not user or not pwd

            # Chiedi credenziali SOLO se mancano nel profilo
            if need_cred:
                from winscp_widget import _dialog_credenziali, _salva_credenziali_profilo
                host = profilo.get("host", "")
                port_int = int(profilo.get("port", 22))
                proto_label = {"ssh": "SSH", "mosh": "SSH", "telnet": "Telnet",
                               "rdp": "RDP", "vnc": "VNC"}.get(proto, proto.upper())
                
                cred = _dialog_credenziali(self, host, port_int, proto_label,
                                           user=user, pwd=pwd,
                                           mostra_pkey=(proto in ("ssh", "mosh")))
                if cred is None: # Utente ha premuto Cancel
                    return
                
                profilo["user"]     = cred["user"]
                profilo["password"] = cred["pwd"]
                if proto in ("ssh", "mosh"):
                    profilo["private_key"] = cred["pkey"]
                
                if cred["ricorda"]:
                    _salva_credenziali_profilo(profilo)
                    self.session_panel.aggiorna()
        # --- FINE CORREZIONE ---

        cmd, modalita = build_command(profilo)
        
        # AGGIUNTA LOGICA VNC INTEGRATO
        if proto == "vnc" and profilo.get("vnc_internal"):
            self._rimuovi_welcome_se_presente()
            self.tabs.setTabsClosable(True)
            self._set_status(f"Avvio VNC integrato: {nome}...")
            
            host = profilo.get("host", "localhost")
            port = profilo.get("port", "5900")
            password = profilo.get("password", "") # <-- Recuperiamo la password dal dizionario!
            
            # Passiamo host, porta E password al widget
            vnc_view = VncWebWidget(host, port, password)
            idx = self.tabs.addTab(vnc_view, _qi("vnc.png"), f" {nome}")
            self.tabs.setCurrentIndex(idx)
            
            self._aggiorna_status()
            return
        
        # ... [il resto di _apri_sessione rimane identico] ...
        if modalita == "external":


            # RDP, VNC, SFTP gui → apre in background
            if cmd:
                subprocess.Popen(cmd, shell=True)
            self._set_status(f"Avviato: {nome} ({proto.upper()})")
            return

        if modalita == "sftp_panel":
            # SFTP → apre la finestra WinSCP come tab nell'area principale
            self._rimuovi_welcome_se_presente()
            self.tabs.setTabsClosable(True)
            self._set_status(f"⏳ Connessione SFTP: {profilo.get('user')}@{profilo.get('host')}…")
            QApplication.processEvents()
            widget = apri_sessione_winscp(profilo, parent=self)
            if widget:
                label = f"📁 {nome}"
                idx = self.tabs.addTab(widget, label)
                self.tabs.setCurrentIndex(idx)
                self._set_status(f"SFTP: {profilo.get('user')}@{profilo.get('host')}")
                self.session_panel.aggiorna()   # aggiorna in caso di credenziali salvate
            else:
                self._set_status("Connessione SFTP fallita")
            self._aggiorna_status()
            return

        if modalita == "ftp_panel":
            # FTP browser stile WinSCP via ftplib
            self._rimuovi_welcome_se_presente()
            self.tabs.setTabsClosable(True)
            self._set_status(f"⏳ Connessione FTP: {profilo.get('user')}@{profilo.get('host')}…")
            QApplication.processEvents()
            widget = apri_sessione_ftp(profilo, parent=self)
            if widget:
                label = f"🗂 {nome}"
                idx = self.tabs.addTab(widget, label)
                self.tabs.setCurrentIndex(idx)
                self._set_status(f"FTP: {profilo.get('user')}@{profilo.get('host')}")
                self.session_panel.aggiorna()   # aggiorna in caso di credenziali salvate
            else:
                self._set_status("Connessione FTP fallita")
            self._aggiorna_status()
            return

        if modalita == "ftp_external":
            # FTP tramite file manager di sistema (nautilus/thunar/dolphin)
            if cmd:
                subprocess.Popen(cmd, shell=True)
            self._set_status(f"Aperto file manager FTP: {nome}")
            return

        if modalita == "ftp_term_ext":
            # FTP in terminale esterno separato
            term_ext = profilo.get("terminal_type", "xterm")
            if term_ext == "Terminale Interno":
                term_ext = "xterm"
            if cmd:
                if shutil.which(term_ext):
                    subprocess.Popen([term_ext, "-e", cmd])
                else:
                    subprocess.Popen(["xterm", "-e", cmd])
            self._set_status(f"Aperto terminale FTP esterno: {nome}")
            return

        if modalita == "ssh_term_ext":
            # SSH/Mosh in terminale esterno separato
            term = profilo.get("terminal_type", "xterm")
            if not term or term == "Terminale Interno":
                term = "xterm"
            if cmd and shutil.which(term.split()[0]):
                subprocess.Popen([term, "-e", cmd])
            elif cmd:
                subprocess.Popen(["xterm", "-e", cmd])
            self._set_status(f"Aperto terminale esterno: {nome}")
            return

        if modalita == "sftp_external":
            # SFTP tramite file manager di sistema
            if cmd:
                subprocess.Popen(cmd, shell=True)
            self._set_status(f"Aperto file manager SFTP: {nome}")
            return

        if modalita == "sftp_term_ext":
            # SFTP CLI in terminale esterno
            term = profilo.get("terminal_type", "xterm")
            if not term or term == "Terminale Interno":
                term = "xterm"
            if cmd:
                if shutil.which(term.split()[0]):
                    subprocess.Popen([term, "-e", cmd])
                else:
                    subprocess.Popen(["xterm", "-e", cmd])
            self._set_status(f"Aperto terminale SFTP esterno: {nome}")
            return

        if modalita == "tunnel":
            # Tunnel SSH → avvia e mostra nella gestione tunnel
            self._apri_sessione_tunnel(nome, profilo, cmd)
            return

        # embedded / serial
        if not cmd:
            QMessageBox.warning(self, "Errore", "Impossibile costruire il comando per questa sessione.")
            return

        self._rimuovi_welcome_se_presente()

        log_dir = ""
        if profilo.get("log_output"):
            log_dir = profilo.get("log_dir", "/tmp/pcm_logs")

        term = TerminalWidget.da_profilo(profilo, log_dir=log_dir)
        
        # Mappiamo i protocolli ai file SVG scaricati
        ICONE = {
            "ssh":    "icons/terminal.png",
            "telnet": "icons/network.png",
            "mosh":   "icons/flash.png",
            "serial": "icons/cable.png",
        }
        
        # Se il protocollo non è nel dizionario, usa un'icona generica
        percorso_icona = ICONE.get(proto, "icons/terminal.png")

        self.tabs.setTabsClosable(True)
        idx = self.tabs.addTab(term, QIcon(percorso_icona), f" {nome}")
        self.tabs.setCurrentIndex(idx)

        # Salva profilo per riconnessione automatica
        self._profili_tab[id(term)] = (nome, profilo)
        term.processo_terminato.connect(lambda t=term: self._on_processo_terminato(t))

        # SALVIAMO IL COMANDO ORIGINALE QUI:
        term.comando_originale = cmd

        # Espande variabili globali {VAR} nel comando
        cmd = config_manager.expand_variables(cmd) 

        # Maschera password se modalità protetta attiva
        cmd_display = cmd
        if self._modalita_protetta:
            import re
            cmd_display = re.sub(r"sshpass -p '[^']*'", "sshpass -p '****'", cmd_display)
            cmd_display = re.sub(r"/p:'[^']*'", "/p:'****'", cmd_display)
        term.barra_info.setText(f"  ▶  {cmd_display}")
        term.avvia(cmd)

        # Apri SFTP browser automaticamente per SSH
        if proto == "ssh" and profilo.get("sftp_browser",
                                           self._settings.get("ssh", {}).get("default_sftp_browser", True)):
            QTimer.singleShot(1500, lambda: self._connetti_sftp_browser(profilo))

        self._aggiorna_status()
        self._set_status(f"Connesso: {nome}")

    def _apri_sessione_tunnel(self, nome, profilo, cmd):
        """Avvia un tunnel SSH come processo in background."""
        if not cmd:
            return
        try:
            proc = subprocess.Popen(
                cmd, shell=True, preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._processi_tunnel[nome] = proc
            self._set_status(f"Tunnel attivo: {nome} (PID {proc.pid})")
            QMessageBox.information(
                self, "Tunnel SSH avviato",
                f"Tunnel '{nome}' avviato in background.\n\nComando:\n{cmd}\n\nPID: {proc.pid}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore tunnel", str(e))

    def _connetti_sftp_browser(self, profilo):
        host = profilo.get("host", "")
        port = profilo.get("port", "22")
        user = profilo.get("user", "")
        pwd  = profilo.get("password", "")
        pkey = profilo.get("private_key", "")
        self.sftp_browser.connetti(host, port, user, pwd, pkey)
        self.left_tabs.setCurrentWidget(self.sftp_browser)

    # ------------------------------------------------------------------
    # Terminale locale
    # ------------------------------------------------------------------

    def _terminale_locale(self):
        self._rimuovi_welcome_se_presente()
        s = self._settings.get("terminal", {})
        from themes import TERMINAL_THEMES
        bg, fg = TERMINAL_THEMES.get(s.get("default_theme", "Scuro (Default)"), ("#1e1e1e", "#cccccc"))
        term = TerminalWidget(
            bg=bg, fg=fg,
            font=s.get("default_font", "Monospace"),
            font_size=s.get("default_font_size", 11)
        )
        self.tabs.setTabsClosable(True)
        idx = self.tabs.addTab(term, _qi("terminal.png"), " Locale")
        self.tabs.setCurrentIndex(idx)
        term.avvia_locale()
        self._aggiorna_status()

    # ------------------------------------------------------------------
    # Quick Connect
    # ------------------------------------------------------------------

    def _esegui_quick_connect(self):
        import re
        testo = self.edit_qc.text().strip()
        if not testo:
            return

        proto = self.combo_proto_qc.currentText().lower()

        # Parse user@host:porta
        match = re.match(r'(?:(\w[\w.-]*)@)?([\w.\-]+)(?::(\d+))?', testo)
        if not match:
            self._set_status("Quick Connect: formato non riconosciuto")
            return

        user  = match.group(1) or os.getlogin()
        host  = match.group(2)
        porta = match.group(3) or {
            "ssh": "22", "telnet": "23", "sftp": "22",
            "rdp": "3389", "vnc": "5900"
        }.get(proto, "22")

        profilo = {
            "protocol": proto,
            "host": host,
            "port": porta,
            "user": user,
            "password": "",
            "term_theme": self._settings.get("terminal", {}).get("default_theme", "Scuro (Default)"),
            "term_font":  self._settings.get("terminal", {}).get("default_font", "Monospace"),
            "term_size":  self._settings.get("terminal", {}).get("default_font_size", 11),
        }

        nome_qc = f"{user}@{host}:{porta}"
        self._apri_sessione(nome_qc, profilo)
        self.edit_qc.clear()

    # ------------------------------------------------------------------
    # Gestione tab
    # ------------------------------------------------------------------

    def _chiudi_tab(self, index):
        # Guardia anti-rientro: evita che la chiusura di un tab scateni
        # richieste di chiusura a cascata sugli altri tab
        if self._chiusura_tab_in_corso:
            return
        self._chiusura_tab_in_corso = True

        try:
            w = self.tabs.widget(index)
            if not w:
                return

            # Conferma per sessioni attive
            ha_processo = hasattr(w, "chiudi_processo") or hasattr(w, "chiudi_connessione")
            if ha_processo and self._settings.get("terminal", {}).get("confirm_on_close", True):
                nome_tab = self.tabs.tabText(index).strip()
                risposta = QMessageBox.question(
                    self, "Chiudi tab",
                    f"Chiudere la sessione '{nome_tab}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if risposta != QMessageBox.StandardButton.Yes:
                    return

            # Chiudiamo fisicamente i processi
            if hasattr(w, "chiudi_processo"):
                w.chiudi_processo()
            if hasattr(w, "chiudi_connessione"):
                w.chiudi_connessione()

            # Rimuoviamo il tab e puliamo la memoria
            self.tabs.removeTab(index)
            w.deleteLater()

            # Se non ci sono più tab, rimettiamo la schermata di benvenuto
            if self.tabs.count() == 0:
                self.tabs.setTabsClosable(False)
                self._welcome = WelcomeWidget()
                self._welcome.nuova_sessione.connect(self._nuova_sessione)
                self._welcome.terminale_locale.connect(self._terminale_locale)
                self.tabs.addTab(self._welcome, "🏠 Benvenuto")
                self.left_tabs.setCurrentIndex(0)

            self._aggiorna_status()

        finally:
            # Il flag viene sempre rilasciato, anche in caso di eccezione
            self._chiusura_tab_in_corso = False

    def _chiudi_tab_corrente(self):
        idx = self.tabs.currentIndex()
        if idx >= 0 and self.tabs.tabText(idx) != "🏠 Benvenuto":
            self._chiudi_tab(idx)

    def _tab_precedente(self):
        c = self.tabs.count()
        if c > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % c)

    def _tab_successivo(self):
        c = self.tabs.count()
        if c > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % c)

    def _rimuovi_welcome_se_presente(self):
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "🏠 Benvenuto":
                self.tabs.removeTab(i)
                break

    # ------------------------------------------------------------------
    # Split mode — usa splitter_term interno all'area destra
    # ------------------------------------------------------------------

    def _split_singolo(self):
        """Un solo pannello, nasconde il secondo."""
        self.splitter_term.setOrientation(Qt.Orientation.Horizontal)
        self.tabs2.hide()
        self.splitter_term.setSizes([1, 0])

    def _split_verticale(self):
        """Due pannelli affiancati (colonne)."""
        self.splitter_term.setOrientation(Qt.Orientation.Horizontal)
        self.tabs2.show()
        w = self.splitter_term.width()
        half = max(200, w // 2)
        self.splitter_term.setSizes([half, half])

    def _split_orizzontale(self):
        """Due pannelli sovrapposti (righe)."""
        self.splitter_term.setOrientation(Qt.Orientation.Vertical)
        self.tabs2.show()
        h = self.splitter_term.height()
        half = max(100, h // 2)
        self.splitter_term.setSizes([half, half])

    def _chiudi_tab2(self, index):
        w = self.tabs2.widget(index)
        if hasattr(w, "chiudi_processo"):
            w.chiudi_processo()
        if hasattr(w, "chiudi_connessione"):
            w.chiudi_connessione()
        self.tabs2.removeTab(index)
        if w:
            w.deleteLater()
        if self.tabs2.count() == 0:
            self.tabs2.hide()
            self.splitter_term.setSizes([1, 0])

    def _sposta_tab(self, sorgente: QTabWidget, destinazione: QTabWidget, index: int):
        """Sposta il tab `index` da `sorgente` a `destinazione`."""
        if index < 0 or index >= sorgente.count():
            return
        testo  = sorgente.tabText(index)
        widget = sorgente.widget(index)
        # Rimuove senza deleteLater
        sorgente.removeTab(index)
        # Assicura che il pannello destinazione sia visibile
        if destinazione == self.tabs2 and not self.tabs2.isVisible():
            self.tabs2.show()
            w = self.splitter_term.width()
            self.splitter_term.setSizes([w // 2, w // 2])
        destinazione.setTabsClosable(True)
        destinazione.addTab(widget, testo)
        destinazione.setCurrentWidget(widget)
        # Se sorgente rimane vuota, ripristina welcome se è tabs
        if sorgente == self.tabs and sorgente.count() == 0:
            sorgente.setTabsClosable(False)
            self._welcome = WelcomeWidget()
            self._welcome.nuova_sessione.connect(self._nuova_sessione)
            self._welcome.terminale_locale.connect(self._terminale_locale)
            sorgente.addTab(self._welcome, "🏠 Benvenuto")
        elif sorgente == self.tabs2 and sorgente.count() == 0:
            sorgente.hide()
            self.splitter_term.setSizes([1, 0])
        self._aggiorna_status()

    # ------------------------------------------------------------------
    # Strumenti
    # ------------------------------------------------------------------

    def _apri_tunnel_manager(self):
        if self._tunnel_dialog is None or not self._tunnel_dialog.isVisible():
            self._tunnel_dialog = TunnelManagerDialog(self)
        self._tunnel_dialog.show()
        self._tunnel_dialog.raise_()

    def _apri_impostazioni(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._settings = config_manager.load_settings()
            self._set_status("Impostazioni salvate")

    def _mostra_dipendenze(self):
        deps = check_dipendenze()
        righe = []
        for k, v in sorted(deps.items()):
            stato = "✅" if v else "❌"
            righe.append(f"  {stato}  {k}")
        QMessageBox.information(
            self, "Dipendenze PCM",
            "\n".join(righe) +
            "\n\nInstalla i mancanti con il gestore pacchetti della tua distribuzione."
        )

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _toggle_modalita_protetta(self, attiva: bool):
        self._modalita_protetta = attiva
        stato = "🔒 ATTIVA" if attiva else "🔓 disattivata"
        self._set_status(f"Modalità protetta {stato}")
        
        # Aggiorna la barra info di tutti i terminali aperti
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            # Verifica che il tab sia un terminale con le info salvate
            if hasattr(w, 'barra_info') and hasattr(w, 'comando_originale'):
                cmd_display = w.comando_originale
                
                # Se attiva, censura il comando originale
                if attiva:
                    import re
                    cmd_display = re.sub(r"sshpass -p '[^']*'", "sshpass -p '****'", cmd_display)
                    cmd_display = re.sub(r"/p:'[^']*'", "/p:'****'", cmd_display)
                
                # Applica il testo (in chiaro o censurato)
                w.barra_info.setText(f"  ▶  {cmd_display}")
                
        # Aggiorna statusbar con indicatore visivo
        if attiva:
            self.lbl_connessioni.setStyleSheet("color:#c9b458; font-weight:bold;")
            self.lbl_connessioni.setText("  🔒 Modalità protetta  ")
        else:
            self.lbl_connessioni.setStyleSheet("")
            self._aggiorna_status()
            
    def _toggle_sidebar(self):
        visible = self.left_tabs.isVisible()
        self.left_tabs.setVisible(not visible)

    # ------------------------------------------------------------------
    # Fullscreen
    # ------------------------------------------------------------------

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ------------------------------------------------------------------
    # Statusbar
    # ------------------------------------------------------------------

    def _aggiorna_status(self):
        n_tab = sum(
            1 for i in range(self.tabs.count())
            if self.tabs.tabText(i) != "🏠 Benvenuto"
        )
        if n_tab == 0:
            self.lbl_connessioni.setText("")
        else:
            self.lbl_connessioni.setText(
                f"  Sessioni aperte: {n_tab}  "
            )

    def _set_status(self, msg: str):
        self.lbl_status.setText(f"  {msg}")

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

    def _apri_guida(self):
        """Apre la guida HTML in una scheda dedicata (QWebEngineView)."""
        from PyQt6.QtCore import QUrl

        # Se la guida è già aperta, la porta in primo piano
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).strip() == "📖 Guida":
                self.tabs.setCurrentIndex(i)
                return

        guida_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "pcm_help.html"
        )
        if not os.path.isfile(guida_path):
            QMessageBox.warning(self, "Guida",
                "File pcm_help.html non trovato nella cartella di PCM.")
            return

        # QWebEngineView: browser Chromium completo, supporta CSS moderno
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            browser = QWebEngineView()
            browser.setUrl(QUrl.fromLocalFile(guida_path))
        except ImportError:
            # Fallback a QTextBrowser se WebEngine non disponibile
            from PyQt6.QtWidgets import QTextBrowser
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            browser.setSource(QUrl.fromLocalFile(guida_path))
            browser.setStyleSheet("background:#f8f8f8; border:none;")

        self._rimuovi_welcome_se_presente()
        self.tabs.setTabsClosable(True)
        idx = self.tabs.addTab(browser, "📖 Guida")
        self.tabs.setCurrentIndex(idx)

    def _about(self):
        QMessageBox.about(
            self, "PCM — Python Connection Manager",
            "<b>PCM — Python Connection Manager</b><br><br>"
            "Sviluppato in Python/PyQt6.<br><br>"
            "<b>Protocolli supportati:</b> SSH, Telnet, SFTP, RDP, VNC, "
            "SSH Tunnel, Mosh, Seriale<br><br>"
            "<b>Tecnologie:</b> Python 3 e Brownie<br><br>"
            "<b>Autore:</b> Andres Zanzani - azanzani@gmail.com"
        )

    # ------------------------------------------------------------------
    # Gestione apertura (intercetta macro dal panel)
    # ------------------------------------------------------------------

    def _gestisci_apertura_sessione(self, nome: str, profilo: dict):
        """Intercetta il segnale sessione_aperta: se è una macro, la invia al tab attivo."""
        if nome.startswith("__macro__:"):
            cmd = nome[len("__macro__:"):]
            # Trova il tab corrente che corrisponde al profilo
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if isinstance(w, TerminalWidget) and w._process:
                    info = self._profili_tab.get(id(w))
                    if info and info[1].get("host") == profilo.get("host"):
                        w.invia_testo(cmd, invio=True, sorgente="macro")
                        self._set_status(f"Macro inviata: {cmd}")
                        return
            QMessageBox.information(self, "Macro", f"Nessuna sessione attiva per '{profilo.get('host')}'.\nComando: {cmd}")
        else:
            self._apri_sessione(nome, profilo)

    # ------------------------------------------------------------------
    # System Tray
    # ------------------------------------------------------------------

    def _setup_tray(self):
        """Configura l'icona nel system tray."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icona = _qi("pcm_icon.png")
        self._tray = QSystemTrayIcon(icona, self)
        self._tray.setToolTip("PCM — Python Connection Manager")

        tray_menu = QMenu()
        tray_menu.addAction("🖥  Mostra PCM", self._mostra_finestra)
        tray_menu.addSeparator()

        # Sottomenu sessioni rapide (prime 10)
        self._tray_sessioni_menu = tray_menu.addMenu("⚡  Connetti a…")
        self._aggiorna_tray_sessioni()

        tray_menu.addSeparator()
        tray_menu.addAction("➕  Nuova sessione", self._nuova_sessione)
        tray_menu.addAction("⌨  Terminale locale", self._terminale_locale)
        tray_menu.addSeparator()
        tray_menu.addAction("✖  Esci", self._esci_definitivo)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._tray_attivato)
        self._tray.show()

    def _aggiorna_tray_sessioni(self):
        """Popola il sottomenu sessioni nel tray.

        Mostra prima le ultime sessioni usate (max 8), poi le restanti
        in ordine alfabetico (limite totale 20 voci).
        """
        if not hasattr(self, '_tray_sessioni_menu'):
            return
        self._tray_sessioni_menu.clear()
        profili = config_manager.load_profiles()
        if not profili:
            self._tray_sessioni_menu.addAction("(nessuna sessione)").setEnabled(False)
            return

        recenti = self._settings.get("recent_sessions", [])
        recenti_validi = [n for n in recenti if n in profili]

        MAX_RECENTI = 8
        MAX_TOTALE  = 20

        def _add_action(nome, dati):
            proto = dati.get("protocol", "ssh").upper()
            host  = dati.get("host", "")
            self._tray_sessioni_menu.addAction(
                f"{nome}  ({proto} {host})",
                lambda n=nome, d=dati: self._apri_dal_tray(n, d)
            )

        # --- Sezione Recenti ---
        mostrati = []
        for nome in recenti_validi[:MAX_RECENTI]:
            _add_action(nome, profili[nome])
            mostrati.append(nome)

        # --- Restanti in ordine alfabetico ---
        restanti = [n for n in sorted(profili.keys()) if n not in mostrati]
        posti_rimasti = MAX_TOTALE - len(mostrati)
        if restanti and posti_rimasti > 0:
            if mostrati:
                self._tray_sessioni_menu.addSeparator()
            for nome in restanti[:posti_rimasti]:
                _add_action(nome, profili[nome])
            if len(restanti) > posti_rimasti:
                rimaste = len(restanti) - posti_rimasti
                self._tray_sessioni_menu.addSeparator()
                a = self._tray_sessioni_menu.addAction(f"... e altre {rimaste} sessioni (apri PCM)")
                a.setEnabled(False)

    def _apri_dal_tray(self, nome: str, profilo: dict):
        self._mostra_finestra()
        self._apri_sessione(nome, profilo)

    def _mostra_finestra(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_attivato(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self._mostra_finestra()

    def _esci_definitivo(self):
        """Chiude davvero l'app anche se la finestra è nascosta nel tray."""
        if hasattr(self, '_tray'):
            self._tray.hide()
        self.close()

    # ------------------------------------------------------------------
    # Variabili globali
    # ------------------------------------------------------------------

    def _apri_variabili(self):
        """Dialog per gestire le variabili globali {NOME} → valore."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                      QTableWidget, QTableWidgetItem,
                                      QPushButton, QLabel, QDialogButtonBox,
                                      QHeaderView, QLineEdit)

        dlg = QDialog(self)
        dlg.setWindowTitle("📦 Variabili globali PCM")
        dlg.setMinimumSize(480, 360)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel(
            "Usa {NOME} nei comandi e nelle macro per sostituire automaticamente il valore.\n"
            "Es: {SERVER}, {USER}, {DB_HOST}"
        ))

        tabella = QTableWidget(0, 2)
        tabella.setHorizontalHeaderLabels(["Nome variabile", "Valore"])
        tabella.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tabella.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tabella.verticalHeader().setVisible(False)
        tabella.setAlternatingRowColors(True)
        layout.addWidget(tabella, 1)

        # Popola con variabili esistenti
        vars_ = config_manager.load_variables()
        for nome, valore in vars_.items():
            r = tabella.rowCount()
            tabella.insertRow(r)
            tabella.setItem(r, 0, QTableWidgetItem(nome))
            tabella.setItem(r, 1, QTableWidgetItem(valore))

        # Riga di aggiunta rapida
        riga_add = QHBoxLayout()
        edit_nome = QLineEdit()
        edit_nome.setPlaceholderText("NOME (es. SERVER_IP)")
        edit_valore = QLineEdit()
        edit_valore.setPlaceholderText("valore")
        btn_add = QPushButton("➕ Aggiungi")
        btn_del = QPushButton("🗑 Elimina")

        def aggiungi():
            n = edit_nome.text().strip().upper().replace(" ", "_")
            v = edit_valore.text()
            if not n:
                return
            r = tabella.rowCount()
            tabella.insertRow(r)
            tabella.setItem(r, 0, QTableWidgetItem(n))
            tabella.setItem(r, 1, QTableWidgetItem(v))
            edit_nome.clear()
            edit_valore.clear()

        def elimina():
            for item in tabella.selectedItems():
                tabella.removeRow(item.row())

        btn_add.clicked.connect(aggiungi)
        btn_del.clicked.connect(elimina)
        edit_valore.returnPressed.connect(aggiungi)

        riga_add.addWidget(edit_nome)
        riga_add.addWidget(edit_valore, 1)
        riga_add.addWidget(btn_add)
        riga_add.addWidget(btn_del)
        layout.addLayout(riga_add)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addWidget(bbox)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            nuove = {}
            for r in range(tabella.rowCount()):
                n = tabella.item(r, 0)
                v = tabella.item(r, 1)
                if n and n.text().strip():
                    nuove[n.text().strip()] = v.text() if v else ""
            config_manager.save_variables(nuove)
            self._set_status(f"Variabili globali salvate ({len(nuove)})")

    # ------------------------------------------------------------------
    # Riconnessione automatica
    # ------------------------------------------------------------------

    def _on_processo_terminato(self, term: "TerminalWidget"):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) is term:
                nome_tab = self.tabs.tabText(i).strip()
                info = self._profili_tab.get(id(term))
                self._mostra_banner_riconnessione(term, info)
                self.tabs.setTabText(i, f"✖ {nome_tab}")
                self._aggiorna_status()
                # Notifica tray
                if hasattr(self, '_tray'):
                    self._tray.showMessage(
                        "PCM — Sessione terminata",
                        f"La sessione '{nome_tab}' si è disconnessa.",
                        QSystemTrayIcon.MessageIcon.Warning, 4000
                    )
                break

    def _mostra_banner_riconnessione(self, term: "TerminalWidget", info):
        from PyQt6.QtWidgets import QPushButton
        for child in term.findChildren(QPushButton, "btn_riconnetti"):
            child.deleteLater()
        btn = QPushButton("🔄  Riconnetti", term)
        btn.setObjectName("btn_riconnetti")
        btn.setFixedHeight(32)
        btn.setStyleSheet(
            "QPushButton { background:#2d5a8e; color:#fff; border:none; "
            "font-size:13px; font-weight:bold; }"
            "QPushButton:hover { background:#4e7abc; }"
        )
        btn.setGeometry(0, 22, term.width(), 32)
        btn.show()

        def _riconnetti():
            btn.deleteLater()
            if info:
                nome, profilo = info
                self._apri_sessione(nome, profilo)
            else:
                term.avvia(term._comando_corrente)

        btn.clicked.connect(_riconnetti)

    # ------------------------------------------------------------------
    # Import / Export sessioni
    # ------------------------------------------------------------------

    def _esporta_sessioni(self):
        import json
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta sessioni", "pcm_sessioni.json", "JSON (*.json)"
        )
        if not path:
            return
        profili = config_manager.load_profiles()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profili, f, indent=4, ensure_ascii=False)
            self._set_status(f"Sessioni esportate: {path}")
            QMessageBox.information(self, "Esportazione completata",
                                    f"Esportate {len(profili)} sessioni in:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Errore esportazione", str(e))

    def _importa_sessioni(self):
        import json
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Importa sessioni", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                nuovi = json.load(f)
            if not isinstance(nuovi, dict):
                raise ValueError("Formato non valido")
            esistenti = config_manager.load_profiles()
            conflitti = [n for n in nuovi if n in esistenti]
            if conflitti:
                risposta = QMessageBox.question(
                    self, "Conflitti trovati",
                    f"Le seguenti sessioni esistono già:\n\n{chr(10).join(conflitti)}\n\nSovrascrivi?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if risposta != QMessageBox.StandardButton.Yes:
                    return
            esistenti.update(nuovi)
            config_manager.save_profiles(esistenti)
            self.session_panel.aggiorna()
            self._aggiorna_tray_sessioni()
            self._set_status(f"Importate {len(nuovi)} sessioni")
        except Exception as e:
            QMessageBox.critical(self, "Errore importazione", str(e))

    def _importa_da_app(self, sorgente: str):
        """Importa sessioni da Remmina o Remote Desktop Manager."""
        from PyQt6.QtWidgets import QFileDialog
        try:
            from importer import importa_remmina, importa_rdm, unisci_in_pcm
        except ImportError:
            QMessageBox.critical(self, "Errore",
                "Modulo importer.py non trovato.\n"
                "Assicurati che importer.py sia nella stessa cartella di PCM.py.")
            return

        profili_importati: dict = {}

        if sorgente == "remmina":
            risposta = QMessageBox.question(
                self, "Importa da Remmina",
                "Usare la cartella Remmina predefinita?\n"
                "(~/.local/share/remmina)\n\n"
                "Scegli «No» per selezionare un file o cartella diversa.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if risposta == QMessageBox.StandardButton.Cancel:
                return
            elif risposta == QMessageBox.StandardButton.Yes:
                percorso = None
            else:
                percorso = QFileDialog.getExistingDirectory(
                    self, "Seleziona cartella Remmina"
                ) or QFileDialog.getOpenFileName(
                    self, "Seleziona file .remmina", "", "Remmina (*.remmina)"
                )[0]
                if not percorso:
                    return
            try:
                profili_importati = importa_remmina(percorso)
            except Exception as e:
                QMessageBox.critical(self, "Errore importazione Remmina", str(e))
                return

        elif sorgente in ("rdm_xml", "rdm_json"):
            ext = "XML (*.xml *.rdm)" if sorgente == "rdm_xml" else "JSON (*.json)"
            path, _ = QFileDialog.getOpenFileName(
                self, "Seleziona export Remote Desktop Manager", "", ext
            )
            if not path:
                return
            try:
                profili_importati = importa_rdm(path)
            except Exception as e:
                QMessageBox.critical(self, "Errore importazione RDM", str(e))
                return

        if not profili_importati:
            QMessageBox.information(self, "Importazione", "Nessuna connessione trovata.")
            return

        # Anteprima e conferma
        nomi = list(profili_importati.keys())
        anteprima = "\n".join(
            f"  [{profili_importati[n].get('protocol','?').upper():8}] {n}"
            for n in nomi[:20]
        )
        if len(nomi) > 20:
            anteprima += f"\n  … e altre {len(nomi)-20}"

        risposta = QMessageBox.question(
            self, "Conferma importazione",
            f"Trovate <b>{len(nomi)}</b> connessioni:\n\n{anteprima}\n\n"
            "Importare e unire a PCM?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if risposta != QMessageBox.StandardButton.Yes:
            return

        try:
            aggiunti, _ = unisci_in_pcm(profili_importati)
            self.session_panel.aggiorna()
            self._aggiorna_tray_sessioni()
            self._set_status(f"Importate {aggiunti} connessioni")
            QMessageBox.information(
                self, "Importazione completata",
                f"Aggiunte <b>{aggiunti}</b> connessioni al pannello sessioni."
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore salvataggio", str(e))

    # ------------------------------------------------------------------
    # Multi-exec
    # ------------------------------------------------------------------

    def _apri_multi_exec(self):
        terminali = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, TerminalWidget) and w._process:
                terminali.append((self.tabs.tabText(i).strip(), w))

        if not terminali:
            QMessageBox.information(self, "Multi-exec", "Nessuna sessione attiva.")
            return

        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget,
                                      QListWidgetItem, QTextEdit, QPushButton,
                                      QLabel, QDialogButtonBox, QCheckBox)

        dlg = QDialog(self)
        dlg.setWindowTitle("⚡ Multi-exec — Invia comando a più sessioni")
        dlg.setMinimumSize(520, 400)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Seleziona le sessioni destinatarie:"))
        lista = QListWidget()
        lista.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for nome, _ in terminali:
            item = QListWidgetItem(nome)
            item.setSelected(True)
            lista.addItem(item)
        layout.addWidget(lista)

        layout.addWidget(QLabel("Comando da inviare:"))
        edit_cmd = QTextEdit()
        edit_cmd.setPlaceholderText("es: uptime")
        edit_cmd.setFixedHeight(80)
        edit_cmd.setStyleSheet(
            "background:#1e1e1e; color:#cccccc; font-family:monospace; font-size:12px;"
        )
        layout.addWidget(edit_cmd)

        chk_invio = QCheckBox("Invia Enter automaticamente dopo il comando")
        chk_invio.setChecked(True)
        layout.addWidget(chk_invio)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.button(QDialogButtonBox.StandardButton.Ok).setText("⚡ Invia")
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addWidget(bbox)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        cmd = edit_cmd.toPlainText().strip()
        if not cmd:
            return
        # Espande variabili globali anche nel multi-exec
        cmd = config_manager.expand_variables(cmd)

        selezionati = {lista.item(i).text() for i in range(lista.count())
                       if lista.item(i).isSelected()}
        n_inviati = 0
        for nome, term in terminali:
            if nome in selezionati:
                term.invia_testo(cmd, invio=chk_invio.isChecked(), sorgente="multi_exec")
                n_inviati += 1
        self._set_status(f"Multi-exec: comando inviato a {n_inviati} sessioni")

    # ------------------------------------------------------------------
    # Chiusura
    # ------------------------------------------------------------------

    def _apri_ftp_server(self):
        """Apre il dialog per avviare un server FTP locale."""
        if not hasattr(self, "_ftp_server_dialog") or self._ftp_server_dialog is None:
            self._ftp_server_dialog = FtpServerDialog(self)
        self._ftp_server_dialog.show()
        self._ftp_server_dialog.raise_()
        self._ftp_server_dialog.activateWindow()

    # ------------------------------------------------------------------
    # Export replay comandi
    # ------------------------------------------------------------------

    def _esporta_replay_tab(self, tab_widget, idx: int):
        """
        Esporta comandi.sh per la sessione attiva nel tab.
        - Se il log xterm NON è abilitato: mostra avviso con istruzioni.
        - Se il log è abilitato: parsa il file di log xterm per estrarre
          i comandi digitati + quelli inviati da PCM, genera lo script replay.
        """
        import os, re, glob

        w = tab_widget.widget(idx)
        if not isinstance(w, TerminalWidget):
            QMessageBox.information(
                self, "Esporta comandi.sh",
                "Il tab selezionato non è una sessione terminale."
            )
            return

        info    = self._profili_tab.get(id(w))
        nome    = info[0] if info else tab_widget.tabText(idx).strip()
        profilo = info[1] if info else {}

        # ── Controlla se il log è abilitato ───────────────────────────
        log_abilitato = profilo.get("log_output", False)
        log_dir       = profilo.get("log_dir", "").strip()

        if not log_abilitato or not log_dir:
            # Avviso con istruzioni precise
            msg = QMessageBox(self)
            msg.setWindowTitle("Esporta comandi.sh — Log non abilitato")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(
                "<b>Il log della sessione non è abilitato.</b><br><br>"
                "Per poter esportare tutti i comandi digitati in console, "
                "abilita il log nel profilo della sessione:"
            )
            msg.setInformativeText(
                "1. Tasto destro sulla sessione nel pannello → Modifica\n"
                "2. Tab Terminale\n"
                "3. Spunta 'Registra output su file'\n"
                "4. Imposta la cartella log\n"
                "5. Riconnetti la sessione\n\n"
                "Senza log, sono disponibili solo i comandi inviati tramite "
                "macro e multi-exec."
            )
            btn_solo_pcm = msg.addButton(
                "Esporta solo comandi PCM", QMessageBox.ButtonRole.AcceptRole
            )
            msg.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() != btn_solo_pcm:
                return
            # Esporta solo comandi PCM (nessun parsing log)
            self._genera_dialog_comandi(nome, profilo, w, comandi_log=[])
            return

        # ── Cerca il file di log più recente per questa sessione ───────
        pattern = os.path.join(log_dir, "pcm_*.log")
        log_files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)

        if not log_files:
            QMessageBox.warning(
                self, "Esporta comandi.sh",
                f"Log abilitato ma nessun file trovato in:\n{log_dir}\n\n"
                "Il file viene creato alla connessione. Assicurati che la sessione "
                "sia stata avviata dopo aver abilitato il log."
            )
            return

        log_path = log_files[0]

        # ── Parsing del log xterm ──────────────────────────────────────
        # Il log xterm contiene tutto l'output del terminale incluse le
        # sequenze ANSI. Estraiamo le righe che sono comandi digitati
        # usando una euristica: righe che seguono un prompt shell tipico
        # (terminano con $, #, >, %) e non sono output di comandi.
        comandi_log = self._parsa_log_xterm(log_path)

        self._genera_dialog_comandi(nome, profilo, w, comandi_log)

    def _parsa_log_xterm(self, log_path: str) -> list:
        """
        Parsa un file di log xterm e restituisce lista di dict
        {ts, cmd, sorgente} con i comandi estratti.
        Rimuove sequenze ANSI, righe vuote e output non-comando.
        """
        import re
        from datetime import datetime

        # Regex per rimuovere sequenze escape ANSI/VT100
        _ansi = re.compile(r'(?:[@-Z\-_]|\[[0-?]*[ -/]*[@-~])')
        # Prompt tipici bash/zsh/sh: terminano con $ # > % seguito da spazio
        _prompt = re.compile(r'.*[\$#>%]\s+(.+)$')

        comandi = []
        try:
            with open(log_path, "r", errors="replace") as f:
                righe = f.readlines()
        except Exception as e:
            return []

        ts_file = datetime.fromtimestamp(
            __import__("os").path.getmtime(log_path)
        ).isoformat(timespec="seconds")

        for riga in righe:
            # Rimuovi sequenze ANSI e caratteri di controllo
            pulita = _ansi.sub("", riga)
            pulita = re.sub('[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', pulita)
            pulita = pulita.rstrip()
            if not pulita:
                continue

            m = _prompt.match(pulita)
            if m:
                cmd = m.group(1).strip()
                # Ignora comandi banali o artefatti
                if cmd and len(cmd) > 1 and not cmd.startswith("\\"):
                    comandi.append({
                        "ts":       ts_file,
                        "cmd":      cmd,
                        "sorgente": "log_xterm",
                    })

        return comandi

    def _genera_dialog_comandi(self, nome: str, profilo: dict,
                               term_widget, comandi_log: list):
        """
        Dialog unificato: mostra e permette di editare la lista comandi
        (PCM + log), genera comandi.sh con heredoc SSH.
        """
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                     QTextEdit, QPushButton, QFileDialog,
                                     QTableWidget, QTableWidgetItem, QHeaderView,
                                     QSplitter, QAbstractItemView, QCheckBox)
        from PyQt6.QtGui import QColor, QFont
        import os

        # Unisci comandi PCM + log, ordinati per timestamp
        comandi_pcm = getattr(term_widget, "_comandi_inviati", [])
        tutti = sorted(
            comandi_pcm + comandi_log,
            key=lambda c: c.get("ts", "")
        )
        # Deduplica: rimuovi comandi log che coincidono con comandi PCM
        cmds_pcm_set = {c["cmd"] for c in comandi_pcm}
        unici = []
        for c in tutti:
            if c["sorgente"] == "log_xterm" and c["cmd"] in cmds_pcm_set:
                continue  # già presente come comando PCM, salta
            unici.append(c)

        host  = profilo.get("host", "?")
        user  = profilo.get("user", "")
        port  = profilo.get("port", "22")
        proto = profilo.get("protocol", "ssh").upper()

        # ── Dialog ────────────────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Esporta comandi.sh — {nome}")
        dlg.setMinimumSize(740, 560)
        root = QVBoxLayout(dlg)

        lbl = QLabel(
            f"<b>Sessione:</b> {nome} &nbsp;|&nbsp; "
            f"<b>{proto}</b> {user+'@' if user else ''}{host}:{port} &nbsp;|&nbsp; "
            f"<b>{len(unici)}</b> comandi"
            + (f" &nbsp;<small style='color:#888'>({len(comandi_pcm)} PCM + "
               f"{len(comandi_log)} da log)</small>" if comandi_log else "")
        )
        lbl.setStyleSheet(
            "padding:6px; background:#f0f6ff; border-bottom:1px solid #c0d0e8;"
        )
        root.addWidget(lbl)

        if not unici:
            root.addWidget(QLabel(
                "\n  Nessun comando trovato.\n"
                "  Invia comandi tramite macro/multi-exec oppure\n"
                "  abilita il log e riconnetti la sessione.\n"
            ))
            btn = QPushButton("Chiudi")
            btn.clicked.connect(dlg.accept)
            root.addWidget(btn)
            dlg.exec()
            return

        spl = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(spl, 1)

        # ── Tabella comandi ────────────────────────────────────────────
        tbl = QTableWidget(len(unici), 3)
        tbl.setHorizontalHeaderLabels(["Timestamp", "Sorgente", "Comando"])
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        tbl.verticalHeader().setDefaultSectionSize(22)
        tbl.setAlternatingRowColors(True)
        tbl.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; font-size:11px; }"
            "QTableWidget::item:selected { background:#4e7abc; color:#ffffff; }"
            "QTableWidget::item:alternate { background:#f5f7fb; }"
        )
        COLORE = {
            "macro":       "#2d7a2d",
            "multi_exec":  "#0057a8",
            "startup_cmd": "#7a4a00",
            "log_xterm":   "#555555",
        }
        for row, c in enumerate(unici):
            ts_i  = QTableWidgetItem(c["ts"])
            src_i = QTableWidgetItem(c["sorgente"])
            cmd_i = QTableWidgetItem(c["cmd"])
            src_i.setForeground(QColor(COLORE.get(c["sorgente"], "#444")))
            src_i.setFont(QFont("monospace", 9, QFont.Weight.Bold))
            # Timestamp e sorgente non editabili
            ts_i.setFlags(ts_i.flags() & ~Qt.ItemFlag.ItemIsEditable)
            src_i.setFlags(src_i.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tbl.setItem(row, 0, ts_i)
            tbl.setItem(row, 1, src_i)
            tbl.setItem(row, 2, cmd_i)
        spl.addWidget(tbl)

        # ── Anteprima script ───────────────────────────────────────────
        txt = QTextEdit()
        txt.setStyleSheet(
            "background:#1a1a1a; color:#cccccc; "
            "font-family:monospace; font-size:11px; border:none;"
        )
        spl.addWidget(txt)
        spl.setSizes([240, 200])

        def _genera_script() -> str:
            cmds = [
                tbl.item(r, 2).text()
                for r in range(tbl.rowCount())
                if tbl.item(r, 2) and tbl.item(r, 2).text().strip()
            ]
            righe = [
                "#!/usr/bin/env bash",
                f"# comandi.sh — {nome}",
                f"# {proto} {user+'@' if user else ''}{host}:{port}",
                f"# {len(cmds)} comandi",
                "",
                "set -e",
                "",
            ]
            pre = profilo.get("pre_cmd", "").strip()
            if pre:
                righe += ["# Pre-connessione locale", pre, ""]

            wol_mac = profilo.get("wol_mac", "").strip()
            if profilo.get("wol_enabled") and wol_mac:
                wait = int(profilo.get("wol_wait", 20))
                righe += [
                    "# Wake-on-LAN",
                    f'wakeonlan "{wol_mac}" 2>/dev/null || true',
                    f'echo "WoL inviato, attendo {wait}s..."',
                    f"sleep {wait}", "",
                ]

            if proto == "SSH" and cmds:
                pkey = profilo.get("private_key", "").strip()
                ssh_args = [f"-p {port}", "-o StrictHostKeyChecking=no",
                            "-o ServerAliveInterval=15"]
                if pkey and os.path.exists(pkey):
                    ssh_args.append(f"-i '{pkey}'")
                jump = profilo.get("jump_host", "").strip()
                if jump:
                    ju = profilo.get("jump_user", "")
                    jp = profilo.get("jump_port", "22")
                    ssh_args.append(
                        f"-J {ju+'@' if ju else ''}{jump}:{jp}"
                    )
                target = f"{user}@{host}" if user else host
                righe += [
                    "# Replay comandi via SSH heredoc",
                    f"ssh {' '.join(ssh_args)} {target} << 'PCMREPLAY'",
                ]
                for cmd in cmds:
                    righe.append(cmd)
                righe += ["exit", "PCMREPLAY", ""]
            else:
                from session_command import build_command
                base_cmd, _ = build_command(profilo)
                if base_cmd:
                    righe += ["# Connessione", base_cmd, ""]
                if cmds:
                    righe += ["# Comandi registrati:"]
                    for c in cmds:
                        righe.append(f"# {c}")
            return "\n".join(righe)

        def _aggiorna():
            txt.setPlainText(_genera_script())

        _aggiorna()
        tbl.itemChanged.connect(lambda _: _aggiorna())

        # ── Toolbar tabella ────────────────────────────────────────────
        tb = QHBoxLayout()
        btn_su  = QPushButton("▲"); btn_su.setMaximumWidth(32)
        btn_giu = QPushButton("▼"); btn_giu.setMaximumWidth(32)
        btn_del = QPushButton("🗑  Rimuovi riga")

        def _sposta(d):
            r = tbl.currentRow(); n = r + d
            if 0 <= n < tbl.rowCount():
                for col in range(3):
                    a = tbl.takeItem(r, col)
                    b = tbl.takeItem(n, col)
                    tbl.setItem(r, col, b)
                    tbl.setItem(n, col, a)
                tbl.setCurrentCell(n, tbl.currentColumn())
                _aggiorna()

        btn_su.clicked.connect(lambda: _sposta(-1))
        btn_giu.clicked.connect(lambda: _sposta(1))
        btn_del.clicked.connect(lambda: (
            tbl.removeRow(tbl.currentRow()) if tbl.currentRow() >= 0 else None,
            _aggiorna()
        ))
        for b in (btn_su, btn_giu, btn_del):
            tb.addWidget(b)
        tb.addStretch()

        btn_salva  = QPushButton("💾  Salva comandi.sh…")
        btn_copia  = QPushButton("📋  Copia script")
        btn_chiudi = QPushButton("Chiudi")

        def _salva():
            nome_f = "comandi_" + nome.replace(" ", "_").replace("/", "_") + ".sh"
            path, _ = QFileDialog.getSaveFileName(
                dlg, "Salva comandi.sh",
                os.path.join(os.path.expanduser("~"), nome_f),
                "Script shell (*.sh);;Tutti i file (*)"
            )
            if path:
                with open(path, "w") as f:
                    f.write(txt.toPlainText())
                os.chmod(path, 0o755)
                QMessageBox.information(
                    dlg, "Salvato", f"Script salvato:\n{path}"
                )

        btn_salva.clicked.connect(_salva)
        btn_copia.clicked.connect(lambda: (
            QApplication.clipboard().setText(txt.toPlainText()),
            btn_copia.setText("✅  Copiato!")
        ))
        btn_chiudi.clicked.connect(dlg.accept)

        for b in (btn_salva, btn_copia, btn_chiudi):
            tb.addWidget(b)
        root.addLayout(tb)
        dlg.exec()

    def closeEvent(self, event):
        if self._chiusura_tab_in_corso:
            event.ignore()
            return

        n_sessioni = sum(
            1 for i in range(self.tabs.count())
            if hasattr(self.tabs.widget(i), "chiudi_processo")
        )
        tray_disponibile = hasattr(self, '_tray') and self._tray.isVisible()
        confirm = self._settings.get("general", {}).get("confirm_on_exit", True)

        if confirm and n_sessioni > 0:
            msg = QMessageBox(self)
            msg.setWindowTitle("Chiudi PCM")
            msg.setIcon(QMessageBox.Icon.Question)

            if tray_disponibile:
                msg.setText(f"Ci sono <b>{n_sessioni}</b> sessione/i attive.")
                msg.setInformativeText("Cosa vuoi fare?")
                btn_tray    = msg.addButton("🔽  Minimizza nel tray", QMessageBox.ButtonRole.AcceptRole)
                btn_chiudi  = msg.addButton("✖  Chiudi e termina tutto", QMessageBox.ButtonRole.DestructiveRole)
                btn_annulla = msg.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
                msg.setDefaultButton(btn_tray)
                msg.exec()
                clicked = msg.clickedButton()
                if clicked == btn_annulla:
                    event.ignore()
                    return
                elif clicked == btn_tray:
                    self.hide()
                    self._tray.showMessage(
                        "PCM in esecuzione",
                        "PCM continua in background. Doppio clic sull'icona per riaprire.",
                        QSystemTrayIcon.MessageIcon.Information, 3000
                    )
                    event.ignore()
                    return
                # btn_chiudi → prosegue con la chiusura definitiva
            else:
                msg.setText(f"Ci sono <b>{n_sessioni}</b> sessione/i attive.")
                msg.setInformativeText("Vuoi chiudere tutto e terminare PCM?")
                btn_chiudi  = msg.addButton("✖  Chiudi tutto", QMessageBox.ButtonRole.DestructiveRole)
                btn_annulla = msg.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
                msg.setDefaultButton(btn_annulla)
                msg.exec()
                if msg.clickedButton() != btn_chiudi:
                    event.ignore()
                    return

        elif tray_disponibile and not confirm:
            # Nessuna sessione attiva e tray disponibile: minimizza silenziosamente
            self.hide()
            event.ignore()
            return

        # --- Chiusura definitiva ---
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if hasattr(w, "chiudi_processo"):
                w.chiudi_processo()
            if hasattr(w, "chiudi_connessione"):
                w.chiudi_connessione()

        for nome, proc in self._processi_tunnel.items():
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass

        if self._tunnel_dialog:
            self._tunnel_dialog.ferma_tutti_alla_chiusura()

        if hasattr(self, '_tray'):
            self._tray.hide()

        event.accept()


# ==============================================================================
# Entry point
# ==============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("PCM")
    app.setApplicationVersion("1.0")
    app.setStyleSheet(APP_STYLESHEET)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())
