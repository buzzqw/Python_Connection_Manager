import urllib.parse
import subprocess
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer

class VncWebWidget(QWidget):
    def __init__(self, host, port, password="", parent=None): 
        super().__init__(parent)
        self.host = host
        self.port = port
        self.password = password 
        self.novnc_proc = None
        self.local_ws_port = 8765 # Porta locale per il webserver/websocket
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Chiamiamo elegantemente l'eseguibile di sistema
        cmd = [
            "novnc", 
            "--listen", str(self.local_ws_port), 
            "--vnc", f"{self.host}:{self.port}"
        ]
        
        try:
            self.novnc_proc = subprocess.Popen(cmd)
        except FileNotFoundError:
            lbl = QLabel(" Errore: comando 'novnc' non trovato nel PATH di sistema.\n Assicurati di aver installato il pacchetto novnc.")
            lbl.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
            layout.addWidget(lbl)
            return
        except Exception as e:
            print(f"Errore avvio novnc: {e}")

        # 2. Crea il mini-browser
        self.webview = QWebEngineView()
        layout.addWidget(self.webview)
        
        # 3. Attendiamo mezzo secondo per dare tempo all'eseguibile di aprire la porta
        QTimer.singleShot(500, self._carica_pagina)

    def _carica_pagina(self):
        url = f"http://localhost:{self.local_ws_port}/vnc.html?host=localhost&port={self.local_ws_port}&autoconnect=true&show_dot=true"

        # Se la password esiste, la codifichiamo e la agganciamo all'URL
        if self.password:
            pwd_codificata = urllib.parse.quote(self.password)
            url += f"&password={pwd_codificata}"

        self.webview.setUrl(QUrl(url))

    def chiudi_processo(self):
        """Termina noVNC in background quando chiudi la scheda in PCM"""
        if self.novnc_proc:
            self.novnc_proc.terminate()
            self.novnc_proc.wait()
