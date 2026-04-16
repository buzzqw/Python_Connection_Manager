#!/usr/bin/env python3
"""
Dependencies Configuration Dialog per PyQt6
Configurazione percorsi personalizzati per le dipendenze/tool esterni
Portato dalla versione GTK3
"""

import shutil
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QScrollArea, QHeaderView, QLineEdit, QFileDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import config_manager
from translations import t


class DepsConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurazione Dipendenze")
        self.setModal(True)
        self.resize(600, 400)
        
        self._settings = config_manager.load_settings()
        self._custom_paths = self._settings.get("tool_paths", {})
        
        self._tools = {
            "ssh": "SSH client", "scp": "SCP", "sftp": "SFTP client",
            "telnet": "Telnet", "ftp": "FTP client", "xfreerdp3": "FreeRDP 3.x",
            "xtigervncviewer": "TigerVNC", "xdotool": "xdotool", "wol": "Wake-on-LAN"
        }
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Tabella dipendenze
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Status", "Componente", "Comando Default", "Percorso Personalizzato"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        
        # Configura colonne
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self._reload_list()
        layout.addWidget(self._tree)

        # Pulsanti azione
        btn_layout = QHBoxLayout()
        
        btn_browse = QPushButton("📁 Sfoglia...")
        btn_browse.clicked.connect(self._browse_path)
        btn_layout.addWidget(btn_browse)
        
        btn_reset = QPushButton("🔄 Reset")
        btn_reset.clicked.connect(self._reset_path)
        btn_layout.addWidget(btn_reset)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Pulsanti dialog
        dialog_layout = QHBoxLayout()
        dialog_layout.addStretch()
        
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        dialog_layout.addWidget(btn_cancel)
        
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._save_and_accept)
        dialog_layout.addWidget(btn_ok)
        
        layout.addLayout(dialog_layout)

    def _reload_list(self):
        """Ricarica la lista delle dipendenze."""
        self._tree.clear()
        
        for tool_id, description in self._tools.items():
            # Controlla se il tool è disponibile
            detected_path = shutil.which(tool_id)
            custom_path = self._custom_paths.get(tool_id, "")
            
            # Determina lo status
            if custom_path and shutil.which(custom_path):
                status = "✅"
                effective_path = custom_path
            elif detected_path:
                status = "✅"
                effective_path = detected_path
            else:
                status = "❌"
                effective_path = "Non trovato"
            
            item = QTreeWidgetItem([
                status,
                description,
                tool_id,
                custom_path
            ])
            
            # Memorizza l'ID del tool nell'item
            item.setData(0, Qt.ItemDataRole.UserRole, tool_id)
            
            self._tree.addTopLevelItem(item)

    def _browse_path(self):
        """Apre un dialog per selezionare il percorso di un tool."""
        current = self._tree.currentItem()
        if not current:
            return
            
        tool_id = current.data(0, Qt.ItemDataRole.UserRole)
        if not tool_id:
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Seleziona percorso per {tool_id}",
            "",
            "Eseguibili (*)"
        )
        
        if file_path:
            current.setText(3, file_path)

    def _reset_path(self):
        """Resetta il percorso personalizzato per il tool selezionato."""
        current = self._tree.currentItem()
        if current:
            current.setText(3, "")

    def _save_and_accept(self):
        """Salva le configurazioni e chiude il dialog."""
        # Raccoglie tutti i percorsi personalizzati
        tool_paths = {}
        
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            tool_id = item.data(0, Qt.ItemDataRole.UserRole)
            custom_path = item.text(3).strip()
            
            if tool_id and custom_path:
                tool_paths[tool_id] = custom_path

        # Salva nei settings
        self._settings["tool_paths"] = tool_paths
        config_manager.save_settings(self._settings)
        
        self.accept()