"""
settings_dialog.py - Impostazioni globali PCM
Tab: Generale (+ Language), Terminale, SSH, Scorciatoie
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QWidget, QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QDialogButtonBox, QFileDialog, QSpinBox, QFrame
)
from PyQt6.QtCore import Qt

import config_manager
from themes import TERMINAL_THEMES
from translations import t, AVAILABLE_LANGUAGES, set_lang


class SettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings.title"))
        self.setMinimumSize(560, 500)
        self.setModal(True)
        self._settings = config_manager.load_settings()
        self._init_ui()
        self._popola()

    def _init_ui(self):
        root = QVBoxLayout(self)

        hdr = QLabel(t("settings.header"))
        hdr.setStyleSheet("color:#6a9fd8; font-size:14px; font-weight:bold; padding:8px;")
        root.addWidget(hdr)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_generale(),    t("settings.tab.general"))
        self.tabs.addTab(self._build_terminale(),   t("settings.tab.terminal"))
        self.tabs.addTab(self._build_ssh(),         t("settings.tab.ssh"))
        self.tabs.addTab(self._build_scorciatoie(), t("settings.tab.shortcuts"))

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
            lambda: self._sfoglia_dir(self.edit_home, "Home directory")
        )
        home_row.addWidget(self.edit_home)
        home_row.addWidget(self.btn_home_browse)
        layout.addRow(t("settings.general.home_dir"), home_row)

        self.combo_editor = QComboBox()
        self.combo_editor.addItems(["nano", "vim", "vi", "gedit", "kate", "code", "mousepad"])
        self.combo_editor.setEditable(True)
        layout.addRow(t("settings.general.editor"), self.combo_editor)

        self.chk_confirm_exit = QCheckBox(t("settings.general.confirm_exit"))
        layout.addRow("", self.chk_confirm_exit)

        # Separatore visivo prima della lingua
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#ccc; margin-top:8px; margin-bottom:4px;")
        layout.addRow(sep)

        # ── Selettore lingua ─────────────────────────────────────────────
        # L'etichetta è SEMPRE fissa "Language / Lingua:" — universalmente
        # comprensibile indipendentemente dalla lingua corrente dell'UI.
        # Il combo mostra i nomi delle lingue nella lingua nativa (es. "Français").
        self.combo_lingua = QComboBox()
        self.combo_lingua.setMinimumWidth(180)
        for code, label in AVAILABLE_LANGUAGES.items():
            self.combo_lingua.addItem(label, code)   # userData = codice ISO

        # L'etichetta è fissa (non tradotta) per garantire leggibilità in qualsiasi lingua
        layout.addRow("Language / Lingua:", self.combo_lingua)

        lbl_note = QLabel(t("settings.general.language_note"))
        lbl_note.setStyleSheet("color:#888; font-size:11px;")
        lbl_note.setWordWrap(True)
        layout.addRow("", lbl_note)

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
        for tema in TERMINAL_THEMES.keys():
            self.combo_def_tema.addItem(tema)
        layout.addRow(t("settings.terminal.default_theme"), self.combo_def_tema)

        self.combo_def_font = QComboBox()
        self.combo_def_font.addItems([
            "Monospace", "DejaVu Sans Mono", "Hack", "JetBrains Mono",
            "Fira Code", "Source Code Pro", "Inconsolata", "Terminus"
        ])
        layout.addRow(t("settings.terminal.default_font"), self.combo_def_font)

        self.spin_def_size = QSpinBox()
        self.spin_def_size.setRange(6, 32)
        self.spin_def_size.setMaximumWidth(60)
        layout.addRow(t("settings.terminal.font_size"), self.spin_def_size)

        self.spin_scrollback = QSpinBox()
        self.spin_scrollback.setRange(100, 100000)
        self.spin_scrollback.setSingleStep(1000)
        self.spin_scrollback.setMaximumWidth(90)
        layout.addRow(t("settings.terminal.scrollback"), self.spin_scrollback)

        self.chk_paste_right = QCheckBox(t("settings.terminal.paste_right"))
        layout.addRow("", self.chk_paste_right)

        self.chk_confirm_close = QCheckBox(t("settings.terminal.confirm_close"))
        layout.addRow("", self.chk_confirm_close)

        self.chk_warn_paste = QCheckBox(t("settings.terminal.warn_paste"))
        layout.addRow("", self.chk_warn_paste)

        self.chk_log = QCheckBox(t("settings.terminal.log_output"))
        layout.addRow("", self.chk_log)

        log_row = QHBoxLayout()
        self.edit_log_dir = QLineEdit()
        btn_log = QPushButton("...")
        btn_log.setMaximumWidth(30)
        btn_log.clicked.connect(
            lambda: self._sfoglia_dir(self.edit_log_dir, "Log folder")
        )
        log_row.addWidget(self.edit_log_dir)
        log_row.addWidget(btn_log)
        layout.addRow(t("settings.terminal.log_dir"), log_row)

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
        layout.addRow(t("settings.ssh.keepalive"), self.spin_ka)

        self.chk_strict = QCheckBox(t("settings.ssh.strict"))
        layout.addRow("", self.chk_strict)

        self.chk_sftp_auto = QCheckBox(t("settings.ssh.sftp_auto"))
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
            "new_terminal":   "settings.shortcuts.new_terminal",
            "close_tab":      "settings.shortcuts.close_tab",
            "prev_tab":       "settings.shortcuts.prev_tab",
            "next_tab":       "settings.shortcuts.next_tab",
            "new_session":    "settings.shortcuts.new_session",
            "toggle_sidebar": "settings.shortcuts.toggle_sidebar",
            "find":           "settings.shortcuts.find",
            "fullscreen":     "settings.shortcuts.fullscreen",
        }
        for key, t_key in labels.items():
            val = shortcuts_cfg.get(key, "")
            edit = QLineEdit(val)
            edit.setMaximumWidth(180)
            self._shortcut_edits[key] = edit
            layout.addRow(f"{t(t_key)}:", edit)

        nota = QLabel(t("settings.shortcuts.note"))
        nota.setStyleSheet("color:#888; font-size:11px;")
        nota.setWordWrap(True)
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

        # Lingua corrente
        lang_code = g.get("language", "it")
        for i in range(self.combo_lingua.count()):
            if self.combo_lingua.itemData(i) == lang_code:
                self.combo_lingua.setCurrentIndex(i)
                break

        t_ = self._settings.get("terminal", {})
        idx = self.combo_def_tema.findText(t_.get("default_theme", "Scuro (Default)"))
        if idx >= 0:
            self.combo_def_tema.setCurrentIndex(idx)
        idx = self.combo_def_font.findText(t_.get("default_font", "Monospace"))
        if idx >= 0:
            self.combo_def_font.setCurrentIndex(idx)
        self.spin_def_size.setValue(t_.get("default_font_size", 11))
        self.spin_scrollback.setValue(t_.get("scrollback_lines", 10000))
        self.chk_paste_right.setChecked(t_.get("paste_on_right_click", False))
        self.chk_confirm_close.setChecked(t_.get("confirm_on_close", True))
        self.chk_warn_paste.setChecked(t_.get("warn_multiline_paste", True))
        self.chk_log.setChecked(t_.get("log_output", False))
        self.edit_log_dir.setText(t_.get("log_dir", "/tmp/pcm_logs"))

        s = self._settings.get("ssh", {})
        self.spin_ka.setValue(s.get("keepalive_interval", 60))
        self.chk_strict.setChecked(s.get("strict_host_check", False))
        self.chk_sftp_auto.setChecked(s.get("default_sftp_browser", True))

        sc = self._settings.get("shortcuts", {})
        for key, edit in self._shortcut_edits.items():
            edit.setText(sc.get(key, ""))

    def _salva_e_accetta(self):
        s = self._settings

        s["general"]["home_dir"]        = self.edit_home.text().strip()
        s["general"]["default_editor"]  = self.combo_editor.currentText()
        s["general"]["confirm_on_exit"] = self.chk_confirm_exit.isChecked()

        # ── Lingua ────────────────────────────────────────────────────
        lang_code = self.combo_lingua.currentData()   # codice ISO es. "en"
        s["general"]["language"] = lang_code
        set_lang(lang_code)   # applica in memoria (UI si aggiornerà al riavvio)

        s["terminal"]["default_theme"]       = self.combo_def_tema.currentText()
        s["terminal"]["default_font"]        = self.combo_def_font.currentText()
        s["terminal"]["default_font_size"]   = self.spin_def_size.value()
        s["terminal"]["scrollback_lines"]    = self.spin_scrollback.value()
        s["terminal"]["paste_on_right_click"]= self.chk_paste_right.isChecked()
        s["terminal"]["confirm_on_close"]    = self.chk_confirm_close.isChecked()
        s["terminal"]["warn_multiline_paste"]= self.chk_warn_paste.isChecked()
        s["terminal"]["log_output"]          = self.chk_log.isChecked()
        s["terminal"]["log_dir"]             = self.edit_log_dir.text().strip()

        s["ssh"]["keepalive_interval"]   = self.spin_ka.value()
        s["ssh"]["strict_host_check"]    = self.chk_strict.isChecked()
        s["ssh"]["default_sftp_browser"] = self.chk_sftp_auto.isChecked()

        for key, edit in self._shortcut_edits.items():
            s["shortcuts"][key] = edit.text().strip()

        config_manager.save_settings(s)
        self.accept()

    def _sfoglia_dir(self, target_edit: QLineEdit, titolo: str):
        d = QFileDialog.getExistingDirectory(self, titolo)
        if d:
            target_edit.setText(d)
