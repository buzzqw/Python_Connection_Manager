"""
terminal_widget.py - Widget terminale per PCM
Usa xterm.js via QWebEngineView — rendering perfetto, scroll nativo,
selezione multi-pagina, colori veri, vim/htop/clear funzionanti.
"""

import os
import pty
import signal
import select
import fcntl
import struct
import termios
import base64
import subprocess
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QHBoxLayout,
                              QPushButton, QApplication, QMenu)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtGui import QAction

from translations import t

# ── HTML / xterm.js ───────────────────────────────────────────────────────────
def _build_html(bg: str, fg: str, font: str, font_size: int,
                paste_on_right_click: bool = True, scrollback_lines: int = 5000) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css"/>
<script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
  body {{ margin:0; background:{bg}; overflow:hidden; height:100vh; }}
  #terminal {{ height:100%; width:100%; padding:4px; box-sizing:border-box; }}
</style>
</head>
<body>
<div id="terminal"></div>
<script>
const term = new Terminal({{
    theme: {{ background:'{bg}', foreground:'{fg}' }},
    fontFamily: '{font}, monospace',
    fontSize: {int(font_size * 1.35)},
    cursorBlink: true,
    allowProposedApi: true,
    scrollback: {scrollback_lines}
}});
const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);
term.open(document.getElementById('terminal'));

new QWebChannel(qt.webChannelTransport, function(channel) {{
    window.backend = channel.objects.backend;

    fitAddon.fit();
    window.backend.resize(term.cols, term.rows);

    term.onData(data => {{ window.backend.write(data); }});

    new ResizeObserver(() => {{
        fitAddon.fit();
        window.backend.resize(term.cols, term.rows);
    }}).observe(document.getElementById('terminal'));

    // Auto-copia selezione in clipboard (come xterm)
    term.onSelectionChange(() => {{
        const sel = term.getSelection();
        if (sel) window.backend.copyToClipboard(sel);
    }});

    // Ctrl+Shift+C → copia
    // Ctrl+Shift+V → incolla
    term.attachCustomKeyEventHandler(e => {{
        if (e.type === 'keydown') {{
            if (e.ctrlKey && e.shiftKey && e.code === 'KeyC') {{
                const sel = term.getSelection();
                if (sel) {{ window.backend.copyToClipboard(sel); term.clearSelection(); }}
                return false;
            }}
            if (e.ctrlKey && e.shiftKey && e.code === 'KeyV') {{
                window.backend.requestPaste();
                return false;
            }}
        }}
        return true;
    }});

    // Tasto destro: comportamento configurabile
    window.addEventListener('contextmenu', e => {{
        e.preventDefault();
        const sel = term.getSelection();
        if (sel) {{
            // Se c'è selezione: copia sempre
            window.backend.copyToClipboard(sel);
            term.clearSelection();
        }} else if ({'true' if paste_on_right_click else 'false'}) {{
            // Incolla solo se l'opzione è attiva
            window.backend.requestPaste();
        }}
    }});
}});

window.termWrite = function(b64) {{
    const raw = atob(b64);
    const arr = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    term.write(arr);
}};
</script>
</body>
</html>"""


# ── Backend QWebChannel ───────────────────────────────────────────────────────
class _Backend(QObject):
    def __init__(self, get_fd, log_callback=None):
        super().__init__()
        self._get_fd   = get_fd        # callable → fd PTY
        self._log_cb   = log_callback  # callable(data: bytes) per log su file

    @pyqtSlot(str)
    def write(self, data: str):
        fd = self._get_fd()
        if fd is not None:
            raw = data.encode('utf-8')
            if self._log_cb:
                self._log_cb(raw)
            try:
                os.write(fd, raw)
            except OSError:
                pass

    @pyqtSlot(int, int)
    def resize(self, cols: int, rows: int):
        fd = self._get_fd()
        if fd is not None:
            try:
                fcntl.ioctl(fd, termios.TIOCSWINSZ,
                            struct.pack("HHHH", rows, cols, 0, 0))
            except OSError:
                pass

    @pyqtSlot(str)
    def copyToClipboard(self, text: str):
        QApplication.clipboard().setText(text)

    @pyqtSlot()
    def requestPaste(self):
        text = QApplication.clipboard().text()
        if text:
            text = text.replace('\r\n', '\r').replace('\n', '\r')
            fd = self._get_fd()
            if fd is not None:
                try:
                    os.write(fd, text.encode('utf-8'))
                except OSError:
                    pass


# ── Thread lettura PTY ────────────────────────────────────────────────────────
class _PtyReader(QThread):
    data_ready = pyqtSignal(bytes)
    pty_closed  = pyqtSignal()

    def __init__(self, fd: int):
        super().__init__()
        self.fd = fd
        self._running = True

    def run(self):
        while self._running:
            try:
                r, _, _ = select.select([self.fd], [], [], 0.05)
                if r:
                    data = os.read(self.fd, 4096)
                    if data:
                        self.data_ready.emit(data)
                    else:
                        break
            except OSError:
                break
        self.pty_closed.emit()

    def stop(self):
        self._running = False


# ── TerminalWidget ────────────────────────────────────────────────────────────
class TerminalWidget(QWidget):
    """
    Terminale per PCM basato su xterm.js + QWebEngineView.
    API pubblica compatibile con la versione xterm embedded.
    """

    processo_terminato = pyqtSignal()

    TEMI = {
        "Scuro (Default)":  ("#1e1e1e", "#cccccc"),
        "Chiaro (B/W)":     ("#ffffff", "#1a1a1a"),
        "Matrix (Verde)":   ("#000000", "#00ff00"),
        "Dracula":          ("#282a36", "#f8f8f2"),
        "Nord":             ("#2e3440", "#d8dee9"),
        "Monokai":          ("#272822", "#f8f8f2"),
        "Solarized Dark":   ("#002b36", "#839496"),
        "Solarized Light":  ("#fdf6e3", "#657b83"),
        "One Dark":         ("#282c34", "#abb2bf"),
        "Gruvbox Dark":     ("#282828", "#ebdbb2"),
        "Tomorrow Night":   ("#1d1f21", "#c5c8c6"),
        "Cobalt":           ("#002240", "#ffffff"),
    }

    def __init__(self, bg="#1e1e1e", fg="#cccccc", font="Monospace",
                 font_size=11, log_dir="", paste_on_right_click=True,
                 scrollback_lines=5000, parent=None):
        super().__init__(parent)
        self._bg       = bg
        self._fg       = fg
        self._font     = font
        self._font_size = self._parse_int(font_size, 11)
        self._log_dir  = log_dir
        self._log_file = None
        self._paste_on_right_click = paste_on_right_click
        self._scrollback_lines     = scrollback_lines

        self._master    = None
        self._child_pid = None
        self._reader    = None
        self._pty_buffer = []   # dati arrivati prima che xterm.js sia pronto
        self._xterm_ready = False
        self._comando_corrente = ""
        self._keepalive_tick   = 0
        self._t_connessione    = None
        self._char_inviati     = 0
        self._comandi_inviati  = []

        # _process: compatibilità con PCM.py che controlla w._process
        self._process = None

        self._init_ui()

        self._keepalive_timer = QTimer(self)
        self._keepalive_timer.timeout.connect(self._controlla_processo)
        self._keepalive_timer.start(3000)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra info (compatibile con PCM.py)
        self.barra_info = QLineEdit()
        self.barra_info.setReadOnly(True)
        self.barra_info.setFixedHeight(22)
        self.barra_info.setStyleSheet(
            "background-color:#252525; color:#888; "
            "font-family:monospace; font-size:11px; "
            "border:none; border-bottom:1px solid #444; padding:0 6px;"
        )
        layout.addWidget(self.barra_info)

        # WebEngineView con xterm.js
        self._view = QWebEngineView()
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(self._view, 1)

        # WebChannel
        self._channel = QWebChannel()
        self._backend = _Backend(
            get_fd=lambda: self._master,
            log_callback=self._log_bytes
        )
        self._channel.registerObject("backend", self._backend)
        self._view.page().setWebChannel(self._channel)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def da_profilo(cls, profilo: dict, log_dir="") -> "TerminalWidget":
        from themes import TERMINAL_THEMES
        tema = profilo.get("term_theme", "Scuro (Default)")
        bg, fg = TERMINAL_THEMES.get(tema, ("#1e1e1e", "#cccccc"))
        font = profilo.get("term_font", "Monospace")
        size = profilo.get("term_size", 11)
        from config_manager import load_settings
        s = load_settings().get('terminal', {})
        paste_right    = s.get('paste_on_right_click', True)
        scrollback     = s.get('scrollback_lines', 5000)
        return cls(bg=bg, fg=fg, font=font, font_size=size, log_dir=log_dir,
                   paste_on_right_click=paste_right, scrollback_lines=scrollback)

    # ── Avvio ─────────────────────────────────────────────────────────────────

    def avvia(self, comando: str):
        self._comando_corrente = comando
        cmd_show = getattr(self, 'comando_display', comando)
        self.barra_info.setText(f"  ▶  {cmd_show}")

        # Log
        if self._log_dir:
            os.makedirs(self._log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                self._log_file = open(
                    os.path.join(self._log_dir, f"pcm_{ts}.log"), "wb")
            except OSError:
                self._log_file = None

        # PTY + fork
        self._child_pid, self._master = pty.fork()
        if self._child_pid == 0:
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            env["COLORTERM"] = "truecolor"
            if isinstance(comando, str):
                os.execvpe("/bin/sh", ["/bin/sh", "-c", comando], env)
            else:
                os.execvpe(comando[0], comando, env)
            os._exit(1)

        # _process per compatibilità PCM.py
        self._process = self._child_pid
        self._t_connessione = datetime.now()
        self._char_inviati  = 0
        self._pty_buffer    = []
        self._xterm_ready   = False

        # Carica HTML xterm.js
        html = _build_html(self._bg, self._fg, self._font, self._font_size,
                           self._paste_on_right_click, self._scrollback_lines)
        self._view.setHtml(html)
        # Quando la pagina è caricata, svuota il buffer
        self._view.loadFinished.connect(self._on_page_loaded)

        # Avvia reader PTY
        self._reader = _PtyReader(self._master)
        self._reader.data_ready.connect(self._on_pty_data)
        self._reader.pty_closed.connect(self._on_pty_closed)
        self._reader.start()

    def avvia_locale(self):
        shell = os.environ.get("SHELL", "bash")
        self.avvia(shell)

    # ── Dati PTY → xterm.js ───────────────────────────────────────────────────

    @pyqtSlot(bytes)
    def _on_pty_data(self, data: bytes):
        if self._log_file:
            self._log_bytes(data)
        if not self._xterm_ready:
            self._pty_buffer.append(data)
            return
        self._send_to_xterm(data)

    def _send_to_xterm(self, data: bytes):
        b64 = base64.b64encode(data).decode('ascii')
        self._view.page().runJavaScript(f"window.termWrite('{b64}');")

    @pyqtSlot(bool)
    def _on_page_loaded(self, ok: bool):
        """Pagina xterm.js caricata: invia i dati bufferizzati."""
        # Disconnetti per non chiamarla di nuovo su reload
        try:
            self._view.loadFinished.disconnect(self._on_page_loaded)
        except Exception:
            pass
        # Aspetta 200ms che JS finisca l'init prima di inviare
        QTimer.singleShot(200, self._flush_pty_buffer)

    def _flush_pty_buffer(self):
        self._xterm_ready = True
        for data in self._pty_buffer:
            self._send_to_xterm(data)
        self._pty_buffer.clear()

    def _log_bytes(self, data: bytes):
        if self._log_file:
            try:
                self._log_file.write(data)
                self._log_file.flush()
            except OSError:
                pass

    @pyqtSlot()
    def _on_pty_closed(self):
        self._keepalive_timer.stop()
        self.barra_info.setStyleSheet(
            "background-color:#4a1a1a; color:#ff6b6b; "
            "font-family:monospace; font-size:11px; "
            "border:none; border-bottom:1px solid #aa3333; padding:0 6px;"
        )
        self.barra_info.setText(t("terminal.session_ended"))
        self._process  = None
        self._child_pid = None
        self.processo_terminato.emit()

    # ── Invio testo/macro ─────────────────────────────────────────────────────

    def _registra_comando(self, testo: str, sorgente: str = "macro"):
        self._comandi_inviati.append({
            "ts":       datetime.now().isoformat(timespec="seconds"),
            "cmd":      testo,
            "sorgente": sorgente,
        })

    def invia_testo(self, testo: str, invio=True, sorgente: str = "macro"):
        self._char_inviati += len(testo)
        self._registra_comando(testo, sorgente=sorgente)
        data = testo.encode("utf-8")
        if invio:
            data += b"\r"
        if self._master is not None:
            try:
                os.write(self._master, data)
            except OSError:
                pass

    # ── Keepalive / barra stato ───────────────────────────────────────────────

    def _controlla_processo(self):
        if self._child_pid is None:
            return
        try:
            pid, _ = os.waitpid(self._child_pid, os.WNOHANG)
            if pid != 0:
                self._on_pty_closed()
                return
        except ChildProcessError:
            self._on_pty_closed()
            return

        DOTS = ["●○○", "○●○", "○○●", "○●○"]
        dot  = DOTS[self._keepalive_tick % len(DOTS)]
        self._keepalive_tick += 1

        if self._t_connessione:
            delta = int((datetime.now() - self._t_connessione).total_seconds())
            if delta < 60:     durata = f"{delta}s"
            elif delta < 3600: durata = f"{delta//60}m{delta%60:02d}s"
            else:              durata = f"{delta//3600}h{(delta%3600)//60:02d}m"
        else:
            durata = ""

        chars = ""
        if self._char_inviati > 0:
            chars = (f"  📤 {self._char_inviati}B" if self._char_inviati < 1024
                     else f"  📤 {self._char_inviati/1024:.1f}KB")

        cmd_show = getattr(self, 'comando_display',
                   getattr(self, 'comando_originale', self._comando_corrente))
        stat = f"  ⏱ {durata}{chars}" if durata else ""
        self.barra_info.setText(f"  {dot}  {cmd_show}{stat}")

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def chiudi_processo(self):
        if hasattr(self, '_keepalive_timer'):
            self._keepalive_timer.stop()

        if self._reader is not None:
            self._reader.stop()
            self._reader.wait(500)
            self._reader = None

        # Chiude prima il master PTY: bash riceve EIO e termina senza aspettare
        if self._master is not None:
            try:
                os.close(self._master)
            except OSError:
                pass
            self._master = None

        if self._child_pid is not None:
            try:
                os.killpg(os.getpgid(self._child_pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            try:
                # WNOHANG: non blocca il main thread
                os.waitpid(self._child_pid, os.WNOHANG)
            except (ChildProcessError, OSError):
                pass
            self._child_pid = None
            self._process   = None

        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None

    def closeEvent(self, event):
        self.chiudi_processo()
        super().closeEvent(event)

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_int(val, default):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _mostra_errore(self, titolo, msg):
        self.barra_info.setText(f"  ✖  {titolo}: {msg}")
