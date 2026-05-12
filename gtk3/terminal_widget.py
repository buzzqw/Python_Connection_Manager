"""
terminal_widget.py - Widget terminale VTE per PCM (GTK3)

Sostituisce l'embedding xterm (X11-only) con Vte.Terminal, che:
  - funziona nativamente su Wayland
  - supporta resize automatico
  - permette feed_child() invece di xdotool
  - supporta temi colore, font, scrollback via API diretta
  - è disponibile su FreeBSD (vte3) e Linux

Dipendenze:
  python3-gi, gir1.2-vte-2.91   (Debian/Ubuntu)
  py311-gobject3, vte3           (FreeBSD)
"""

import os
import signal
import subprocess
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, Gdk, GLib, Vte, GObject

from translations import t


def _hex_to_rgba(hex_color: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(hex_color)
    return rgba


class TerminalWidget(Gtk.Box):
    """
    Widget terminale basato su VTE.
    Segnale: 'processo-terminato' emesso quando il processo figlio esce.
    """

    __gsignals__ = {
        "processo-terminato": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # Temi built-in: (background, foreground)
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
                 font_size=11, log_dir="", paste_on_right_click=False, parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._bg = bg
        self._fg = fg
        self._font = font
        self._font_size = self._parse_int(font_size, 11)
        self._log_dir = log_dir
        self._paste_on_right_click = paste_on_right_click
        self._pid = -1
        self._comando_corrente = ""
        self._keepalive_tick = 0
        self._t_connessione = None
        self._char_inviati = 0
        self._comandi_inviati: list = []

        self._init_ui()

        # Timer keepalive / statistiche ogni 3 secondi
        self._keepalive_source = GLib.timeout_add(3000, self._controlla_processo)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        # ── Terminale VTE (occupa tutta l'area) ──────────────────────
        self._vte = Vte.Terminal()
        self._vte.set_scrollback_lines(10000)  # Default, verrà sovrascritto da imposta_scrollback
        self._applica_tema()
        self._applica_font()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._vte)
        self.pack_start(scroll, True, True, 0)

        # _stato_testo: testo live letto dalla statusbar di PCM via get_stato()
        self._stato_testo = ""
        self._stato_terminato = False

        # Segnale fine processo e selezione testo
        self._vte.connect("child-exited", self._on_child_exited)
        self._vte.connect("selection-changed", self._on_selection_changed)
        
        # Clic destro → incolla; Ctrl+Shift+V → incolla esplicito
        self._vte.connect("button-press-event", self._on_button_press)
        self._vte.connect("key-press-event", self._on_key_press)
        
    def _on_selection_changed(self, terminal):
        """Copia automaticamente il testo evidenziato nella clipboard principale."""
        if terminal.get_has_selection():
            terminal.copy_clipboard()    

    def get_stato(self) -> tuple[str, bool]:
        """Restituisce (testo_stato, è_terminato) per la statusbar di PCM."""
        return self._stato_testo, self._stato_terminato



    # ------------------------------------------------------------------
    # Avvio
    # ------------------------------------------------------------------

    def avvia(self, comando: str, env_extra: dict = None):
        """
        Avvia il comando nella VTE.
        Il comando viene passato a /bin/sh -c per supportare pipeline e opzioni.
        env_extra: variabili d'ambiente aggiuntive da iniettare (es. PCM_PWD_FIFO).
        """
        self._comando_corrente = comando
        cmd_show = getattr(self, "comando_display", comando)
        self._stato_testo = f"▶  {cmd_show}"
        self._stato_terminato = False

        # Logging: redirige output su file tramite script(1) se richiesto
        if self._log_dir:
            os.makedirs(self._log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self._log_dir, f"pcm_{ts}.log")
            argv = ["/bin/sh", "-c",
                    f"script -q -c {_shell_quote(comando)} {_shell_quote(log_file)}"]
        else:
            argv = ["/bin/sh", "-c", comando]

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        if env_extra:
            env.update(env_extra)

        try:
            result = self._vte.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                None,          # working dir (None = home)
                argv,
                [f"{k}={v}" for k, v in env.items()],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None, None,    # child setup
                None           # cancellable
            )
            # spawn_sync ritorna una _ResultTuple: estraiamo solo il pid intero
            # In VTE ≥ 0.62 ritorna (pid,), in alcune versioni (bool, pid)
            if isinstance(result, (tuple, list)):
                self._pid = int(result[-1])  # l'ultimo elemento è sempre il pid
            else:
                self._pid = int(result)
        except GLib.Error as e:
            self._stato_testo = f"✖  Errore avvio: {e.message}"
            self._stato_terminato = True
            return

        self._t_connessione = datetime.now()
        self._char_inviati = 0

        # Registra startup_cmd se presente nel comando SSH
        import re as _re
        m = _re.search(r"-t '(.+?);\s*exec \$SHELL", comando)
        if m:
            self._registra_comando(m.group(1), sorgente="startup_cmd")

    def avvia_locale(self):
        """Avvia la shell di login dell'utente."""
        shell = os.environ.get("SHELL", "/bin/bash")
        self.avvia(shell)

    # ------------------------------------------------------------------
    # Invio testo al terminale
    # ------------------------------------------------------------------

    def invia_testo(self, testo: str, invio=True, sorgente: str = "macro"):
        """
        Invia testo direttamente al processo VTE tramite feed_child().
        Molto più pulito e affidabile rispetto a xdotool.
        """
        self._char_inviati += len(testo)
        self._registra_comando(testo, sorgente=sorgente)

        payload = testo
        if invio:
            payload += "\n"

        try:
            encoded = payload.encode("utf-8")
            self._vte.feed_child(encoded)
        except Exception as e:
            print(f"[terminal] Errore feed_child: {e}")

    def _registra_comando(self, testo: str, sorgente: str = "macro"):
        self._comandi_inviati.append({
            "ts":       datetime.now().isoformat(timespec="seconds"),
            "cmd":      testo,
            "sorgente": sorgente,
        })

    # ------------------------------------------------------------------
    # Tema e font
    # ------------------------------------------------------------------

    def _applica_tema(self):
        fg = _hex_to_rgba(self._fg)
        bg = _hex_to_rgba(self._bg)
        self._vte.set_colors(fg, bg, [])

    def _applica_font(self):
        import gi
        gi.require_version("Pango", "1.0")
        from gi.repository import Pango
        font_desc = Pango.FontDescription(f"{self._font} {self._font_size}")
        self._vte.set_font(font_desc)

    def imposta_tema(self, tema_nome: str):
        """Cambia tema a runtime."""
        from themes import TERMINAL_THEMES
        bg, fg = TERMINAL_THEMES.get(tema_nome, ("#1e1e1e", "#cccccc"))
        self._bg = bg
        self._fg = fg
        self._applica_tema()

    def imposta_scrollback(self, righe: int):
        self._vte.set_scrollback_lines(righe)

    def grab_focus(self):
        self._vte.grab_focus()

    # ------------------------------------------------------------------
    # Keepalive / statistiche
    # ------------------------------------------------------------------

    def _controlla_processo(self) -> bool:
        """Chiamato ogni 3 secondi da GLib.timeout_add. Ritorna True per continuare."""
        if self._pid <= 0:
            return True  # nessun processo avviato ancora

        DOTS = ["●○○", "○●○", "○○●", "○●○"]
        dot = DOTS[self._keepalive_tick % len(DOTS)]
        self._keepalive_tick += 1

        if self._t_connessione:
            delta = int((datetime.now() - self._t_connessione).total_seconds())
            if delta < 60:
                durata = f"{delta}s"
            elif delta < 3600:
                durata = f"{delta//60}m{delta%60:02d}s"
            else:
                durata = f"{delta//3600}h{(delta%3600)//60:02d}m"
        else:
            durata = ""

        if self._char_inviati > 0:
            if self._char_inviati < 1024:
                chars = f"  📤 {self._char_inviati}B"
            else:
                chars = f"  📤 {self._char_inviati/1024:.1f}KB"
        else:
            chars = ""

        cmd_show = getattr(self, "comando_display",
                   getattr(self, "comando_originale", self._comando_corrente))
        stat = f"  ⏱ {durata}{chars}" if durata else ""
        self._stato_testo = f"{dot}  {cmd_show}{stat}"
        return True  # continua il timer

    def _on_child_exited(self, terminal, status):
        """Chiamato da VTE quando il processo figlio termina."""
        self._pid = -1
        if self._keepalive_source:
            GLib.source_remove(self._keepalive_source)
            self._keepalive_source = None

        self._stato_testo = t("terminal.session_ended")
        self._stato_terminato = True
        self.emit("processo-terminato")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def chiudi_processo(self):
        if self._keepalive_source:
            GLib.source_remove(self._keepalive_source)
            self._keepalive_source = None
        if self._pid > 0:
            try:
                pgid = os.getpgid(self._pid)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    pgid = None
                if pgid is not None:
                    def _sigkill(gid):
                        try:
                            os.killpg(gid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        return False  # non ripetere
                    GLib.timeout_add(500, _sigkill, pgid)
            except Exception as e:
                print(f"[terminal] Errore chiusura: {e}")
            finally:
                self._pid = -1

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_int(val, default):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _on_button_press(self, terminal, event):
        """Tasto destro → incolla dalla clipboard CLIPBOARD (stessa di Ctrl+V)."""
        if event.button == 3:
            if self._paste_on_right_click:
                self._incolla_clipboard()
            return True   # blocca il menu contestuale VTE
        return False

    def _on_key_press(self, terminal, event):
        """Ctrl+Shift+V → incolla esplicito (fallback se VTE non lo gestisce)."""
        ctrl  = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        key   = Gdk.keyval_name(event.keyval).upper()
        if ctrl and shift and key == "V":
            self._incolla_clipboard()
            return True
        return False

    def _incolla_clipboard(self):
        """Incolla dalla CLIPBOARD (Ctrl+C/Ctrl+X) nel terminale tramite feed_child."""
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        testo = clipboard.wait_for_text()
        if testo:
            self._vte.feed_child(testo.encode("utf-8"))

    @classmethod
    def da_profilo(cls, profilo: dict, log_dir="") -> "TerminalWidget":
        """Factory: crea un TerminalWidget dai parametri di un profilo sessione."""
        from themes import TERMINAL_THEMES
        tema = profilo.get("term_theme", "Scuro (Default)")
        bg, fg = TERMINAL_THEMES.get(tema, ("#1e1e1e", "#cccccc"))
        font = profilo.get("term_font", "Monospace")
        size = profilo.get("term_size", 11)
        paste_right = profilo.get("paste_on_right_click", False)
        scrollback = profilo.get("term_scrollback_lines", 10000)
        infinite_sb = profilo.get("term_infinite_scrollback", False)
        widget = cls(bg=bg, fg=fg, font=font, font_size=size, log_dir=log_dir,
                     paste_on_right_click=paste_right)
        if infinite_sb:
            widget.imposta_scrollback(-1)
        else:
            widget.imposta_scrollback(scrollback)
        return widget


# ---------------------------------------------------------------------------
# Helper quoting shell-safe
# ---------------------------------------------------------------------------

def _shell_quote(s: str) -> str:
    import shlex
    return shlex.quote(s)
