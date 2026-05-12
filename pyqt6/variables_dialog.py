#!/usr/bin/env python3
"""
Variables Dialog per PyQt6
Gestione variabili {NOME} nei comandi delle sessioni
Portato dalla versione GTK3
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLineEdit, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import config_manager
from translations import t


class VariablesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("variables.title"))
        self.setModal(True)
        self.resize(450, 350)
        
        # Recupera le variabili salvate
        try:
            self._vars = config_manager.load_variables()
        except AttributeError:
            s = config_manager.load_settings()
            self._vars = s.get("variables", {})

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 8)

        # Etichetta informativa
        lbl = QLabel("Le variabili nel formato {NOME} verranno sostituite automaticamente nei comandi della sessione.")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        # Tabella variabili
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([t("variables.col_name"), t("variables.col_value")])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        
        # Rendi le colonne editabili
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # Popola la tabella
        for k, v in self._vars.items():
            item = QTreeWidgetItem([k, v])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._tree.addTopLevelItem(item)
        
        layout.addWidget(self._tree)

        # Pulsanti azione
        btn_layout = QHBoxLayout()
        
        self._btn_add = QPushButton(t("variables.btn_add"))
        self._btn_add.clicked.connect(self._add_variable)
        btn_layout.addWidget(self._btn_add)
        
        self._btn_remove = QPushButton(t("variables.btn_remove"))
        self._btn_remove.clicked.connect(self._remove_variable)
        btn_layout.addWidget(self._btn_remove)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Pulsanti dialog
        dialog_layout = QHBoxLayout()
        dialog_layout.addStretch()
        
        btn_cancel = QPushButton(t("variables.btn_cancel"))
        btn_cancel.clicked.connect(self.reject)
        dialog_layout.addWidget(btn_cancel)
        
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._save_and_accept)
        dialog_layout.addWidget(btn_ok)
        
        layout.addLayout(dialog_layout)

    def _add_variable(self):
        """Aggiunge una nuova variabile vuota."""
        item = QTreeWidgetItem(["NUOVA_VAR", ""])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._tree.addTopLevelItem(item)
        self._tree.setCurrentItem(item)
        self._tree.editItem(item, 0)

    def _remove_variable(self):
        """Rimuove la variabile selezionata."""
        current = self._tree.currentItem()
        if current:
            reply = QMessageBox.question(
                self,
                t("variables.confirm_delete_title"),
                t("variables.confirm_delete_msg").format(name=current.text(0)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                index = self._tree.indexOfTopLevelItem(current)
                self._tree.takeTopLevelItem(index)

    def _save_and_accept(self):
        """Salva le variabili e chiude il dialog."""
        # Raccoglie tutte le variabili dalla tabella
        variables = {}
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            name = item.text(0).strip()
            value = item.text(1).strip()
            
            if name:  # Ignora righe con nome vuoto
                variables[name] = value

        # Salva usando config_manager
        try:
            config_manager.save_variables(variables)
        except AttributeError:
            # Fallback: salva nei settings
            s = config_manager.load_settings()
            s["variables"] = variables
            config_manager.save_settings(s)

        self.accept()