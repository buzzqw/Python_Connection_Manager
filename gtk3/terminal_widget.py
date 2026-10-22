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
import shutil
import signal
import sys
import contextlib
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, Gdk, GLib, Vte, GObject

from pcm_logging import get_logger
from translations import t

_log = get_logger(__name__)

# Prompt di shell riconosciuto a fine riga: usato per fermare il watcher
# dell'auto-password una volta completato il login.
_SHELL_PROMPT_RE = r"^[^\n]{0,160}[$#%]\s*$"

# Prompt di autenticazione SSH noti. Il generico "Password:" è incluso perché
# alcuni server non mostrano il formato user@host, ma il watcher è a colpo
# singolo e limitato nel tempo (vedi imposta_auto_password).
_SSH_PASSWORD_RE = (
    r"\S+@\S+'s password:\s*$"
    r"|(?:^|\n)[^\n]{0,80}[Pp]assword[^\n:]{0,40}:\s*$"
    r"|(?:^|\n)[Pp]asswd:\s*$"
    r"|(?:^|\n)[Ss]ecret[^\n:]{0,15}:\s*$"
    r"|(?:^|\n)[Ee]nter .*[Pp]assword[^\n:]{0,20}:\s*$"
    r"|(?:^|\n)[Aa]uthentication [Pp]assword:\s*$"
)


def _hex_to_rgba(hex_color: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(hex_color)
    return rgba


class TerminalWidget(Gtk.Box):
    """
    Widget terminale basato su VTE.
    Segnale: 'processo-terminato' emesso quando il processo figlio esce.
    I temi sono definiti in themes.TERMINAL_THEMES — unica fonte di verità.
    """

    __gsignals__ = {
        "processo-terminato": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, bg="#1e1e1e", fg="#cccccc", font="Monospace",
                 font_size=11, log_dir="", paste_on_right_click=False,
                 warn_paste=False, encoding="UTF-8", bell="none",
                 scrollback_lines=10000, infinite_scrollback=False,
                 word_char_exceptions=None, parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._bg = bg
        self._fg = fg
        self._font = font
        self._font_size = self._parse_int(font_size, 11)
        self._font_size_base = self._font_size  # per Ctrl+0 (reset zoom)
        self._log_dir = log_dir
        self._paste_on_right_click = paste_on_right_click
        self._warn_paste = warn_paste
        self._encoding = encoding
        self._bell = bell
        self._scrollback_lines = self._parse_int(scrollback_lines, 10000)
        self._infinite_scrollback = bool(infinite_scrollback)
        self._word_char_exceptions = word_char_exceptions
        self._pid = -1
        self._comando_corrente = ""
        self._keepalive_tick = 0
        self._keepalive_source = None
        self._expect_cleanup = None
        self._t_connessione = None
        self._char_inviati = 0
        self._comandi_inviati: list = []
        self._tipo_sessione = "locale"
        self._exit_code: int | None = None

        self._init_ui()

        # Timer keepalive / statistiche ogni 3 secondi. Viene riavviato da
        # avvia() dopo un'eventuale riconnessione automatica.
        self._avvia_keepalive()
        self.connect("destroy", self._on_destroy)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        self._vte = Vte.Terminal()
        self._vte.set_scrollback_lines(
            -1 if self._infinite_scrollback else max(0, self._scrollback_lines))
        self._applica_tema()
        self._applica_font()

        # Link OSC 8 e URL cliccabili (Ctrl+clic, vedi _apri_link_evento)
        with contextlib.suppress(Exception):
            self._vte.set_allow_hyperlink(True)

        # Delimitatori di parola configurabili (Impostazioni → Terminale)
        if self._word_char_exceptions:
            with contextlib.suppress(Exception):
                self._vte.set_word_char_exceptions(self._word_char_exceptions)

        self._highlighter = None
        self._init_highlighter()

        # Encoding (deprecato in VTE 0.54 ma ancora funzionante)
        if self._encoding and self._encoding.upper() != "UTF-8":
            try:
                self._vte.set_encoding(self._encoding)
            except Exception as e:
                _log.debug("Encoding %r non supportato: %s", self._encoding, e)

        # Bell
        self._vte.set_audible_bell(self._bell == "audible")
        if self._bell == "visual":
            self._vte.connect("bell", self._on_bell)
        else:
            self._vte.set_audible_bell(self._bell == "audible")

        # Padding sinistro: impedisce che il primo carattere finisca
        # sotto il cursore di resize del Paned
        _css = Gtk.CssProvider()
        _css.load_from_data(b"vte-terminal { padding-left: 8px; }")
        self._vte.get_style_context().add_provider(
            _css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Provider unico riutilizzato dal visual bell (evita di crearne uno
        # nuovo a ogni campanello).
        self._bell_css = Gtk.CssProvider()
        self._bell_css.load_from_data(
            b"vte-terminal { background-color: #888888; }")

        # Cursore I-beam (testo) sull'intera area VTE
        self._vte.connect("realize", self._on_vte_realize)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._vte)
        self.pack_start(scroll, True, True, 0)

        # Barra di ricerca (nascosta di default, Ctrl+F per aprirla)
        self._init_search_bar()

        # _stato_testo: testo live letto dalla statusbar di PCM via get_stato()
        self._stato_testo = ""
        self._stato_terminato = False

        # Segnale fine processo e selezione testo
        self._vte.connect("child-exited", self._on_child_exited)
        self._vte.connect("selection-changed", self._on_selection_changed)

        # Clic destro → incolla; Ctrl+Shift+V → incolla esplicito
        self._vte.connect("button-press-event", self._on_button_press)
        self._vte.connect("key-press-event", self._on_key_press)

        # Ctrl+rotella → zoom font
        self._vte.add_events(Gdk.EventMask.SCROLL_MASK)
        self._vte.connect("scroll-event", self._on_scroll)

    def _init_search_bar(self):
        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_show_close_button(True)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(t("term.search.placeholder"))
        self._search_entry.set_width_chars(35)
        self._search_entry.connect("search-changed", lambda _: self._aggiorna_ricerca())
        self._search_entry.connect("activate", lambda _: self._cerca_avanti())
        self._search_entry.connect("key-press-event", self._on_search_key_press)
        box.pack_start(self._search_entry, True, True, 0)

        btn_prev = Gtk.Button.new_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
        btn_prev.set_tooltip_text(t("term.search.prev_tt"))
        btn_prev.connect("clicked", lambda _: self._cerca_indietro())
        box.pack_start(btn_prev, False, False, 0)

        btn_next = Gtk.Button.new_from_icon_name("go-down-symbolic", Gtk.IconSize.BUTTON)
        btn_next.set_tooltip_text(t("term.search.next_tt"))
        btn_next.connect("clicked", lambda _: self._cerca_avanti())
        box.pack_start(btn_next, False, False, 0)

        self._chk_case = Gtk.CheckButton(label="Aa")
        self._chk_case.set_tooltip_text(t("term.search.case_tt"))
        self._chk_case.connect("toggled", lambda _: self._aggiorna_ricerca())
        box.pack_start(self._chk_case, False, False, 0)

        self._search_bar.add(box)
        self._search_bar.connect_entry(self._search_entry)
        self.pack_start(self._search_bar, False, False, 0)
        self.reorder_child(self._search_bar, 0)

    def _on_vte_realize(self, widget):
        cursor = Gdk.Cursor.new_for_display(widget.get_display(), Gdk.CursorType.XTERM)
        widget.get_window().set_cursor(cursor)

    def _on_selection_changed(self, terminal):
        """Copia la selezione nella PRIMARY (selezione X11), non nella CLIPBOARD.

        Il comportamento standard dei terminali è: selezione → PRIMARY,
        Ctrl+Shift+C / menu → CLIPBOARD. Così selezionare per errore non
        sovrascrive gli appunti espliciti dell'utente.
        """
        if terminal.get_has_selection():
            with contextlib.suppress(Exception):
                terminal.copy_primary()

    def _avvia_keepalive(self):
        """Attiva il timer di stato se non è già in esecuzione."""
        if self._keepalive_source is None:
            self._keepalive_source = GLib.timeout_add(
                3000, self._controlla_processo)

    def _on_destroy(self, _widget):
        """Ferma timer e watcher quando il tab viene chiuso (evita leak)."""
        if self._keepalive_source:
            with contextlib.suppress(Exception):
                GLib.source_remove(self._keepalive_source)
            self._keepalive_source = None
        if self._expect_cleanup:
            with contextlib.suppress(Exception):
                self._expect_cleanup()
            self._expect_cleanup = None

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
        env_extra: variabili d'ambiente aggiuntive da iniettare (es. SSH_ASKPASS).
        """
        self._comando_corrente = comando
        cmd_show = getattr(self, "comando_display", comando)
        self._stato_testo = f"▶  {cmd_show}"
        self._stato_terminato = False

        # Logging: redirige output su file tramite script(1) se richiesto.
        # Se script(1) non è disponibile la sessione parte comunque, senza log.
        argv = ["/bin/sh", "-c", comando]
        if self._log_dir:
            try:
                os.makedirs(self._log_dir, mode=0o700, exist_ok=True)
                st = os.stat(self._log_dir)
                if st.st_uid != os.getuid():
                    self._log_dir = None
                elif not shutil.which("script"):
                    _log.warning(
                        "Log output richiesto ma 'script(1)' non trovato: "
                        "la sessione parte senza registrazione")
                else:
                    os.chmod(self._log_dir, 0o700)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_file = os.path.join(self._log_dir, f"pcm_{ts}.log")
                    with open(log_file, "a"):
                        pass
                    os.chmod(log_file, 0o600)
                    if sys.platform.startswith(("freebsd", "openbsd",
                                                "netbsd", "darwin")):
                        # BSD/macOS: script [-q] file [command ...]
                        argv = ["/bin/sh", "-c",
                                f"script -q {_shell_quote(log_file)} "
                                f"/bin/sh -c {_shell_quote(comando)}"]
                    else:
                        # util-linux: script -q -c command file
                        argv = ["/bin/sh", "-c",
                                f"script -q -c {_shell_quote(comando)} "
                                f"{_shell_quote(log_file)}"]
            except OSError as e:
                _log.error("Impossibile preparare il log in %r: %s",
                           self._log_dir, e)
                self._log_dir = None

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
                GLib.SpawnFlags(0),   # VTE gestisce da sé il figlio
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
        # Avvia (o riavvia dopo auto-reconnect) il timer di stato.
        self._avvia_keepalive()

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
            from pcm_logging import get_logger
            get_logger(__name__).error("Errore feed_child: %s", e)

    def _registra_comando(self, testo: str, sorgente: str = "macro"):
        # Non registrare le password inviate automaticamente (sorgente "auto_password")
        if sorgente == "auto_password":
            return
        self._comandi_inviati.append({
            "ts":       datetime.now().isoformat(timespec="seconds"),
            "cmd":      testo,
            "sorgente": sorgente,
        })
        # Evita crescita illimitata in sessioni di lunga durata.
        if len(self._comandi_inviati) > 1000:
            del self._comandi_inviati[:-1000]

    def imposta_auto_password(self, password: str):
        """Invia automaticamente la password al prompt di autenticazione.

        Sicurezza: il watcher è a colpo singolo e scade dopo 60 secondi,
        inoltre si ferma quando compare il prompt della shell. In questo modo
        la password SSH non viene più digitata in prompt successivi (sudo,
        ssh verso altri host) nella stessa tab.
        """
        if not password:
            return
        self._setup_expect_watcher([{
            "pattern": _SSH_PASSWORD_RE,
            "command": password,
            "max_trigger": 1,
            "delay": 0.08,
            "timeout": 60,
            "stop_on_prompt": True,
        }])

    def imposta_expect(self, rules: list[dict]):
        if not rules:
            return
        self._setup_expect_watcher(rules)

    def _testo_recente(self, righe: int = 20) -> str:
        """Legge solo le ultime `righe` del buffer, non tutto lo scrollback.

        Su scrollback enormi (100000 righe o illimitato) get_text() copiava
        l'intero buffer a ogni contents-changed, causando lag della UI.
        """
        try:
            col, row = self._vte.get_cursor_position()
            start = max(0, row - max(1, int(righe)))
            if hasattr(self._vte, "get_text_range_format"):
                text, _attrs = self._vte.get_text_range_format(
                    Vte.Format.TEXT, start, 0, row, col)
                return text or ""
            # Fallback per VTE molto vecchie prive di get_text_range_format.
            return self._vte.get_text(lambda *_: True)[0] or ""
        except Exception as e:
            _log.debug("Lettura testo recente fallita: %s", e, exc_info=True)
            return ""

    def _setup_expect_watcher(self, rules: list[dict]):
        import re as _re
        import time as _time
        # Se un watcher precedente è ancora attivo, rimuovilo (evita handler
        # "contents-changed" duplicati e l'invio doppio della password).
        if self._expect_cleanup:
            self._expect_cleanup()
        compiled = []
        timeout_s = 0.0
        for r in rules:
            pat = r.get("pattern", "")
            cmd = r.get("command", "")
            max_t = int(r.get("max_trigger", 1))
            delay = max(0.05, float(r.get("delay", 0.5)))
            if pat and cmd:
                compiled.append({
                    "re": _re.compile(pat, _re.MULTILINE),
                    "command": cmd,
                    "max_trigger": max_t,
                    "delay": delay,
                    "sent": 0,
                    "last_prompt": None,
                    "stop_on_prompt": bool(r.get("stop_on_prompt", False)),
                })
                timeout_s = max(timeout_s, float(r.get("timeout", 0) or 0))

        if not compiled:
            return

        _timer_id = [None]
        _conn_id  = [None]
        _done     = [False]
        _debounce = 80  # ms
        _start    = _time.monotonic()
        _prompt_re = _re.compile(_SHELL_PROMPT_RE)

        def _cleanup():
            _done[0] = True
            if _timer_id[0] is not None:
                with contextlib.suppress(Exception):
                    GLib.source_remove(_timer_id[0])
                _timer_id[0] = None
            if _conn_id[0] is not None:
                with contextlib.suppress(Exception):
                    self._vte.disconnect(_conn_id[0])
                _conn_id[0] = None
            if self._expect_cleanup is _cleanup:
                self._expect_cleanup = None

        self._expect_cleanup = _cleanup

        def _do_check():
            _timer_id[0] = None
            if _done[0]:
                return False
            # Limite temporale: un prompt tardivo (sudo, ssh successivo) non
            # deve più ricevere la credenziale della connessione.
            if timeout_s and (_time.monotonic() - _start) > timeout_s:
                _log.debug("Watcher expect scaduto dopo %.0fs", timeout_s)
                _cleanup()
                return False
            active = any(c["sent"] < c["max_trigger"] for c in compiled)
            if not active:
                _cleanup()
                return False

            tail = self._testo_recente(righe=20).rstrip()[-600:]
            if not tail:
                return False

            # Login completato: la shell ha stampato il suo prompt.
            # Si controlla solo l'ultima riga, altrimenti un banner che
            # termina con '#' o '%' fermerebbe il watcher troppo presto.
            ultima_riga = tail.rsplit("\n", 1)[-1]
            if any(c["stop_on_prompt"] for c in compiled) \
                    and _prompt_re.search(ultima_riga):
                _log.debug("Prompt di shell rilevato: watcher expect fermato")
                _cleanup()
                return False

            for c in compiled:
                if c["sent"] >= c["max_trigger"]:
                    continue
                match = c["re"].search(tail)
                if not match:
                    continue

                # Il prompt resta nello scrollback anche dopo feed_child().
                # Senza una chiave, ogni output successivo (per esempio il
                # banner SSH) faceva reinviare la password nel nuovo shell.
                prompt_key = tail[:match.end()]
                if prompt_key == c["last_prompt"]:
                    continue
                c["last_prompt"] = prompt_key
                c["sent"] += 1
                cmd = c["command"]
                if not cmd.endswith("\n"):
                    cmd += "\n"
                self._vte.feed_child(cmd.encode("utf-8"))
            if not any(c["sent"] < c["max_trigger"] for c in compiled):
                # Tutte le regole hanno raggiunto max_trigger: chiudi subito
                # il watcher (niente invii su prompt successivi).
                _cleanup()
            return False

        def _on_changed(_vte):
            if _timer_id[0] is not None:
                GLib.source_remove(_timer_id[0])
            _timer_id[0] = GLib.timeout_add(_debounce, _do_check)

        _conn_id[0] = self._vte.connect("contents-changed", _on_changed)
        _do_check()

    # ------------------------------------------------------------------
    # Tema e font
    # ------------------------------------------------------------------

    def _applica_tema(self):
        fg = _hex_to_rgba(self._fg)
        bg = _hex_to_rgba(self._bg)
        self._vte.set_colors(fg, bg, [])

    # ------------------------------------------------------------------
    # Syntax highlighting
    # ------------------------------------------------------------------

    def _init_highlighter(self):
        try:
            from terminal_highlight import Highlighter
            self._highlighter = Highlighter(self._vte)
        except Exception as e:
            _log.debug("Highlighter non disponibile: %s", e, exc_info=True)
            self._highlighter = None

    def toggle_highlight(self, enabled: bool = None):
        if self._highlighter is None:
            return
        if enabled is None:
            enabled = not self._highlighter.is_enabled()
        self._highlighter.set_enabled(enabled)

    def has_highlight(self) -> bool:
        return self._highlighter is not None and self._highlighter.is_enabled()

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
        # Un eventuale watcher expect non deve sopravvivere al processo.
        if self._expect_cleanup:
            with contextlib.suppress(Exception):
                self._expect_cleanup()
            self._expect_cleanup = None

        if os.WIFEXITED(status):
            self._exit_code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            self._exit_code = -(os.WTERMSIG(status))
        else:
            self._exit_code = None

        if self._exit_code and self._exit_code != 0 and self._tipo_sessione != "locale":
            msg = self._exit_msg(self._exit_code)
            self._vte.feed(f"\r\n\x1b[1;33m[PCM] {msg}\x1b[0m\r\n".encode("utf-8"))
            self._stato_testo = f"✖  {msg}"
        else:
            self._stato_testo = t("terminal.session_ended")

        self._stato_terminato = True
        self.emit("processo-terminato")

    def _exit_msg(self, code: int) -> str:
        if self._tipo_sessione == "ssh":
            if code == 255:
                return t("terminal.exit.ssh_connection_error")
            if code < 0:
                return t("terminal.exit.signal", sig=-code)
            return t("terminal.exit.error_code", code=code)
        if code < 0:
            return t("terminal.exit.signal", sig=-code)
        return t("terminal.exit.error_code", code=code)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def chiudi_processo(self):
        if getattr(self, "_expect_cleanup", None):
            self._expect_cleanup()
            self._expect_cleanup = None
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
                from pcm_logging import get_logger
                get_logger(__name__).error("Errore chiusura processo: %s", e)
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
        """Tasto destro → incolla/menu; Ctrl+clic → apre URL."""
        if event.button == 1 and (event.state & Gdk.ModifierType.CONTROL_MASK):
            if self._apri_link_evento(event):
                return True
        if event.button == 3:
            if self._paste_on_right_click:
                self._incolla_clipboard()
            else:
                self._mostra_menu_contestuale(event)
            return True
        return False

    def _apri_link_evento(self, event) -> bool:
        """Apre nel browser l'URL o il link OSC 8 sotto il puntatore."""
        uri = None
        with contextlib.suppress(Exception):
            uri = self._vte.hyperlink_check_event(event)
        if not uri:
            with contextlib.suppress(Exception):
                testo, _tag = self._vte.match_check_event(event)
                if testo and testo.lower().startswith(
                        ("http://", "https://", "ftp://", "ftps://")):
                    uri = testo
        if not uri:
            return False
        if not uri.lower().startswith(("http://", "https://", "ftp://",
                                       "ftps://")):
            return False
        try:
            from gi.repository import Gio
            Gio.AppInfo.launch_default_for_uri(uri, None)
            return True
        except Exception as e:
            _log.warning("Impossibile aprire l'URL %r: %s", uri, e)
            return False

    def _mostra_menu_contestuale(self, event):
        menu = Gtk.Menu()

        mi_copy = Gtk.MenuItem(label=t("term.context.copy"))
        ha_selezione = self._vte.get_has_selection()
        mi_copy.set_sensitive(ha_selezione)
        mi_copy.connect("activate", lambda _: self._copia_selezione())

        mi_paste = Gtk.MenuItem(label=t("term.context.paste"))
        mi_paste.connect("activate", lambda _: self._incolla_clipboard())

        mi_snippet = Gtk.MenuItem(label=t("term.context.snippet"))
        mi_snippet.connect("activate", lambda _: self._apri_snippet_picker())

        mi_cerca = Gtk.MenuItem(label=t("term.context.search"))
        mi_cerca.connect("activate", lambda _: self.mostra_cerca())

        menu.append(mi_copy)
        if not ha_selezione:
            # Mc/htop/vim/tmux catturano il mouse: il drag evidenzia nel
            # programma remoto ma non crea una selezione VTE. Il suggerimento
            # compare solo quando "Copia" è disabilitato, cioè quando serve.
            mi_hint = Gtk.MenuItem(label=t("term.context.copy_hint"))
            mi_hint.set_sensitive(False)
            menu.append(mi_hint)
        menu.append(mi_paste)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(mi_snippet)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(mi_cerca)

        if self._highlighter is not None:
            menu.append(Gtk.SeparatorMenuItem())
            mi_hl = Gtk.CheckMenuItem(label=t("term.context.highlight"))
            mi_hl.set_active(self._highlighter.is_enabled())
            mi_hl.connect("toggled", lambda w: self.toggle_highlight(w.get_active()))
            menu.append(mi_hl)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _apri_snippet_picker(self):
        try:
            from snippets_dialog import SnippetsDialog
            dlg = SnippetsDialog(
                parent=self.get_toplevel(),
                on_invia=lambda cmd: self.invia_testo(cmd, sorgente="snippet"),
            )
            dlg.run()
            dlg.destroy()
        except Exception as e:
            _log.debug("Impossibile aprire lo snippet picker: %s", e,
                       exc_info=True)

    def _on_scroll(self, terminal, event):
        """Ctrl+rotella → aumenta/diminuisce dimensione font."""
        if not (event.state & Gdk.ModifierType.CONTROL_MASK):
            return False
        direction = event.direction
        if direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0:
                direction = Gdk.ScrollDirection.UP
            elif event.delta_y > 0:
                direction = Gdk.ScrollDirection.DOWN
            else:
                return False
        if direction == Gdk.ScrollDirection.UP:
            self._zoom_font(+1)
        elif direction == Gdk.ScrollDirection.DOWN:
            self._zoom_font(-1)
        else:
            return False
        return True

    def _zoom_font(self, delta: int):
        """Varia la dimensione font di delta punti (0 → reset al valore della sessione)."""
        if delta == 0:
            nuova = self._font_size_base
        else:
            nuova = max(4, min(self._font_size + delta, 72))
        if nuova != self._font_size:
            self._font_size = nuova
            self._applica_font()

    # Ctrl(+Shift) + tasto → zoom font. Si confronta il keyval *senza* Shift,
    # così Ctrl+Shift funziona su ogni layout (IT: '+' diretto, US: '=').
    _ZOOM_KEYS = {
        "PLUS": +1, "EQUAL": +1, "KP_ADD": +1,
        "MINUS": -1, "KP_SUBTRACT": -1,
        "0": 0, "KP_0": 0,
    }

    def _zoom_da_tasto(self, terminal, event):
        """Ritorna il delta di zoom per l'evento, o None se non è un tasto zoom."""
        keymap = Gdk.Keymap.get_for_display(terminal.get_display())
        ok, keyval, *_ = keymap.translate_keyboard_state(
            event.hardware_keycode,
            event.state & ~Gdk.ModifierType.SHIFT_MASK,
            event.group)
        nome = Gdk.keyval_name(keyval if ok else event.keyval) or ""
        return self._ZOOM_KEYS.get(nome.upper())

    def _on_key_press(self, terminal, event):
        """Ctrl+Shift+C / Ctrl+Insert → copia; Ctrl+Shift+V / Shift+Insert → incolla;
        Ctrl+F → search bar; Ctrl+'+' / Ctrl+'-' / Ctrl+0 → zoom font."""
        ctrl  = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        key   = (Gdk.keyval_name(event.keyval) or "").upper()
        alt   = bool(event.state & Gdk.ModifierType.MOD1_MASK)
        if ctrl and not alt:
            delta = self._zoom_da_tasto(terminal, event)
            if delta is not None:
                self._zoom_font(delta)
                return True
        if ctrl and shift and key == "V":
            self._incolla_clipboard()
            return True
        if ctrl and shift and key == "C":
            self._copia_selezione()
            return True
        if ctrl and key == "INSERT":
            self._copia_selezione()
            return True
        if shift and key == "INSERT":
            self._incolla_primary()
            return True
        if ctrl and not shift and key == "F":
            self.mostra_cerca()
            return True
        return False

    def _on_search_key_press(self, widget, event):
        """Shift+Enter nella search entry → cerca indietro; Escape → chiudi."""
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        key   = Gdk.keyval_name(event.keyval).upper()
        if key == "RETURN" and shift:
            self._cerca_indietro()
            return True
        if key == "ESCAPE":
            self._search_bar.set_search_mode(False)
            self._vte.grab_focus()
            return True
        return False

    def mostra_cerca(self):
        """Attiva/disattiva la search bar (Ctrl+F)."""
        attiva = not self._search_bar.get_search_mode()
        self._search_bar.set_search_mode(attiva)
        if attiva:
            self._search_entry.grab_focus()
        else:
            self._vte.search_set_regex(None, 0)
            self._vte.grab_focus()

    def _aggiorna_ricerca(self):
        pattern = self._search_entry.get_text()
        if not pattern:
            self._vte.search_set_regex(None, 0)
            self._search_entry.get_style_context().remove_class("error")
            return
        import re as _re
        escaped = _re.escape(pattern)
        PCRE2_CASELESS = 0x00000008
        flags = 0 if self._chk_case.get_active() else PCRE2_CASELESS
        try:
            regex = Vte.Regex.new_for_search(escaped, len(escaped.encode("utf-8")), flags)
            self._vte.search_set_regex(regex, 0)
            self._vte.search_set_wrap_around(True)
            self._search_entry.get_style_context().remove_class("error")
        except Exception:
            self._search_entry.get_style_context().add_class("error")

    def _cerca_avanti(self):
        if not self._vte.search_find_next():
            self._search_entry.get_style_context().add_class("error")
        else:
            self._search_entry.get_style_context().remove_class("error")

    def _cerca_indietro(self):
        if not self._vte.search_find_previous():
            self._search_entry.get_style_context().add_class("error")
        else:
            self._search_entry.get_style_context().remove_class("error")

    def _on_bell(self, terminal):
        """Visual bell: flash breve del widget (provider riutilizzato)."""
        ctx = self._vte.get_style_context()
        ctx.add_provider(self._bell_css,
                         Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        def _ripristina():
            ctx.remove_provider(self._bell_css)
            return False
        GLib.timeout_add(120, _ripristina)

    def _copia_selezione(self) -> bool:
        """Copia la selezione VTE nella clipboard (Ctrl+Shift+C, Ctrl+Insert, menu).

        Nei programmi a schermo intero che catturano il mouse (mc, htop, vim,
        tmux) il drag NON crea una selezione VTE: l'evidenziazione è disegnata
        dal programma remoto, quindi non c'è nulla da copiare. Per selezionare
        davvero il testo occorre tenere premuto Shift mentre si trascina.
        """
        if self._vte.get_has_selection():
            self._vte.copy_clipboard()
            return True
        return False

    def _incolla_clipboard(self):
        """Incolla dalla CLIPBOARD (Ctrl+Shift+V, menu contestuale)."""
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        # request_text è asincrono: wait_for_text() poteva bloccare la UI se
        # il proprietario degli appunti non rispondeva.
        clipboard.request_text(self._on_clipboard_testo, None)

    def _incolla_primary(self):
        """Incolla dalla PRIMARY selection (selezione mouse, Shift+Insert)."""
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        clipboard.request_text(self._on_clipboard_testo, None)

    def _on_clipboard_testo(self, _clipboard, testo, _user_data=None):
        if testo:
            self._incolla_testo(testo)

    def _incolla_testo(self, testo: str):
        """Punto di ingresso unico per ogni incolla: applica warn_paste se attivo."""
        if self._warn_paste and len(testo.splitlines()) > 1:
            if not self._conferma_incolla(testo):
                return
        self._vte.feed_child(testo.encode("utf-8"))

    def _conferma_incolla(self, testo: str) -> bool:
        righe = testo.splitlines()
        n = len(righe)
        parent = self.get_toplevel()
        if not isinstance(parent, Gtk.Window):
            parent = None

        dlg = Gtk.MessageDialog(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text=t("paste_warn.title"),
        )
        dlg.format_secondary_text(t("paste_warn.body", n=n))
        dlg.set_default_size(700, 350)
        dlg.set_resizable(True)

        preview_lines = []
        for line in righe[:5]:
            preview_lines.append(line[:100] + ("…" if len(line) > 100 else ""))
        if n > 5:
            preview_lines.append(f"… ({n - 5} {t('paste_warn.more_lines')})")

        buf = Gtk.TextBuffer()
        buf.set_text("\n".join(preview_lines))
        tv = Gtk.TextView(buffer=buf)
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_monospace(True)
        tv.set_margin_start(4)
        tv.set_margin_end(4)
        tv.set_margin_top(4)
        tv.set_margin_bottom(4)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(200)
        sw.set_min_content_width(500)
        sw.add(tv)
        sw.set_margin_start(12)
        sw.set_margin_end(12)
        sw.set_margin_bottom(8)

        dlg.get_content_area().pack_start(sw, True, True, 0)
        sw.show_all()

        dlg.add_button(t("paste_warn.cancel"), Gtk.ResponseType.CANCEL)
        btn_ok = dlg.add_button(t("paste_warn.confirm"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("destructive-action")
        dlg.set_default_response(Gtk.ResponseType.CANCEL)

        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.OK

    @classmethod
    def da_profilo(cls, profilo: dict, log_dir="") -> "TerminalWidget":
        """Factory: crea un TerminalWidget dai parametri di un profilo sessione."""
        from themes import TERMINAL_THEMES, migrate_theme_name
        tema = migrate_theme_name(profilo.get("term_theme", "Dark (Default)"))
        bg, fg = TERMINAL_THEMES.get(tema, ("#1e1e1e", "#cccccc"))
        font = profilo.get("term_font", "Monospace")
        size = profilo.get("term_size", 11)
        paste_right = profilo.get("paste_on_right_click", False)
        warn_paste  = profilo.get("term_warn_paste", False)
        encoding    = profilo.get("term_encoding", "UTF-8")
        bell        = profilo.get("term_bell", "none")
        scrollback = profilo.get("term_scrollback_lines", 10000)
        infinite_sb = profilo.get("term_infinite_scrollback", False)
        # word_delimiters è un'impostazione globale (non per-sessione).
        try:
            from config_manager import load_settings
            word_chars = load_settings().get(
                "terminal", {}).get("word_delimiters", "")
        except Exception as e:
            _log.debug("Impossibile leggere word_delimiters: %s", e)
            word_chars = ""
        return cls(bg=bg, fg=fg, font=font, font_size=size, log_dir=log_dir,
                   paste_on_right_click=paste_right, warn_paste=warn_paste,
                   encoding=encoding, bell=bell,
                   scrollback_lines=scrollback,
                   infinite_scrollback=infinite_sb,
                   word_char_exceptions=word_chars or None)

    @classmethod
    def da_impostazioni(cls, log_dir="") -> "TerminalWidget":
        """Factory: terminale locale basato sulle impostazioni globali."""
        from config_manager import load_settings
        s = load_settings().get("terminal", {})
        profilo = {
            "term_theme": s.get("default_theme", "Dark (Default)"),
            "term_font": s.get("default_font", "Monospace"),
            "term_size": s.get("default_font_size", 11),
            "term_scrollback_lines": s.get("scrollback_lines", 10000),
            "term_infinite_scrollback": s.get("infinite_scrollback", False),
            "term_warn_paste": s.get("warn_multiline_paste", True),
            "paste_on_right_click": s.get("paste_on_right_click", False),
            "term_encoding": "UTF-8",
            "term_bell": "none",
        }
        return cls.da_profilo(profilo, log_dir=log_dir)


# ---------------------------------------------------------------------------
# Helper quoting shell-safe
# ---------------------------------------------------------------------------

def _shell_quote(s: str) -> str:
    import shlex
    return shlex.quote(s)
