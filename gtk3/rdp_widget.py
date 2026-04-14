"""
rdp_widget.py - Widget RDP embedded per PCM (GTK3)

Stessa strategia dell'originale (xdotool reparent), ma il container
è un Gtk.DrawingArea + Gtk.Socket per ospitare la finestra xfreerdp.

Nota: questa tecnica richiede XWayland quando si usa Wayland.
Per sessioni RDP external (finestra separata) funziona nativamente.

Dipendenze:
  xfreerdp o xfreerdp3, xdotool
"""

import os
import re
import signal
import subprocess
import shutil
import time
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GObject

from translations import t


def _freerdp_major_version(client: str) -> int:
    try:
        out = subprocess.check_output(
            [client, "--version"], stderr=subprocess.STDOUT,
            timeout=3, text=True
        )
        m = re.search(r"(\d+)\.\d+", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return 3 if "3" in client else 2


def _build_freerdp_cmd(profilo: dict) -> list[str]:
    """Costruisce la lista argv per xfreerdp/xfreerdp3."""
    client = profilo.get("rdp_client", "xfreerdp")
    host   = profilo.get("host", "")
    port   = profilo.get("port", "3389")
    user   = profilo.get("user", "")
    pwd    = profilo.get("password", "")
    domain = profilo.get("rdp_domain", "")
    clip   = profilo.get("redirect_clipboard", True)
    drives = profilo.get("redirect_drives", False)

    ver = _freerdp_major_version(client)

    if ver >= 3:
        cmd = [client, f"/v:{host}:{port}"]
        if user:   cmd += [f"/u:{user}"]
        if pwd:    cmd += [f"/p:{pwd}"]
        if domain: cmd += [f"/d:{domain}"]
        if clip:   cmd += ["/clipboard"]
        if drives: cmd += ["/drive:home,/home"]
        cmd += ["/dynamic-resolution", "/cert:ignore"]
    else:
        cmd = [client, f"/v:{host}", f"/port:{port}"]
        if user:   cmd += [f"/u:{user}"]
        if pwd:    cmd += [f"/p:{pwd}"]
        if domain: cmd += [f"/d:{domain}"]
        if clip:   cmd += ["+clipboard"]
        if drives: cmd += [f"/drive:home,{os.path.expanduser('~')}"]
        cmd += ["/dynamic-resolution", "/cert-ignore"]

    return cmd


class RdpEmbedWidget(Gtk.Box):
    """
    Widget RDP per PCM (GTK3).

    Modalità:
      - external: apre xfreerdp in finestra separata (Wayland nativo)
      - internal: tenta reparent via Gtk.Socket (richiede XWayland)
    """

    __gsignals__ = {
        "processo-terminato": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, profilo: dict, open_mode: str = "external", parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._profilo = profilo
        self._open_mode = open_mode
        self._proc = None
        self._rdp_win_id = None
        self._poll_count = 0

        self._init_ui()

    def _init_ui(self):
        # Barra info
        self._info = Gtk.Label(label="")
        self._info.set_xalign(0.0)
        self._info.get_style_context().add_class("terminal-infobar")
        self.pack_start(self._info, False, False, 0)

        if self._open_mode == "internal":
            # Gtk.Socket per embedding X11 (XWayland)
            self._socket = Gtk.Socket()
            self._socket.set_hexpand(True)
            self._socket.set_vexpand(True)
            self.pack_start(self._socket, True, True, 0)
        else:
            # Modalità esterna: placeholder informativo
            lbl = Gtk.Label(
                label="Sessione RDP avviata in finestra esterna."
            )
            lbl.set_valign(Gtk.Align.CENTER)
            self.pack_start(lbl, True, True, 0)

    def avvia(self):
        cmd = _build_freerdp_cmd(self._profilo)
        host = self._profilo.get("host", "")
        self._info.set_text(f"  ▶  RDP → {host}")

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
        except FileNotFoundError as e:
            self._info.set_text(f"  ✖  {e}")
            return

        if self._open_mode == "internal":
            # Polling per trovare la finestra xfreerdp e reparentarla
            GLib.timeout_add(800, self._poll_rdp_window)

        # Monitor processo
        GLib.timeout_add(3000, self._monitor_proc)

    def _poll_rdp_window(self) -> bool:
        """Cerca la finestra xfreerdp via xdotool e la reparenta."""
        self._poll_count += 1
        if self._poll_count > 20:  # timeout 16 secondi
            self._info.set_text("  ✖  Finestra RDP non trovata")
            return False

        if not self._proc or self._proc.poll() is not None:
            return False

        if not shutil.which("xdotool"):
            self._info.set_text("  ✖  xdotool non trovato (richiesto per internal mode)")
            return False

        host = self._profilo.get("host", "")
        pid  = self._proc.pid

        # Cerca per PID o per titolo
        for search_arg in [f"--pid {pid}", f"--name {host}", "--name FreeRDP"]:
            try:
                out = subprocess.check_output(
                    f"xdotool search {search_arg} 2>/dev/null | head -n1",
                    shell=True, text=True, timeout=2
                ).strip()
                if out and out.isdigit():
                    win_id = int(out)
                    xid = self._socket.get_id()
                    subprocess.Popen(
                        ["xdotool", "windowreparent", str(win_id), str(xid)]
                    )
                    self._rdp_win_id = win_id
                    self._info.set_text(f"  ●  RDP → {host}")
                    return False  # stop polling
            except Exception:
                pass

        return True  # continua polling

    def _monitor_proc(self) -> bool:
        if self._proc and self._proc.poll() is not None:
            self._info.set_text("  ✖  Sessione RDP terminata")
            self.emit("processo-terminato")
            return False
        return True

    def chiudi_processo(self):
        if self._proc:
            try:
                pgid = os.getpgid(self._proc.pid)
                os.killpg(pgid, signal.SIGTERM)
            except Exception:
                pass
            finally:
                self._proc = None
