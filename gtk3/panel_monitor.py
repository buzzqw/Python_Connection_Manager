"""
panel_monitor.py — Pannello laterale destro per PCM (GTK3)

Due tab: Monitor (CPU, RAM, Processi, Disco, Rete) e Log (journalctl/tail).
Usa UN SOLO canale SSH persistente con loop remoto — nessun exec_command ripetuto.
Aggiornamento ogni 2 secondi (< 1 Hz, mai più di 1 al secondo).
"""

import base64
import os
import re
import threading
import time
import collections

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False

from log_viewer import LogViewerWidget
from translations import t


# ---------------------------------------------------------------------------
# Loop remoto — UN solo canale, il server invia dati ogni SLEEP secondi
# ---------------------------------------------------------------------------

_SLEEP = 2   # secondi tra un tick e l'altro

# Singolo comando su una riga — nessuna virgoletta singola nei marker,
# exec_command() lo invia direttamente a /bin/sh -c via execl() (no shell wrapping).
# NOTA: NON avvolgere in sh -c '...' — le virgolette nei grep/awk romperebbero il parsing.
_REMOTE_LOOP = (
    "while true; do "
    "echo ===TICK; "
    "echo ===CPU; cat /proc/stat | head -1; "
    "echo ===MEM; cat /proc/meminfo | grep -E '^(MemTotal|MemFree|MemAvailable):'; "
    "echo ===PROCS; ps -eo pid,pcpu,pmem,comm --sort=-%cpu --no-headers 2>/dev/null | head -12; "
    "echo ===DISK; df -h -x tmpfs -x devtmpfs -x squashfs 2>/dev/null | tail -n +2; "
    "echo ===NET; cat /proc/net/dev | tail -n +3 | grep -v ' lo:'; "
    "echo ===END; "
    f"sleep {_SLEEP}; "
    "done"
)

# ---------------------------------------------------------------------------
# Loop Windows — PowerShell via OpenSSH.
# Output formattato per riusare i parser esistenti (stessi marker ===SECTION).
# CPU: singolo float percentuale (diverso da /proc/stat — gestito in _dispatch).
# MEM: "MemTotal: N kB" / "MemAvailable: N kB" — identico a /proc/meminfo.
# PROCS: "pid cpu_s mem_mb name" (cpu in secondi cumulativi, mem in MB).
# DISK: "root totG usedG freeG pct% root" — compatibile con il parser df.
# NET:  "iface: rx 0 0 0 0 0 0 0 tx 0 0 0 0 0 0" — compatibile con /proc/net/dev.
# ---------------------------------------------------------------------------

_PS_LOOP = """\
while ($true) {
  Write-Host '===TICK'
  Write-Host '===CPU'
  Write-Host ([string][math]::Round((Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average, 1))
  Write-Host '===MEM'
  $os = Get-CimInstance Win32_OperatingSystem
  Write-Host "MemTotal: $($os.TotalVisibleMemorySize) kB"
  Write-Host "MemAvailable: $($os.FreePhysicalMemory) kB"
  Write-Host '===PROCS'
  Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 12 | ForEach-Object {
    $c = if ($_.CPU) { [math]::Round($_.CPU, 1) } else { 0.0 }
    $m = [math]::Round($_.WorkingSet64 / 1MB, 1)
    Write-Host "$($_.Id) $c $m $($_.ProcessName)"
  }
  Write-Host '===DISK'
  Get-PSDrive -PSProvider FileSystem | Where-Object { $null -ne $_.Used } | ForEach-Object {
    $tot = $_.Used + $_.Free
    if ($tot -gt 0) {
      $pct = [math]::Round(100 * $_.Used / $tot)
      $root = $_.Root.TrimEnd('\\')
      Write-Host "$root $([math]::Round($tot/1GB,1))G $([math]::Round($_.Used/1GB,1))G $([math]::Round($_.Free/1GB,1))G $($pct)% $root"
    }
  }
  Write-Host '===NET'
  Get-NetAdapterStatistics | ForEach-Object {
    $n = $_.Name -replace ' ','_'
    Write-Host "$($n): $($_.ReceivedBytes) 0 0 0 0 0 0 0 $($_.SentBytes) 0 0 0 0 0 0"
  }
  Write-Host '===END'
  Start-Sleep -Seconds 2
}
"""

# Codificato in UTF-16LE + base64 per passarlo senza problemi di escaping a cmd.exe
_REMOTE_LOOP_WIN = (
    "powershell -NonInteractive -NoProfile -EncodedCommand "
    + base64.b64encode(_PS_LOOP.encode("utf-16-le")).decode("ascii")
)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _fmt(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


# ---------------------------------------------------------------------------
# Sparkline (Cairo)
# ---------------------------------------------------------------------------

class _Spark(Gtk.DrawingArea):
    MAX = 60

    def __init__(self, r=0.2, g=0.6, b=1.0, height=36):
        super().__init__()
        self.set_size_request(-1, height)
        self._data  = collections.deque(maxlen=self.MAX)
        self._color = (r, g, b)
        self.connect("draw", self._draw)

    def push(self, v: float):
        self._data.append(max(0.0, min(1.0, v)))
        self.queue_draw()

    def _draw(self, _w, cr):
        a = self.get_allocation()
        w, h = a.width, a.height
        cr.set_source_rgb(0.08, 0.08, 0.08)
        cr.paint()
        pts = list(self._data)
        if len(pts) < 2:
            return
        n = self.MAX
        r, g, b = self._color
        cr.set_source_rgba(r, g, b, 0.25)
        cr.move_to(0, h)
        for i, v in enumerate(pts):
            cr.line_to(i * w / (n - 1), h - v * (h - 2))
        cr.line_to((len(pts) - 1) * w / (n - 1), h)
        cr.close_path()
        cr.fill()
        cr.set_source_rgb(r, g, b)
        cr.set_line_width(1.5)
        cr.move_to(0, h - pts[0] * (h - 2))
        for i, v in enumerate(pts[1:], 1):
            cr.line_to(i * w / (n - 1), h - v * (h - 2))
        cr.stroke()


# ---------------------------------------------------------------------------
# Sezione: CPU + RAM
# ---------------------------------------------------------------------------

class _SysOverview(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_margin_start(8); self.set_margin_end(8)
        self.set_margin_top(6);   self.set_margin_bottom(4)

        hdr = Gtk.Label()
        hdr.set_markup(f"<b>{t('mon.sys_overview')}</b>")
        hdr.set_xalign(0.0)
        self.pack_start(hdr, False, False, 0)

        for attr, label in (("_cpu_bar", "CPU"), ("_ram_bar", "Memory")):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            lbl = Gtk.Label(label=label, xalign=0.0)
            lbl.set_width_chars(7)
            row.pack_start(lbl, False, False, 0)
            bar = Gtk.ProgressBar()
            bar.set_hexpand(True)
            bar.set_show_text(True)
            bar.set_fraction(0.0)
            row.pack_start(bar, True, True, 0)
            setattr(self, attr, bar)
            self.pack_start(row, False, False, 0)

        self._prev_total = 0
        self._prev_idle  = 0
        self._mem_total  = 0

    def aggiorna_win_cpu(self, pct: float):
        """Aggiorna CPU con percentuale diretta (Windows — non usa delta /proc/stat)."""
        frac = max(0.0, min(1.0, pct / 100.0))
        self._cpu_bar.set_fraction(frac)
        self._cpu_bar.set_text(f"{pct:.1f}%")

    def aggiorna(self, cpu_lines: list[str], mem_lines: list[str]):
        # CPU
        for line in cpu_lines:
            if line.startswith("cpu "):
                parts = line.split()
                try:
                    vals  = list(map(int, parts[1:8]))
                    total = sum(vals)
                    idle  = vals[3]
                    dt = total - self._prev_total
                    di = idle  - self._prev_idle
                    pct = max(0.0, min(1.0, 1.0 - di / dt)) if dt > 0 else 0.0
                    self._cpu_bar.set_fraction(pct)
                    self._cpu_bar.set_text(f"{pct*100:.1f}%")
                    self._prev_total = total
                    self._prev_idle  = idle
                except (ValueError, ZeroDivisionError):
                    pass
        # RAM
        mem: dict[str, int] = {}
        for line in mem_lines:
            if ":" in line:
                k, v = line.split(":", 1)
                try:
                    mem[k.strip()] = int(v.strip().split()[0])
                except ValueError:
                    pass
        if "MemTotal" in mem and "MemAvailable" in mem:
            tot  = mem["MemTotal"]
            used = tot - mem["MemAvailable"]
            frac = used / tot if tot > 0 else 0.0
            self._ram_bar.set_fraction(min(frac, 1.0))
            self._ram_bar.set_text(f"{used // 1024} MB / {tot // 1024} MB")


# ---------------------------------------------------------------------------
# Sezione: Processi
# ---------------------------------------------------------------------------

class _ProcessSection(Gtk.Box):
    # Store: PID(int), CPU(float), MEM(float), Command(str)
    _C_PID, _C_CPU, _C_MEM, _C_CMD = range(4)

    def __init__(self, kill_cb):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.set_margin_start(8); self.set_margin_end(8)
        self.set_margin_bottom(4)
        self._kill_cb = kill_cb

        hdr = Gtk.Label()
        hdr.set_markup(f"<b>{t('mon.running_procs')}</b>")
        hdr.set_xalign(0.0)
        hdr.set_margin_top(6)
        self.pack_start(hdr, False, False, 0)

        # Store con tipi numerici per ordinamento corretto
        self._store  = Gtk.ListStore(int, float, float, str)
        self._sorted = Gtk.TreeModelSort(model=self._store)
        tv = Gtk.TreeView(model=self._sorted)
        tv.set_headers_visible(True)
        tv.set_headers_clickable(True)

        # Colonna PID
        cell_pid = Gtk.CellRendererText()
        col_pid  = Gtk.TreeViewColumn("PID", cell_pid)
        col_pid.set_cell_data_func(cell_pid,
            lambda c, r, m, i, _: r.set_property("text", str(m.get_value(i, self._C_PID))))
        col_pid.set_sort_column_id(self._C_PID)
        col_pid.set_min_width(52)
        tv.append_column(col_pid)

        # Colonna CPU%
        cell_cpu = Gtk.CellRendererText()
        col_cpu  = Gtk.TreeViewColumn("CPU%", cell_cpu)
        col_cpu.set_cell_data_func(cell_cpu,
            lambda c, r, m, i, _: r.set_property("text", f"{m.get_value(i, self._C_CPU):.1f}%"))
        col_cpu.set_sort_column_id(self._C_CPU)
        col_cpu.set_min_width(46)
        tv.append_column(col_cpu)
        self._sorted.set_sort_column_id(self._C_CPU, Gtk.SortType.DESCENDING)

        # Colonna MEM%
        cell_mem = Gtk.CellRendererText()
        col_mem  = Gtk.TreeViewColumn("Mem%", cell_mem)
        col_mem.set_cell_data_func(cell_mem,
            lambda c, r, m, i, _: r.set_property("text", f"{m.get_value(i, self._C_MEM):.1f}%"))
        col_mem.set_sort_column_id(self._C_MEM)
        col_mem.set_min_width(46)
        tv.append_column(col_mem)

        # Colonna Command
        cell_cmd = Gtk.CellRendererText()
        cell_cmd.set_property("ellipsize", Pango.EllipsizeMode.END)
        col_cmd  = Gtk.TreeViewColumn("Command", cell_cmd, text=self._C_CMD)
        col_cmd.set_sort_column_id(self._C_CMD)
        col_cmd.set_expand(True)
        tv.append_column(col_cmd)

        # Colonna kill
        btn_cell = Gtk.CellRendererPixbuf()
        btn_cell.set_property("icon-name", "window-close-symbolic")
        col_kill = Gtk.TreeViewColumn("", btn_cell)
        col_kill.set_min_width(22)
        tv.append_column(col_kill)
        self._col_kill = col_kill

        tv.connect("button-press-event", self._on_click)
        tv.set_size_request(-1, 100)
        self.pack_start(tv, False, False, 0)
        self._tv = tv

    def aggiorna(self, lines: list[str]):
        self._store.clear()
        for line in lines:
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            try:
                pid = int(parts[0].strip())
                cpu = float(parts[1].strip())
                mem = float(parts[2].strip())
            except ValueError:
                continue
            cmd = parts[3].strip()
            self._store.append([pid, cpu, mem, cmd])

    def _on_click(self, tv, event):
        if event.button != 1:
            return False
        info = tv.get_path_at_pos(int(event.x), int(event.y))
        if not info:
            return False
        path, col, _, _ = info
        if col is self._col_kill:
            it  = self._sorted.get_iter(path)
            pid = self._sorted.get_value(it, self._C_PID)
            self._kill_cb(str(pid))
        return False


# ---------------------------------------------------------------------------
# Sezione: Disco — card per partizione (stile figma)
# ---------------------------------------------------------------------------

class _DiskSection(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_margin_start(8); self.set_margin_end(8)
        self.set_margin_bottom(4)

        hdr = Gtk.Label()
        hdr.set_markup(f"<b>{t('mon.disk_usage')}</b>")
        hdr.set_xalign(0.0)
        hdr.set_margin_top(6)
        hdr.set_margin_bottom(4)
        self.pack_start(hdr, False, False, 0)

        # Contenitore dinamico delle righe partizione
        self._rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.pack_start(self._rows_box, False, False, 0)

    def aggiorna(self, lines: list[str]):
        # Rimuovi righe vecchie
        for child in list(self._rows_box.get_children()):
            self._rows_box.remove(child)

        for line in lines:
            # df output: Filesystem  Size  Used  Avail  Use%  Mounted-on
            parts = line.split()
            if len(parts) < 6:
                continue
            mount   = parts[-1]
            use_pct = parts[-2]
            avail   = parts[-3]
            used    = parts[-4]
            size    = parts[-5]
            device  = parts[0]
            if not use_pct.endswith("%"):
                continue
            try:
                pct = int(use_pct.rstrip("%")) / 100.0
            except ValueError:
                continue

            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)

            # Riga unica: mount point  device (grigio)  |  used/size   avail free
            top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

            lbl_mount = Gtk.Label(xalign=0.0)
            lbl_mount.set_markup(f"<b>{mount}</b>")
            lbl_mount.set_ellipsize(Pango.EllipsizeMode.END)

            lbl_dev = Gtk.Label(label=device, xalign=0.0)
            lbl_dev.get_style_context().add_class("dim-label")
            lbl_dev.set_ellipsize(Pango.EllipsizeMode.END)
            lbl_dev.set_hexpand(True)

            lbl_info = Gtk.Label(xalign=1.0)
            lbl_info.set_markup(
                f"{used}/{size} <span foreground='gray'>{avail} free</span>"
            )

            top.pack_start(lbl_mount, False, False, 0)
            top.pack_start(lbl_dev,   True,  True,  0)
            top.pack_start(lbl_info,  False, False, 0)
            row.pack_start(top, False, False, 0)

            # Barra progresso compatta
            bar = Gtk.ProgressBar()
            bar.set_fraction(min(pct, 1.0))
            bar.set_hexpand(True)
            bar.set_size_request(-1, 6)  # barra sottile
            ctx = bar.get_style_context()
            ctx.remove_class("bar-crit"); ctx.remove_class("bar-warn")
            if pct >= 0.9:    ctx.add_class("bar-crit")
            elif pct >= 0.75: ctx.add_class("bar-warn")
            row.pack_start(bar, False, False, 0)

            self._rows_box.pack_start(row, False, False, 0)

        self._rows_box.show_all()


# ---------------------------------------------------------------------------
# Sparkline doppia (download blu + upload rosso)
# ---------------------------------------------------------------------------

class _DualSpark(Gtk.DrawingArea):
    MAX = 60

    def __init__(self, height=60):
        super().__init__()
        self.set_size_request(-1, height)
        self._rx   = collections.deque(maxlen=self.MAX)  # normalizzati 0-1
        self._tx   = collections.deque(maxlen=self.MAX)
        self.connect("draw", self._draw)

    def push(self, rx: float, tx: float):
        self._rx.append(max(0.0, min(1.0, rx)))
        self._tx.append(max(0.0, min(1.0, tx)))
        self.queue_draw()

    def _draw_line(self, cr, data, r, g, b, w, h):
        pts = list(data)
        if len(pts) < 2:
            return
        n = self.MAX
        cr.set_source_rgb(r, g, b)
        cr.set_line_width(1.5)
        cr.move_to(0, h - pts[0] * (h - 2))
        for i, v in enumerate(pts[1:], 1):
            cr.line_to(i * w / (n - 1), h - v * (h - 2))
        cr.stroke()

    def _draw(self, _w, cr):
        a = self.get_allocation()
        w, h = a.width, a.height
        cr.set_source_rgb(0.08, 0.08, 0.08)
        cr.paint()
        # Linea zero (grigia)
        cr.set_source_rgba(0.3, 0.3, 0.3, 0.5)
        cr.set_line_width(0.5)
        cr.move_to(0, h // 2)
        cr.line_to(w, h // 2)
        cr.stroke()
        self._draw_line(cr, self._rx, 0.2, 0.6, 1.0, w, h)   # blu = download
        self._draw_line(cr, self._tx, 1.0, 0.3, 0.1, w, h)   # rosso = upload


# ---------------------------------------------------------------------------
# Sezione: Rete — speeds + selettore interfaccia + dual sparkline
# ---------------------------------------------------------------------------

class _NetSection(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.set_margin_start(8); self.set_margin_end(8)
        self.set_margin_bottom(4)

        # Header + combo interfaccia
        hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hdr = Gtk.Label()
        hdr.set_markup(f"<b>{t('mon.network_usage')}</b>")
        hdr.set_xalign(0.0)
        hdr.set_hexpand(True)
        hdr.set_margin_top(6)
        hdr_box.pack_start(hdr, True, True, 0)

        self._iface_combo = Gtk.ComboBoxText()
        self._iface_combo.set_tooltip_text("Scheda di rete")
        self._iface_combo.connect("changed", lambda c: self.queue_draw())
        hdr_box.pack_start(self._iface_combo, False, False, 0)
        self.pack_start(hdr_box, False, False, 0)

        # Velocità download/upload
        speeds = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        speeds.set_margin_top(4)

        # Download
        dl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        dl_hdr = Gtk.Label(label="Download", xalign=0.0)
        dl_hdr.get_style_context().add_class("dim-label")
        self._rx_lbl = Gtk.Label(xalign=0.0)
        self._rx_lbl.set_markup("<b>— —</b>")
        dl_box.pack_start(dl_hdr, False, False, 0)
        dl_box.pack_start(self._rx_lbl, False, False, 0)
        speeds.pack_start(dl_box, False, False, 0)

        # Upload
        ul_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        ul_hdr = Gtk.Label(label="Upload", xalign=0.0)
        ul_hdr.get_style_context().add_class("dim-label")
        self._tx_lbl = Gtk.Label(xalign=0.0)
        self._tx_lbl.set_markup("<b>— —</b>")
        ul_box.pack_start(ul_hdr, False, False, 0)
        ul_box.pack_start(self._tx_lbl, False, False, 0)
        speeds.pack_start(ul_box, False, False, 0)
        self.pack_start(speeds, False, False, 0)

        # Etichetta storico
        hist_lbl = Gtk.Label(label="Usage history", xalign=0.0)
        hist_lbl.get_style_context().add_class("dim-label")
        hist_lbl.set_margin_top(4)
        self.pack_start(hist_lbl, False, False, 0)

        self._spark = _DualSpark(height=60)
        self._spark.set_hexpand(True)
        self.pack_start(self._spark, False, False, 0)

        self._prev: dict[str, tuple[int, int]] = {}
        self._max_speed = 1.0
        self._known_ifaces: list[str] = []

    def aggiorna(self, lines: list[str], dt: float):
        if dt <= 0:
            return

        # Aggiorna lista interfacce nel combo (una sola volta per nuove iface)
        new_ifaces = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 10:
                iface = parts[0].rstrip(":")
                if iface not in self._known_ifaces:
                    new_ifaces.append(iface)
                    self._known_ifaces.append(iface)
                    self._iface_combo.append_text(iface)
        if new_ifaces and self._iface_combo.get_active() < 0:
            self._iface_combo.set_active(0)

        # Interfaccia selezionata
        active = self._iface_combo.get_active_text() or ""

        for line in lines:
            parts = line.split()
            if len(parts) < 10:
                continue
            iface = parts[0].rstrip(":")
            try:
                rx = int(parts[1])
                tx = int(parts[9])
            except (ValueError, IndexError):
                continue
            pr = self._prev.get(iface)
            if pr and iface == active:
                rx_s = max(0.0, (rx - pr[0]) / dt)
                tx_s = max(0.0, (tx - pr[1]) / dt)
                self._max_speed = max(self._max_speed, rx_s, tx_s, 1.0)
                self._rx_lbl.set_markup(f"<b>{_fmt(rx_s)}/s</b>")
                self._tx_lbl.set_markup(f"<b>{_fmt(tx_s)}/s</b>")
                self._spark.push(rx_s / self._max_speed,
                                  tx_s / self._max_speed)
            self._prev[iface] = (rx, tx)


# ---------------------------------------------------------------------------
# InfoPanelWidget — contenitore principale
# ---------------------------------------------------------------------------

class InfoPanelWidget(Gtk.Box):
    WIDTH = 240  # larghezza minima — l'utente può allargarla con il Paned

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_size_request(self.WIDTH, -1)
        self.set_no_show_all(True)

        self._profilo    = None
        self._ssh        = None
        self._channel    = None
        self._attivo     = False
        self._is_windows = False
        self._log_widget: LogViewerWidget | None = None
        self._last_tick  = time.monotonic()

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._nb = Gtk.Notebook()
        self._nb.set_tab_pos(Gtk.PositionType.TOP)
        self.pack_start(self._nb, True, True, 0)

        # ---------- Tab Monitor ----------
        self._sys   = _SysOverview()
        self._procs = _ProcessSection(self._on_kill)
        self._disk  = _DiskSection()
        self._net   = _NetSection()

        mon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        def _sep():
            return Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        mon_box.pack_start(self._sys,   False, False, 0)
        mon_box.pack_start(_sep(),      False, False, 0)
        mon_box.pack_start(self._procs, False, False, 0)
        mon_box.pack_start(_sep(),      False, False, 0)
        mon_box.pack_start(self._disk,  False, False, 0)
        mon_box.pack_start(_sep(),      False, False, 0)
        mon_box.pack_start(self._net,   False, False, 0)

        mon_scroll = Gtk.ScrolledWindow()
        mon_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        mon_scroll.add(mon_box)
        self._nb.append_page(mon_scroll, Gtk.Label(label=t("mon.tab_monitor")))

        # ---------- Tab Log (placeholder) ----------
        self._log_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        no_sess = Gtk.Label(label=t("mon.no_session"))
        no_sess.set_valign(Gtk.Align.CENTER)
        no_sess.set_vexpand(True)
        self._log_page.pack_start(no_sess, True, True, 0)
        self._nb.append_page(self._log_page, Gtk.Label(label=t("mon.tab_logs")))

        # Status bar
        self._status = Gtk.Label(label="")
        self._status.set_xalign(0.0)
        self._status.set_margin_start(8)
        self._status.set_margin_top(2)
        self._status.set_margin_bottom(2)
        self.pack_start(self._status, False, False, 0)

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def aggiorna_per_sessione(self, profilo: dict):
        p = profilo
        show_sys   = p.get("panel_cpu_mem",   False)
        show_procs = p.get("panel_processes", False)
        show_disk  = p.get("panel_disk",      False)
        show_net   = p.get("panel_network",   False)

        any_monitor = any([show_sys, show_procs, show_disk, show_net])
        if not any_monitor:
            # Nessuna sezione monitor abilitata → pannello nascosto
            self.nascondi()
            return

        # Se stessa sessione e già attivo, aggiorna solo visibilità sezioni
        if profilo is self._profilo and self._attivo:
            self._sys.set_visible(show_sys)
            self._procs.set_visible(show_procs)
            self._disk.set_visible(show_disk)
            self._net.set_visible(show_net)
            return

        self._ferma()
        self._profilo = profilo

        self._sys.set_visible(show_sys)
        self._procs.set_visible(show_procs)
        self._disk.set_visible(show_disk)
        self._net.set_visible(show_net)

        # Il LogViewerWidget viene creato SOLO da _crea_log_widget_con_ssh,
        # chiamato da _connetti() DOPO che la SSH è stabilita.
        # Non creare il widget qui: evita race condition con thread _connetti() orfani.

        self.show()

        if any_monitor and PARAMIKO_OK:
            threading.Thread(target=self._connetti, daemon=True).start()

    def nascondi(self):
        self._ferma()
        self.hide()

    # ------------------------------------------------------------------
    # Tab Log — creato solo dopo che SSH monitor è connessa
    # ------------------------------------------------------------------

    def _crea_log_widget_con_ssh(self, profilo: dict, ssh):
        """Crea (o ricrea) il LogViewerWidget riusando la SSH del monitor."""
        if self._profilo is not profilo:
            return  # profilo cambiato nel frattempo
        if self._log_widget is not None:
            return  # già presente
        widget = LogViewerWidget(profilo, existing_ssh=ssh)
        self._installa_log_widget(widget)

    def _installa_log_widget(self, widget):
        widget.show_all()
        self._log_widget = widget
        idx = self._nb.page_num(self._log_page)
        if idx >= 0:
            self._nb.remove_page(idx)
        self._nb.append_page(widget, Gtk.Label(label=t("mon.tab_logs")))
        self._nb.show_all()

    def _rimuovi_log(self):
        if self._log_widget:
            try:
                self._log_widget.chiudi_processo()
            except Exception:
                pass
            idx = self._nb.page_num(self._log_widget)
            if idx >= 0:
                self._nb.remove_page(idx)
            self._nb.append_page(self._log_page, Gtk.Label(label=t("mon.tab_logs")))
            self._nb.show_all()
            self._log_widget = None

    # ------------------------------------------------------------------
    # Kill processo
    # ------------------------------------------------------------------

    def _on_kill(self, pid: str):
        if not self._ssh:
            return
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(), modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=t("mon.kill_confirm").format(pid=pid)
        )
        if dlg.run() == Gtk.ResponseType.YES:
            if self._is_windows:
                cmd = f"taskkill /PID {pid} /F"
            else:
                cmd = f"kill -15 {pid} 2>/dev/null || kill -9 {pid}"
            threading.Thread(
                target=lambda: self._ssh.exec_command(cmd),
                daemon=True
            ).start()
        dlg.destroy()

    # ------------------------------------------------------------------
    # Connessione SSH + loop persistente
    # ------------------------------------------------------------------

    def _connetti(self):
        # Salva riferimento al profilo corrente — se cambia mentre connetttiamo, abbandoniamo
        p = self._profilo
        if p is None:
            return
        try:
            proto = p.get("protocol", "ssh")
            host  = p.get("host", "")
            # VNC e RDP usano mon_ssh_port (OpenSSH sul loro host), non la porta di sessione
            if proto in ("rdp", "vnc"):
                port = int(p.get("mon_ssh_port", 22))
            else:
                port = int(p.get("port", 22))
            user = p.get("user", "")
            pwd  = p.get("password", "")
            pkey = p.get("private_key", "")

            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

            kw = {"hostname": host, "port": port, "username": user, "timeout": 10}
            if pkey and os.path.isfile(pkey):
                kw["key_filename"] = pkey
            elif pwd:
                kw["password"] = pwd

            ssh.connect(**kw)

            # Se nel frattempo il profilo è cambiato (tab switch rapido), abbandona
            if self._profilo is not p:
                ssh.close()
                return

            self._ssh        = ssh
            self._attivo     = True
            self._is_windows = (proto == "rdp")
            GLib.idle_add(self._set_status, f"✔ {host}")

            # Apri UN SOLO canale persistente — exec_command invia il loop direttamente
            # a /bin/sh via execl(). NON usare sh -c '...' (le virgolette romperebbero tutto).
            # Su Windows (RDP) si usa il loop PowerShell codificato in base64.
            transport     = ssh.get_transport()
            self._channel = transport.open_session()
            loop = _REMOTE_LOOP_WIN if self._is_windows else _REMOTE_LOOP
            self._channel.exec_command(loop)

            threading.Thread(target=self._leggi_loop, args=(p,), daemon=True).start()

            # Log viewer: solo su Linux (journalctl/tail non disponibili su Windows)
            if not self._is_windows:
                # Crea LogViewerWidget condividendo questa connessione SSH (nessun
                # TCP aggiuntivo, nessun problema di known_hosts)
                GLib.idle_add(self._crea_log_widget_con_ssh, p, ssh)

        except paramiko.ssh_exception.SSHException as e:
            msg = str(e)
            if "not found in known_hosts" in msg or "Unknown server" in msg.lower():
                GLib.idle_add(self._set_status,
                              f"Chiave di {p.get('host','?')} non in known_hosts")
            else:
                GLib.idle_add(self._set_status, f"✖ {e}")
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ {e}")

    # ------------------------------------------------------------------
    # Lettura output del loop
    # ------------------------------------------------------------------

    def _leggi_loop(self, profilo_at_start):
        """Thread: legge lo stdout del loop remoto e dispatcha i tick all'UI."""
        buf      = ""
        sections: dict[str, list[str]] = {}
        cur      = None

        while self._attivo and self._profilo is profilo_at_start:
            try:
                self._channel.settimeout(5.0)
                data = self._channel.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8", errors="replace")
                lines = buf.split("\n")
                buf = lines[-1]

                for raw in lines[:-1]:
                    line = raw.rstrip()
                    if line == "===TICK":
                        sections = {}
                        cur = None
                        self._last_tick = time.monotonic()
                    elif line == "===CPU":
                        cur = "cpu";   sections[cur] = []
                    elif line == "===MEM":
                        cur = "mem";   sections[cur] = []
                    elif line == "===PROCS":
                        cur = "procs"; sections[cur] = []
                    elif line == "===DISK":
                        cur = "disk";  sections[cur] = []
                    elif line == "===NET":
                        cur = "net";   sections[cur] = []
                    elif line == "===END":
                        now = time.monotonic()
                        dt  = now - self._last_tick
                        GLib.idle_add(self._dispatch, dict(sections), dt)
                        sections = {}
                        cur = None
                    elif cur is not None and line:
                        sections[cur].append(line)

            except Exception:
                if not self._attivo:
                    break
                time.sleep(1)

    def _dispatch(self, sec: dict, dt: float):
        """Aggiorna le sezioni UI con i dati del tick. Chiamato sul thread GTK."""
        p = self._profilo
        if not p:
            return

        if p.get("panel_cpu_mem"):
            if self._is_windows:
                # CPU: singolo float percentuale diretto (non /proc/stat)
                cpu_lines = sec.get("cpu", [])
                if cpu_lines:
                    try:
                        self._sys.aggiorna_win_cpu(float(cpu_lines[0]))
                    except ValueError:
                        pass
                # RAM: stesso formato MemTotal/MemAvailable kB
                self._sys.aggiorna([], sec.get("mem", []))
            else:
                self._sys.aggiorna(sec.get("cpu", []), sec.get("mem", []))

        if p.get("panel_processes"):
            self._procs.aggiorna(sec.get("procs", []))

        if p.get("panel_disk"):
            self._disk.aggiorna(sec.get("disk", []))

        if p.get("panel_network"):
            self._net.aggiorna(sec.get("net", []), dt if dt > 0 else _SLEEP)

        self._set_status(f"✔ {time.strftime('%H:%M:%S')}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _ferma(self):
        self._attivo = False
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None
        self._rimuovi_log()
        self._profilo = None

    def _set_status(self, msg: str):
        self._status.set_text(msg)

    def chiudi_processo(self):
        self._ferma()
