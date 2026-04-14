"""
vnc_widget.py - Widget VNC per PCM (GTK3)

Usa WebKit2.WebView (WebKitGTK) al posto di QWebEngineView.
Lancia novnc in background e carica la pagina web nel widget.

Dipendenze:
  python3-gi, gir1.2-webkit2-4.1   (Debian/Ubuntu)
  py311-gobject3, webkit2-gtk3      (FreeBSD)
"""

import urllib.parse
import subprocess

import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, GLib, WebKit2


class VncWebWidget(Gtk.Box):

    def __init__(self, host, port, password="", parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.host = host
        self.port = port
        self.password = password
        self.novnc_proc = None
        self.local_ws_port = 8765

        self._init_ui()

    def _init_ui(self):
        cmd = [
            "novnc",
            "--listen", str(self.local_ws_port),
            "--vnc", f"{self.host}:{self.port}"
        ]
        try:
            self.novnc_proc = subprocess.Popen(cmd)
        except FileNotFoundError:
            lbl = Gtk.Label(
                label="Errore: comando 'novnc' non trovato nel PATH.\n"
                      "Assicurati di aver installato il pacchetto novnc."
            )
            lbl.set_xalign(0.0)
            lbl.get_style_context().add_class("error-label")
            self.pack_start(lbl, True, True, 20)
            return
        except Exception as e:
            print(f"[vnc] Errore avvio novnc: {e}")

        # WebKit2 WebView
        self.webview = WebKit2.WebView()
        self.pack_start(self.webview, True, True, 0)

        # Attende 500ms per dare tempo a novnc di aprire la porta
        GLib.timeout_add(500, self._carica_pagina)

    def _carica_pagina(self):
        url = (
            f"http://localhost:{self.local_ws_port}"
            f"/vnc.html?host=localhost&port={self.local_ws_port}"
            f"&autoconnect=true&show_dot=true"
        )
        if self.password:
            pwd_enc = urllib.parse.quote(self.password)
            url += f"&password={pwd_enc}"
        self.webview.load_uri(url)
        return False  # non ripetere il timeout

    def chiudi_processo(self):
        if self.novnc_proc:
            self.novnc_proc.terminate()
            self.novnc_proc.wait()
