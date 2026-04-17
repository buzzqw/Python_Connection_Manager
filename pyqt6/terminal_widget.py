"""
terminal_widget.py - Widget terminale xterm embedded per PCM
Supporta: embedding xterm, resize, log output, tema colori, keepalive
"""

import os
import signal
import subprocess
import shutil
from datetime import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QApplication, QMessageBox, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from translations import t


class TerminalWidget(QWidget):
    """
    Incorpora un processo xterm all'interno di un QWidget Qt.
    Gestisce resize dinamico, logging e invio comandi via xdotool.
    """

    processo_terminato = pyqtSignal()

    # Temi built-in
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
                 font_size=11, log_dir="", parent=None):
        super().__init__(parent)
        self._bg = bg
        self._fg = fg
        self._font = font
        self._font_size = self._parse_int(font_size, 11)
        self._log_dir = log_dir
        self._process = None
        self._comando_corrente = ""
        self._keepalive_tick = 0
        self._t_connessione = None   # datetime di connessione
        self._char_inviati  = 0      # caratteri inviati via invia_testo
        self._comandi_inviati: list  = []  # [(timestamp_iso, testo)] per replay export

        self._init_ui()

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._applica_resize)

        # Timer keepalive visivo + statistiche: aggiorna ogni 3 secondi
        self._keepalive_timer = QTimer(self)
        self._keepalive_timer.timeout.connect(self._controlla_processo)
        self._keepalive_timer.start(3000)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra comando (read-only, mostra il comando in esecuzione)
        self.barra_info = QLineEdit()
        self.barra_info.setReadOnly(True)
        self.barra_info.setFixedHeight(22)
        self.barra_info.setStyleSheet(
            "background-color:#252525; color:#888; "
            "font-family:monospace; font-size:11px; "
            "border:none; border-bottom:1px solid #444; padding:0 6px;"
        )
        layout.addWidget(self.barra_info)

        # Banner informativo selezione (con pulsante X per chiuderlo)
        self._banner = QWidget()
        self._banner.setStyleSheet(
            "background-color:#2a2a1a; border-bottom:1px solid #555;"
        )
        banner_layout = QHBoxLayout(self._banner)
        banner_layout.setContentsMargins(6, 2, 4, 2)
        banner_layout.setSpacing(4)
        self.lbl_scroll_hint = QLabel(
            "  ℹ  Limite xterm: la selezione è limitata alla videata corrente. "
            "Per copiare più pagine usa il log di sessione."
        )
        self.lbl_scroll_hint.setStyleSheet(
            "background-color:transparent; color:#aaa870; "
            "font-size:10px; border:none;"
        )
        btn_close_banner = QPushButton("✕")
        btn_close_banner.setFixedSize(16, 16)
        btn_close_banner.setStyleSheet(
            "QPushButton { background:transparent; color:#aaa870; border:none; "
            "font-size:10px; padding:0; } "
            "QPushButton:hover { color:#ffffff; }"
        )
        btn_close_banner.clicked.connect(lambda: self._banner.setVisible(False))
        banner_layout.addWidget(self.lbl_scroll_hint, 1)
        banner_layout.addWidget(btn_close_banner)
        self._banner.setVisible(False)  # mostrato solo quando xterm è attivo
        layout.addWidget(self._banner)

        # Contenitore xterm
        self.container = QWidget()
        self.container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.container.setStyleSheet(f"background-color:{self._bg};")
        layout.addWidget(self.container, 1)

    # ------------------------------------------------------------------
    # Avvio terminale
    # ------------------------------------------------------------------

    def avvia(self, comando: str):
        """Avvia xterm con il comando dato, embedded nel container Qt."""
        self._comando_corrente = comando
        # Mostra la stringa censurata se fornita da PCM.py, altrimenti usa quella normale
        cmd_show = getattr(self, 'comando_display', comando)
        self.barra_info.setText(f"  ▶  {cmd_show}")
        # Estrai startup_cmd remoto se presente nel comando SSH
        # Formato: ssh ... -t 'CMD; exec $SHELL -l'
        import re as _re
        _m = _re.search(r"-t '(.+?);\s*exec \$SHELL", comando)
        if _m:
            self._registra_comando(_m.group(1), sorgente="startup_cmd")
        self.show()
        self._banner.setVisible(True)
        QApplication.processEvents()

        if not shutil.which("xterm"):
            self._mostra_errore(t("terminal.xterm_missing"), t("terminal.xterm_install"))
            return

        w = max(self.container.width(), 400)
        h = max(self.container.height(), 200)
        cols, rows = self._calcola_dimensioni(w, h)
        win_id = str(int(self.container.winId()))

        # Gestione log
        log_arg = ""
        if self._log_dir:
            os.makedirs(self._log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self._log_dir, f"pcm_{ts}.log")
            log_arg = f"-l -lf '{log_file}'"

        # Traduzioni xterm: Ctrl+Shift+V incolla, Ctrl+C copia se selezionato
        traduz = (
            "#override\\n"
            "Ctrl Shift <Key>C: copy-selection(CLIPBOARD)\\n"
            "Ctrl Shift <Key>V: insert-selection(CLIPBOARD)\\n"
            "Ctrl <Key>v: insert-selection(CLIPBOARD)"
        )

        xterm_cmd = (
            f"xterm "
            f"-xrm 'XTerm.vt100.allowSendEvents: true' "
            f"-xrm 'XTerm.vt100.selectToClipboard: true' "
            f"-xrm 'XTerm.vt100.translations: {traduz}' "
            f"-xrm 'XTerm.vt100.scrollBar: false' "
            f"{log_arg} "
            f"-geometry {cols}x{rows} "
            f"-into {win_id} "
            f"-bg '{self._bg}' -fg '{self._fg}' "
            f"-fa '{self._font}' -fs {self._font_size} "
            f"-e {comando}"
        )

        self._process = subprocess.Popen(
            xterm_cmd, shell=True, preexec_fn=os.setsid
        )
        from datetime import datetime as _dt
        self._t_connessione = _dt.now()
        self._char_inviati  = 0
        QTimer.singleShot(600, self._applica_resize)

    def avvia_locale(self):
        """Avvia una shell bash locale."""
        shell = os.environ.get("SHELL", "bash")
        self.avvia(shell)

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(200)

    def _applica_resize(self):
        if not self._process:
            return
        w = self.container.width()
        h = self.container.height()
        wid = str(int(self.container.winId()))

        if not shutil.which("xdotool") or not shutil.which("xwininfo"):
            return

        cmd = (
            f"CHILD=$(xwininfo -id {wid} -children 2>/dev/null "
            f"| grep -E '^ *0x' | awk '{{print $1}}' | head -n 1);"
            f"if [ -n \"$CHILD\" ]; then xdotool windowsize $CHILD {w} {h}; fi"
        )
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _calcola_dimensioni(self, w, h):
        char_w = max(6, int(self._font_size * 0.62))
        char_h = max(12, int(self._font_size * 1.75))
        cols = max(40, int(w / char_w))
        rows = max(10, int(h / char_h))
        return cols, rows

    # ------------------------------------------------------------------
    # Invio comandi via xdotool
    # ------------------------------------------------------------------

    def _registra_comando(self, testo: str, sorgente: str = "macro"):
        """Registra un comando inviato per il replay export."""
        from datetime import datetime as _dt
        self._comandi_inviati.append({
            "ts":       _dt.now().isoformat(timespec="seconds"),
            "cmd":      testo,
            "sorgente": sorgente,   # "macro" | "multi_exec" | "startup_cmd"
        })

    def invia_testo(self, testo: str, invio=True, sorgente: str = "macro"):
        """
        Invia testo al terminale in modo istantaneo tramite clipboard X11.

        Strategia:
          1. Copia il testo nella CLIPBOARD di X11 con xclip/xsel (o QApplication).
          2. Invia Ctrl+Shift+V al terminale xterm (già mappato come "incolla da CLIPBOARD").
          3. Opzionalmente invia Return.

        Questo è ordini di grandezza più veloce di 'xdotool type --delay N'
        perché non simula la tastiera tasto per tasto.
        """
        self._char_inviati += len(testo)
        self._registra_comando(testo, sorgente=sorgente)
        if not shutil.which("xdotool") or not shutil.which("xwininfo"):
            self._mostra_errore(
                t("terminal.deps_missing"),
                t("terminal.install_xdotool")
            )
            return

        wid = str(int(self.container.winId()))

        # --- Passo 1: metti il testo nella CLIPBOARD X11 ---
        # Prima prova xclip (più diffuso), poi xsel, poi fallback PyQt6.
        testo_bytes = testo.encode("utf-8")
        clipboard_ok = False

        if shutil.which("xclip"):
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=testo_bytes, timeout=3,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                clipboard_ok = True
            except Exception:
                pass

        if not clipboard_ok and shutil.which("xsel"):
            try:
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=testo_bytes, timeout=3,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                clipboard_ok = True
            except Exception:
                pass

        if not clipboard_ok:
            # Fallback: usa QApplication.clipboard() (meno affidabile cross-window)
            try:
                from PyQt6.QtWidgets import QApplication
                QApplication.clipboard().setText(testo)
                clipboard_ok = True
            except Exception:
                pass

        if not clipboard_ok:
            self._mostra_errore(
                t("terminal.clipboard_unavail"),
                t("terminal.install_xclip")
            )
            return

        # --- Passo 2: attiva xterm e incolla con Ctrl+Shift+V ---
        invio_cmd = "xdotool key --window $CHILD Return" if invio else ""
        cmd = f"""
        CHILD=$(xwininfo -id {wid} -children 2>/dev/null | grep -E '^ *0x' | awk '{{print $1}}' | head -n 1)
        if [ -n "$CHILD" ]; then
            xdotool windowactivate --sync $CHILD
            xdotool key --window $CHILD --clearmodifiers ctrl+shift+v
            {invio_cmd}
        fi
        """
        subprocess.Popen(cmd, shell=True)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _controlla_processo(self):
        """Keepalive visivo + statistiche: aggiorna barra info ogni 3s."""
        if not self._process:
            return

        if self._process.poll() is not None:
            # Processo terminato
            self._keepalive_timer.stop()
            self.barra_info.setStyleSheet(
                "background-color:#4a1a1a; color:#ff6b6b; "
                "font-family:monospace; font-size:11px; "
                "border:none; border-bottom:1px solid #aa3333; padding:0 6px;"
            )
            self._banner.setVisible(False)
            self.barra_info.setText(t("terminal.session_ended"))
            self._process = None
            self.processo_terminato.emit()
            return

        # Processo vivo: mostra statistiche + animazione
        from datetime import datetime as _dt
        DOTS = ["●○○", "○●○", "○○●", "○●○"]
        dot = DOTS[self._keepalive_tick % len(DOTS)]
        self._keepalive_tick += 1

        # Durata connessione
        if self._t_connessione:
            delta = int((_dt.now() - self._t_connessione).total_seconds())
            if delta < 60:
                durata = f"{delta}s"
            elif delta < 3600:
                durata = f"{delta//60}m{delta%60:02d}s"
            else:
                durata = f"{delta//3600}h{(delta%3600)//60:02d}m"
        else:
            durata = ""

        # Caratteri inviati (approssimazione output)
        if self._char_inviati > 0:
            if self._char_inviati < 1024:
                chars = f"  📤 {self._char_inviati}B"
            else:
                chars = f"  📤 {self._char_inviati/1024:.1f}KB"
        else:
            chars = ""

        # Cerca prima la versione censurata, poi l'originale, infine il comando grezzo
        cmd_show = getattr(self, 'comando_display', getattr(self, 'comando_originale', self._comando_corrente))
        stat = f"  ⏱ {durata}{chars}" if durata else ""
        self.barra_info.setText(f"  {dot}  {cmd_show}{stat}")

    def chiudi_processo(self):
        if hasattr(self, '_keepalive_timer'):
            self._keepalive_timer.stop()
        if self._process:
            try:
                pgid = os.getpgid(self._process.pid)

                # 1. SIGTERM educato a tutto il process group (xterm + ssh + sshpass)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # il gruppo è già morto, va bene

                # 2. Aspettiamo che xterm termini (fino a 1 secondo)
                try:
                    self._process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    # 3. Se ancora vivo, SIGKILL senza pietà
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        self._process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        pass

                # 4. Raccoglie il processo comunque per evitare zombie
                try:
                    self._process.poll()
                except Exception:
                    pass

            except ProcessLookupError:
                pass  # processo già terminato
            except Exception as e:
                print(f"Errore chiusura terminale: {e}")
            finally:
                self._process = None

    def closeEvent(self, event):
        self.chiudi_processo()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_int(val, default):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _mostra_errore(self, titolo, msg):
        from PyQt6.QtWidgets import QLabel
        self.barra_info.setText(f"  ✖  {titolo}: {msg}")

    @classmethod
    def da_profilo(cls, profilo: dict, log_dir="") -> "TerminalWidget":
        """Factory: crea un TerminalWidget dai parametri di un profilo sessione."""
        from themes import TERMINAL_THEMES
        tema = profilo.get("term_theme", "Scuro (Default)")
        bg, fg = TERMINAL_THEMES.get(tema, ("#1e1e1e", "#cccccc"))
        font = profilo.get("term_font", "Monospace")
        size = profilo.get("term_size", 11)
        return cls(bg=bg, fg=fg, font=font, font_size=size, log_dir=log_dir)
