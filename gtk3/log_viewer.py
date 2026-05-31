"""
log_viewer.py — Visualizzatore log remoto in streaming per PCM (GTK3)

Mostra output di journalctl -f o tail -f via SSH (paramiko).
Supporta filtro regex con evidenziazione e colorazione per livello.

Thread safety: ogni _riavvia() incrementa _gen.  I thread di lettura
controllano il proprio gen e escono se ne esiste uno più recente —
evita canali orfani che causano "no more sessions".
"""

import os
import re
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False

from translations import t


_SORGENTI = [
    ("journalctl -f -n 200",               "journalctl (tutto)"),
    ("journalctl -f -n 200 -p err..emerg", "journalctl (errori)"),
    ("journalctl -f -n 200 -u {svc}",      "journalctl -u <service>"),
    ("tail -f {file}",                      "tail -f <file>"),
]

_MAX_LINES = 5000


class LogViewerWidget(Gtk.Box):
    """Visualizzatore log SSH in streaming."""

    def __init__(self, profilo: dict, existing_ssh=None):
        """
        existing_ssh: se fornita, viene riutilizzata (es. dal pannello monitor)
                      invece di aprire una nuova connessione TCP.
        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._profilo     = profilo
        self._ssh         = existing_ssh   # None = crea connessione propria
        self._ssh_owned   = existing_ssh is None  # True = dobbiamo chiuderla noi
        self._gen         = 0              # generation counter — invalida thread vecchi
        self._stopped     = False          # True dopo chiudi_processo() — blocca _connetti()
        self._filter_re   = None

        self._init_ui()
        self.connect("destroy", lambda w: self._stop())

        if existing_ssh is not None:
            # SSH già pronta: avvia subito lo streaming
            GLib.idle_add(self._riavvia)
        elif PARAMIKO_OK:
            threading.Thread(target=self._connetti, daemon=True).start()
        else:
            self._set_status("paramiko non installato")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_margin_start(6); tb.set_margin_end(6)
        tb.set_margin_top(4);   tb.set_margin_bottom(4)

        self._combo = Gtk.ComboBoxText()
        for _, label in _SORGENTI:
            self._combo.append_text(label)
        self._combo.set_active(0)
        self._combo.connect("changed", self._on_sorgente_cambiata)
        tb.pack_start(self._combo, False, False, 0)

        self._extra = Gtk.Entry()
        self._extra.set_placeholder_text("servizio o /path/file")
        self._extra.set_width_chars(22)
        self._extra.set_no_show_all(True)
        self._extra.hide()
        tb.pack_start(self._extra, False, False, 0)

        btn = Gtk.Button(label="▶ Avvia")
        btn.connect("clicked", lambda b: self._riavvia())
        tb.pack_start(btn, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        tb.pack_start(sep, False, False, 4)
        tb.pack_start(Gtk.Label(label="Filtro:"), False, False, 0)

        self._filter_entry = Gtk.SearchEntry()
        self._filter_entry.set_placeholder_text("regex…")
        self._filter_entry.set_width_chars(18)
        self._filter_entry.connect("search-changed", self._on_filter_cambiato)
        tb.pack_start(self._filter_entry, False, False, 0)

        self._chk_scroll = Gtk.CheckButton(label="Auto-scroll")
        self._chk_scroll.set_active(True)
        tb.pack_end(self._chk_scroll, False, False, 0)

        btn_clear = Gtk.Button(label="Svuota")
        btn_clear.connect("clicked", lambda b: self._svuota())
        tb.pack_end(btn_clear, False, False, 0)

        self.pack_start(tb, False, False, 0)
        self.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                        False, False, 0)

        self._buf = Gtk.TextBuffer()
        self._tag_err  = self._buf.create_tag("err",  foreground="#ff6b6b",
                                               weight=Pango.Weight.BOLD)
        self._tag_warn = self._buf.create_tag("warn", foreground="#ffd93d")
        self._tag_hit  = self._buf.create_tag("hit",  background="#2d4a22",
                                               foreground="#b8f5b8")

        tv = Gtk.TextView(buffer=self._buf)
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_monospace(True)
        tv.set_wrap_mode(Gtk.WrapMode.CHAR)
        self._tv = tv

        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._scroll.set_vexpand(True)
        self._scroll.add(tv)
        self.pack_start(self._scroll, True, True, 0)

        self._status = Gtk.Label(label="In attesa…")
        self._status.set_xalign(0.0)
        self._status.set_margin_start(6)
        self._status.set_margin_top(2)
        self._status.set_margin_bottom(2)
        self.pack_start(self._status, False, False, 0)

    # ------------------------------------------------------------------
    # Toolbar handlers
    # ------------------------------------------------------------------

    def _on_sorgente_cambiata(self, combo):
        tmpl = _SORGENTI[combo.get_active()][0]
        if "{svc}" in tmpl or "{file}" in tmpl:
            ph = "nome.service" if "{svc}" in tmpl else "/var/log/syslog"
            self._extra.set_placeholder_text(ph)
            self._extra.show()
        else:
            self._extra.hide()

    def _on_filter_cambiato(self, entry):
        pattern = entry.get_text().strip()
        try:
            self._filter_re = re.compile(pattern, re.IGNORECASE) if pattern else None
            entry.get_style_context().remove_class("error")
        except re.error:
            self._filter_re = None
            entry.get_style_context().add_class("error")

    def _get_cmd(self) -> str:
        idx  = self._combo.get_active()
        tmpl = _SORGENTI[idx][0]
        extra = self._extra.get_text().strip()
        if "{svc}" in tmpl:
            return tmpl.format(svc=extra or "ssh")
        if "{file}" in tmpl:
            return tmpl.format(file=extra or "/var/log/syslog")
        return tmpl

    # ------------------------------------------------------------------
    # Connessione SSH propria (usata solo se existing_ssh=None)
    # ------------------------------------------------------------------

    def _connetti(self):
        try:
            host = self._profilo.get("host", "")
            port = int(self._profilo.get("port", 22))
            user = self._profilo.get("user", "")
            pwd  = self._profilo.get("password", "")
            pkey = self._profilo.get("private_key", "")

            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

            kw = {"hostname": host, "port": port, "username": user, "timeout": 10}
            if pkey and os.path.isfile(pkey):
                kw["key_filename"] = pkey
            elif pwd:
                kw["password"] = pwd

            ssh.connect(**kw)
            if self._stopped:          # widget distrutto mentre connettevamo
                ssh.close()
                return
            self._ssh = ssh
            GLib.idle_add(self._set_status, f"✔ {host}")
            GLib.idle_add(self._riavvia)
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ {e}")

    # ------------------------------------------------------------------
    # Streaming con generation counter
    # ------------------------------------------------------------------

    def _riavvia(self):
        """Avvia (o riavvia) lo streaming. Thread-safe tramite gen counter."""
        # Invalida thread precedenti
        self._gen += 1
        gen = self._gen

        if not self._ssh:
            return

        cmd = self._get_cmd()
        self._set_status(f"▶ {cmd}")
        threading.Thread(target=self._leggi, args=(cmd, gen), daemon=True).start()

    def _leggi(self, cmd: str, gen: int):
        """Apre UN SOLO canale per questa generazione e legge in streaming."""
        channel = None
        try:
            transport = self._ssh.get_transport()
            if transport is None or not transport.is_active():
                GLib.idle_add(self._set_status, "✖ Transport SSH non attivo")
                return

            channel = transport.open_session()
            channel.exec_command(cmd)
            channel.settimeout(3.0)

            buf = ""
            while gen == self._gen:
                try:
                    data = channel.recv(4096)
                    if not data:
                        break
                    buf += data.decode("utf-8", errors="replace")
                    lines = buf.split("\n")
                    buf = lines[-1]
                    for line in lines[:-1]:
                        GLib.idle_add(self._append, line + "\n")
                except Exception:
                    # timeout o canale chiuso — controlla se siamo ancora validi
                    if gen != self._gen:
                        break
        except Exception as e:
            if gen == self._gen:
                GLib.idle_add(self._append, f"\n✖ {e}\n")
        finally:
            if channel:
                try:
                    channel.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Rendering testo
    # ------------------------------------------------------------------

    def _append(self, line: str):
        if self._filter_re and not self._filter_re.search(line):
            return

        end = self._buf.get_end_iter()
        low = line.lower()

        if any(w in low for w in ("error", "fail", "crit", "emerg", "alert")):
            base_tag = self._tag_err
        elif any(w in low for w in ("warn", "warning", "notice")):
            base_tag = self._tag_warn
        else:
            base_tag = None

        if self._filter_re:
            last = 0
            for m in self._filter_re.finditer(line):
                if m.start() > last:
                    seg = line[last:m.start()]
                    if base_tag:
                        self._buf.insert_with_tags(end, seg, base_tag)
                    else:
                        self._buf.insert(end, seg)
                    end = self._buf.get_end_iter()
                self._buf.insert_with_tags(end, line[m.start():m.end()], self._tag_hit)
                end = self._buf.get_end_iter()
                last = m.end()
            rem = line[last:]
            if rem:
                if base_tag:
                    self._buf.insert_with_tags(end, rem, base_tag)
                else:
                    self._buf.insert(end, rem)
        elif base_tag:
            self._buf.insert_with_tags(end, line, base_tag)
        else:
            self._buf.insert(end, line)

        n = self._buf.get_line_count()
        if n > _MAX_LINES:
            start = self._buf.get_start_iter()
            lim   = self._buf.get_iter_at_line(n - _MAX_LINES)
            self._buf.delete(start, lim)

        if self._chk_scroll.get_active():
            adj = self._scroll.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())

    def _svuota(self):
        self._buf.set_text("")

    def _set_status(self, msg: str):
        self._status.set_text(msg)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _stop(self):
        self._stopped = True    # segnala ai thread _connetti() orfani di non procedere
        self._gen += 1          # invalida tutti i thread _leggi() attivi
        if self._ssh_owned and self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None

    def chiudi_processo(self):
        self._stop()
