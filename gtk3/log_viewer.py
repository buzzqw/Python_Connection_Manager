"""
log_viewer.py — Visualizzatore log remoto in streaming per PCM (GTK3)

Mostra output di journalctl -f o tail -f via SSH (paramiko).
Supporta filtro regex con evidenziazione e colorazione per livello.

Thread safety: ogni _riavvia() incrementa _gen.  I thread di lettura
controllano il proprio gen e escono se ne esiste uno più recente —
evita canali orfani che causano "no more sessions".
"""

import contextlib
import os
import re
import shlex
import socket
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
from pcm_logging import get_logger as _get_log


_SORGENTI = [
    ("journalctl -f -n 200",               "journalctl (tutto)"),
    ("journalctl -f -n 200 -p err..emerg", "journalctl (errori)"),
    ("journalctl -f -n 200 -u {svc}",      "journalctl -u <service>"),
    ("tail -f {file}",                      "tail -f <file>"),
]

# Scansione unica: file di log leggibili, servizi systemd attivi, container
# Docker. I marker sono su righe dedicate e non contengono virgolette.
_DISCOVERY_SCRIPT = (
    "echo ===FILES; "
    "find /var/log -maxdepth 3 -type f \\( "
    "-name '*.log' -o -name 'syslog' -o -name 'messages' -o -name 'auth.log' "
    "\\) -readable -exec du -h {} + 2>/dev/null | head -50; "
    "echo ===SYSTEMD; "
    "if command -v journalctl >/dev/null 2>&1; then "
    "systemctl list-units --type=service --state=running --no-pager --no-legend "
    "2>/dev/null | awk '{print $1}' | head -30; fi; "
    "echo ===DOCKER; "
    "if command -v docker >/dev/null 2>&1; then "
    "docker ps --format '{{.Names}}' 2>/dev/null | head -25; fi"
)

_MAX_LINES = 5000


def parse_sorgenti_log(output: str) -> dict[str, list[tuple[str, str]]]:
    """Interpreta l'output di _DISCOVERY_SCRIPT.

    Ritorna {files: [(cmd, label)], systemd: [...], docker: [...]}.
    Le chiavi mancanti restano liste vuote. I comandi sono già shell-quoted.
    """
    gruppi: dict[str, list[tuple[str, str]]] = {
        "files": [], "systemd": [], "docker": [],
    }
    sezione = ""
    for riga in output.splitlines():
        riga = riga.strip()
        if not riga:
            continue
        if riga == "===FILES":
            sezione = "files"
            continue
        if riga == "===SYSTEMD":
            sezione = "systemd"
            continue
        if riga == "===DOCKER":
            sezione = "docker"
            continue

        if sezione == "files":
            # du -h separa dimensione e percorso con TAB (spazi nei path ok)
            if "\t" in riga:
                size, path = riga.split("\t", 1)
            else:
                parti = riga.split(None, 1)
                size, path = (parti[0], parti[1]) if len(parti) == 2 else ("", parti[0])
            path = path.strip()
            if not path.startswith("/"):
                continue
            nome = os.path.basename(path)
            label = f"{nome} ({size})" if size else nome
            gruppi["files"].append((f"tail -f -n 200 {shlex.quote(path)}", label))

        elif sezione == "systemd":
            svc = riga.split()[0]
            if not svc or svc.endswith(")"):
                continue
            nome = svc[:-8] if svc.endswith(".service") else svc
            gruppi["systemd"].append(
                (f"journalctl -f -n 200 -u {shlex.quote(svc)}", nome))

        elif sezione == "docker":
            nome = riga.split()[0]
            if nome:
                gruppi["docker"].append(
                    (f"docker logs -f --tail 200 {shlex.quote(nome)}", nome))

    return gruppi


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
        self._canale      = None           # canale attivo, chiuso subito al riavvio
        self._stopped     = False          # True dopo chiudi_processo() — blocca _connetti()
        self._filter_re   = None
        self._scoperta_in_corso = False

        # Sorgenti del combo: i 4 template statici + quelle scoperte sul server.
        # Ogni voce: {"cmd": template o comando, "label": testo, "placeholder": str}
        self._sorgenti: list[dict] = [
            {
                "cmd": cmd,
                "label": label,
                "placeholder": ("nome.service" if "{svc}" in cmd
                                else "/var/log/syslog" if "{file}" in cmd
                                else ""),
            }
            for cmd, label in _SORGENTI
        ]

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
        for voce in self._sorgenti:
            self._combo.append_text(voce["label"])
        self._combo.set_active(0)
        self._combo_handler = self._combo.connect("changed",
                                                  self._on_sorgente_cambiata)
        tb.pack_start(self._combo, False, False, 0)

        self._btn_scopri = Gtk.Button(label="🔍")
        self._btn_scopri.set_tooltip_text(t("log.discover_tooltip"))
        self._btn_scopri.connect("clicked", lambda b: self._scopri_sorgenti())
        tb.pack_start(self._btn_scopri, False, False, 0)

        self._extra = Gtk.Entry()
        self._extra.set_placeholder_text(t("log.extra_ph"))
        self._extra.set_width_chars(22)
        self._extra.set_no_show_all(True)
        self._extra.hide()
        tb.pack_start(self._extra, False, False, 0)

        btn = Gtk.Button(label=t("log.btn_start"))
        btn.connect("clicked", lambda b: self._riavvia())
        tb.pack_start(btn, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        tb.pack_start(sep, False, False, 4)
        tb.pack_start(Gtk.Label(label=t("log.filter_label")), False, False, 0)

        self._filter_entry = Gtk.SearchEntry()
        self._filter_entry.set_placeholder_text(t("log.filter_ph"))
        self._filter_entry.set_width_chars(18)
        self._filter_entry.connect("search-changed", self._on_filter_cambiato)
        tb.pack_start(self._filter_entry, False, False, 0)

        self._chk_scroll = Gtk.CheckButton(label=t("log.autoscroll"))
        self._chk_scroll.set_active(True)
        tb.pack_end(self._chk_scroll, False, False, 0)

        btn_clear = Gtk.Button(label=t("log.btn_clear"))
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

        self._status = Gtk.Label(label=t("log.waiting"))
        self._status.set_xalign(0.0)
        self._status.set_margin_start(6)
        self._status.set_margin_top(2)
        self._status.set_margin_bottom(2)
        self.pack_start(self._status, False, False, 0)

    # ------------------------------------------------------------------
    # Toolbar handlers
    # ------------------------------------------------------------------

    def _on_sorgente_cambiata(self, combo):
        idx = combo.get_active()
        if idx < 0 or idx >= len(self._sorgenti):
            return
        ph = self._sorgenti[idx].get("placeholder", "")
        if ph:
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
        idx = self._combo.get_active()
        if idx < 0 or idx >= len(self._sorgenti):
            return ""
        tmpl = self._sorgenti[idx]["cmd"]
        extra = self._extra.get_text().strip()
        if "{svc}" in tmpl:
            safe = shlex.quote(extra) if extra else "ssh"
            return tmpl.format(svc=safe)
        if "{file}" in tmpl:
            safe = shlex.quote(extra) if extra else "/var/log/syslog"
            return tmpl.format(file=safe)
        return tmpl

    # ------------------------------------------------------------------
    # Auto-discovery sorgenti log (/var/log, systemd, docker)
    # ------------------------------------------------------------------

    def _scopri_sorgenti(self):
        """Avvia la scansione remota (thread separato, un solo canale)."""
        if self._scoperta_in_corso:
            return
        if not self._ssh:
            self._set_status(t("log.discover_no_ssh"))
            return
        if self._stopped:
            return
        self._scoperta_in_corso = True
        self._btn_scopri.set_sensitive(False)
        self._set_status(t("log.discover_running"))
        threading.Thread(target=self._scopri_worker, daemon=True).start()

    def _scopri_worker(self):
        output = ""
        errore = ""
        channel = None
        try:
            transport = self._ssh.get_transport() if self._ssh else None
            if transport is None or not transport.is_active():
                errore = t("log.discover_no_ssh")
            else:
                channel = transport.open_session()
                channel.settimeout(8.0)
                channel.exec_command(_DISCOVERY_SCRIPT)
                pezzi = []
                try:
                    while True:
                        data = channel.recv(4096)
                        if not data:
                            break
                        pezzi.append(data.decode("utf-8", errors="replace"))
                except Exception as e:
                    # Timeout: usa comunque l'output già ricevuto (la scansione
                    # può essere lenta su /var/log molto grandi).
                    if not pezzi:
                        raise
                    _get_log(__name__).debug(
                        "Discovery interrotta, uso output parziale: %s", e)
                output = "".join(pezzi)
        except Exception as e:
            errore = str(e)
        finally:
            if channel:
                try:
                    channel.close()
                except Exception as e:
                    _get_log(__name__).debug("Canale discovery close fallito: %s", e)

        if self._stopped:
            return
        if errore:
            GLib.idle_add(self._scoperta_finita, None, errore)
        else:
            GLib.idle_add(self._scoperta_finita, parse_sorgenti_log(output), "")

    def _scoperta_finita(self, gruppi, errore: str):
        self._scoperta_in_corso = False
        if self._stopped:
            return
        self._btn_scopri.set_sensitive(True)
        if errore or gruppi is None:
            self._set_status(t("log.discover_error", e=errore or "?"))
            return
        self._applica_sorgenti(gruppi)

    def _applica_sorgenti(self, gruppi: dict):
        """Ricostruisce il combo: template statici + sorgenti trovate."""
        etichette = {
            "files":   t("log.src_file"),
            "systemd": t("log.src_systemd"),
            "docker":  t("log.src_docker"),
        }
        selezione = self._get_cmd()
        nuove = [dict(v) for v in self._sorgenti[:len(_SORGENTI)]]
        viste = {v["cmd"] for v in nuove}
        for chiave in ("files", "systemd", "docker"):
            for cmd, label in gruppi.get(chiave, []):
                if cmd in viste:
                    continue
                viste.add(cmd)
                nuove.append({
                    "cmd": cmd,
                    "label": f"{etichette[chiave]} · {label}",
                    "placeholder": "",
                })

        trovate = len(nuove) - len(_SORGENTI)
        self._sorgenti = nuove

        self._combo.handler_block(self._combo_handler)
        try:
            self._combo.remove_all()
            for voce in self._sorgenti:
                self._combo.append_text(voce["label"])
            ripristinata = False
            for i, voce in enumerate(self._sorgenti):
                if voce["cmd"] == selezione:
                    self._combo.set_active(i)
                    ripristinata = True
                    break
            if not ripristinata:
                self._combo.set_active(0)
        finally:
            self._combo.handler_unblock(self._combo_handler)

        self._on_sorgente_cambiata(self._combo)
        if trovate:
            self._set_status(t("log.discover_done", n=trovate))
        else:
            self._set_status(t("log.discover_none"))

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
        # Invalida thread precedenti e chiude subito il loro canale: aspettare
        # il timeout di recv() (3s) a ogni riavvio può esaurire i MaxSessions.
        self._gen += 1
        gen = self._gen
        canale_vecchio = self._canale
        self._canale = None
        if canale_vecchio is not None:
            with contextlib.suppress(Exception):
                canale_vecchio.close()

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
            if gen == self._gen:
                self._canale = channel
            else:
                with contextlib.suppress(Exception):
                    channel.close()
                return

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
                except (socket.timeout, TimeoutError):
                    # timeout di polling: controlla solo se siamo ancora validi
                    if gen != self._gen:
                        break
                except Exception as e:
                    # Un errore reale (socket rotto, canale chiuso) non deve
                    # far girare il loop a 100% CPU: segnala e termina.
                    if gen == self._gen:
                        GLib.idle_add(self._append, f"\n✖ {e}\n")
                    break
        except Exception as e:
            if gen == self._gen:
                GLib.idle_add(self._append, f"\n✖ {e}\n")
        finally:
            if self._canale is channel:
                self._canale = None
            if channel:
                with contextlib.suppress(Exception):
                    channel.close()

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
            except Exception as e:
                _get_log(__name__).debug("SSH connection close failed: %s", e)
            self._ssh = None

    def chiudi_processo(self):
        self._stop()
