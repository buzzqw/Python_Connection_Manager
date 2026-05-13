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

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, Gdk, GLib, GObject

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

        # Menu kebab (⋮) sul lato destro
        self._menu_btn = Gtk.MenuButton()
        self._menu_btn.set_direction(Gtk.ArrowType.DOWN)
        self._menu_btn.add(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        self._menu_btn.set_popup(self._build_menu())
        hb.pack_end(self._menu_btn)

        # Impostazioni
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

        _item(t("menu.file.settings"),     self._on_impostazioni)
        menu.append(Gtk.SeparatorMenuItem())
        _item(t("menu.tools.tunnels"),     self._on_tunnel_manager)
        _item(t("menu.tools.variables"),   self._on_variabili_globali)
        _item(t("menu.tools.ftp_server"),  self._on_ftp_server)
        _item(t("menu.tools.import_from"), self._on_importa_sessioni)
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
        lbl = Gtk.Label(label="Home")
        self._notebook.append_page(welcome, lbl)

    # ------------------------------------------------------------------
    # Apertura sessioni
    # ------------------------------------------------------------------

    def _on_connetti(self, panel, nome: str, dati: dict):
        proto = dati.get("protocol", "ssh")
        pre_cmd = dati.get("pre_cmd", "").strip()
        wol_mac = dati.get("wol_mac", "") if dati.get("wol_enabled") else ""

        if pre_cmd or wol_mac:
            # Pre-cmd e WoL sono bloccanti: eseguiti in thread per non congelare la UI
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

    def _apri_protocollo(self, proto: str, nome: str, dati: dict):
        if proto in ("ssh", "telnet", "mosh", "serial"):
            self._apri_terminale(nome, dati)
        elif proto == "sftp" or (proto == "file_transfer" and dati.get("ft_protocol", "SFTP") == "SFTP"):
            self._apri_sftp(nome, dati)
        elif proto in ("ftp", "file_transfer"):
            self._apri_ftp(nome, dati)
        elif proto == "rdp":
            self._apri_rdp(nome, dati)
        elif proto == "vnc":
            self._apri_vnc(nome, dati)
        self._status(f"Connesso: {nome}")

    def _apri_terminale(self, nome: str, dati: dict):
        log_dir = dati.get("log_dir", "") if dati.get("log_output") else ""

        cmd, modalita = build_command(dati)

        # Password via FIFO anonimo: evita SSHPASS in env var e cmdline
        env_extra = {}
        pwd  = dati.get("password", "")
        pkey = dati.get("private_key", "")
        if pwd and not pkey and shutil.which("sshpass"):
            fifo = tempfile.mktemp(prefix=".pcm_ssh_", dir="/tmp")
            os.mkfifo(fifo, 0o600)
            def _scrivi_pwd(fp=fifo, p=pwd):
                try:
                    with open(fp, "w") as fh:
                        fh.write(p + "\n")
                except Exception:
                    pass
                finally:
                    with contextlib.suppress(Exception):
                        os.unlink(fp)
            threading.Thread(target=_scrivi_pwd, daemon=True).start()
            env_extra["PCM_PWD_FIFO"] = fifo

        # Modalità terminale ESTERNO: lancia nel terminal emulator scelto
        if modalita and modalita.endswith("_term_ext"):
            term = dati.get("terminal_type", "Terminale Interno")
            if term and term != "Terminale Interno":
                import shlex, shutil as _sh
                inner = cmd + "; echo ''; read -rp 'Premi Invio per chiudere...' _x"
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
                    self._warn(f"Terminale non trovato: {term}\nVerifica che sia installato.")
                self._status(f"Connesso (esterno): {nome}")
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

        widget.avvia(cmd, env_extra=env_extra)
        widget.connect("processo-terminato",
                       lambda w: self._on_processo_terminato(w))

    def _apri_sftp(self, nome: str, dati: dict):
        widget = WinScpWidget(dati)
        widget.show_all()
        self._append_tab(widget, nome, lambda: self._chiudi_tab(widget))

    def _apri_ftp(self, nome: str, dati: dict):
        widget = FtpWinScpWidget(dati)
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
                self._warn(f"Comando VNC non disponibile.\nDettagli in {_VNC_LOG}")
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
                            f"VNC uscito subito (codice {rc}).\nVedi {_VNC_LOG}")
                    log_f.close()
                    return False
                GLib.timeout_add(1500, _check_exit)
                self._status(f"VNC avviato: {nome}  — log: {_VNC_LOG}")
            except Exception as _e:
                _log(f"ECCEZIONE Popen: {_e}")
                self._warn(f"Errore avvio VNC: {_e}")

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
        """Dialog di importazione sessioni da Remmina / RDM."""
        dlg = Gtk.Dialog(
            title="Importa sessioni",
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
        lbl.set_markup("<b>Importa connessioni da file esterno</b>\n<small>Supporta: Remmina, RDM (.rdm/.json)</small>")
        area.pack_start(lbl, False, False, 0)

        # Selettore file
        fc = Gtk.FileChooserButton(title="Seleziona file da importare",
                                   action=Gtk.FileChooserAction.OPEN)
        fc.set_hexpand(True)
        for nome, pattern in [("Remmina", "*.remmina"),
                               ("RDM XML", "*.rdm"),
                               ("RDM JSON", "*.json"),
                               ("Tutti i file", "*")]:
            f = Gtk.FileFilter()
            f.set_name(nome); f.add_pattern(pattern)
            fc.add_filter(f)
        area.pack_start(fc, False, False, 0)

        # Opzione sovrascrivi
        chk_sost = Gtk.CheckButton(label="Sovrascrivi sessioni esistenti con lo stesso nome")
        area.pack_start(chk_sost, False, False, 0)

        # Label risultato
        lbl_result = Gtk.Label(label="")
        lbl_result.set_xalign(0.0); lbl_result.set_line_wrap(True)
        area.pack_start(lbl_result, False, False, 0)

        btn_import = dlg.add_button("Importa", Gtk.ResponseType.APPLY)
        btn_import.get_style_context().add_class("suggested-action")
        dlg.add_button("Chiudi", Gtk.ResponseType.CLOSE)

        def _esegui(b):
            percorso = fc.get_filename()
            if not percorso:
                lbl_result.set_markup("<span foreground='red'>Nessun file selezionato.</span>")
                return
            try:
                import importer
                ext = os.path.splitext(percorso)[1].lower()
                if ext == ".remmina":
                    nuovi = importer.importa_remmina(percorso)
                elif ext in (".rdm", ".json"):
                    nuovi = importer.importa_rdm(percorso)
                else:
                    # Prova entrambi
                    try:
                        nuovi = importer.importa_remmina(percorso)
                    except Exception:
                        nuovi = importer.importa_rdm(percorso)
                aggiunti, saltati = importer.unisci_in_pcm(nuovi, chk_sost.get_active())
                lbl_result.set_markup(
                    f"<span foreground='green'>✓ Importate {aggiunti} sessioni"
                    f"{f', {saltati} saltate' if saltati else ''}.</span>"
                )
                self._pannello.aggiorna()
            except Exception as e:
                lbl_result.set_markup(f"<span foreground='red'>Errore: {e}</span>")

        btn_import.connect("clicked", _esegui)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def _on_ftp_server(self):
        from ftp_server_dialog import FtpServerDialog
        dlg = FtpServerDialog(parent=self)
        dlg.run()
        dlg.destroy()

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
        """Apre la guida HTML in una tab del notebook."""
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(here, "pcm_help.html")
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
        )
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

        lbl_desc = Gtk.Label(label="Sviluppato in Python/GTK3.")
        lbl_desc.set_xalign(0.0)
        box.pack_start(lbl_desc, False, False, 0)

        lbl_proto = Gtk.Label()
        lbl_proto.set_markup(
            "<b>Protocolli supportati:</b> SSH, Telnet, SFTP, FTP, RDP, VNC, "
            "SSH Tunnel, Mosh, Seriale"
        )
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
        lbl_lic.set_markup(
            "<b>Licenza:</b> European Union Public Licence (EUPL) v1.2"
        )
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
            self._status("Pronto")
        else:
            nome_pulito = self._get_tab_nome(page).lstrip("✖ ")
            self._status(f"Connesso: {nome_pulito}")

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
            self._status(f"✖ Terminata: {nome_pulito}  —  {stato}")
        else:
            self._status(f"Connesso: {nome_pulito}  —  {stato}")
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
        super().__init__(application_id="it.pcm.connectionmanager")
        self.connect("activate", self._on_activate)

    def _on_activate(self, app):
        apply_css()
        win = MainWindow(app)
        win.show_all()


def main():
    _tr.init_from_settings()
    app = PCMApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
