"""
ftp_server_dialog.py — Server FTP locale per PCM (GTK3)

Usa pyftpdlib in un thread di sistema.
Log e stati aggiornati via GLib.idle_add() per thread-safety Wayland.

Dipendenza: pip install pyftpdlib
"""

import os
import socket
import threading
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

try:
    from pyftpdlib.handlers   import FTPHandler
    from pyftpdlib.servers    import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer
    PYFTPDLIB_OK = True
except ImportError:
    PYFTPDLIB_OK = False


# ---------------------------------------------------------------------------
# Calcolo permessi FTP da config utente
# ---------------------------------------------------------------------------

def _calcola_permessi(u: dict) -> str:
    perms = ""
    if u.get("perm_read",    True):  perms += "elr"
    if u.get("perm_write",   False): perms += "adfmw"
    if u.get("perm_delete",  False): perms += "d"
    if u.get("perm_rename",  False): perms += "fm"
    if u.get("perm_mkdir",   False): perms += "mf"
    return perms or "elr"


# ---------------------------------------------------------------------------
# Thread server FTP
# ---------------------------------------------------------------------------

class _ServerThread(threading.Thread):

    def __init__(self, config: dict, on_log, on_avviato, on_errore, on_fermato):
        super().__init__(daemon=True)
        self.config     = config
        self._on_log    = on_log
        self._on_avv    = on_avviato
        self._on_err    = on_errore
        self._on_stop   = on_fermato
        self._server    = None
        self._stop_evt  = threading.Event()

    def run(self):
        if not PYFTPDLIB_OK:
            GLib.idle_add(self._on_err, "pyftpdlib non installato.\npip install pyftpdlib")
            return

        try:
            auth = DummyAuthorizer()
            for u in self.config.get("utenti", []):
                perm = _calcola_permessi(u)
                cartella = u.get("cartella", os.path.expanduser("~"))
                if not os.path.isdir(cartella):
                    os.makedirs(cartella, exist_ok=True)
                if u.get("tipo") == "anonymous":
                    auth.add_anonymous(cartella, perm=perm)
                else:
                    auth.add_user(u["nome"], u.get("password",""), cartella, perm=perm)

            on_log = self._on_log

            class Handler(FTPHandler):
                def on_connect(self):
                    GLib.idle_add(on_log, f"[+] Connessione da {self.remote_ip}:{self.remote_port}")
                def on_disconnect(self):
                    GLib.idle_add(on_log, f"[-] Disconnessione {self.remote_ip}")
                def on_login(self, username):
                    GLib.idle_add(on_log, f"[OK] Login: {username} da {self.remote_ip}")
                def on_login_failed(self, username, password):
                    GLib.idle_add(on_log, f"[ERR] Login fallito: {username} da {self.remote_ip}")
                def on_logout(self, username):
                    GLib.idle_add(on_log, f"[->] Logout: {username}")
                def on_file_sent(self, file):
                    GLib.idle_add(on_log, f"[⬇] Inviato: {os.path.basename(file)}")
                def on_file_received(self, file):
                    GLib.idle_add(on_log, f"[⬆] Ricevuto: {os.path.basename(file)}")

            Handler.authorizer  = auth
            Handler.passive_ports = range(
                self.config.get("pasv_min", 60000),
                self.config.get("pasv_max", 60100)
            )

            host = self.config.get("bind", "0.0.0.0")
            port = int(self.config.get("porta", 21))

            self._server = FTPServer((host, port), Handler)
            self._server.max_cons = 50
            self._server.max_cons_per_ip = 10

            ip = socket.gethostbyname(socket.gethostname())
            GLib.idle_add(self._on_avv, f"ftp://{ip}:{port}")

            # Polling ogni 0.3s — permette stop pulito
            while not self._stop_evt.is_set():
                self._server.serve_forever(timeout=0.3, blocking=False)

        except Exception as e:
            GLib.idle_add(self._on_err, str(e))
        finally:
            if self._server:
                try:
                    self._server.close_all()
                except Exception:
                    pass
            GLib.idle_add(self._on_stop)

    def ferma(self):
        self._stop_evt.set()


# ---------------------------------------------------------------------------
# Dialog principale
# ---------------------------------------------------------------------------

class FtpServerDialog(Gtk.Dialog):

    def __init__(self, parent=None):
        super().__init__(
            title="Server FTP locale",
            transient_for=parent,
            modal=False,
            destroy_with_parent=True
        )
        self.set_default_size(700, 560)
        self._server_thread: _ServerThread | None = None
        self._utenti: list[dict] = [
            {
                "tipo": "named", "nome": "pcm", "password": "pcm",
                "cartella": os.path.expanduser("~"),
                "perm_read": True, "perm_write": False,
                "perm_delete": False, "perm_rename": False, "perm_mkdir": False,
            }
        ]
        self._init_ui()
        self._aggiorna_utenti()
        self.show_all()
        self.connect("destroy", self._on_destroy)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(0)

        nb = Gtk.Notebook()
        area.pack_start(nb, True, True, 0)

        nb.append_page(self._build_tab_server(),  Gtk.Label(label="Server"))
        nb.append_page(self._build_tab_utenti(),  Gtk.Label(label="Utenti"))
        nb.append_page(self._build_tab_log(),     Gtk.Label(label="Log"))

        # Pulsanti
        bbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bbox.set_margin_start(12); bbox.set_margin_end(12)
        bbox.set_margin_top(8);   bbox.set_margin_bottom(8)
        area.pack_start(bbox, False, False, 0)

        self.btn_avvia = Gtk.Button(label="▶  Avvia server")
        self.btn_avvia.get_style_context().add_class("connect-button")
        self.btn_avvia.connect("clicked", lambda b: self._on_avvia())

        self.btn_ferma = Gtk.Button(label="■  Ferma server")
        self.btn_ferma.set_sensitive(False)
        self.btn_ferma.connect("clicked", lambda b: self._on_ferma())

        self.btn_chiudi = Gtk.Button(label="Chiudi")
        self.btn_chiudi.connect("clicked", lambda b: self.destroy())

        bbox.pack_start(self.btn_avvia,  False, False, 0)
        bbox.pack_start(self.btn_ferma,  False, False, 0)
        bbox.pack_end(self.btn_chiudi,   False, False, 0)

    # ------------------------------------------------------------------
    # Tab Server
    # ------------------------------------------------------------------

    def _build_tab_server(self) -> Gtk.Widget:
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        grid.set_margin_start(16)
        grid.set_margin_end(16)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)

        def row(lbl_text, widget, r):
            lbl = Gtk.Label(label=lbl_text)
            lbl.set_xalign(1.0)
            grid.attach(lbl, 0, r, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, r, 1, 1)

        self.spin_porta = Gtk.SpinButton.new_with_range(1, 65535, 1)
        self.spin_porta.set_value(2121)  # default >1024 per non richiedere root
        row("Porta:", self.spin_porta, 0)

        self.entry_bind = Gtk.Entry()
        self.entry_bind.set_text("0.0.0.0")
        row("Bind IP:", self.entry_bind, 1)

        self.spin_pasv_min = Gtk.SpinButton.new_with_range(1024, 65000, 1)
        self.spin_pasv_min.set_value(60000)
        row("Passive ports min:", self.spin_pasv_min, 2)

        self.spin_pasv_max = Gtk.SpinButton.new_with_range(1025, 65535, 1)
        self.spin_pasv_max.set_value(60100)
        row("Passive ports max:", self.spin_pasv_max, 3)

        self.chk_tls = Gtk.CheckButton(label="Abilita TLS (FTPS — richiede certificato)")
        grid.attach(self.chk_tls, 0, 4, 2, 1)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        grid.attach(sep, 0, 5, 2, 1)

        # Stato server
        self.lbl_stato = Gtk.Label(label="● Server fermo")
        self.lbl_stato.set_xalign(0.0)
        grid.attach(self.lbl_stato, 0, 6, 2, 1)

        self.lbl_url = Gtk.Label(label="")
        self.lbl_url.set_xalign(0.0)
        self.lbl_url.set_selectable(True)
        grid.attach(self.lbl_url, 0, 7, 2, 1)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(grid)
        return sw

    # ------------------------------------------------------------------
    # Tab Utenti
    # ------------------------------------------------------------------

    def _build_tab_utenti(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(12); box.set_margin_end(12)
        box.set_margin_top(12);  box.set_margin_bottom(12)

        # Toolbar utenti
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for label, cb in [("Aggiungi", self._on_aggiungi_utente),
                           ("Modifica", self._on_modifica_utente),
                           ("Rimuovi",  self._on_rimuovi_utente)]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", lambda b, c=cb: c())
            tb.pack_start(btn, False, False, 0)
        box.pack_start(tb, False, False, 0)

        # Lista utenti: tipo, nome, cartella, permessi
        self._utenti_store = Gtk.ListStore(str, str, str, str)
        self._utenti_view  = Gtk.TreeView(model=self._utenti_store)
        self._utenti_view.set_headers_visible(True)

        for i, h in enumerate(["Tipo", "Nome/Utente", "Cartella", "Permessi"]):
            cell = Gtk.CellRendererText()
            col  = Gtk.TreeViewColumn(h, cell, text=i)
            col.set_resizable(True)
            col.set_expand(i in (1, 2))
            self._utenti_view.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(200)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._utenti_view)
        box.pack_start(scroll, True, True, 0)

        return box

    # ------------------------------------------------------------------
    # Tab Log
    # ------------------------------------------------------------------

    def _build_tab_log(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8); box.set_margin_end(8)
        box.set_margin_top(8);  box.set_margin_bottom(8)

        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_clear = Gtk.Button(label="Pulisci log")
        btn_clear.connect("clicked", lambda b: self._pulisci_log())
        tb.pack_start(btn_clear, False, False, 0)
        box.pack_start(tb, False, False, 0)

        self._log_view = Gtk.TextView()
        self._log_view.set_editable(False)
        self._log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._log_view.set_monospace(True)
        self._log_buf = self._log_view.get_buffer()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._log_view)
        box.pack_start(scroll, True, True, 0)

        return box

    # ------------------------------------------------------------------
    # Gestione utenti
    # ------------------------------------------------------------------

    def _aggiorna_utenti(self):
        self._utenti_store.clear()
        for u in self._utenti:
            perms = []
            if u.get("perm_read"):   perms.append("r")
            if u.get("perm_write"):  perms.append("w")
            if u.get("perm_delete"): perms.append("d")
            if u.get("perm_rename"): perms.append("m")
            if u.get("perm_mkdir"):  perms.append("k")
            self._utenti_store.append([
                u.get("tipo", "named"),
                u.get("nome", "anonymous"),
                u.get("cartella", "~"),
                "".join(perms) or "—"
            ])

    def _on_aggiungi_utente(self):
        dlg = _UtenteDialog(parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            self._utenti.append(dlg.get_data())
            self._aggiorna_utenti()
        dlg.destroy()

    def _on_modifica_utente(self):
        sel = self._utenti_view.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return
        idx = int(model.get_path(it).to_string())
        dlg = _UtenteDialog(parent=self, dati=self._utenti[idx])
        if dlg.run() == Gtk.ResponseType.OK:
            self._utenti[idx] = dlg.get_data()
            self._aggiorna_utenti()
        dlg.destroy()

    def _on_rimuovi_utente(self):
        sel = self._utenti_view.get_selection()
        model, it = sel.get_selected()
        if it is None:
            return
        idx = int(model.get_path(it).to_string())
        self._utenti.pop(idx)
        self._aggiorna_utenti()

    # ------------------------------------------------------------------
    # Avvio / Stop server
    # ------------------------------------------------------------------

    def _on_avvia(self):
        if self._server_thread and self._server_thread.is_alive():
            return

        config = {
            "porta":    int(self.spin_porta.get_value()),
            "bind":     self.entry_bind.get_text().strip() or "0.0.0.0",
            "pasv_min": int(self.spin_pasv_min.get_value()),
            "pasv_max": int(self.spin_pasv_max.get_value()),
            "utenti":   self._utenti,
        }

        self._server_thread = _ServerThread(
            config,
            on_log     = self._log_riga,
            on_avviato = self._on_avviato,
            on_errore  = self._on_errore,
            on_fermato = self._on_fermato,
        )
        self._server_thread.start()
        self.btn_avvia.set_sensitive(False)
        self.btn_ferma.set_sensitive(True)
        self.lbl_stato.set_markup('<span foreground="#e8a020">⏳ Avvio in corso…</span>')

    def _on_ferma(self):
        if self._server_thread:
            self._server_thread.ferma()
        self.btn_ferma.set_sensitive(False)

    # ------------------------------------------------------------------
    # Callbacks server (chiamate su thread principale via GLib.idle_add)
    # ------------------------------------------------------------------

    def _on_avviato(self, url: str):
        self.lbl_stato.set_markup('<span foreground="#4ec9b0">● Server attivo</span>')
        self.lbl_url.set_text(url)
        self._log_riga(f"Server avviato: {url}")

    def _on_errore(self, msg: str):
        self.lbl_stato.set_markup(f'<span foreground="#cc4444">✖ Errore</span>')
        self._log_riga(f"ERRORE: {msg}")
        self.btn_avvia.set_sensitive(True)
        self.btn_ferma.set_sensitive(False)

    def _on_fermato(self):
        self.lbl_stato.set_markup('● Server fermo')
        self.lbl_url.set_text("")
        self._log_riga("Server fermato.")
        self.btn_avvia.set_sensitive(True)
        self.btn_ferma.set_sensitive(False)

    def _log_riga(self, msg: str):
        ts  = datetime.now().strftime("%H:%M:%S")
        riga = f"[{ts}] {msg}\n"
        end_it = self._log_buf.get_end_iter()
        self._log_buf.insert(end_it, riga)
        # Scroll automatico in fondo
        self._log_view.scroll_mark_onscreen(self._log_buf.get_insert())

    def _pulisci_log(self):
        self._log_buf.set_text("")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _on_destroy(self, *args):
        if self._server_thread:
            self._server_thread.ferma()


# ---------------------------------------------------------------------------
# Dialog modifica utente FTP
# ---------------------------------------------------------------------------

class _UtenteDialog(Gtk.Dialog):

    def __init__(self, parent=None, dati: dict = None):
        super().__init__(
            title="Utente FTP",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.set_default_size(420, 0)
        dati = dati or {
            "tipo": "named", "nome": "", "password": "",
            "cartella": os.path.expanduser("~"),
            "perm_read": True, "perm_write": False,
            "perm_delete": False, "perm_rename": False, "perm_mkdir": False,
        }
        self._init_ui(dati)
        self.add_button("Annulla", Gtk.ResponseType.CANCEL)
        self.add_button("Salva",   Gtk.ResponseType.OK)
        self.show_all()

    def _init_ui(self, d: dict):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12); area.set_margin_end(12)
        area.set_margin_top(12);  area.set_margin_bottom(8)

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        area.add(grid)

        def row(lbl_text, widget, r):
            lbl = Gtk.Label(label=lbl_text)
            lbl.set_xalign(1.0)
            grid.attach(lbl, 0, r, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, r, 1, 1)

        self.combo_tipo = Gtk.ComboBoxText()
        self.combo_tipo.append_text("named")
        self.combo_tipo.append_text("anonymous")
        self.combo_tipo.set_active(0 if d.get("tipo","named") == "named" else 1)
        self.combo_tipo.connect("changed", self._on_tipo)
        row("Tipo:", self.combo_tipo, 0)

        self.entry_nome = Gtk.Entry()
        self.entry_nome.set_text(d.get("nome", ""))
        row("Nome utente:", self.entry_nome, 1)

        self.entry_pwd = Gtk.Entry()
        self.entry_pwd.set_visibility(False)
        self.entry_pwd.set_text(d.get("password", ""))
        row("Password:", self.entry_pwd, 2)

        cart_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.entry_cart = Gtk.Entry()
        self.entry_cart.set_text(d.get("cartella", os.path.expanduser("~")))
        self.entry_cart.set_hexpand(True)
        btn_browse = Gtk.Button(label="…")
        btn_browse.connect("clicked", self._browse_cartella)
        cart_box.pack_start(self.entry_cart, True, True, 0)
        cart_box.pack_start(btn_browse,      False, False, 0)
        _lbl = Gtk.Label(label="Cartella:")
        _lbl.set_xalign(1.0)
        grid.attach(_lbl, 0, 3, 1, 1)
        grid.attach(cart_box, 1, 3, 1, 1)

        # Permessi
        perm_lbl = Gtk.Label(label="Permessi:")
        perm_lbl.set_xalign(1.0)
        grid.attach(perm_lbl, 0, 4, 1, 1)

        perm_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.chk_read   = Gtk.CheckButton(label="Lettura")
        self.chk_write  = Gtk.CheckButton(label="Scrittura")
        self.chk_delete = Gtk.CheckButton(label="Eliminazione")
        self.chk_rename = Gtk.CheckButton(label="Rinomina")
        self.chk_mkdir  = Gtk.CheckButton(label="Crea cartelle")

        self.chk_read.set_active(d.get("perm_read",    True))
        self.chk_write.set_active(d.get("perm_write",  False))
        self.chk_delete.set_active(d.get("perm_delete",False))
        self.chk_rename.set_active(d.get("perm_rename",False))
        self.chk_mkdir.set_active(d.get("perm_mkdir",  False))

        for chk in [self.chk_read, self.chk_write, self.chk_delete,
                    self.chk_rename, self.chk_mkdir]:
            perm_box.pack_start(chk, False, False, 0)
        grid.attach(perm_box, 1, 4, 1, 1)

        self._on_tipo(self.combo_tipo)

    def _on_tipo(self, combo):
        is_named = combo.get_active() == 0
        self.entry_nome.set_sensitive(is_named)
        self.entry_pwd.set_sensitive(is_named)

    def _browse_cartella(self, btn):
        dlg = Gtk.FileChooserDialog(
            title="Cartella radice FTP",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dlg.add_buttons("_Annulla", Gtk.ResponseType.CANCEL,
                        "_Seleziona", Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            self.entry_cart.set_text(dlg.get_filename())
        dlg.destroy()

    def get_data(self) -> dict:
        return {
            "tipo":        "named" if self.combo_tipo.get_active() == 0 else "anonymous",
            "nome":        self.entry_nome.get_text().strip(),
            "password":    self.entry_pwd.get_text(),
            "cartella":    self.entry_cart.get_text().strip(),
            "perm_read":   self.chk_read.get_active(),
            "perm_write":  self.chk_write.get_active(),
            "perm_delete": self.chk_delete.get_active(),
            "perm_rename": self.chk_rename.get_active(),
            "perm_mkdir":  self.chk_mkdir.get_active(),
        }
