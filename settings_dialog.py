"""
settings_dialog.py - Impostazioni globali PCM stile MobaXterm
Tab: Generale, Terminale, SSH, Scorciatoie
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QWidget, QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QDialogButtonBox, QFileDialog, QSpinBox, QGroupBox, QKeySequenceEdit,
    QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import config_manager
from themes import TERMINAL_THEMES


class SettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Impostazioni PCM")
        self.setMinimumSize(540, 480)
        self.setModal(True)
        self._settings = config_manager.load_settings()
        self._init_ui()
        self._popola()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)

        hdr = QLabel("  ⚙  Impostazioni Globali")
        hdr.setStyleSheet("color:#6a9fd8; font-size:14px; font-weight:bold; padding:8px;")
        root.addWidget(hdr)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_generale(), "🏠 Generale")
        self.tabs.addTab(self._build_terminale(), "⌨ Terminale")
        self.tabs.addTab(self._build_ssh(), "🔐 SSH")
        self.tabs.addTab(self._build_scorciatoie(), "⌨ Scorciatoie")

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._salva_e_accetta)
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)

    # ------------------------------------------------------------------
    # Tab Generale
    # ------------------------------------------------------------------

    def _build_generale(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        home_row = QHBoxLayout()
        self.edit_home = QLineEdit()
        self.btn_home_browse = QPushButton("...")
        self.btn_home_browse.setMaximumWidth(30)
        self.btn_home_browse.clicked.connect(
            lambda: self._sfoglia_dir(self.edit_home, "Home directory persistente")
        )
        home_row.addWidget(self.edit_home)
        home_row.addWidget(self.btn_home_browse)
        layout.addRow("Home directory:", home_row)

        self.combo_editor = QComboBox()
        self.combo_editor.addItems(["nano", "vim", "vi", "gedit", "kate", "code", "mousepad"])
        self.combo_editor.setEditable(True)
        layout.addRow("Editor di testo:", self.combo_editor)

        self.chk_confirm_exit = QCheckBox("Chiedi conferma alla chiusura")
        layout.addRow("", self.chk_confirm_exit)

        return w

    # ------------------------------------------------------------------
    # Tab Terminale
    # ------------------------------------------------------------------

    def _build_terminale(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.combo_def_tema = QComboBox()
        for t in TERMINAL_THEMES.keys():
            self.combo_def_tema.addItem(t)
        layout.addRow("Tema predefinito:", self.combo_def_tema)

        self.combo_def_font = QComboBox()
        self.combo_def_font.addItems([
            "Monospace", "DejaVu Sans Mono", "Hack", "JetBrains Mono",
            "Fira Code", "Source Code Pro", "Inconsolata", "Terminus"
        ])
        layout.addRow("Font predefinito:", self.combo_def_font)

        self.spin_def_size = QSpinBox()
        self.spin_def_size.setRange(6, 32)
        self.spin_def_size.setMaximumWidth(60)
        layout.addRow("Dimensione font:", self.spin_def_size)

        self.spin_scrollback = QSpinBox()
        self.spin_scrollback.setRange(100, 100000)
        self.spin_scrollback.setSingleStep(1000)
        self.spin_scrollback.setMaximumWidth(90)
        layout.addRow("Righe scrollback:", self.spin_scrollback)

        self.chk_paste_right = QCheckBox("Incolla con tasto destro")
        layout.addRow("", self.chk_paste_right)

        self.chk_confirm_close = QCheckBox("Conferma chiusura tab con processo attivo")
        layout.addRow("", self.chk_confirm_close)

        self.chk_warn_paste = QCheckBox("Avverti prima di incollare più righe")
        layout.addRow("", self.chk_warn_paste)

        self.chk_log = QCheckBox("Registra output terminale su file")
        layout.addRow("", self.chk_log)

        log_row = QHBoxLayout()
        self.edit_log_dir = QLineEdit()
        btn_log = QPushButton("...")
        btn_log.setMaximumWidth(30)
        btn_log.clicked.connect(
            lambda: self._sfoglia_dir(self.edit_log_dir, "Cartella log")
        )
        log_row.addWidget(self.edit_log_dir)
        log_row.addWidget(btn_log)
        layout.addRow("Cartella log:", log_row)

        return w

    # ------------------------------------------------------------------
    # Tab SSH
    # ------------------------------------------------------------------

    def _build_ssh(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spin_ka = QSpinBox()
        self.spin_ka.setRange(0, 3600)
        self.spin_ka.setSuffix(" s")
        self.spin_ka.setMaximumWidth(80)
        layout.addRow("Keepalive interval:", self.spin_ka)

        self.chk_strict = QCheckBox("StrictHostKeyChecking (consigliato: disabilitato per lab)")
        layout.addRow("", self.chk_strict)

        self.chk_sftp_auto = QCheckBox("Apri browser SFTP automaticamente per sessioni SSH")
        layout.addRow("", self.chk_sftp_auto)

        return w

    # ------------------------------------------------------------------
    # Tab Scorciatoie
    # ------------------------------------------------------------------

    def _build_scorciatoie(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._shortcut_edits = {}
        shortcuts_cfg = self._settings.get("shortcuts", {})
        labels = {
            "new_terminal":   "Nuovo terminale locale",
            "close_tab":      "Chiudi tab",
            "prev_tab":       "Tab precedente",
            "next_tab":       "Tab successivo",
            "new_session":    "Nuova sessione remota",
            "toggle_sidebar": "Mostra/nascondi sidebar",
            "find":           "Cerca nel terminale",
            "fullscreen":     "Schermo intero",
        }
        for key, label in labels.items():
            val = shortcuts_cfg.get(key, "")
            edit = QLineEdit(val)
            edit.setMaximumWidth(180)
            self._shortcut_edits[key] = edit
            layout.addRow(f"{label}:", edit)

        nota = QLabel(
            "Nota: le scorciatoie sono applicate al riavvio dell'applicazione."
        )
        nota.setStyleSheet("color:#888; font-size:11px;")
        layout.addRow("", nota)

        return w

    # ------------------------------------------------------------------
    # Popola / Salva
    # ------------------------------------------------------------------

    def _popola(self):
        g = self._settings.get("general", {})
        self.edit_home.setText(g.get("home_dir", os.path.expanduser("~")))
        idx = self.combo_editor.findText(g.get("default_editor", "nano"))
        if idx >= 0:
            self.combo_editor.setCurrentIndex(idx)
        self.chk_confirm_exit.setChecked(g.get("confirm_on_exit", True))

        t = self._settings.get("terminal", {})
        idx = self.combo_def_tema.findText(t.get("default_theme", "Scuro (Default)"))
        if idx >= 0:
            self.combo_def_tema.setCurrentIndex(idx)
        idx = self.combo_def_font.findText(t.get("default_font", "Monospace"))
        if idx >= 0:
            self.combo_def_font.setCurrentIndex(idx)
        self.spin_def_size.setValue(t.get("default_font_size", 11))
        self.spin_scrollback.setValue(t.get("scrollback_lines", 10000))
        self.chk_paste_right.setChecked(t.get("paste_on_right_click", False))
        self.chk_confirm_close.setChecked(t.get("confirm_on_close", True))
        self.chk_warn_paste.setChecked(t.get("warn_multiline_paste", True))
        self.chk_log.setChecked(t.get("log_output", False))
        self.edit_log_dir.setText(t.get("log_dir", "/tmp/pcm_logs"))

        s = self._settings.get("ssh", {})
        self.spin_ka.setValue(s.get("keepalive_interval", 60))
        self.chk_strict.setChecked(s.get("strict_host_check", False))
        self.chk_sftp_auto.setChecked(s.get("default_sftp_browser", True))

        sc = self._settings.get("shortcuts", {})
        for key, edit in self._shortcut_edits.items():
            edit.setText(sc.get(key, ""))

    def _salva_e_accetta(self):
        s = self._settings

        s["general"]["home_dir"] = self.edit_home.text().strip()
        s["general"]["default_editor"] = self.combo_editor.currentText()
        s["general"]["confirm_on_exit"] = self.chk_confirm_exit.isChecked()

        s["terminal"]["default_theme"] = self.combo_def_tema.currentText()
        s["terminal"]["default_font"] = self.combo_def_font.currentText()
        s["terminal"]["default_font_size"] = self.spin_def_size.value()
        s["terminal"]["scrollback_lines"] = self.spin_scrollback.value()
        s["terminal"]["paste_on_right_click"] = self.chk_paste_right.isChecked()
        s["terminal"]["confirm_on_close"] = self.chk_confirm_close.isChecked()
        s["terminal"]["warn_multiline_paste"] = self.chk_warn_paste.isChecked()
        s["terminal"]["log_output"] = self.chk_log.isChecked()
        s["terminal"]["log_dir"] = self.edit_log_dir.text().strip()

        s["ssh"]["keepalive_interval"] = self.spin_ka.value()
        s["ssh"]["strict_host_check"] = self.chk_strict.isChecked()
        s["ssh"]["default_sftp_browser"] = self.chk_sftp_auto.isChecked()

        for key, edit in self._shortcut_edits.items():
            s["shortcuts"][key] = edit.text().strip()

        config_manager.save_settings(s)
        self.accept()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _sfoglia_dir(self, target_edit: QLineEdit, titolo: str):
        d = QFileDialog.getExistingDirectory(self, titolo)
        if d:
            target_edit.setText(d)
