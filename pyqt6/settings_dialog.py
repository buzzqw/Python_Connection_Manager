"""
settings_dialog.py - Impostazioni globali PCM
Tab: Generale (+ Language), Terminale, SSH, Scorciatoie
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QWidget, QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QDialogButtonBox, QFileDialog, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt

import config_manager
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
        self.tabs.addTab(self._build_scorciatoie(), t("settings.tab.shortcuts"))
        self.tabs.addTab(self._build_strumenti(),   t("settings.tab.tools"))

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
    # Tab Strumenti
    # ------------------------------------------------------------------

    def _build_strumenti(self) -> QWidget:
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setSpacing(12)

        # ── VNC ──────────────────────────────────────────────────────────
        grp_vnc = QGroupBox(t("settings.tools.vnc_group"))
        vnc_layout = QVBoxLayout(grp_vnc)

        self.tbl_vnc = self._make_tool_table()
        vnc_layout.addWidget(self.tbl_vnc)

        vnc_btn_row = QHBoxLayout()
        btn_add_vnc = QPushButton(t("settings.tools.add"))
        btn_add_vnc.clicked.connect(lambda: self._aggiungi_tool("vnc"))
        btn_rem_vnc = QPushButton(t("settings.tools.remove"))
        btn_rem_vnc.clicked.connect(lambda: self._rimuovi_tool(self.tbl_vnc))
        vnc_btn_row.addWidget(btn_add_vnc)
        vnc_btn_row.addWidget(btn_rem_vnc)
        vnc_btn_row.addStretch()
        vnc_layout.addLayout(vnc_btn_row)
        outer_layout.addWidget(grp_vnc)

        # ── RDP ──────────────────────────────────────────────────────────
        grp_rdp = QGroupBox(t("settings.tools.rdp_group"))
        rdp_layout = QVBoxLayout(grp_rdp)

        self.tbl_rdp = self._make_tool_table()
        rdp_layout.addWidget(self.tbl_rdp)

        rdp_btn_row = QHBoxLayout()
        btn_add_rdp = QPushButton(t("settings.tools.add"))
        btn_add_rdp.clicked.connect(lambda: self._aggiungi_tool("rdp"))
        btn_rem_rdp = QPushButton(t("settings.tools.remove"))
        btn_rem_rdp.clicked.connect(lambda: self._rimuovi_tool(self.tbl_rdp))
        rdp_btn_row.addWidget(btn_add_rdp)
        rdp_btn_row.addWidget(btn_rem_rdp)
        rdp_btn_row.addStretch()
        rdp_layout.addLayout(rdp_btn_row)
        outer_layout.addWidget(grp_rdp)

        nota = QLabel(t("settings.tools.note"))
        nota.setStyleSheet("color:#888; font-size:11px;")
        nota.setWordWrap(True)
        outer_layout.addWidget(nota)
        outer_layout.addStretch()

        return outer

    def _make_tool_table(self) -> QTableWidget:
        tbl = QTableWidget(0, 3)
        tbl.setHorizontalHeaderLabels([
            t("settings.tools.col_label"),
            t("settings.tools.col_path"),
            t("settings.tools.col_syntax"),
        ])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        tbl.setMaximumHeight(130)
        tbl.verticalHeader().setVisible(False)
        return tbl

    def _aggiungi_tool(self, category: str):
        syntaxes_vnc = ["TigerVNC", "RealVNC", "Remmina", "Generico"]
        syntaxes_rdp = ["xfreerdp", "rdesktop", "Generico"]
        syntaxes = syntaxes_vnc if category == "vnc" else syntaxes_rdp
        title_key = "settings.tools.dlg_title_vnc" if category == "vnc" else "settings.tools.dlg_title_rdp"

        dlg = QDialog(self)
        dlg.setWindowTitle(t(title_key))
        dlg.setMinimumWidth(420)
        layout = QFormLayout(dlg)
        layout.setSpacing(10)

        edit_label = QLineEdit()
        edit_label.setPlaceholderText("UltraVNC, AnyDesk…")
        layout.addRow(t("settings.tools.lbl_label"), edit_label)

        path_row = QHBoxLayout()
        edit_path = QLineEdit()
        edit_path.setPlaceholderText("/usr/bin/vncviewer")
        btn_browse = QPushButton(t("settings.tools.browse"))
        btn_browse.setMaximumWidth(90)
        btn_browse.clicked.connect(lambda: self._sfoglia_exe(edit_path))
        path_row.addWidget(edit_path)
        path_row.addWidget(btn_browse)
        layout.addRow(t("settings.tools.lbl_path"), path_row)

        combo_syntax = QComboBox()
        combo_syntax.addItems(syntaxes)
        layout.addRow(t("settings.tools.lbl_syntax"), combo_syntax)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addRow(bbox)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        label = edit_label.text().strip()
        path  = edit_path.text().strip()
        if not label or not path:
            return

        entry = {"label": label, "path": path, "syntax": combo_syntax.currentText()}
        tbl = self.tbl_vnc if category == "vnc" else self.tbl_rdp
        row = tbl.rowCount()
        tbl.insertRow(row)
        tbl.setItem(row, 0, QTableWidgetItem(entry["label"]))
        tbl.setItem(row, 1, QTableWidgetItem(entry["path"]))
        tbl.setItem(row, 2, QTableWidgetItem(entry["syntax"]))

    def _rimuovi_tool(self, tbl: QTableWidget):
        row = tbl.currentRow()
        if row >= 0:
            tbl.removeRow(row)

    def _sfoglia_exe(self, target_edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, t("settings.tools.browse"), "/usr/bin")
        if path:
            target_edit.setText(path)

    def _popola_tbl(self, tbl: QTableWidget, entries: list):
        tbl.setRowCount(0)
        for e in entries:
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, QTableWidgetItem(e.get("label", "")))
            tbl.setItem(row, 1, QTableWidgetItem(e.get("path", "")))
            tbl.setItem(row, 2, QTableWidgetItem(e.get("syntax", "")))

    def _leggi_tbl(self, tbl: QTableWidget) -> list:
        result = []
        for row in range(tbl.rowCount()):
            result.append({
                "label":  tbl.item(row, 0).text() if tbl.item(row, 0) else "",
                "path":   tbl.item(row, 1).text() if tbl.item(row, 1) else "",
                "syntax": tbl.item(row, 2).text() if tbl.item(row, 2) else "",
            })
        return result

    # ------------------------------------------------------------------
    # Popola / Salva
    # ------------------------------------------------------------------

    def _popola(self):
        g = self._settings.get("general", {})
        self.edit_home.setText(g.get("home_dir", os.path.expanduser("~")))
        self.chk_confirm_exit.setChecked(g.get("confirm_on_exit", True))

        lang_code = g.get("language", "it")
        for i in range(self.combo_lingua.count()):
            if self.combo_lingua.itemData(i) == lang_code:
                self.combo_lingua.setCurrentIndex(i)
                break

        sc = self._settings.get("shortcuts", {})
        for key, edit in self._shortcut_edits.items():
            edit.setText(sc.get(key, ""))

        ct = self._settings.get("custom_tools", {"vnc": [], "rdp": []})
        self._popola_tbl(self.tbl_vnc, ct.get("vnc", []))
        self._popola_tbl(self.tbl_rdp, ct.get("rdp", []))

    def _salva_e_accetta(self):
        s = self._settings

        s["general"]["home_dir"]        = self.edit_home.text().strip()
        s["general"]["confirm_on_exit"] = self.chk_confirm_exit.isChecked()

        lang_code = self.combo_lingua.currentData()
        s["general"]["language"] = lang_code
        set_lang(lang_code)

        for key, edit in self._shortcut_edits.items():
            s["shortcuts"][key] = edit.text().strip()

        s["custom_tools"] = {
            "vnc": self._leggi_tbl(self.tbl_vnc),
            "rdp": self._leggi_tbl(self.tbl_rdp),
        }

        config_manager.save_settings(s)
        self.accept()

    def _sfoglia_dir(self, target_edit: QLineEdit, titolo: str):
        d = QFileDialog.getExistingDirectory(self, titolo)
        if d:
            target_edit.setText(d)
