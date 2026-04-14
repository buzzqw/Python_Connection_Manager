"""
tunnel_manager.py - Gestore grafico SSH Tunnel per PCM (GTK3)

Usa Gtk.TreeView + Gtk.ListStore al posto di QTableWidget.
"""

import os
import signal
import subprocess
import shutil

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

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

        self.entry_host = Gtk.Entry()
        self.entry_host.set_text(d.get("ssh_host", ""))
        self.entry_host.set_placeholder_text("user@server.example.com")
        row("SSH host:", self.entry_host, 2)

        self.entry_ssh_port = Gtk.Entry()
        self.entry_ssh_port.set_text(str(d.get("ssh_port", "22")))
        row("SSH porta:", self.entry_ssh_port, 3)

        self.entry_lport = Gtk.Entry()
        self.entry_lport.set_text(str(d.get("local_port", "1080")))
        row("Porta locale:", self.entry_lport, 4)

        self.entry_rhost = Gtk.Entry()
        self.entry_rhost.set_text(d.get("remote_host", ""))
        self.entry_rhost.set_placeholder_text("host.interno (per -L/-R)")
        row("Host remoto:", self.entry_rhost, 5)

        self.entry_rport = Gtk.Entry()
        self.entry_rport.set_text(str(d.get("remote_port", "")))
        row("Porta remota:", self.entry_rport, 6)

        self.chk_autostart = Gtk.CheckButton(label="Avvia automaticamente")
        self.chk_autostart.set_active(d.get("autostart", False))
        grid.attach(self.chk_autostart, 0, 7, 2, 1)

        self._on_tipo_changed(self.combo_tipo)

    def _on_tipo_changed(self, combo):
        is_socks = combo.get_active() == 0
        self.entry_rhost.set_sensitive(not is_socks)
        self.entry_rport.set_sensitive(not is_socks)

    def get_data(self) -> dict:
        return {
            "nome":        self.entry_nome.get_text().strip(),
            "tipo":        self.combo_tipo.get_active_text(),
            "ssh_host":    self.entry_host.get_text().strip(),
            "ssh_port":    self.entry_ssh_port.get_text().strip() or "22",
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
        self.set_default_size(700, 420)
        self._tunnels: list[dict] = config_manager.load_tunnels()
        self._procs:   dict[int, subprocess.Popen] = {}  # idx → processo
        self._init_ui()
        self._ricarica()
        self.show_all()
        # Polling stato ogni 3 secondi
        self._poll_source = GLib.timeout_add(3000, self._aggiorna_stati)
        self.connect("destroy", self._on_destroy)

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(0)

        # Toolbar pulsanti
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_margin_start(8)
        tb.set_margin_end(8)
        tb.set_margin_top(8)
        tb.set_margin_bottom(8)
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

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        area.pack_start(sep, False, False, 0)

        # Tabella: nome, tipo, host, lport, rhost, rport, stato
        self._store = Gtk.ListStore(str, str, str, str, str, str, str, int)
        # cols:       nome tipo host lport rhost rport stato idx_interno

        self._view = Gtk.TreeView(model=self._store)
        self._view.set_headers_visible(True)

        headers = ["Nome", "Tipo", "SSH Host", "Porta locale",
                   "Host remoto", "Porta remota", "Stato"]
        for i, h in enumerate(headers):
            cell = Gtk.CellRendererText()
            col  = Gtk.TreeViewColumn(h, cell, text=i)
            col.set_resizable(True)
            col.set_min_width(80)
            self._view.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add(self._view)
        area.pack_start(scroll, True, True, 0)

        self.add_button("Chiudi", Gtk.ResponseType.CLOSE)
        self.connect("response", lambda d, r: d.destroy())

    # ------------------------------------------------------------------

    def _ricarica(self):
        self._store.clear()
        for i, t in enumerate(self._tunnels):
            stato = "Attivo" if i in self._procs and self._procs[i].poll() is None \
                    else "Fermo"
            self._store.append([
                t.get("nome", ""),
                t.get("tipo", ""),
                t.get("ssh_host", ""),
                str(t.get("local_port", "")),
                t.get("remote_host", ""),
                str(t.get("remote_port", "")),
                stato,
                i
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
        if idx is None:
            return
        dlg = TunnelEditDialog(parent=self, dati=self._tunnels[idx])
        if dlg.run() == Gtk.ResponseType.OK:
            self._tunnels[idx] = dlg.get_data()
            config_manager.save_tunnels(self._tunnels)
            self._ricarica()
        dlg.destroy()

    def _on_elimina(self):
        idx = self._selected_idx()
        if idx is None:
            return
        self._on_ferma_idx(idx)
        self._tunnels.pop(idx)
        config_manager.save_tunnels(self._tunnels)
        self._ricarica()

    def _on_avvia(self):
        idx = self._selected_idx()
        if idx is None:
            return
        self._avvia_tunnel(idx)
        self._ricarica()

    def _on_ferma(self):
        idx = self._selected_idx()
        if idx is None:
            return
        self._on_ferma_idx(idx)
        self._ricarica()

    def _avvia_tunnel(self, idx: int):
        if idx in self._procs and self._procs[idx].poll() is None:
            return  # già attivo
        t = self._tunnels[idx]
        cmd = self._build_cmd(t)
        try:
            proc = subprocess.Popen(cmd, preexec_fn=os.setsid,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            self._procs[idx] = proc
        except Exception as e:
            print(f"[tunnel] Errore avvio: {e}")

    def _on_ferma_idx(self, idx: int):
        if idx in self._procs:
            proc = self._procs.pop(idx)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass

    @staticmethod
    def _build_cmd(t: dict) -> list:
        tipo  = t.get("tipo", "Proxy SOCKS (-D)")
        host  = t.get("ssh_host", "")
        sport = str(t.get("ssh_port", "22"))
        lport = str(t.get("local_port", "1080"))
        rhost = t.get("remote_host", "")
        rport = str(t.get("remote_port", ""))

        cmd = ["ssh", "-N", "-p", sport]
        if "SOCKS" in tipo:
            cmd += ["-D", lport]
        elif "Locale" in tipo:
            cmd += ["-L", f"{lport}:{rhost}:{rport}"]
        elif "Remoto" in tipo:
            cmd += ["-R", f"{rport}:{rhost}:{lport}"]
        cmd.append(host)
        return cmd

    def _aggiorna_stati(self) -> bool:
        self._ricarica()
        return True  # continua il timer

    def _on_destroy(self, *args):
        if hasattr(self, "_poll_source"):
            GLib.source_remove(self._poll_source)
