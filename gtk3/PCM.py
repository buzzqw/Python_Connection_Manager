#!/usr/bin/env python3
"""
PCM - Python Connection Manager (GTK3 port)
Ispirato a MobaXterm, sviluppato in Python/GTK3.

Licensed under the European Union Public Licence (EUPL) v1.2
© 2025 - All rights reserved

Dipendenze:
  python3-gi
  gir1.2-gtk-3.0
  gir1.2-vte-2.91
  gir1.2-webkit2-4.1   (per VNC/web)
  python3-paramiko      (SFTP)

FreeBSD equivalenti:
  py311-gobject3  vte3  webkit2-gtk3  py311-paramiko
"""

import sys
import os
import subprocess
import shutil
import threading
import tempfile
import contextlib
from urllib.parse import urlparse

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, Gdk, GLib, GObject, Gio

# ---------------------------------------------------------------------------
# Moduli PCM (tutti GTK3)
# ---------------------------------------------------------------------------
import config_manager
import translations as _tr
from translations import t
from themes import apply_css, TERMINAL_THEMES
from terminal_widget import TerminalWidget
from session_panel import SessionPanel
from session_dialog import SessionDialog
from session_command import build_command, check_dipendenze
from settings_dialog import SettingsDialog
from tunnel_manager import TunnelManagerDialog
from vnc_widget import VncWebWidget
from rdp_widget import RdpEmbedWidget
from sftp_browser import SftpBrowserWidget
from winscp_widget import WinScpWidget, FtpWinScpWidget

# ---------------------------------------------------------------------------
# Percorso icone
# ---------------------------------------------------------------------------
_HERE      = os.path.dirname(os.path.abspath(__file__))
_ICONS_DIR = os.path.join(_HERE, "icons")


def _icon_path(name: str) -> str:
    return os.path.join(_ICONS_DIR, name)


def _load_icon(name: str, size: int = 24):
    from gi.repository import GdkPixbuf
    path = _icon_path(name)
    if os.path.isfile(path):
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
        except Exception:
            pass
    return None


# ===========================================================================
# Schermata di benvenuto
# ===========================================================================

class WelcomeWidget(Gtk.Box):

    nuova_sessione   = GObject.Signal("nuova-sessione")
    terminale_locale = GObject.Signal("terminale-locale")

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self._build()

    def _build(self):
        # Titolo
        title = Gtk.Label(label=t("app.title"))
        title.get_style_context().add_class("section-header")
        self.pack_start(title, False, False, 0)

        # Pulsanti azione rapida
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        btn_box.set_halign(Gtk.Align.CENTER)

        btn_new = Gtk.Button(label=t("welcome.btn_new_session"))
        btn_new.get_style_context().add_class("connect-button")
        btn_new.set_size_request(160, 48)
        btn_new.connect("clicked", lambda b: self.emit("nuova-sessione"))

        btn_term = Gtk.Button(label=t("welcome.btn_local_terminal"))
        btn_term.set_size_request(160, 48)
        btn_term.connect("clicked", lambda b: self.emit("terminale-locale"))

        btn_box.pack_start(btn_new,  False, False, 0)
        btn_box.pack_start(btn_term, False, False, 0)
        self.pack_start(btn_box, False, False, 0)


# ===========================================================================
# Finestra principale
# ===========================================================================

class MainWindow(Gtk.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title=t("app.title"))
        self.set_default_size(1200, 720)
        self.set_position(Gtk.WindowPosition.CENTER)

        _tr.init_from_settings()
        self._settings = config_manager.load_settings()
        self._profili:  dict = {}

        # Icona finestra
        pb = _load_icon("app.png", 64)
        if pb:
            self.set_icon(pb)

        self._build_ui()
        self._connect_signals()
        self._setup_accels()
        self._pannello.aggiorna()

        self._pending_cli_uri: str | None = None   # URI da aprire dopo unlock crypto

        # Sblocco credenziali cifrate — 300ms dopo avvio per dare tempo al rendering
        GLib.timeout_add(300, self._check_crypto_unlock)
        # Timer live stat: aggiorna statusbar ogni 3s con stato del terminale attivo
        GLib.timeout_add(3000, self._aggiorna_stato_live)

    # ------------------------------------------------------------------
    # Sblocco credenziali cifrate
    # ------------------------------------------------------------------

    def _check_crypto_unlock(self):
        """Chiamato 300ms dopo l'avvio per sbloccare le credenziali cifrate.

        Gestisce due scenari:
        a) crypto.enabled=True + salt in settings  → flusso normale
        b) ENC: trovati nei profili ma settings incompleto → flusso recovery
           (tipico quando si porta connections.json da un'altra installazione)
        """
        try:
            import crypto_manager
            import config_manager as _cm

            already_unlocked = crypto_manager.is_unlocked()
            if already_unlocked:
                return False

            # --- Scenario A: impostazioni crypto complete ---
            if crypto_manager.is_enabled():
                self._esegui_unlock_dialog()
                return False

            # --- Scenario B: ENC: trovati ma settings incompleto ---
            # Controlla se connections.json ha valori cifrati
            profili = _cm.load_profiles()
            ha_enc = any(
                str(v.get("user","")).startswith("ENC:") or
                str(v.get("password","")).startswith("ENC:")
                for v in profili.values()
            )
            if not ha_enc:
                return False  # nessuna cifratura, niente da fare

            # Ha valori ENC: ma manca la configurazione crypto in settings.
            # Chiedi la password e tenta di recuperare il salt dal vecchio settings.
            s = _cm.load_settings()
            salt_b64 = s.get("crypto", {}).get("salt", "")

            if not salt_b64:
                # Manca il salt: non possiamo decifrare senza il pcm_settings.json originale
                dlg = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK,
                    text=t("crypto.unlock.title"),
                    secondary_text=(
                        "Il file connections.json contiene credenziali cifrate (ENC:…)\n"
                        "ma il file pcm_settings.json non contiene il salt di cifratura.\n\n"
                        "Soluzione: copia il pcm_settings.json originale dalla vecchia installazione\n"
                        "e assicurati che contenga la sezione \"crypto\" con salt, verify ed enabled:true.\n\n"
                        "In alternativa, modifica le sessioni manualmente per reinserire le credenziali."
                    )
                )
                dlg.run()
                dlg.destroy()
                return False

            # Il salt c'è ma enabled=False: ripristiniamo enabled e proviamo
            s["crypto"]["enabled"] = True
            _cm.save_settings(s)
            self._esegui_unlock_dialog()

        except ImportError:
            pass
        return False

    def _esegui_unlock_dialog(self):
        """Mostra il dialog password e sblocca le credenziali."""
        import crypto_manager
        dlg = _CryptoUnlockDialog(parent=self)
        resp = dlg.run()
        pwd  = dlg.get_password()
        dlg.destroy()

        if resp == Gtk.ResponseType.OK and pwd:
            if crypto_manager.unlock(pwd):
                self._pannello.aggiorna()
                if self._pending_cli_uri:
                    uri, self._pending_cli_uri = self._pending_cli_uri, None
                    GLib.idle_add(self.apri_da_cli, uri)
            else:
                err = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=t("crypto.unlock.wrong_master")
                )
                err.run()
                err.destroy()

    # ------------------------------------------------------------------
    # Costruzione UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Layout radice: headerbar + contenuto
        self._build_headerbar()

        # Paned principale: sidebar | area lavoro
        self._paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned.set_position(240)
        self.add(self._paned)

        # --- Sidebar ---
        self._pannello = SessionPanel()
        self._paned.pack1(self._pannello, False, False)

        # --- Area lavoro destra ---
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._paned.pack2(right_box, True, True)

        # Paned terminali: supporta split verticale/orizzontale
        self._paned_term = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned_term.set_wide_handle(True)
        right_box.pack_start(self._paned_term, True, True, 0)

        # Notebook primario (sempre visibile)
        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_show_border(False)
        self._notebook.connect("switch-page", self._on_switch_tab)
        self._notebook.connect("button-press-event", self._on_nb_button_press)
        self._paned_term.pack1(self._notebook, True, True)

        # Notebook secondario (split — inizialmente nascosto)
        self._notebook2 = Gtk.Notebook()
        self._notebook2.set_scrollable(True)
        self._notebook2.set_show_border(False)
        self._notebook2.set_no_show_all(True)
        self._notebook2.connect("button-press-event", self._on_nb2_button_press)
        self._notebook2.connect("switch-page", self._on_switch_tab)
        self._paned_term.pack2(self._notebook2, True, True)

        # Quale notebook è attivo (aggiornato da switch-page di entrambi)
        self._notebook_attivo = self._notebook

        # page_widget → Gtk.Label dentro la box del tab (per leggere/scrivere il nome)
        self._tab_labels: dict = {}

        # Barra inferiore: solo statusbar (la chiusura avviene con la X sul tab)
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        bottom_bar.get_style_context().add_class("bottom-bar")

        self._statusbar = Gtk.Statusbar()
        self._statusbar_ctx = self._statusbar.get_context_id("main")
        self._statusbar.set_hexpand(True)
        bottom_bar.pack_start(self._statusbar, True, True, 0)

        right_box.pack_start(bottom_bar, False, False, 0)

        # Schermata benvenuto (prima tab)
        self._mostra_benvenuto()

    def _build_headerbar(self):
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.set_title(t("app.title"))
        self.set_titlebar(hb)

        # Pulsante nuova sessione
        btn_new = Gtk.Button()
        btn_new.set_tooltip_text(t("toolbar.session.tooltip"))
        btn_new.add(Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON))
        btn_new.connect("clicked", lambda b: self._on_nuova_sessione())
        hb.pack_start(btn_new)

        # Pulsante terminale locale
        btn_term = Gtk.Button()
        btn_term.set_tooltip_text(t("toolbar.local.tooltip"))
        btn_term.add(Gtk.Image.new_from_icon_name("utilities-terminal-symbolic", Gtk.IconSize.BUTTON))
        btn_term.connect("clicked", lambda b: self._on_terminale_locale())
        hb.pack_start(btn_term)

        # Pulsante quick connect
        btn_qc = Gtk.Button()
        btn_qc.set_tooltip_text(t("toolbar.quickconn.tooltip"))
        btn_qc.add(Gtk.Image.new_from_icon_name("go-jump-symbolic", Gtk.IconSize.BUTTON))
        btn_qc.connect("clicked", lambda b: self._on_quick_connect())
        hb.pack_start(btn_qc)

        # Pulsante tunnel
        btn_tun = Gtk.Button()
        btn_tun.set_tooltip_text(t("toolbar.tunnel.tooltip"))
        btn_tun.add(Gtk.Image.new_from_icon_name("network-wired-symbolic", Gtk.IconSize.BUTTON))
        btn_tun.connect("clicked", lambda b: self._on_tunnel_manager())
        hb.pack_start(btn_tun)

        # Pulsante split
        btn_split = Gtk.MenuButton()
        btn_split.set_tooltip_text(t("toolbar.split.tooltip"))
        btn_split.add(Gtk.Image.new_from_icon_name("view-dual-symbolic", Gtk.IconSize.BUTTON))
        split_menu = Gtk.Menu()
        for label, cb in [
            (f"□  {t('toolbar.split.single')}",     self._split_singolo),
            (f"◫  {t('toolbar.split.vertical')}",   self._split_verticale),
            (f"⬒  {t('toolbar.split.horizontal')}", self._split_orizzontale),
        ]:
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _, c=cb: c())
            split_menu.append(mi)
        split_menu.show_all()
        btn_split.set_popup(split_menu)
        hb.pack_start(btn_split)

        # Menu applicazione (⋮ tre puntini verticali)
        self._menu_btn = Gtk.MenuButton()
        self._menu_btn.set_direction(Gtk.ArrowType.DOWN)
        self._menu_btn.set_tooltip_text(t("toolbar.menu.tooltip"))
        self._menu_btn.add(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.BUTTON))
        self._menu_btn.set_popup(self._build_menu())
        hb.pack_end(self._menu_btn)

        # Impostazioni (rotella ⚙)
        btn_set = Gtk.Button()
        btn_set.set_tooltip_text(t("toolbar.settings.tooltip"))
        btn_set.add(Gtk.Image.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON))
        btn_set.connect("clicked", lambda b: self._on_impostazioni())
        hb.pack_end(btn_set)

    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        def _item(label, callback):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: callback())
            menu.append(mi)

        _item(t("menu.tools.tunnels"),     self._on_tunnel_manager)
        _item(t("menu.tools.broadcast"),   self._on_broadcast)
        _item(t("menu.tools.variables"),   self._on_variabili_globali)
        _item(t("menu.tools.ftp_server"),  self._on_ftp_server)
        _item(t("menu.tools.import_from"), self._on_importa_sessioni)
        _item(t("menu.tools.audit"),       self._on_audit_log)
        _item(t("menu.tools.keepass"),     self._on_keepass_settings)
        menu.append(Gtk.SeparatorMenuItem())
        _item(t("menu.tools.crypto"),      self._on_gestione_crypto)
        _item(t("menu.tools.check_deps"),  self._on_check_deps)
        menu.append(Gtk.SeparatorMenuItem())
        _item(t("menu.help.guide"),        self._on_guida)
        _item(t("menu.help.about"),        self._on_about)
        menu.append(Gtk.SeparatorMenuItem())
        _item(t("menu.file.quit"),         self._on_esci)

        menu.show_all()
        return menu

    # ------------------------------------------------------------------
    # Segnali
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._pannello.connect("connetti", self._on_connetti)
        self._pannello.connect("nuova",    lambda p: self._on_nuova_sessione())
        self._pannello.connect("modifica", self._on_modifica_sessione)
        self._pannello.connect("elimina",  self._on_elimina_sessione)
        self._pannello.connect("duplica",  self._on_duplica_sessione)
        self._pannello.connect("apri-ft",  lambda _p, n, d: self._apri_ft_da_sessione(d))
        self._pannello.connect("ping",     self._on_ping_sessione)
        self.connect("delete-event", self._on_close)

    def _setup_accels(self):
        ag = Gtk.AccelGroup()
        self.add_accel_group(ag)
        # Ctrl+Shift+G → variabili globali  (Ctrl+Shift+V rimane libero per incolla VTE)
        key, mod = Gtk.accelerator_parse("<Primary><Shift>G")
        if key:
            ag.connect(key, mod, Gtk.AccelFlags.VISIBLE,
                       lambda *_: self._on_variabili_globali() or True)

    # ------------------------------------------------------------------
    # Schermata benvenuto
    # ------------------------------------------------------------------

    def _mostra_benvenuto(self):
        welcome = WelcomeWidget()
        welcome.connect("nuova-sessione",   lambda w: self._on_nuova_sessione())
        welcome.connect("terminale-locale", lambda w: self._on_terminale_locale())
        welcome.show_all()
        lbl = Gtk.Label(label=t("app.home_tab"))
        self._notebook.append_page(welcome, lbl)

    # ------------------------------------------------------------------
    # Apertura sessioni
    # ------------------------------------------------------------------

    def _on_connetti(self, panel, nome: str, dati: dict):
        proto = dati.get("protocol", "ssh")
        pre_cmd = dati.get("pre_cmd", "").strip()
        wol_mac = dati.get("wol_mac", "") if dati.get("wol_enabled") else ""

        # Registra sessione recente
        config_manager.add_recent(nome, dati)
        self._pannello.aggiorna()

        if pre_cmd or wol_mac:
            def _bg():
                if pre_cmd:
                    timeout = dati.get("pre_cmd_timeout", 15)
                    try:
                        subprocess.run(pre_cmd, shell=True, timeout=timeout)
                    except Exception as e:
                        GLib.idle_add(self._warn, f"Pre-cmd fallito: {e}")
                if wol_mac:
                    err = self._invia_wol(wol_mac, dati.get("wol_wait", 20))
                    if err:
                        GLib.idle_add(self._warn, f"WoL fallito: {err}")
                GLib.idle_add(self._apri_protocollo, proto, nome, dati)
            threading.Thread(target=_bg, daemon=True).start()
            return

        self._apri_protocollo(proto, nome, dati)

    def apri_da_cli(self, uri: str):
        """Apre una connessione da URI passato via riga di comando.

        Formati supportati:
          ssh://nome_sessione          — cerca sessione salvata per nome o hostname
          ssh://user@host:port         — connessione ad-hoc
          rdp://host?mode=external     — forza client esterno
          sftp://host / ftp://host     — file transfer
          vnc://host / telnet://host   — altri protocolli

        Query string opzionali (solo connessioni ad-hoc):
          ?mode=external               — apre in terminale/client esterno
          ?terminal=xterm              — emulatore esterno specifico
        """
        _PROTO_MAP = {
            "ssh": "ssh", "telnet": "telnet", "mosh": "mosh", "serial": "serial",
            "rdp": "rdp", "vnc": "vnc",
            "sftp": "file_transfer", "ftp": "file_transfer", "ftps": "file_transfer",
        }
        _DEFAULT_PORTS = {
            "ssh": "22", "telnet": "23", "mosh": "60001", "rdp": "3389",
            "vnc": "5900", "file_transfer": "22", "ftp": "21", "ftps": "21",
        }
        _FT_PROTO = {"sftp": "SFTP", "ftp": "FTP", "ftps": "FTPS"}

        # Se crypto è abilitato ma non ancora sbloccato, rimanda dopo l'unlock
        try:
            import crypto_manager
            if crypto_manager.is_enabled() and not crypto_manager.is_unlocked():
                self._pending_cli_uri = uri
                return
        except ImportError:
            pass

        parsed = urlparse(uri)
        scheme = (parsed.scheme or "ssh").lower()
        proto = _PROTO_MAP.get(scheme)
        if not proto:
            self._warn(f"Protocollo non supportato nella URI: {scheme}")
            return

        host = parsed.hostname or ""
        port = str(parsed.port) if parsed.port else ""
        user = parsed.username or ""
        password = parsed.password or ""

        # Opzioni da query string (solo per connessioni ad-hoc)
        from urllib.parse import parse_qs
        qs = parse_qs(parsed.query)
        mode_ext = qs.get("mode", [""])[0].lower() == "external"
        terminal_ext = qs.get("terminal", [""])[0]

        # --- Cerca sessione salvata ---
        profili = config_manager.load_profiles()
        nome_match = None
        dati_match = None

        # 1. Nome sessione == host nella URI (case-insensitive)
        for nome_s, dati_s in profili.items():
            if nome_s.lower() == host.lower():
                nome_match, dati_match = nome_s, dati_s
                break

        # 2. Hostname + stesso protocollo
        if not dati_match:
            for nome_s, dati_s in profili.items():
                if (dati_s.get("host", "").lower() == host.lower()
                        and dati_s.get("protocol") == proto):
                    nome_match, dati_match = nome_s, dati_s
                    break

        # 3. Hostname qualsiasi protocollo
        if not dati_match:
            for nome_s, dati_s in profili.items():
                if dati_s.get("host", "").lower() == host.lower():
                    nome_match, dati_match = nome_s, dati_s
                    break

        if dati_match:
            dati = dict(dati_match)
            if user:
                dati["user"] = user
            if port:
                dati["port"] = port
            self._on_connetti(None, nome_match, dati)
            return

        # --- Connessione ad-hoc ---
        dati = {
            "protocol": proto,
            "host": host,
            "port": port or _DEFAULT_PORTS.get(proto, ""),
            "user": user,
            "password": password,
        }
        if scheme in _FT_PROTO:
            dati["ft_protocol"] = _FT_PROTO[scheme]

        # Modalità apertura per protocollo
        mode = qs.get("mode", [""])[0].lower()   # "external" | "internal" | ""
        if proto in ("ssh", "telnet", "mosh", "serial"):
            if mode in ("external", "internal"):
                dati["ssh_open_mode"] = mode
            if terminal_ext:
                dati["terminal_type"] = terminal_ext
        elif proto == "rdp":
            # default RDP è già "external"; accetta esplicito "internal"
            if mode in ("external", "internal"):
                dati["rdp_open_mode"] = mode
        elif proto == "vnc":
            # vnc_internal=True → viewer embedded, False → client esterno
            if mode == "internal":
                dati["vnc_internal"] = True
            elif mode == "external":
                dati["vnc_internal"] = False

        nome_display = f"{scheme}://{host}"
        self._on_connetti(None, nome_display, dati)

    def _apri_protocollo(self, proto: str, nome: str, dati: dict):
        from datetime import datetime
        _ts_start = datetime.now()
        _status = "ok"
        try:
            if proto in ("ssh", "telnet", "mosh", "serial", "exec"):
                self._apri_terminale(nome, dati)
            elif proto == "sftp" or (proto == "file_transfer" and dati.get("ft_protocol", "SFTP") == "SFTP"):
                self._apri_sftp(nome, dati)
            elif proto in ("ftp", "file_transfer"):
                self._apri_ftp(nome, dati)
            elif proto == "rdp":
                self._apri_rdp(nome, dati)
            elif proto == "vnc":
                self._apri_vnc(nome, dati)
            self._status(t("status.connected", name=nome))
        except Exception as e:
            _status = "error"
            self._warn(str(e))
        finally:
            _dur = int((datetime.now() - _ts_start).total_seconds())
            config_manager.audit_append({
                "ts":       _ts_start.strftime("%Y-%m-%d %H:%M:%S"),
                "session":  nome,
                "host":     dati.get("host", ""),
                "proto":    proto,
                "duration": _dur,
                "status":   _status,
            })

    def _apri_terminale(self, nome: str, dati: dict):
        log_dir = dati.get("log_dir", "") if dati.get("log_output") else ""

        cmd, modalita = build_command(dati)

        # Gestione password: feed_child (primario) + SSH_ASKPASS (fallback)
        # feed_child digita la password quando compare il prompt nel VTE (imposta_auto_password).
        # SSH_ASKPASS gestisce il caso in cui SSH non mostra il prompt nel VTE:
        #   OpenSSH ≥ 8.4 + SSH_ASKPASS_REQUIRE=force → auth silenziosa senza prompt visibile.
        #   Old SSH → SSH_ASKPASS ignorato (TTY presente) → feed_child gestisce tutto.
        import shlex as _shlex
        env_extra = {}
        pwd  = dati.get("password", "")
        pkey = dati.get("private_key", "").strip()
        if pwd and not pkey:
            # SSH_ASKPASS: script temp mode 0700, password via env (non embedded nel file)
            _fd, _askpass = tempfile.mkstemp(prefix=".pcm_ask_", suffix=".sh", dir="/tmp", text=True)
            with os.fdopen(_fd, "w") as _f:
                _f.write("#!/bin/sh\nprintf '%s' \"$PCM_ASKPASS_PASSWORD\"\n")
            os.chmod(_askpass, 0o700)
            env_extra["PCM_ASKPASS_PASSWORD"] = pwd
            env_extra["SSH_ASKPASS"] = _askpass
            env_extra["SSH_ASKPASS_REQUIRE"] = "force"   # OpenSSH ≥ 8.4
            def _cleanup_askpass(path=_askpass):
                with contextlib.suppress(Exception):
                    os.unlink(path)
                return False
            GLib.timeout_add(15000, _cleanup_askpass)    # pulizia dopo 15 s

        # Modalità terminale ESTERNO: lancia nel terminal emulator scelto
        if modalita and modalita.endswith("_term_ext"):
            term = dati.get("terminal_type", "Terminale Interno")
            if term and term != "Terminale Interno":
                import shlex, shutil as _sh
                _press_enter_msg = t("term_ext.press_enter")
                inner = cmd + f"; echo ''; read -rp '{_press_enter_msg}' _x"
                inner_q = shlex.quote(inner)
                t = term.lower()
                if "xfce4-terminal" in t:
                    args = [term, f"--command=bash -c {inner_q}"]
                elif "gnome-terminal" in t or "mate-terminal" in t:
                    args = [term, "--", "bash", "-c", inner]
                elif "konsole" in t:
                    args = [term, "-e", "bash", "-c", inner]
                elif "tilix" in t:
                    args = [term, "-e", f"bash -c {inner_q}"]
                elif "alacritty" in t:
                    args = [term, "-e", "bash", "-c", inner]
                elif "kitty" in t or "foot" in t:
                    args = [term, "bash", "-c", inner]
                else:
                    # xterm e generici: -e bash -c CMD
                    args = [term, "-e", "bash", "-c", inner]
                try:
                    subprocess.Popen(args,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                except FileNotFoundError:
                    self._warn(t("term_ext.not_found", term=term))
                self._status(t("status.connected_ext", name=nome))
                return

        # Modalità INTERNA: usa TerminalWidget VTE
        widget = TerminalWidget.da_profilo(dati, log_dir=log_dir)
        widget.comando_display   = nome
        widget.comando_originale = cmd

        # SFTP browser laterale (solo SSH con sftp_browser attivo)
        if dati.get("sftp_browser") and dati.get("protocol") == "ssh":
            paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
            sftp = SftpBrowserWidget(dati)
            paned.pack1(widget, True, True)
            paned.pack2(sftp, False, False)
            paned.set_position(700)
            container = paned
        else:
            container = widget

        container._pcm_dati = dati
        container.show_all()
        self._append_tab(container, nome)
        GLib.idle_add(widget.grab_focus)

        # Primario: feed_child digita la password quando il VTE mostra un prompt
        if pwd and not pkey:
            widget.imposta_auto_password(pwd)

        widget.avvia(cmd, env_extra=env_extra)
        widget.connect("processo-terminato",
                       lambda w: self._on_processo_terminato(w))

    def _apri_sftp(self, nome: str, dati: dict):
        widget = WinScpWidget(dati)
        widget._pcm_dati = dati
        widget.show_all()
        self._append_tab(widget, nome, lambda: self._chiudi_tab(widget))

    def _apri_ftp(self, nome: str, dati: dict):
        widget = FtpWinScpWidget(dati)
        widget._pcm_dati = dati
        widget.show_all()
        self._append_tab(widget, nome, lambda: self._chiudi_tab(widget))

    def _apri_ft_da_sessione(self, dati_ssh: dict):
        """Mostra dialog per aprire SFTP/FTP riciclando le credenziali di una sessione."""
        dlg = _DialogApriFileTransfer(parent=self, dati_ssh=dati_ssh)
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            dati_ft = dlg.get_dati()
            host = dati_ft.get("host", "")
            ft_proto = dati_ft.get("ft_protocol", "SFTP")
            nome_tab = f"{ft_proto}: {host}"
            if ft_proto == "SFTP":
                self._apri_sftp(nome_tab, dati_ft)
            else:
                self._apri_ftp(nome_tab, dati_ft)
        dlg.destroy()

    def _apri_rdp(self, nome: str, dati: dict):
        open_mode = dati.get("rdp_open_mode", "external")
        if open_mode == "internal":
            widget = RdpEmbedWidget(dati, open_mode="internal")
            widget._pcm_dati = dati
            widget.show_all()
            self._append_tab(widget, nome, lambda: self._chiudi_tab(widget))
            widget.avvia()
        else:
            # Apre xfreerdp in finestra esterna
            from rdp_widget import _build_freerdp_cmd
            cmd = _build_freerdp_cmd(dati)
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _apri_vnc(self, nome: str, dati: dict):
        if dati.get("vnc_internal", False):
            # Viewer integrato
            def _salva_password_vnc(pwd: str):
                """Callback chiamato da VncWebWidget se l'utente sceglie 'salva'."""
                try:
                    profili = config_manager.load_profiles()
                    for gruppo in profili.values():
                        if isinstance(gruppo, dict) and nome in gruppo:
                            gruppo[nome]["password"] = pwd
                            config_manager.save_profiles(profili)
                            return
                    if nome in profili:
                        profili[nome]["password"] = pwd
                        config_manager.save_profiles(profili)
                except Exception:
                    pass

            widget = VncWebWidget(
                host=dati.get("host",""),
                port=dati.get("port","5900"),
                password=dati.get("password",""),
                color_depth=dati.get("vnc_color", 0),
                quality=dati.get("vnc_quality", 2),
                on_save_password=_salva_password_vnc,
            )
            widget._pcm_dati = dati
            widget.show_all()
            self._append_tab(widget, nome, lambda: self._chiudi_tab(widget))
        else:
            # Client VNC esterno — con logging su /tmp/pcm_vnc.log
            cmd, _ = build_command(dati)
            _VNC_LOG = "/tmp/pcm_vnc.log"
            import shutil as _sh, datetime as _dt, shlex as _shlex

            def _log(msg: str):
                ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(_VNC_LOG, "a") as _f:
                    _f.write(f"[{ts}] {msg}\n")

            _log(f"--- nuova connessione VNC: {nome} ---")
            _log(f"host={dati.get('host')} port={dati.get('port')} "
                 f"client={dati.get('vnc_client')} vnc_internal={dati.get('vnc_internal')}")

            if not cmd:
                _log("ERRORE: build_command ha restituito None")
                self._warn(t("vnc.unavailable", log=_VNC_LOG))
                return

            _log(f"comando: {cmd}")

            # Verifica eseguibile
            try:
                exe_token = _shlex.split(cmd)[0].strip('"').strip("'")
                exe_found = _sh.which(exe_token) or (
                    exe_token.startswith("/") and __import__("os").path.isfile(exe_token))
                _log(f"eseguibile '{exe_token}': {'trovato' if exe_found else 'NON TROVATO'}")
            except Exception as _e:
                _log(f"warning verifica exe: {_e}")

            try:
                log_f = open(_VNC_LOG, "a")
                proc = subprocess.Popen(
                    cmd, shell=True,
                    stdout=log_f, stderr=log_f,
                    close_fds=True
                )
                _log(f"PID={proc.pid}")

                def _check_exit(proc=proc, log_f=log_f):
                    rc = proc.poll()
                    if rc is not None:
                        _log(f"ATTENZIONE: uscito subito con codice {rc}")
                        GLib.idle_add(self._warn,
                            t("vnc.exit_early", rc=rc, log=_VNC_LOG))
                    log_f.close()
                    return False
                GLib.timeout_add(1500, _check_exit)
                self._status(t("vnc.started", name=nome, log=_VNC_LOG))
            except Exception as _e:
                _log(f"ECCEZIONE Popen: {_e}")
                self._warn(t("vnc.error", e=_e))

    # ------------------------------------------------------------------
    # Tab label con pulsante chiudi
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Helper label tab
    # ------------------------------------------------------------------

    def _make_tab_label(self, nome: str, on_close) -> "tuple[Gtk.Box, Gtk.Label]":
        """Crea la box label di un tab con nome + pulsante X."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl = Gtk.Label(label=nome)
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_focus_on_click(False)
        btn.set_tooltip_text(t("tab.close_session_tooltip"))
        img = Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        btn.add(img)
        btn.connect("clicked", lambda _b: on_close())
        box.pack_start(lbl, True, True, 0)
        box.pack_start(btn, False, False, 0)
        box.show_all()
        return box, lbl

    def _get_tab_nome(self, widget) -> str:
        """Legge il nome del tab da _tab_labels (o stringa vuota per la Home)."""
        lbl = self._tab_labels.get(widget)
        return lbl.get_text() if lbl else ""

    def _set_tab_nome(self, widget, nome: str):
        """Aggiorna il testo del label nel tab."""
        lbl = self._tab_labels.get(widget)
        if lbl:
            lbl.set_text(nome)

    def _append_tab(self, widget, nome: str, on_close=None):
        """Aggiunge un tab con label personalizzata (nome + pulsante X)."""
        cb = on_close or (lambda: self._chiudi_tab(widget))
        lbl_box, lbl = self._make_tab_label(nome, cb)
        self._tab_labels[widget] = lbl
        self._notebook.append_page(widget, lbl_box)
        self._notebook.set_tab_reorderable(widget, True)
        self._notebook.set_current_page(self._notebook.get_n_pages() - 1)
        GLib.idle_add(widget.grab_focus)

    # ------------------------------------------------------------------
    # Split pannelli
    # ------------------------------------------------------------------

    def _split_singolo(self):
        """Riporta tutto nel notebook primario e nasconde il secondario."""
        while self._notebook2.get_n_pages() > 0:
            self._sposta_tab(self._notebook2, self._notebook, 0)
        self._notebook2.hide()

    def _split_verticale(self):
        """Due notebook affiancati."""
        self._paned_term.set_orientation(Gtk.Orientation.HORIZONTAL)
        self._notebook2.show()
        alloc = self._paned_term.get_allocation()
        self._paned_term.set_position(max(200, alloc.width // 2))

    def _split_orizzontale(self):
        """Due notebook sovrapposti."""
        self._paned_term.set_orientation(Gtk.Orientation.VERTICAL)
        self._notebook2.show()
        alloc = self._paned_term.get_allocation()
        self._paned_term.set_position(max(100, alloc.height // 2))

    def _sposta_tab(self, sorgente: Gtk.Notebook, destinazione: Gtk.Notebook, idx: int):
        """Sposta il tab idx da sorgente a destinazione."""
        if idx < 0 or idx >= sorgente.get_n_pages():
            return
        widget = sorgente.get_nth_page(idx)
        nome   = self._get_tab_nome(widget)
        sorgente.remove_page(idx)
        # Ricrea la label custom per il notebook di destinazione
        lbl_box, lbl = self._make_tab_label(nome, lambda: self._chiudi_tab(widget))
        self._tab_labels[widget] = lbl
        destinazione.append_page(widget, lbl_box)
        destinazione.set_tab_reorderable(widget, True)
        destinazione.set_current_page(destinazione.get_n_pages() - 1)
        if destinazione is self._notebook2:
            self._notebook2.show()
        if sorgente is self._notebook2 and sorgente.get_n_pages() == 0:
            self._notebook2.hide()

    def _menu_tab(self, notebook, idx, event):
        """Menu tasto destro su un tab."""
        if idx < 0:
            return
        menu = Gtk.Menu()
        altra = self._notebook2 if notebook is self._notebook else self._notebook

        mi_sposta = Gtk.MenuItem(label=t("tab.move_to_other"))
        mi_sposta.connect("activate", lambda _: self._sposta_tab(notebook, altra, idx))
        menu.append(mi_sposta)

        page = notebook.get_nth_page(idx)
        dati_tab = getattr(page, "_pcm_dati", None)
        if dati_tab and dati_tab.get("protocol") in ("ssh", "telnet", "mosh", "serial"):
            menu.append(Gtk.SeparatorMenuItem())
            mi_ft = Gtk.MenuItem(label=t("tab.open_ft_here"))
            mi_ft.connect("activate", lambda _b, d=dati_tab: self._apri_ft_da_sessione(d))
            menu.append(mi_ft)

        if dati_tab:
            nome_tab = self._get_tab_nome(page)
            menu.append(Gtk.SeparatorMenuItem())
            mi_dup = Gtk.MenuItem(label=t("tab.duplicate"))
            mi_dup.connect(
                "activate",
                lambda _b, d=dati_tab, n=nome_tab: self._apri_protocollo(d.get("protocol", "ssh"), n, dict(d)),
            )
            menu.append(mi_dup)

        menu.append(Gtk.SeparatorMenuItem())

        mi_chiudi = Gtk.MenuItem(label=t("tab.close"))
        mi_chiudi.connect("activate", lambda _: self._chiudi_tab(notebook.get_nth_page(idx)))
        menu.append(mi_chiudi)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _on_nb_button_press(self, nb, event):
        if event.button != 3:
            return False
        # Trova su quale tab è il click
        for i in range(nb.get_n_pages()):
            page = nb.get_nth_page(i)
            lbl  = nb.get_tab_label(page)
            if lbl and lbl.get_window():
                alloc = lbl.get_allocation()
                x, y  = lbl.translate_coordinates(nb, 0, 0)
                if x <= event.x <= x + alloc.width and y <= event.y <= y + alloc.height:
                    if i > 0:  # non mostrare menu su Home
                        self._menu_tab(nb, i, event)
                    return True
        return False

    def _on_nb2_button_press(self, nb, event):
        if event.button != 3:
            return False
        for i in range(nb.get_n_pages()):
            page = nb.get_nth_page(i)
            lbl  = nb.get_tab_label(page)
            if lbl and lbl.get_window():
                alloc = lbl.get_allocation()
                x, y  = lbl.translate_coordinates(nb, 0, 0)
                if x <= event.x <= x + alloc.width and y <= event.y <= y + alloc.height:
                    self._menu_tab(nb, i, event)
                    return True
        return False

    def _trova_in_notebook(self, nb: "Gtk.Notebook", widget) -> "tuple[int, object]":
        """Cerca widget (o il Paned che lo contiene) in nb.
        Ritorna (idx, page_widget) se trovato, (-1, widget) altrimenti."""
        idx = nb.page_num(widget)
        if idx >= 0:
            return idx, widget
        for i in range(nb.get_n_pages()):
            page = nb.get_nth_page(i)
            if page is widget:
                return i, widget
            if hasattr(page, "get_child1"):
                if page.get_child1() is widget or page.get_child2() is widget:
                    return i, page
        return -1, widget

    def _chiudi_tab_corrente(self):
        """Chiude la tab corrente nel notebook attivo (primo o secondo pannello)."""
        nb  = self._notebook_attivo
        idx = nb.get_current_page()
        # Non chiudere la Home (sempre idx 0 nel notebook primario)
        if nb is self._notebook and idx <= 0:
            return
        widget = nb.get_nth_page(idx)
        if widget:
            self._chiudi_tab(widget)

    def _chiudi_tab(self, widget):
        """Chiude la tab che contiene widget (cerca in entrambi i notebook)."""
        nb = None
        idx = -1
        for candidate in (self._notebook, self._notebook2):
            idx, widget = self._trova_in_notebook(candidate, widget)
            if idx >= 0:
                nb = candidate
                break
        if idx < 0 or nb is None:
            return

        # --- Conferma chiusura se processo attivo ---
        # Trova il TerminalWidget (direttamente o dentro un Paned)
        _term_widget = None
        if hasattr(widget, "_pid"):
            _term_widget = widget
        elif hasattr(widget, "get_child1"):
            for _child in [widget.get_child1(), widget.get_child2()]:
                if _child and hasattr(_child, "_pid"):
                    _term_widget = _child
                    break

        if _term_widget is not None and getattr(_term_widget, "_pid", -1) > 0:
            # Legge l'impostazione dal profilo della sessione
            _dati = getattr(widget, "_pcm_dati", None) or getattr(_term_widget, "_pcm_dati", None)
            _confirm = True  # default: chiedi conferma
            if _dati is not None:
                _confirm = _dati.get("term_confirm_close", True)
            if _confirm:
                _nome_tab = self._get_tab_nome(widget)
                dlg = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    message_type=Gtk.MessageType.QUESTION,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text=t("tab.close_confirm_title"),
                )
                dlg.format_secondary_text(
                    t("tab.close_confirm_msg", name=_nome_tab) if _nome_tab
                    else t("tab.close_confirm_msg", name="?")
                )
                resp = dlg.run()
                dlg.destroy()
                if resp != Gtk.ResponseType.YES:
                    return  # l'utente ha annullato

        # Cleanup processi
        if hasattr(widget, "chiudi_processo"):
            widget.chiudi_processo()
        elif hasattr(widget, "get_child1"):
            for child in [widget.get_child1(), widget.get_child2()]:
                if child and hasattr(child, "chiudi_processo"):
                    child.chiudi_processo()
        nb.remove_page(idx)
        self._tab_labels.pop(widget, None)
        if nb is self._notebook2 and nb.get_n_pages() == 0:
            self._notebook2.hide()

    def _on_processo_terminato(self, widget, tab_label=None):
        """Marca la tab come terminata aggiungendo '✖' al nome (entrambi i notebook)."""
        for nb in (self._notebook, self._notebook2):
            idx, page = self._trova_in_notebook(nb, widget)
            if idx >= 0:
                nome = self._get_tab_nome(page)
                if nome and not nome.startswith("✖"):
                    self._set_tab_nome(page, f"✖ {nome}")
                return

    # ------------------------------------------------------------------
    # Azioni menu / toolbar
    # ------------------------------------------------------------------

    def _on_nuova_sessione(self):
        dlg = SessionDialog(parent=self)
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            nome, dati = dlg.get_data()
            profili = config_manager.load_profiles()
            profili[nome] = dati
            config_manager.save_profiles(profili)
            self._pannello.aggiorna(profili)
        dlg.destroy()

    def _on_terminale_locale(self):
        s = config_manager.load_settings().get("terminal", {})
        paste_right = s.get("paste_on_right_click", False)
        widget = TerminalWidget(paste_on_right_click=paste_right)
        widget.show_all()
        self._append_tab(widget, "Locale", lambda: self._chiudi_tab(widget))
        widget.avvia_locale()

    def _on_modifica_sessione(self, panel, nome: str, dati: dict):
        dlg = SessionDialog(parent=self, nome=nome, dati=dati)
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            nuovo_nome, nuovi_dati = dlg.get_data()
            profili = config_manager.load_profiles()
            if nome != nuovo_nome and nome in profili:
                del profili[nome]
            profili[nuovo_nome] = nuovi_dati
            config_manager.save_profiles(profili)
            self._pannello.aggiorna(profili)
        dlg.destroy()

    def _on_elimina_sessione(self, panel, nome: str):
        profili = config_manager.load_profiles()
        if nome in profili:
            del profili[nome]
            config_manager.save_profiles(profili)
            self._pannello.aggiorna(profili)
        else:
            self._pannello.aggiorna()

    def _on_duplica_sessione(self, panel, nome: str):
        profili = config_manager.load_profiles()
        if nome in profili:
            nuovo_nome = f"{nome} (copia)"
            profili[nuovo_nome] = dict(profili[nome])
            config_manager.save_profiles(profili)
            self._pannello.aggiorna(profili)
        else:
            self._pannello.aggiorna()

    def _on_tunnel_manager(self):
        dlg = TunnelManagerDialog(parent=self)
        dlg.run()
        dlg.destroy()

    def _on_impostazioni(self):
        dlg = SettingsDialog(parent=self)
        resp = dlg.run()
        dlg.destroy()
        if resp == Gtk.ResponseType.OK:
            self._settings = config_manager.load_settings()
            # Ricarica la lingua e ricostruisce il menu kebab
            _tr.init_from_settings()
            if hasattr(self, "_menu_btn") and self._menu_btn is not None:
                self._menu_btn.set_popup(self._build_menu())

    def _on_importa_sessioni(self):
        """Dialog di importazione sessioni da sorgenti esterne."""
        dlg = Gtk.Dialog(
            title=t("import.title"),
            transient_for=self,
            modal=True,
            destroy_with_parent=True
        )
        dlg.set_default_size(480, 0)
        area = dlg.get_content_area()
        area.set_spacing(10)
        area.set_margin_start(16); area.set_margin_end(16)
        area.set_margin_top(16);  area.set_margin_bottom(8)

        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{t('import.label')}</b>")
        area.pack_start(lbl, False, False, 0)

        # Sorgenti: 0=Remmina, 1=RDM, 2=PuTTY, 3=SSH Config
        # (indici usati in _esegui e _on_src_changed)
        SORGENTI = [
            t("import.source_remmina"),
            t("import.source_rdm"),
            t("importer.putty_title"),
            t("importer.ssh_cfg_title"),
        ]

        sorgente_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_src = Gtk.Label(label=t("import.source_lbl"))
        lbl_src.set_xalign(0.0)
        combo_src = Gtk.ComboBoxText()
        for s in SORGENTI:
            combo_src.append_text(s)
        combo_src.set_active(0)
        combo_src.set_hexpand(True)
        sorgente_box.pack_start(lbl_src, False, False, 0)
        sorgente_box.pack_start(combo_src, True, True, 0)
        area.pack_start(sorgente_box, False, False, 0)

        # Selettore file (solo per sorgenti file: Remmina e RDM)
        fc = Gtk.FileChooserButton(title=t("import.file_chooser"),
                                   action=Gtk.FileChooserAction.OPEN)
        fc.set_hexpand(True)
        area.pack_start(fc, False, False, 0)

        _filters_remmina = [("Remmina", "*.remmina"), (t("import.filter_all"), "*")]
        _filters_rdm     = [(t("import.filter_rdmxml"), "*.rdm"), (t("import.filter_rdmjson"), "*.json"), (t("import.filter_all"), "*")]

        def _set_filters(filtri):
            for old in fc.list_filters():
                fc.remove_filter(old)
            for nome_f, pattern in filtri:
                f = Gtk.FileFilter(); f.set_name(nome_f); f.add_pattern(pattern)
                fc.add_filter(f)

        _set_filters(_filters_remmina)

        def _on_src_changed(_combo):
            src = combo_src.get_active()
            file_based = src in (0, 1)
            fc.set_sensitive(file_based)
            if src == 0:
                _set_filters(_filters_remmina)
            elif src == 1:
                _set_filters(_filters_rdm)

        combo_src.connect("changed", _on_src_changed)

        chk_sost = Gtk.CheckButton(label=t("import.overwrite"))
        area.pack_start(chk_sost, False, False, 0)

        lbl_result = Gtk.Label(label="")
        lbl_result.set_xalign(0.0); lbl_result.set_line_wrap(True)
        area.pack_start(lbl_result, False, False, 0)

        btn_import = dlg.add_button(t("import.btn"), Gtk.ResponseType.APPLY)
        btn_import.get_style_context().add_class("suggested-action")
        dlg.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)

        def _esegui(b):
            import importer as _imp
            src = combo_src.get_active()
            try:
                if src == 0:  # Remmina
                    percorso = fc.get_filename()
                    if not percorso:
                        lbl_result.set_markup(f"<span foreground='red'>{t('import.no_file')}</span>")
                        return
                    nuovi = _imp.importa_remmina(percorso)
                elif src == 1:  # RDM
                    percorso = fc.get_filename()
                    if not percorso:
                        lbl_result.set_markup(f"<span foreground='red'>{t('import.no_file')}</span>")
                        return
                    nuovi = _imp.importa_rdm(percorso)
                elif src == 2:  # PuTTY
                    nuovi = _imp.importa_putty()
                    if not nuovi:
                        lbl_result.set_markup(f"<span foreground='orange'>{t('importer.putty_none')}</span>")
                        return
                else:  # SSH Config
                    nuovi = _imp.importa_ssh_config()
                    if not nuovi:
                        lbl_result.set_markup(f"<span foreground='orange'>{t('importer.ssh_cfg_none')}</span>")
                        return

                aggiunti, saltati = _imp.unisci_in_pcm(nuovi, chk_sost.get_active())
                _skipped_str = t("import.skipped", n=saltati) if saltati else ""
                lbl_result.set_markup(
                    f"<span foreground='green'>{t('import.result', n=aggiunti, skipped=_skipped_str)}</span>"
                )
                self._pannello.aggiorna()
            except Exception as e:
                lbl_result.set_markup(f"<span foreground='red'>{t('import.error', e=e)}</span>")

        btn_import.connect("clicked", _esegui)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def _on_ftp_server(self):
        from ftp_server_dialog import FtpServerDialog
        dlg = FtpServerDialog(parent=self)
        dlg.run()
        dlg.destroy()

    # ------------------------------------------------------------------
    # Quick connect
    # ------------------------------------------------------------------

    def _on_quick_connect(self):
        """Dialog connessione rapida senza salvare la sessione."""
        dlg = Gtk.Dialog(
            title=t("quickconn.title"), transient_for=self,
            modal=True, destroy_with_parent=True
        )
        dlg.set_default_size(420, 0)
        area = dlg.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(16); area.set_margin_end(16)
        area.set_margin_top(12);  area.set_margin_bottom(8)

        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{t('quickconn.title')}</b>\n<small>{t('quickconn.subtitle')}</small>")
        lbl.set_xalign(0.0)
        area.pack_start(lbl, False, False, 0)

        grid = Gtk.Grid()
        grid.set_row_spacing(6); grid.set_column_spacing(8)

        def _lbl(txt):
            l = Gtk.Label(label=txt); l.set_xalign(1.0)
            return l

        from session_dialog import PROTOCOLLI, PROTO_LABEL
        combo_proto = Gtk.ComboBoxText()
        for k in PROTOCOLLI:
            if k != "exec":
                combo_proto.append_text(PROTO_LABEL[k])
        combo_proto.set_active(0)
        combo_proto.set_hexpand(True)

        entry_host = Gtk.Entry(); entry_host.set_hexpand(True)
        entry_host.set_placeholder_text("hostname / IP")
        entry_port = Gtk.Entry(); entry_port.set_text("22"); entry_port.set_width_chars(6)
        entry_user = Gtk.Entry(); entry_user.set_hexpand(True)
        entry_pass = Gtk.Entry(); entry_pass.set_visibility(False); entry_pass.set_hexpand(True)

        grid.attach(_lbl(t("quickconn.proto_lbl")), 0, 0, 1, 1); grid.attach(combo_proto, 1, 0, 1, 1)
        grid.attach(_lbl(t("quickconn.host_lbl")),  0, 1, 1, 1); grid.attach(entry_host,  1, 1, 1, 1)
        grid.attach(_lbl(t("quickconn.port_lbl")),  0, 2, 1, 1); grid.attach(entry_port,  1, 2, 1, 1)
        grid.attach(_lbl(t("quickconn.user_lbl")),  0, 3, 1, 1); grid.attach(entry_user,  1, 3, 1, 1)
        grid.attach(_lbl(t("quickconn.pass_lbl")),  0, 4, 1, 1); grid.attach(entry_pass,  1, 4, 1, 1)
        area.pack_start(grid, False, False, 0)

        lbl_err = Gtk.Label(label=""); lbl_err.set_xalign(0.0)
        area.pack_start(lbl_err, False, False, 0)

        btn_conn = dlg.add_button(t("quickconn.connect"), Gtk.ResponseType.OK)
        btn_conn.get_style_context().add_class("suggested-action")
        dlg.add_button(t("dialog.cancel"), Gtk.ResponseType.CANCEL)

        # Porta default per protocollo
        _default_port = {"SSH": "22", "Telnet": "23", "FTP/SFTP": "22",
                         "RDP": "3389", "VNC": "5900", "Mosh": "22", "Seriale": ""}
        def _on_proto(_c):
            lbl_p = PROTO_LABEL.get(PROTOCOLLI[_c.get_active()], "")
            entry_port.set_text(_default_port.get(lbl_p, ""))
        combo_proto.connect("changed", _on_proto)

        dlg.show_all()
        if dlg.run() == Gtk.ResponseType.OK:
            host = entry_host.get_text().strip()
            if not host:
                lbl_err.set_markup(f"<span foreground='red'>{t('quickconn.no_host')}</span>")
                dlg.destroy()
                return
            proto_idx  = combo_proto.get_active()
            proto_lbls = [PROTO_LABEL[k] for k in PROTOCOLLI if k != "exec"]
            proto_lbl  = proto_lbls[proto_idx] if proto_idx >= 0 else "SSH"
            proto      = next((k for k, v in PROTO_LABEL.items() if v == proto_lbl), "ssh")
            dati = {
                "protocol": proto, "host": host,
                "port":     entry_port.get_text().strip(),
                "user":     entry_user.get_text().strip(),
                "password": entry_pass.get_text(),
                "sftp_browser": False,
            }
            nome_tab = f"{proto_lbl}: {host}"
            self._apri_protocollo(proto, nome_tab, dati)
        dlg.destroy()

    # ------------------------------------------------------------------
    # Connectivity test / ping
    # ------------------------------------------------------------------

    def _on_ping_sessione(self, _panel, nome: str, dati: dict):
        host = dati.get("host", "")
        try:
            port = int(dati.get("port", 22))
        except (ValueError, TypeError):
            port = 22

        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.CLOSE,
            text=f"Ping: {nome}",
        )
        dlg.format_secondary_text(t("ping.testing"))
        dlg.show_all()

        def _cb(ms):
            if ms >= 0:
                dlg.format_secondary_markup(
                    f"<span foreground='green'>{t('ping.ok', ms=ms)}</span>"
                )
            else:
                dlg.format_secondary_markup(
                    f"<span foreground='red'>{t('ping.fail', port=port)}</span>"
                )

        self._test_connettivita(host, port, _cb)
        dlg.run()
        dlg.destroy()

    def _test_connettivita(self, host: str, port: int, callback):
        """Verifica TCP raggiungibilità in thread. Chiama callback(ms) o callback(-1)."""
        import socket, time
        def _check():
            try:
                t0 = time.monotonic()
                with socket.create_connection((host, port), timeout=5):
                    ms = int((time.monotonic() - t0) * 1000)
                GLib.idle_add(callback, ms)
            except Exception:
                GLib.idle_add(callback, -1)
        threading.Thread(target=_check, daemon=True).start()

    # ------------------------------------------------------------------
    # Broadcast terminali
    # ------------------------------------------------------------------

    def _raccoglie_terminal_widgets(self) -> list:
        """Restituisce lista di (nome_tab, TerminalWidget) attivi."""
        result = []
        for nb in (self._notebook, self._notebook2):
            for i in range(nb.get_n_pages()):
                page = nb.get_nth_page(i)
                tw = None
                if isinstance(page, TerminalWidget):
                    tw = page
                elif hasattr(page, "get_child1"):
                    c1 = page.get_child1()
                    if isinstance(c1, TerminalWidget):
                        tw = c1
                if tw and not getattr(tw, "_stato_terminato", True):
                    nome = self._get_tab_nome(page) or f"Tab {i}"
                    result.append((nome, tw))
        return result

    def _on_broadcast(self):
        """Dialog broadcast: invia testo a più terminali selezionati."""
        terminali = self._raccoglie_terminal_widgets()

        dlg = Gtk.Dialog(
            title=t("broadcast.title"), transient_for=self,
            modal=True, destroy_with_parent=True
        )
        dlg.set_default_size(500, 380)
        area = dlg.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(16); area.set_margin_end(16)
        area.set_margin_top(12);  area.set_margin_bottom(8)

        if not terminali:
            lbl_no = Gtk.Label(label=t("broadcast.no_terminals"))
            area.pack_start(lbl_no, True, True, 0)
            dlg.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)
            dlg.show_all(); dlg.run(); dlg.destroy()
            return

        lbl = Gtk.Label(label=t("broadcast.label"))
        lbl.set_xalign(0.0)
        area.pack_start(lbl, False, False, 0)

        # Lista terminali con checkbox
        scroll_t = Gtk.ScrolledWindow()
        scroll_t.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_t.set_min_content_height(120)
        chk_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroll_t.add(chk_list)
        checks = []
        for nome_tab, tw in terminali:
            chk = Gtk.CheckButton(label=nome_tab)
            chk.set_active(True)
            chk.set_tooltip_text(getattr(tw, "_stato_testo", ""))
            chk_list.pack_start(chk, False, False, 0)
            checks.append((chk, tw))
        area.pack_start(scroll_t, True, True, 0)

        # Pulsanti seleziona/deseleziona
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_all = Gtk.Button(label=t("broadcast.select_all"))
        btn_all.connect("clicked", lambda _: [c.set_active(True) for c, _ in checks])
        btn_none = Gtk.Button(label=t("broadcast.deselect_all"))
        btn_none.connect("clicked", lambda _: [c.set_active(False) for c, _ in checks])
        btn_row.pack_start(btn_all, False, False, 0)
        btn_row.pack_start(btn_none, False, False, 0)
        area.pack_start(btn_row, False, False, 0)

        # Area testo
        lbl2 = Gtk.Label(label=t("broadcast.label"))
        lbl2.set_xalign(0.0)
        area.pack_start(lbl2, False, False, 0)

        sw_txt = Gtk.ScrolledWindow()
        sw_txt.set_min_content_height(80)
        tv = Gtk.TextView()
        tv.set_monospace(True)
        sw_txt.add(tv)
        area.pack_start(sw_txt, True, True, 0)

        chk_newline = Gtk.CheckButton(label=t("broadcast.add_enter"))
        chk_newline.set_active(True)
        area.pack_start(chk_newline, False, False, 0)

        lbl_result = Gtk.Label(label="")
        lbl_result.set_xalign(0.0)
        area.pack_start(lbl_result, False, False, 0)

        btn_send = dlg.add_button(t("broadcast.send"), Gtk.ResponseType.APPLY)
        btn_send.get_style_context().add_class("suggested-action")
        dlg.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)

        def _invia(b):
            buf = tv.get_buffer()
            testo = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
            if not testo:
                return
            add_nl = chk_newline.get_active()
            payload = (testo + "\n").encode("utf-8") if add_nl else testo.encode("utf-8")
            n_inviati = 0
            for chk, tw in checks:
                if chk.get_active():
                    try:
                        tw._vte.feed_child(payload)
                        n_inviati += 1
                    except Exception:
                        pass
            lbl_result.set_markup(f"<span foreground='green'>{t('broadcast.sent', n=n_inviati)}</span>")

        btn_send.connect("clicked", _invia)
        dlg.show_all()
        while True:
            resp = dlg.run()
            if resp != Gtk.ResponseType.APPLY:
                break
        dlg.destroy()

    # ------------------------------------------------------------------
    # Audit log viewer
    # ------------------------------------------------------------------

    def _on_audit_log(self):
        """Dialog visualizzazione registro audit connessioni."""
        dlg = Gtk.Dialog(
            title=t("audit.title"), transient_for=self,
            modal=True, destroy_with_parent=True
        )
        dlg.set_default_size(820, 480)
        area = dlg.get_content_area()
        area.set_margin_start(12); area.set_margin_end(12)
        area.set_margin_top(8);   area.set_margin_bottom(8)

        # TreeView
        store = Gtk.ListStore(str, str, str, str, str, str)
        tv = Gtk.TreeView(model=store)
        for i, col_title in enumerate([
            t("audit.col_time"), t("audit.col_session"), t("audit.col_host"),
            t("audit.col_proto"), t("audit.col_duration"), t("audit.col_status")
        ]):
            cell = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(col_title, cell, text=i)
            col.set_resizable(True)
            tv.append_column(col)

        def _ricarica():
            store.clear()
            log = config_manager.audit_load()
            if not log:
                store.append(["", t("audit.no_entries"), "", "", "", ""])
                return
            for e in reversed(log):
                dur = e.get("duration", 0)
                dur_str = f"{dur}s" if dur < 60 else f"{dur//60}m{dur%60:02d}s"
                stato = t("audit.status_ok") if e.get("status") == "ok" else t("audit.status_err")
                store.append([
                    e.get("ts", ""), e.get("session", ""), e.get("host", ""),
                    e.get("proto", ""), dur_str, stato
                ])

        _ricarica()

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(tv)
        area.pack_start(sw, True, True, 0)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(6)
        btn_clear = Gtk.Button(label=t("audit.clear"))
        btn_clear.get_style_context().add_class("destructive-action")
        def _cancella(_b):
            config_manager.audit_clear()
            _ricarica()
        btn_clear.connect("clicked", _cancella)

        btn_csv = Gtk.Button(label=t("audit.export_csv"))
        def _esporta_csv(_b):
            import csv, io
            fc = Gtk.FileChooserDialog(
                title=t("audit.csv_title"), transient_for=dlg,
                action=Gtk.FileChooserAction.SAVE
            )
            fc.add_button(t("audit.csv_cancel"), Gtk.ResponseType.CANCEL)
            fc.add_button(t("audit.csv_save"),   Gtk.ResponseType.OK)
            fc.set_current_name("pcm_audit.csv")
            if fc.run() == Gtk.ResponseType.OK:
                path = fc.get_filename()
                log  = config_manager.audit_load()
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=["ts","session","host","proto","duration","status"])
                    w.writeheader(); w.writerows(log)
            fc.destroy()
        btn_csv.connect("clicked", _esporta_csv)

        btn_row.pack_start(btn_clear, False, False, 0)
        btn_row.pack_end(btn_csv, False, False, 0)
        area.pack_start(btn_row, False, False, 0)

        dlg.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    # ------------------------------------------------------------------
    # KeePassXC settings (placeholder — configurazione associazione)
    # ------------------------------------------------------------------

    def _on_keepass_settings(self):
        """Apre il dialog impostazioni KeePassXC."""
        try:
            from keepassxc_manager import KeePassXCSettingsDialog
            dlg = KeePassXCSettingsDialog(parent=self)
            dlg.run()
            dlg.destroy()
        except ImportError:
            self._warn(t("keepass.missing"))

    def _on_variabili_globali(self):
        """Dialog variabili globali (variabili {VAR} usabili nei comandi)."""
        from variables_dialog import VariablesDialog
        dlg = VariablesDialog(parent=self)
        dlg.run()
        dlg.destroy()

    def _on_gestione_crypto(self):
        """Dialog gestione password master / cifratura credenziali."""
        from crypto_manager_dialog import CryptoManagerDialog
        dlg = CryptoManagerDialog(parent=self)
        dlg.run()
        dlg.destroy()

    def _on_check_deps(self):
        """Apre il pannello di configurazione dei percorsi eseguibili."""
        from deps_dialog import DepsConfigDialog
        dlg = DepsConfigDialog(parent=self)
        dlg.run()
        dlg.destroy()

    def _on_guida(self):
        """Apre la guida HTML nella lingua corrente (fallback inglese)."""
        import os
        from translations import get_lang
        here = os.path.dirname(os.path.abspath(__file__))
        lang = get_lang()
        # Cerca prima il file specifico per la lingua, poi cade sull'inglese
        html_path = os.path.join(here, f"pcm_help_{lang}.html")
        if not os.path.exists(html_path):
            html_path = os.path.join(here, "pcm_help_en.html")
        if not os.path.exists(html_path):
            dlg = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.CLOSE,
                text=t("guide.file_missing"),
            )
            dlg.run()
            dlg.destroy()
            return
        import subprocess
        subprocess.Popen(["xdg-open", html_path])

    def _on_about(self):
        """Dialog Informazioni su PCM."""
        dlg = Gtk.Dialog(
            title="PCM — Python Connection Manager",
            transient_for=self,
            modal=True,
        )  # titolo app: non tradotto intenzionalmente
        dlg.set_default_size(400, -1)
        dlg.add_button("OK", Gtk.ResponseType.OK)

        box = dlg.get_content_area()
        box.set_spacing(12)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(16)
        box.set_margin_bottom(12)

        lbl_title = Gtk.Label()
        lbl_title.set_markup("<b>PCM — Python Connection Manager</b>")
        lbl_title.set_xalign(0.0)
        box.pack_start(lbl_title, False, False, 0)

        lbl_desc = Gtk.Label(label=t("about.dev_label"))
        lbl_desc.set_xalign(0.0)
        box.pack_start(lbl_desc, False, False, 0)

        lbl_proto = Gtk.Label()
        lbl_proto.set_markup(t("about.proto_label"))
        lbl_proto.set_xalign(0.0)
        lbl_proto.set_line_wrap(True)
        box.pack_start(lbl_proto, False, False, 0)

        lbl_author = Gtk.Label()
        lbl_author.set_markup(
            "<b>Autore:</b> Andres Zanzani - "
            "<a href=\"mailto:azanzani@gmail.com\">azanzani@gmail.com</a>"
        )
        lbl_author.set_xalign(0.0)
        box.pack_start(lbl_author, False, False, 0)

        lbl_gh = Gtk.Label()
        lbl_gh.set_markup(
            "<b>GitHub:</b> "
            "<a href=\"https://github.com/buzzqw/Python_Connection_Manager\">"
            "github.com/buzzqw/Python_Connection_Manager</a>"
        )
        lbl_gh.set_xalign(0.0)
        box.pack_start(lbl_gh, False, False, 0)

        lbl_lic = Gtk.Label()
        lbl_lic.set_markup(t("about.license_label"))
        lbl_lic.set_xalign(0.0)
        box.pack_start(lbl_lic, False, False, 0)

        box.show_all()
        dlg.run()
        dlg.destroy()

    def _on_esci(self):
        self.get_application().quit()

    # ------------------------------------------------------------------
    # Chiusura finestra
    # ------------------------------------------------------------------

    def _on_close(self, window, event):
        settings = config_manager.load_settings()
        if settings.get("general", {}).get("confirm_on_exit", True):
            # Conta tab aperte (escludi la tab benvenuto)
            n_tabs = self._notebook.get_n_pages() - 1
            if n_tabs > 0:
                dlg = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    message_type=Gtk.MessageType.QUESTION,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text=t("close.title"),
                )
                dlg.format_secondary_text(t("close.confirm_msg"))
                resp = dlg.run()
                dlg.destroy()
                if resp != Gtk.ResponseType.YES:
                    return True  # blocca la chiusura
        # Chiudi tutti i processi aperti
        for i in range(self._notebook.get_n_pages()):
            page = self._notebook.get_nth_page(i)
            if page and hasattr(page, "chiudi_processo"):
                page.chiudi_processo()
        return False  # permetti chiusura

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _on_switch_tab(self, notebook, page, page_num):
        """Aggiorna statusbar al cambio tab (entrambi i notebook)."""
        self._notebook_attivo = notebook
        is_home = page not in self._tab_labels
        if is_home:
            self._status(t("status.ready"))
        else:
            nome_pulito = self._get_tab_nome(page).lstrip("✖ ")
            self._status(t("status.connected", name=nome_pulito))

    def _aggiorna_stato_live(self) -> bool:
        """Timer ogni 3s: aggiorna la statusbar con le stat live del terminale attivo."""
        idx = self._notebook.get_current_page()
        if idx <= 0:
            return True
        page = self._notebook.get_nth_page(idx)
        if page is None:
            return True
        # Cerca il TerminalWidget (può essere direttamente la page o figlio di Paned)
        tw = None
        if hasattr(page, "get_stato"):
            tw = page
        elif hasattr(page, "get_child1"):
            child = page.get_child1()
            if child and hasattr(child, "get_stato"):
                tw = child
        if tw is None:
            return True
        stato, terminato = tw.get_stato()
        if not stato:
            return True
        nome_pulito = self._get_tab_nome(page).lstrip("✖ ")
        if terminato:
            self._status(t("status.terminated", name=nome_pulito, state=stato))
        else:
            self._status(t("status.active", name=nome_pulito, state=stato))
        return True  # continua il timer

    def _status(self, msg: str):
        self._statusbar.pop(self._statusbar_ctx)
        self._statusbar.push(self._statusbar_ctx, msg)

    def _warn(self, msg: str):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=msg
        )
        dlg.run()
        dlg.destroy()

    def _invia_wol(self, mac: str, attesa: int) -> str:
        """Invia magic packet WoL e attende. Restituisce stringa errore o "" se OK.
        Thread-safe: non tocca la UI."""
        import socket, time
        try:
            mac_clean = mac.replace(":", "").replace("-", "")
            payload = bytes.fromhex("FF" * 6 + mac_clean * 16)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.sendto(payload, ("<broadcast>", 9))
            time.sleep(attesa)
            return ""
        except Exception as e:
            return str(e)


# ===========================================================================
# Applicazione GTK
# ===========================================================================


# ---------------------------------------------------------------------------
# Dialog "Apri SFTP/FTP da sessione esistente"
# ---------------------------------------------------------------------------

class _DialogApriFileTransfer(Gtk.Dialog):
    """Dialog che pre-compila host/credenziali da una sessione SSH e chiede il protocollo FT."""

    _PORT_DEFAULT = {"SFTP": "22", "FTP": "21", "FTPS": "21"}

    def __init__(self, parent, dati_ssh: dict):
        super().__init__(
            title=t("dlg_ft.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(420, 0)
        self._dati_ssh = dati_ssh
        self._init_ui()
        self.show_all()
        self._on_proto_changed(self._combo_proto)

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(6)
        area.set_margin_start(16)
        area.set_margin_end(16)
        area.set_margin_top(12)
        area.set_margin_bottom(8)

        grid = Gtk.Grid(row_spacing=6, column_spacing=8)
        area.pack_start(grid, False, False, 0)

        def _row(row, label_key, widget):
            lbl = Gtk.Label(label=t(label_key))
            lbl.set_xalign(1.0)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
            widget.set_hexpand(True)

        # Protocollo
        self._combo_proto = Gtk.ComboBoxText()
        for p in ("SFTP", "FTP", "FTPS"):
            self._combo_proto.append_text(p)
        self._combo_proto.set_active(0)
        self._combo_proto.connect("changed", self._on_proto_changed)
        _row(0, "dlg_ft.protocol", self._combo_proto)

        # Host
        self._entry_host = Gtk.Entry()
        self._entry_host.set_text(self._dati_ssh.get("host", ""))
        _row(1, "dlg_ft.host", self._entry_host)

        # Porta
        self._entry_port = Gtk.Entry()
        self._entry_port.set_text(self._dati_ssh.get("port", "22") or "22")
        _row(2, "dlg_ft.port", self._entry_port)

        # Utente
        self._entry_user = Gtk.Entry()
        self._entry_user.set_text(self._dati_ssh.get("user", ""))
        _row(3, "dlg_ft.user", self._entry_user)

        # Password
        self._entry_pwd = Gtk.Entry()
        self._entry_pwd.set_visibility(False)
        self._entry_pwd.set_text(self._dati_ssh.get("password", ""))
        _row(4, "dlg_ft.password", self._entry_pwd)

        # Chiave privata (solo SFTP)
        self._pkey_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._entry_pkey = Gtk.Entry()
        self._entry_pkey.set_text(self._dati_ssh.get("private_key", ""))
        self._entry_pkey.set_hexpand(True)
        btn_pkey = Gtk.Button(label=t("dlg_ft.pkey_browse"))
        btn_pkey.connect("clicked", self._on_browse_pkey)
        self._pkey_box.pack_start(self._entry_pkey, True, True, 0)
        self._pkey_box.pack_start(btn_pkey, False, False, 0)
        self._lbl_pkey = Gtk.Label(label=t("dlg_ft.pkey"))
        self._lbl_pkey.set_xalign(1.0)
        grid.attach(self._lbl_pkey, 0, 5, 1, 1)
        grid.attach(self._pkey_box, 1, 5, 1, 1)
        self._pkey_box.set_hexpand(True)

        self.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        ok = self.add_button(t("sd.ok"), Gtk.ResponseType.OK)
        ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)
        self._entry_host.connect("activate", lambda _: self.response(Gtk.ResponseType.OK))

    def _on_proto_changed(self, combo):
        proto = combo.get_active_text() or "SFTP"
        is_sftp = proto == "SFTP"
        self._lbl_pkey.set_visible(is_sftp)
        self._pkey_box.set_visible(is_sftp)
        # Aggiorna porta solo se invariata rispetto ai default
        current_port = self._entry_port.get_text().strip()
        for p, default in self._PORT_DEFAULT.items():
            if current_port == default:
                self._entry_port.set_text(self._PORT_DEFAULT[proto])
                break

    def _on_browse_pkey(self, _btn):
        dlg = Gtk.FileChooserDialog(
            title=t("dlg_ft.pkey"),
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dlg.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        dlg.add_button(t("sd.ok"), Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            self._entry_pkey.set_text(dlg.get_filename() or "")
        dlg.destroy()

    def get_dati(self) -> dict:
        proto = self._combo_proto.get_active_text() or "SFTP"
        return {
            "protocol":    "file_transfer",
            "ft_protocol": proto,
            "host":        self._entry_host.get_text().strip(),
            "port":        self._entry_port.get_text().strip(),
            "user":        self._entry_user.get_text().strip(),
            "password":    self._entry_pwd.get_text(),
            "private_key": self._entry_pkey.get_text().strip() if proto == "SFTP" else "",
            "ftp_tls":     proto == "FTPS",
            "ftp_passive": True,
        }


# ---------------------------------------------------------------------------
# Dialog sblocco password master (cifratura credenziali)
# ---------------------------------------------------------------------------

class _CryptoUnlockDialog(Gtk.Dialog):
    """Dialog modale per inserire la password master al primo avvio con crypto."""

    def __init__(self, parent=None):
        super().__init__(
            title=t("crypto.unlock.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.set_default_size(360, 0)
        self._pwd = ""
        self._init_ui()
        self.show_all()

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(10)
        area.set_margin_start(16)
        area.set_margin_end(16)
        area.set_margin_top(16)
        area.set_margin_bottom(8)

        lbl = Gtk.Label()
        lbl.set_markup(f"<b>🔒 {t('crypto.unlock.title')}</b>\n"
                       f"<small>{t('crypto.unlock.prompt')}</small>")
        lbl.set_xalign(0.0)
        lbl.set_line_wrap(True)
        area.pack_start(lbl, False, False, 0)

        self._entry = Gtk.Entry()
        self._entry.set_visibility(False)
        self._entry.set_placeholder_text(t("crypto.password_label"))
        self._entry.connect("activate", lambda e: self.response(Gtk.ResponseType.OK))
        area.pack_start(self._entry, False, False, 0)

        self.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        ok = self.add_button(t("crypto.unlock.btn_ok"), Gtk.ResponseType.OK)
        ok.get_style_context().add_class("suggested-action")

    def get_password(self) -> str:
        return self._entry.get_text()

class PCMApp(Gtk.Application):

    def __init__(self):
        super().__init__(
            application_id="it.pcm.connectionmanager",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.connect("activate", self._on_activate)
        self.connect("command-line", self._on_command_line)

    def _on_activate(self, app):
        apply_css()
        win = MainWindow(app)
        win.show_all()

    def _on_command_line(self, app, cmdline):
        args = cmdline.get_arguments()   # args[0] = nome programma
        uri = args[1] if len(args) > 1 else None

        # Porta la finestra principale in primo piano (o la crea)
        wins = self.get_windows()
        if not wins:
            self.activate()
            wins = self.get_windows()

        if wins:
            wins[0].present()
            if uri:
                GLib.idle_add(wins[0].apri_da_cli, uri)

        return 0


def main():
    _tr.init_from_settings()
    app = PCMApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
