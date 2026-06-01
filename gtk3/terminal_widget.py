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
                 font_size=11, log_dir="", paste_on_right_click=False,
                 warn_paste=False, encoding="UTF-8", bell="none", parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._bg = bg
        self._fg = fg
        self._font = font
        self._font_size = self._parse_int(font_size, 11)
        self._log_dir = log_dir
        self._paste_on_right_click = paste_on_right_click
        self._warn_paste = warn_paste
        self._encoding = encoding
        self._bell = bell
        self._pid = -1
        self._comando_corrente = ""
        self._keepalive_tick = 0
        self._t_connessione = None
        self._char_inviati = 0
        self._comandi_inviati: list = []
        self._tipo_sessione = "locale"
        self._exit_code: int | None = None

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

        # Encoding (deprecato in VTE 0.54 ma ancora funzionante)
        if self._encoding and self._encoding.upper() != "UTF-8":
            try:
                self._vte.set_encoding(self._encoding)
            except Exception:
                pass

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
        env_extra: variabili d'ambiente aggiuntive da iniettare (es. SSH_ASKPASS).
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
        # Non registrare le password inviate automaticamente (sorgente "auto_password")
        if sorgente == "auto_password":
            return
        self._comandi_inviati.append({
            "ts":       datetime.now().isoformat(timespec="seconds"),
            "cmd":      testo,
            "sorgente": sorgente,
        })

    def imposta_auto_password(self, password: str):
        """
        Digita automaticamente la password quando il terminale mostra un prompt.
        Primario: sostituisce sshpass — PCM 'scrive' nel terminale come farebbe un umano.
        Copre: SSH password, Cisco enable/secret, PAM, RADIUS, 2FA, prompt personalizzati.
        Fallback: SSH_ASKPASS gestisce i casi dove SSH non mostra il prompt nel VTE
                  (keyboard-interactive su OpenSSH ≥ 8.4 con SSH_ASKPASS_REQUIRE=force).
        """
        if not password:
            return

        import re as _re
        _PWD_RE = _re.compile(
            r'(?:'
            r'[Pp]assword[^:\n]{0,40}:\s*$'            # password: / Password for user@host:
            r'|[Pp]asswd:\s*$'                          # passwd:
            r'|[Ss]ecret[^:\n]{0,15}:\s*$'              # Secret: (Cisco enable secret)
            r'|[Pp]asscode:\s*$'                         # Passcode: (RADIUS/MFA)
            r'|[Vv]erification [Cc]ode:\s*$'            # Verification code: (Google Auth)
            r'|[Ee]nter .*[Pp]assword[^:\n]{0,20}:\s*$' # Enter (current/new) password:
            r'|[Aa]uthentication [Pp]assword:\s*$'       # Authentication password:
            r')',
            _re.MULTILINE,
        )

        _timer_id = [None]
        _conn_id  = [None]
        _sent     = [0]
        _MAX      = 3   # tentativi max (gestisce wrong-password senza loop infinito)

        def _do_check():
            _timer_id[0] = None
            if _sent[0] >= _MAX:
                return False
            try:
                # Legge le ultime righe visibili — sufficiente per rilevare il prompt
                text = self._vte.get_text(lambda *_: True)[0]
            except Exception:
                return False
            tail = (text or "").rstrip()[-400:]
            if _PWD_RE.search(tail):
                _sent[0] += 1
                self._vte.feed_child((password + "\n").encode("utf-8"))
            return False  # timer one-shot

        def _on_changed(_vte):
            if _sent[0] >= _MAX:
                if _conn_id[0] is not None:
                    _vte.disconnect(_conn_id[0])
                    _conn_id[0] = None
                return
            # Debounce 80 ms: evita check multipli durante burst di output
            if _timer_id[0] is not None:
                GLib.source_remove(_timer_id[0])
            _timer_id[0] = GLib.timeout_add(80, _do_check)

        _conn_id[0] = self._vte.connect("contents-changed", _on_changed)

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
        """Tasto destro → incolla o menu contestuale."""
        if event.button == 3:
            if self._paste_on_right_click:
                self._incolla_clipboard()
            else:
                self._mostra_menu_contestuale(event)
            return True
        return False

    def _mostra_menu_contestuale(self, event):
        menu = Gtk.Menu()

        mi_copy = Gtk.MenuItem(label="Copia")
        mi_copy.set_sensitive(self._vte.get_has_selection())
        mi_copy.connect("activate", lambda _: self._vte.copy_clipboard())

        mi_paste = Gtk.MenuItem(label="Incolla")
        mi_paste.connect("activate", lambda _: self._incolla_clipboard())

        mi_snippet = Gtk.MenuItem(label="Inserisci snippet…")
        mi_snippet.connect("activate", lambda _: self._apri_snippet_picker())

        mi_cerca = Gtk.MenuItem(label="Cerca…  (Ctrl+F)")
        mi_cerca.connect("activate", lambda _: self.mostra_cerca())

        menu.append(mi_copy)
        menu.append(mi_paste)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(mi_snippet)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(mi_cerca)
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
        except Exception:
            pass

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
            self._font_size = min(self._font_size + 1, 72)
        elif direction == Gdk.ScrollDirection.DOWN:
            self._font_size = max(self._font_size - 1, 4)
        else:
            return False
        self._applica_font()
        return True

    def _on_key_press(self, terminal, event):
        """Ctrl+Shift+V / Shift+Insert → incolla; Ctrl+F → search bar."""
        ctrl  = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        key   = Gdk.keyval_name(event.keyval).upper()
        if ctrl and shift and key == "V":
            self._incolla_clipboard()
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
        """Visual bell: flash breve del widget."""
        css = Gtk.CssProvider()
        css.load_from_data(b"vte-terminal { background-color: #888888; }")
        ctx = self._vte.get_style_context()
        ctx.add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        def _ripristina():
            ctx.remove_provider(css)
            return False
        GLib.timeout_add(120, _ripristina)

    def _incolla_clipboard(self):
        """Incolla dalla CLIPBOARD (Ctrl+C/Ctrl+X) nel terminale."""
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        testo = clipboard.wait_for_text()
        if testo:
            self._incolla_testo(testo)

    def _incolla_primary(self):
        """Incolla dalla PRIMARY selection (selezione mouse, Shift+Insert)."""
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        testo = clipboard.wait_for_text()
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
        sw.set_min_content_height(90)
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
        from themes import TERMINAL_THEMES
        tema = profilo.get("term_theme", "Scuro (Default)")
        bg, fg = TERMINAL_THEMES.get(tema, ("#1e1e1e", "#cccccc"))
        font = profilo.get("term_font", "Monospace")
        size = profilo.get("term_size", 11)
        paste_right = profilo.get("paste_on_right_click", False)
        warn_paste  = profilo.get("term_warn_paste", False)
        encoding    = profilo.get("term_encoding", "UTF-8")
        bell        = profilo.get("term_bell", "none")
        scrollback = profilo.get("term_scrollback_lines", 10000)
        infinite_sb = profilo.get("term_infinite_scrollback", False)
        widget = cls(bg=bg, fg=fg, font=font, font_size=size, log_dir=log_dir,
                     paste_on_right_click=paste_right, warn_paste=warn_paste,
                     encoding=encoding, bell=bell)
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
