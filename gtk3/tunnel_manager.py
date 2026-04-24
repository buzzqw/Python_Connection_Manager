"""
tunnel_manager.py - Gestore grafico SSH Tunnel per PCM (GTK3)

Usa Gtk.TreeView + Gtk.ListStore al posto di QTableWidget.
Aggiunto supporto a sshpass, campo Utente, e Log terminal integrato.
"""

import os
import shutil
import signal
import subprocess
import fcntl

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

import config_manager


# ---------------------------------------------------------------------------
# Dialog aggiungi/modifica tunnel
# ---------------------------------------------------------------------------

class TunnelEditDialog(Gtk.Dialog):

    TIPI = ["Proxy SOCKS (-D)", "Locale (-L)", "Remoto (-R)"]

    def __init__(self, parent=None, dati: dict = None):
        super().__init__(
            title="Configura Tunnel SSH",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.set_default_size(420, 0)
        dati = dati or {}
        self._init_ui(dati)
        self.add_button("Annulla", Gtk.ResponseType.CANCEL)
        self.add_button("Salva",   Gtk.ResponseType.OK)
        self.show_all()

    def _init_ui(self, d: dict):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.set_margin_top(12)
        area.set_margin_bottom(8)

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        area.add(grid)

        def row(label, widget, r):
            lbl = Gtk.Label(label=label)
            lbl.set_xalign(1.0)
            grid.attach(lbl, 0, r, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, r, 1, 1)

        self.entry_nome = Gtk.Entry()
        self.entry_nome.set_text(d.get("nome", ""))
        self.entry_nome.set_placeholder_text("es. SOCKS proxy casa")
        row("Nome:", self.entry_nome, 0)

        self.combo_tipo = Gtk.ComboBoxText()
        for t in self.TIPI:
            self.combo_tipo.append_text(t)
        tipo = d.get("tipo", self.TIPI[0])
        idx = self.TIPI.index(tipo) if tipo in self.TIPI else 0
        self.combo_tipo.set_active(idx)
        self.combo_tipo.connect("changed", self._on_tipo_changed)
        row("Tipo:", self.combo_tipo, 1)

        self.entry_user = Gtk.Entry()
        self.entry_user.set_text(d.get("ssh_user", ""))
        self.entry_user.set_placeholder_text("es. root")
        row("Utente:", self.entry_user, 2)

        self.entry_host = Gtk.Entry()
        self.entry_host.set_text(d.get("ssh_host", ""))
        self.entry_host.set_placeholder_text("server.example.com")
        row("SSH host:", self.entry_host, 3)

        self.entry_ssh_port = Gtk.Entry()
        self.entry_ssh_port.set_text(str(d.get("ssh_port", "22")))
        row("SSH porta:", self.entry_ssh_port, 4)

        self.entry_pwd = Gtk.Entry()
        self.entry_pwd.set_visibility(False)
        self.entry_pwd.set_text(d.get("password", ""))
        self.entry_pwd.set_placeholder_text("Vuoto = Chiavi SSH")
        row("Password:", self.entry_pwd, 5)

        self.entry_lport = Gtk.Entry()
        self.entry_lport.set_text(str(d.get("local_port", "1080")))
        row("Porta locale:", self.entry_lport, 6)

        self.entry_rhost = Gtk.Entry()
        self.entry_rhost.set_text(d.get("remote_host", ""))
        self.entry_rhost.set_placeholder_text("host.interno (per -L/-R)")
        row("Host remoto:", self.entry_rhost, 7)

        self.entry_rport = Gtk.Entry()
        self.entry_rport.set_text(str(d.get("remote_port", "")))
        row("Porta remota:", self.entry_rport, 8)

        self.chk_autostart = Gtk.CheckButton(label="Avvia automaticamente")
        self.chk_autostart.set_active(d.get("autostart", False))
        grid.attach(self.chk_autostart, 0, 9, 2, 1)

        self._on_tipo_changed(self.combo_tipo)

    def _on_tipo_changed(self, combo):
        is_socks = combo.get_active() == 0
        self.entry_rhost.set_sensitive(not is_socks)
        self.entry_rport.set_sensitive(not is_socks)

    def get_data(self) -> dict:
        return {
            "nome":        self.entry_nome.get_text().strip(),
            "tipo":        self.combo_tipo.get_active_text(),
            "ssh_user":    self.entry_user.get_text().strip(),
            "ssh_host":    self.entry_host.get_text().strip(),
            "ssh_port":    self.entry_ssh_port.get_text().strip() or "22",
            "password":    self.entry_pwd.get_text(),
            "local_port":  self.entry_lport.get_text().strip() or "1080",
            "remote_host": self.entry_rhost.get_text().strip(),
            "remote_port": self.entry_rport.get_text().strip(),
            "autostart":   self.chk_autostart.get_active(),
            "pid":         None,
        }


# ---------------------------------------------------------------------------
# Dialog principale tunnel manager
# ---------------------------------------------------------------------------

class TunnelManagerDialog(Gtk.Dialog):

    def __init__(self, parent=None):
        super().__init__(
            title="Tunnel SSH",
            transient_for=parent,
            modal=False,
            destroy_with_parent=True
        )
        self.set_default_size(750, 550)
        self._tunnels: list[dict] = config_manager.load_tunnels()
        self._procs:   dict[int, subprocess.Popen] = {}  # idx → processo
        self._init_ui()
        self._ricarica_e_riaggancia()
        self.show_all()
        self._poll_source = GLib.timeout_add(3000, self._aggiorna_stati)
        self.connect("destroy", self._on_destroy)

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(0)

        # Toolbar pulsanti
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_margin_start(8); tb.set_margin_end(8)
        tb.set_margin_top(8); tb.set_margin_bottom(8)
        area.pack_start(tb, False, False, 0)

        for label, callback in [
            ("Aggiungi", self._on_aggiungi),
            ("Modifica", self._on_modifica),
            ("Elimina",  self._on_elimina),
        ]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", lambda b, cb=callback: cb())
            tb.pack_start(btn, False, False, 0)

        tb.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)

        self.btn_start = Gtk.Button(label="▶ Avvia")
        self.btn_start.connect("clicked", lambda b: self._on_avvia())
        tb.pack_start(self.btn_start, False, False, 0)

        self.btn_stop = Gtk.Button(label="■ Ferma")
        self.btn_stop.connect("clicked", lambda b: self._on_ferma())
        tb.pack_start(self.btn_stop, False, False, 0)

        # Tabella (Metà superiore)
        self._store = Gtk.ListStore(str, str, str, str, str, str, str, int)
        self._view = Gtk.TreeView(model=self._store)
        self._view.set_headers_visible(True)

        headers = ["Nome", "Tipo", "Host", "Porta locale", "Host remoto", "Porta remota", "Stato"]
        for i, h in enumerate(headers):
            cell = Gtk.CellRendererText()
            col  = Gtk.TreeViewColumn(h, cell, text=i)
            col.set_resizable(True)
            col.set_min_width(80)
            self._view.append_column(col)

        scroll_tabella = Gtk.ScrolledWindow()
        scroll_tabella.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll_tabella.add(self._view)

        # Terminale di Log (Metà inferiore)
        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.1, 0.1, 0.1, 1.0))
        self.log_view.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.2, 1.0, 0.2, 1.0))
        self.log_view.override_font(Pango.FontDescription('Monospace 10'))

        scroll_log = Gtk.ScrolledWindow()
        scroll_log.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll_log.add(self.log_view)

        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned.pack1(scroll_tabella, True, True)
        paned.pack2(scroll_log, False, False)
        paned.set_position(200)

        area.pack_start(paned, True, True, 0)
        self.add_button("Chiudi", Gtk.ResponseType.CLOSE)
        self.connect("response", lambda d, r: d.destroy())

    # ------------------------------------------------------------------

    def _processo_vivo(self, pid: int) -> bool:
        """Controlla se un PID è ancora in esecuzione senza ucciderlo."""
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def _ricarica_e_riaggancia(self):
        """
        Carica i tunnel dalla config e tenta di riagganciare i processi SSH
        già in esecuzione (identificati dal PID salvato). Utile dopo
        chiusura e riapertura della finestra.
        """
        for i, t in enumerate(self._tunnels):
            pid = t.get("pid")
            if pid and self._processo_vivo(pid):
                # Crea un oggetto Popen "fantasma" per tracciare il PID
                proxy = object.__new__(subprocess.Popen)
                proxy.pid = pid
                proxy.returncode = None
                self._procs[i] = proxy
                self._scrivi_log(f"[{t.get('nome')}] Riagganciato processo PID {pid}\n")
            else:
                # PID non valido: reset stato
                if t.get("pid"):
                    t["pid"] = None
        self._ricarica()

    def _ricarica(self):
        self._store.clear()
        for i, t in enumerate(self._tunnels):
            vivo = i in self._procs and self._processo_vivo(self._procs[i].pid)
            stato = "Attivo" if vivo else "Fermo"
            target = f"{t.get('ssh_user', '')}@{t.get('ssh_host', '')}".strip("@")
            self._store.append([
                t.get("nome", ""), t.get("tipo", ""), target,
                str(t.get("local_port", "")), t.get("remote_host", ""),
                str(t.get("remote_port", "")), stato, i
            ])

    def _selected_idx(self) -> int | None:
        sel = self._view.get_selection()
        model, it = sel.get_selected()
        if it:
            return model.get_value(it, 7)
        return None

    def _on_aggiungi(self):
        dlg = TunnelEditDialog(parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            self._tunnels.append(dlg.get_data())
            config_manager.save_tunnels(self._tunnels)
            self._ricarica()
        dlg.destroy()

    def _on_modifica(self):
        idx = self._selected_idx()
        if idx is None: return
        dlg = TunnelEditDialog(parent=self, dati=self._tunnels[idx])
        if dlg.run() == Gtk.ResponseType.OK:
            self._tunnels[idx] = dlg.get_data()
            config_manager.save_tunnels(self._tunnels)
            self._ricarica()
        dlg.destroy()

    def _on_elimina(self):
        idx = self._selected_idx()
        if idx is None: return
        self._on_ferma_idx(idx)
        self._tunnels.pop(idx)
        config_manager.save_tunnels(self._tunnels)
        self._ricarica()

    def _on_avvia(self):
        idx = self._selected_idx()
        if idx is None: return
        self._avvia_tunnel(idx)
        self._ricarica()

    def _on_ferma(self):
        idx = self._selected_idx()
        if idx is None: return
        self._on_ferma_idx(idx)
        self._ricarica()

    def _avvia_tunnel(self, idx: int):
        if idx in self._procs and self._processo_vivo(self._procs[idx].pid):
            return

        t = self._tunnels[idx]
        cmd = self._build_cmd(t)
        pwd = t.get("password", "")

        self._scrivi_log(f"\n[{t.get('nome', 'Tunnel')}] Esecuzione: {' '.join(cmd)}\n")

        env = None
        if pwd:
            if not shutil.which("sshpass"):
                self._scrivi_log("ERRORE: Devi installare 'sshpass'. Esegui: sudo apt install sshpass\n")
                return
            cmd = ["sshpass", "-e"] + cmd
            env = {**os.environ, "SSHPASS": pwd}

        try:
            proc = subprocess.Popen(
                cmd,
                preexec_fn=os.setsid,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
            self._procs[idx] = proc
            self._tunnels[idx]["pid"] = proc.pid
            config_manager.save_tunnels(self._tunnels)

            # Rendiamo l'output non-bloccante per leggerlo in tempo reale
            fd = proc.stdout.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            GLib.io_add_watch(proc.stdout, GLib.IO_IN | GLib.IO_HUP, self._leggi_output_processo)

        except Exception as e:
            self._scrivi_log(f"ERRORE CRITICO: {str(e)}\n")

    def _leggi_output_processo(self, file_obj, condition):
        """Legge l'output asincrono del processo e lo stampa nel terminalino."""
        try:
            data = file_obj.read()
            if data:
                text = data.decode('utf-8', errors='replace')
                GLib.idle_add(self._scrivi_log, text)

            if condition & GLib.IO_HUP:
                return False
            return True
        except Exception:
            return False

    def _scrivi_log(self, testo: str):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, testo)
        mark = self.log_buffer.get_insert()
        self.log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _on_ferma_idx(self, idx: int):
        if idx in self._procs:
            proc = self._procs.pop(idx)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                self._scrivi_log(f"Tunnel (PID {proc.pid}) terminato.\n")
            except Exception:
                pass
            self._tunnels[idx]["pid"] = None
            config_manager.save_tunnels(self._tunnels)

    @staticmethod
    def _build_cmd(t: dict) -> list:
        tipo  = t.get("tipo", "Proxy SOCKS (-D)")
        user  = t.get("ssh_user", "")
        host  = t.get("ssh_host", "")
        sport = str(t.get("ssh_port", "22"))
        lport = str(t.get("local_port", "1080"))
        rhost = t.get("remote_host", "")
        rport = str(t.get("remote_port", ""))
        pwd   = t.get("password", "")

        target = f"{user}@{host}" if user else host

        cmd = [
            "ssh", "-N",
            "-p", sport,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=60"
        ]

        if not pwd:
            cmd += ["-o", "BatchMode=yes"]

        if "SOCKS" in tipo:
            cmd += ["-D", lport]
        elif "Locale" in tipo:
            cmd += ["-L", f"{lport}:{rhost}:{rport}"]
        elif "Remoto" in tipo:
            cmd += ["-R", f"{rport}:{rhost}:{lport}"]

        cmd.append(target)
        return cmd

    def _aggiorna_stati(self) -> bool:
        """Aggiorna solo la colonna Stato usando os.kill(0) per verificare
        se il processo è vivo, senza ricostruire tutta la lista."""
        it = self._store.get_iter_first()
        while it:
            idx = self._store.get_value(it, 7)
            vivo = idx in self._procs and self._processo_vivo(self._procs[idx].pid)
            if not vivo and idx in self._procs:
                # processo morto inaspettatamente: pulizia
                self._procs.pop(idx)
                self._tunnels[idx]["pid"] = None
                config_manager.save_tunnels(self._tunnels)
            self._store.set_value(it, 6, "Attivo" if vivo else "Fermo")
            it = self._store.iter_next(it)
        return True  # mantieni il timer attivo

    def _on_destroy(self, *args):
        if hasattr(self, "_poll_source"):
            GLib.source_remove(self._poll_source)
        # I tunnel SSH rimangono attivi dopo la chiusura della finestra.
        # I processi sopravvivono grazie a os.setsid(); i PID sono salvati
        # in config e verranno riagganciati alla prossima apertura.

    def ferma_tutti_alla_chiusura(self):
        """Chiama questo alla chiusura dell'app principale se vuoi
        terminare tutti i tunnel attivi."""
        for idx in list(self._procs.keys()):
            self._on_ferma_idx(idx)
