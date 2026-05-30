"""
sysmon_widget.py — Monitor risorse sistema remoto per PCM (GTK3)

Mostra CPU, RAM, disco, rete e uptime via SSH (paramiko).
Aggiorna ogni 2 secondi. SparklineWidget disegna lo storico CPU con Cairo.
"""

import os
import re
import time
import threading
import collections

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False


# ---------------------------------------------------------------------------
# Comando remoto one-shot — produce output parsabile con separatori noti
# ---------------------------------------------------------------------------
_CMD = (
    "echo '---CPU'; cat /proc/stat | head -1; "
    "echo '---MEM'; cat /proc/meminfo | grep -E "
    "'^(MemTotal|MemFree|MemAvailable|Buffers|Cached):'; "
    "echo '---DISK'; df -k / | tail -1; "
    "echo '---UP'; uptime; "
    "echo '---NET'; cat /proc/net/dev | awk 'NR>2 && !/lo:/{print;exit}'"
)


def _parse(text: str) -> dict:
    d: dict = {}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("---"):
            section = line[3:]
            continue

        if section == "CPU" and line.startswith("cpu "):
            parts = line.split()
            try:
                vals = list(map(int, parts[1:8]))
                d["cpu_total"] = sum(vals)
                d["cpu_idle"]  = vals[3]
            except (ValueError, IndexError):
                pass

        elif section == "MEM":
            if line.startswith("MemTotal:"):
                d["mem_total"] = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                d["mem_avail"] = int(line.split()[1])

        elif section == "DISK":
            parts = line.split()
            if len(parts) >= 3:
                try:
                    d["disk_total"] = int(parts[1])
                    d["disk_used"]  = int(parts[2])
                except (ValueError, IndexError):
                    pass

        elif section == "UP":
            m = re.search(r"up\s+(.+?),\s+\d+\s+user", line)
            if not m:
                m = re.search(r"up\s+(.+?),", line)
            if m:
                d["uptime"] = m.group(1).strip()

        elif section == "NET":
            parts = line.split()
            if len(parts) >= 10:
                try:
                    d["net_iface"] = parts[0].rstrip(":")
                    d["net_rx"]    = int(parts[1])
                    d["net_tx"]    = int(parts[9])
                except (ValueError, IndexError):
                    pass
    return d


def _fmt(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.0f} {u}"
        n //= 1024
    return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# Sparkline — grafico a linea degli ultimi 60 campioni
# ---------------------------------------------------------------------------

class SparklineWidget(Gtk.DrawingArea):
    MAX = 60

    def __init__(self, r=0.2, g=0.6, b=1.0):
        super().__init__()
        self.set_size_request(-1, 52)
        self._data  = collections.deque(maxlen=self.MAX)
        self._color = (r, g, b)
        self.connect("draw", self._on_draw)

    def push(self, v: float):
        self._data.append(max(0.0, min(1.0, v)))
        self.queue_draw()

    def _on_draw(self, _widget, cr):
        alloc = self.get_allocation()
        w, h  = alloc.width, alloc.height
        cr.set_source_rgb(0.08, 0.08, 0.08)
        cr.paint()

        pts = list(self._data)
        if len(pts) < 2:
            return

        n   = self.MAX
        r, g, b = self._color

        # Area riempita
        cr.set_source_rgba(r, g, b, 0.25)
        cr.move_to(0, h)
        for i, v in enumerate(pts):
            cr.line_to(i * w / (n - 1), h - v * (h - 2))
        cr.line_to((len(pts) - 1) * w / (n - 1), h)
        cr.close_path()
        cr.fill()

        # Linea
        cr.set_source_rgb(r, g, b)
        cr.set_line_width(1.5)
        cr.move_to(0, h - pts[0] * (h - 2))
        for i, v in enumerate(pts[1:], 1):
            cr.line_to(i * w / (n - 1), h - v * (h - 2))
        cr.stroke()


# ---------------------------------------------------------------------------
# SysMonitorWidget
# ---------------------------------------------------------------------------

class SysMonitorWidget(Gtk.Box):
    _POLL_MS = 2000

    def __init__(self, profilo: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._profilo  = profilo
        self._ssh      = None
        self._attivo   = False
        self._prev     = {}
        self._timer_id = None

        self._init_ui()
        self.connect("destroy", lambda w: self._ferma())

        if PARAMIKO_OK:
            threading.Thread(target=self._connetti, daemon=True).start()
        else:
            self._set_status("❌ paramiko non installato")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        host = self._profilo.get("host", "?")

        hdr = Gtk.Label()
        hdr.set_markup(f"<b>Monitor: {host}</b>")
        hdr.set_xalign(0.0)
        hdr.set_margin_start(8)
        hdr.set_margin_top(6)
        hdr.set_margin_bottom(4)
        self.pack_start(hdr, False, False, 0)

        self.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                        False, False, 0)

        grid = Gtk.Grid(column_spacing=10, row_spacing=5,
                        margin_start=8, margin_end=8,
                        margin_top=6, margin_bottom=4)
        self.pack_start(grid, False, False, 0)
        row = 0

        def lbl(txt):
            l = Gtk.Label(label=txt, xalign=1.0)
            l.set_width_chars(9)
            return l

        # CPU
        grid.attach(lbl("CPU:"), 0, row, 1, 1)
        self._cpu_bar = Gtk.ProgressBar()
        self._cpu_bar.set_hexpand(True)
        self._cpu_bar.set_show_text(True)
        grid.attach(self._cpu_bar, 1, row, 1, 1)
        row += 1

        self._spark = SparklineWidget()
        self._spark.set_hexpand(True)
        self._spark.set_margin_bottom(4)
        grid.attach(self._spark, 1, row, 1, 1)
        row += 1

        # RAM
        grid.attach(lbl("RAM:"), 0, row, 1, 1)
        self._ram_bar = Gtk.ProgressBar()
        self._ram_bar.set_hexpand(True)
        self._ram_bar.set_show_text(True)
        grid.attach(self._ram_bar, 1, row, 1, 1)
        row += 1

        # Disco
        grid.attach(lbl("Disco /:"), 0, row, 1, 1)
        self._disk_bar = Gtk.ProgressBar()
        self._disk_bar.set_hexpand(True)
        self._disk_bar.set_show_text(True)
        grid.attach(self._disk_bar, 1, row, 1, 1)
        row += 1

        # Rete
        grid.attach(lbl("Rete:"), 0, row, 1, 1)
        self._net_lbl = Gtk.Label(label="—", xalign=0.0)
        grid.attach(self._net_lbl, 1, row, 1, 1)
        row += 1

        # Uptime
        grid.attach(lbl("Uptime:"), 0, row, 1, 1)
        self._up_lbl = Gtk.Label(label="—", xalign=0.0)
        grid.attach(self._up_lbl, 1, row, 1, 1)
        row += 1

        self.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                        False, False, 0)

        self._status_lbl = Gtk.Label(label="Connessione in corso…")
        self._status_lbl.set_xalign(0.0)
        self._status_lbl.set_margin_start(8)
        self._status_lbl.set_margin_top(3)
        self._status_lbl.set_margin_bottom(3)
        self.pack_start(self._status_lbl, False, False, 0)

    # ------------------------------------------------------------------
    # Connessione SSH
    # ------------------------------------------------------------------

    def _connetti(self):
        try:
            host = self._profilo.get("host", "")
            port = int(self._profilo.get("port", 22))
            user = self._profilo.get("user", "")
            pwd  = self._profilo.get("password", "")
            pkey = self._profilo.get("private_key", "")

            self._ssh = paramiko.SSHClient()
            self._ssh.load_system_host_keys()
            self._ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

            kw = {"hostname": host, "port": port, "username": user, "timeout": 10}
            if pkey and os.path.isfile(pkey):
                kw["key_filename"] = pkey
            elif pwd:
                kw["password"] = pwd

            self._ssh.connect(**kw)
            self._attivo = True
            GLib.idle_add(self._set_status, f"✔ Connesso a {host}")
            GLib.idle_add(self._poll)
        except paramiko.ssh_exception.SSHException as e:
            msg = str(e)
            if "not found in known_hosts" in msg or "Unknown server" in msg.lower():
                host = self._profilo.get("host", "")
                GLib.idle_add(self._set_status,
                              f"Chiave host di '{host}' non in known_hosts.\n"
                              f"ssh-keyscan -H {host} >> ~/.ssh/known_hosts")
            else:
                GLib.idle_add(self._set_status, f"✖ {e}")
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ {e}")

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _poll(self) -> bool:
        if not self._attivo or not self._ssh:
            return False
        # Avvia fetch solo se il precedente è completato
        if not getattr(self, "_fetch_running", False):
            self._fetch_running = True
            threading.Thread(target=self._fetch, daemon=True).start()
        self._timer_id = GLib.timeout_add(self._POLL_MS, self._poll)
        return False

    def _fetch(self):
        try:
            _, stdout, _ = self._ssh.exec_command(_CMD, timeout=5)
            out  = stdout.read().decode("utf-8", errors="replace")
            dati = _parse(out)
            GLib.idle_add(self._aggiorna, dati)
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ {e}")
        finally:
            self._fetch_running = False

    # ------------------------------------------------------------------
    # Aggiornamento UI
    # ------------------------------------------------------------------

    def _aggiorna(self, d: dict):
        now = time.monotonic()

        # CPU — delta tra due letture
        if "cpu_total" in d and "cpu_idle" in d:
            pt = self._prev.get("cpu_total", 0)
            pi = self._prev.get("cpu_idle",  0)
            dt = d["cpu_total"] - pt
            di = d["cpu_idle"]  - pi
            pct = max(0.0, min(1.0, 1.0 - di / dt)) if dt > 0 else 0.0
            self._cpu_bar.set_fraction(pct)
            self._cpu_bar.set_text(f"{pct*100:.1f}%")
            self._spark.push(pct)
            self._prev["cpu_total"] = d["cpu_total"]
            self._prev["cpu_idle"]  = d["cpu_idle"]

        # RAM
        if "mem_total" in d and "mem_avail" in d:
            tot  = d["mem_total"]
            used = tot - d["mem_avail"]
            frac = used / tot if tot > 0 else 0.0
            self._ram_bar.set_fraction(min(frac, 1.0))
            self._ram_bar.set_text(f"{_fmt(used * 1024)} / {_fmt(tot * 1024)}")

        # Disco
        if "disk_total" in d and "disk_used" in d:
            tot  = d["disk_total"]
            used = d["disk_used"]
            frac = used / tot if tot > 0 else 0.0
            self._disk_bar.set_fraction(min(frac, 1.0))
            self._disk_bar.set_text(f"{_fmt(used * 1024)} / {_fmt(tot * 1024)}")

        # Rete
        if "net_rx" in d and "net_tx" in d:
            iface  = d.get("net_iface", "eth0")
            prev_t = self._prev.get("net_time", now)
            pr, pt = self._prev.get("net_rx", d["net_rx"]), self._prev.get("net_tx", d["net_tx"])
            dt = now - prev_t
            if dt > 0:
                rx_s = (d["net_rx"] - pr) / dt
                tx_s = (d["net_tx"] - pt) / dt
                self._net_lbl.set_text(
                    f"{iface}  ↓ {_fmt(int(rx_s))}/s  ↑ {_fmt(int(tx_s))}/s"
                )
            self._prev.update({"net_time": now, "net_rx": d["net_rx"], "net_tx": d["net_tx"]})

        # Uptime
        if "uptime" in d:
            self._up_lbl.set_text(d["uptime"])

        self._set_status(f"Aggiornato {time.strftime('%H:%M:%S')}")

    def _set_status(self, msg: str):
        self._status_lbl.set_text(msg)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _ferma(self):
        self._attivo = False
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass

    def chiudi_processo(self):
        self._ferma()
