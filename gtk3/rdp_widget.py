"""
rdp_widget.py - Widget RDP embedded per PCM (GTK3)

Riposizionamento finestra via xdotool (xfreerdp non supporta XEmbed):
  1. Lancia xfreerdp come finestra normale
  2. Polling con xdotool search finché la finestra non appare
  3. Reparenta la finestra dentro un Gtk.Socket via xdotool windowreparent
  4. Ridimensiona per riempire il container

Ricerca finestra in cascata:
  - xdotool search --name "FreeRDP: <host>"
  - xdotool search --name <host>
  - xdotool search --name FreeRDP  (escluse finestre preesistenti)

rdesktop: embedding nativo con -X <xid> (no polling necessario).

Dipendenze:
  xfreerdp o xfreerdp3, xdotool
"""

import os
import re
import signal
import subprocess
import shutil
import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GObject

from translations import t
from pcm_logging import get_logger as _get_log


_freerdp_ver_cache: dict[str, int] = {}


def _freerdp_major_version(client: str) -> int:
    """Rileva la major version di xfreerdp/xfreerdp3 lanciando '--version'.
    Il risultato è cache-ato per eseguibile: non cambia durante la vita
    del processo e altrimenti verrebbe ri-eseguito a ogni connessione e
    a ogni aggiornamento dell'anteprima comando nell'editor sessione."""
    if client in _freerdp_ver_cache:
        return _freerdp_ver_cache[client]
    try:
        out = subprocess.check_output(
            [client, "--version"], stderr=subprocess.STDOUT,
            timeout=3, text=True
        )
        m = re.search(r"(\d+)\.\d+", out)
        ver = int(m.group(1)) if m else (3 if "3" in client else 2)
    except Exception as e:
        _get_log(__name__).debug("Versione FreeRDP non rilevata per '%s': %s", client, e)
        ver = 3 if "3" in client else 2
    _freerdp_ver_cache[client] = ver
    return ver


def _resolve_rdp_exe(client_id: str) -> str:
    """Percorso eseguibile per il client RDP: rispetta un path custom
    configurato in Impostazioni > Dipendenze (tool_paths), esattamente
    come session_command._get_tool() fa già per gli altri protocolli.
    Prima d'ora solo l'anteprima comando lo rispettava; il lancio reale
    ignorava sempre il path custom e usava il nome nudo dell'eseguibile."""
    try:
        import config_manager
        custom = config_manager.load_settings().get("tool_paths", {}).get(client_id, "").strip()
    except Exception:
        custom = ""
    return custom or client_id


def _rdp_tool_available(client_id: str) -> bool:
    return bool(shutil.which(_resolve_rdp_exe(client_id)))


def build_rdp_args(p: dict, client: str, exe: str | None = None,
                    freerdp_ver: int | None = None,
                    window_size: tuple[int, int] | None = None,
                    embed_xid: str | None = None) -> list[str]:
    """Costruisce l'argv per rdesktop/xfreerdp/xfreerdp3.

    Unica fonte di verità usata sia dall'anteprima comando nell'editor
    sessione sia dal lancio reale (esterno ed embedded): prima esistevano
    tre copie di questa logica che avevano già iniziato a divergere
    (multimonitor, /cert:, drive redirection).

    client:      identificatore del dialetto ("xfreerdp3"/"xfreerdp"/"rdesktop").
    exe:         percorso eseguibile da mettere in argv[0], se diverso da
                 `client` (es. path custom); default: `client` stesso.
    window_size: (w, h) iniziali per la finestra xfreerdp, o geometria
                 rdesktop quando embed_xid è impostato.
    embed_xid:   XID del Gtk.Socket per il reparenting nativo di rdesktop
                 (solo rdesktop supporta l'embedding senza xdotool).
    """
    exe = exe or client
    host   = p.get("host", "")
    port   = p.get("port", "3389")
    user   = p.get("user", "")
    pwd    = p.get("password", "")
    domain = p.get("rdp_domain", "").strip()
    fs     = p.get("fullscreen", False)
    clips  = p.get("redirect_clipboard", True)
    drives = p.get("redirect_drives", False)
    mon_mode = p.get("rdp_monitor_mode", "single")
    mon_ids  = p.get("rdp_monitor_ids", "0").strip()

    if client == "rdesktop":
        args = [exe]
        if embed_xid:
            w, h = window_size or (1024, 768)
            args += [f"-X{embed_xid}", f"-g{w}x{h}", "-a16", "-DN"]
        else:
            args.append("-a16")
            if fs: args.append("-f")
        if user:   args.append(f"-u{user}")
        if domain: args.append(f"-d{domain}")
        if clips:  args.append("-rclipboard:PRIMARYCLIPBOARD")
        args.append(f"{host}:{port}")
        return args

    # xfreerdp / xfreerdp3
    ver = freerdp_ver if freerdp_ver is not None else _freerdp_major_version(exe)
    args = [exe, f"/v:{host}:{port}", "/cert:tofu"]
    if window_size:
        w, h = window_size
        args += [f"/w:{w}", f"/h:{h}"]
    if ver >= 3:
        args.append("/dynamic-resolution")
    if user:   args.append(f"/u:{user}")
    if domain:
        args.append(f"/d:{domain}")
        # Forza NTLM: evita il timeout Kerberos quando il KDC non è
        # raggiungibile (rete aziendale senza DNS Kerberos configurato)
        args.append("/auth-pkg-list:ntlm")
    if pwd:    args.append("/from-stdin")
    if fs:     args.append("/f")
    if clips:  args.append("/clipboard")
    if drives: args.append(f"/drive:home,{os.path.expanduser('~')}")
    if mon_mode == "all":
        args.append("/multimon")
    elif mon_mode == "custom" and mon_ids:
        args.append(f"/monitors:{mon_ids}")
    return args


class RdpEmbedWidget(Gtk.Box):
    """
    Widget RDP per PCM (GTK3).

    Modalità:
      - external: apre xfreerdp in finestra separata
      - internal: tenta reparent via Gtk.Socket + xdotool (richiede XWayland su Wayland)
    """

    __gsignals__ = {
        "processo-terminato": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, profilo: dict, open_mode: str = "external", parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._profilo        = profilo
        self._open_mode      = open_mode
        self._proc           = None
        self._avviato        = False
        self._reparented     = False
        self._wid_rdp        = None
        self._wid_esistenti  = set()
        self._poll_attempts  = 0
        self._poll_source    = None   # GLib.timeout_add handle
        self._monitor_source = None
        self._t_avvio        = None
        self._client_name    = ""
        self._rdp_host       = ""

        self._init_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        # Barra info in cima
        self._info = Gtk.Label(label="")
        self._info.set_xalign(0.0)
        self._info.set_margin_start(6)
        self._info.get_style_context().add_class("terminal-infobar")
        self.pack_start(self._info, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 0)

        if self._open_mode == "internal":
            # Container log: label di stato + text view per output xfreerdp
            self._log_container = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self._log_container.set_hexpand(True)
            self._log_container.set_vexpand(True)

            self._lbl_attesa = Gtk.Label(label=t("rdp.embed.waiting"))
            self._lbl_attesa.set_xalign(0.0)
            self._lbl_attesa.set_margin_start(6)
            self._lbl_attesa.set_margin_top(4)
            self._lbl_attesa.set_margin_bottom(2)
            self._log_container.pack_start(self._lbl_attesa, False, False, 0)

            self._log_view = Gtk.TextView()
            self._log_view.set_editable(False)
            self._log_view.set_cursor_visible(False)
            self._log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            self._log_view.set_monospace(True)
            self._log_scroll = Gtk.ScrolledWindow()
            self._log_scroll.set_hexpand(True)
            self._log_scroll.set_vexpand(True)
            self._log_scroll.add(self._log_view)
            self._log_container.pack_start(self._log_scroll, True, True, 0)

            self.pack_start(self._log_container, True, True, 0)

            # Gtk.Socket per embedding X11
            self._socket = Gtk.Socket()
            self._socket.set_hexpand(True)
            self._socket.set_vexpand(True)
            self._socket.set_no_show_all(True)
            self._socket.set_can_focus(True)
            self._socket.connect("plug-added",        self._on_plug_added)
            self._socket.connect("plug-removed",      self._on_plug_removed)
            self._socket.connect("button-press-event", self._on_socket_click)
            self._socket.connect("focus-in-event",    self._on_socket_focus_in)
            self.pack_start(self._socket, True, True, 0)
        else:
            lbl = Gtk.Label(label=t("rdp.external_label"))
            lbl.set_valign(Gtk.Align.CENTER)
            self.pack_start(lbl, True, True, 0)

    # ------------------------------------------------------------------
    # Avvio (chiamato da PCM dopo show_all)
    # ------------------------------------------------------------------

    def avvia(self):
        if self._avviato:
            return
        self._avviato = True
        GLib.idle_add(self._avvia_rdp)

    # ------------------------------------------------------------------
    # Logica avvio RDP
    # ------------------------------------------------------------------

    def _avvia_rdp(self):
        p = self._profilo

        # Wayland check
        wayland = (os.environ.get("WAYLAND_DISPLAY") or
                   os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland")
        display = os.environ.get("DISPLAY", "")
        if wayland and not display:
            self._mostra_errore(t("rdp.embed.wayland_no_xwayland"))
            return False
        self._extra_env = {"DISPLAY": display} if wayland and display else {}

        client = p.get("rdp_client", "xfreerdp3")
        if not _rdp_tool_available(client):
            for alt in ("xfreerdp3", "xfreerdp", "rdesktop"):
                if _rdp_tool_available(alt):
                    client = alt
                    break
            else:
                self._mostra_errore(t("rdp.embed.client_missing", client=client))
                return False
        exe = _resolve_rdp_exe(client)

        self._client_name = client
        host = p.get("host", "")
        pwd  = p.get("password", "")
        self._rdp_host = host

        # rdesktop: embedding nativo con -X (no polling)
        if client == "rdesktop" and self._open_mode == "internal":
            if pwd:
                self._mostra_errore(
                    "rdesktop integrato non accetta password salvate in modo sicuro. "
                    "Usa FreeRDP o la modalita esterna."
                )
                return False
            self._avvia_rdesktop(p)
            return False

        # xfreerdp: avvia + polling + xdotool reparent
        if self._open_mode == "internal" and not shutil.which("xdotool"):
            self._mostra_errore(t("rdp.embed.reparent_failed"))
            return False

        freerdp_ver = _freerdp_major_version(exe)
        # Dimensioni iniziali
        alloc = self.get_allocation()
        w_init = max(alloc.width,  1024)
        h_init = max(alloc.height - 30, 768)

        args = build_rdp_args(p, client, exe=exe, freerdp_ver=freerdp_ver,
                               window_size=(w_init, h_init))

        cmd_display = " ".join(args)
        if pwd:
            cmd_display += " /from-stdin ****"
        self._info.set_text(f"  ▶  {cmd_display}")

        env = dict(os.environ)
        env.update(self._extra_env)

        # Snapshot finestre FreeRDP preesistenti (per escluderle nel polling)
        self._wid_esistenti = set()
        try:
            out = subprocess.check_output(
                ["xdotool", "search", "--name", "FreeRDP"],
                stderr=subprocess.DEVNULL, timeout=2, text=True
            ).strip()
            if out:
                self._wid_esistenti = set(out.split())
        except Exception as e:
            _get_log(__name__).debug("xdotool search esistenti fallito: %s", e)

        try:
            stdin_arg = subprocess.PIPE if pwd else None
            self._proc = subprocess.Popen(
                args, preexec_fn=os.setsid,
                stdin=stdin_arg,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env,
            )
            if pwd:
                try:
                    self._proc.stdin.write((pwd + "\n").encode())
                    self._proc.stdin.close()
                except Exception as e:
                    _get_log(__name__).debug("Invio password RDP fallito: %s", e)
        except Exception as e:
            _get_log(__name__).debug("Avvio RDP fallito: %s", e)
            self._mostra_errore(str(e))
            return False

        self._t_avvio = datetime.datetime.now()
        from pcm_logging import get_logger
        get_logger(__name__).info("Avviato %s PID=%s", client, self._proc.pid)
        if hasattr(self, "_log_view"):
            GLib.io_add_watch(
                self._proc.stdout.fileno(),
                GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                self._on_rdp_output,
            )

        self._poll_attempts = 0
        if self._open_mode == "internal":
            self._poll_source = GLib.timeout_add(500, self._cerca_e_reparenta)

        self._monitor_source = GLib.timeout_add(3000, self._monitor_proc)
        return False

    # ------------------------------------------------------------------
    # rdesktop: embedding nativo con -X
    # ------------------------------------------------------------------

    def _avvia_rdesktop(self, p: dict):
        host = p.get("host", "")
        # Il socket deve essere realizzato prima di passare il XID a rdesktop
        self._log_container.set_visible(False)
        self._socket.set_visible(True)
        self._socket.show()

        # Forza la realizzazione del socket per ottenere l'XID
        self._socket.realize()

        xid = self._socket.get_id()
        if not xid:
            self._mostra_errore("Socket XID non disponibile")
            return

        alloc = self.get_allocation()
        w = max(alloc.width,  1024)
        h = max(alloc.height - 30, 768)

        args = build_rdp_args(p, "rdesktop", exe=_resolve_rdp_exe("rdesktop"),
                               window_size=(w, h), embed_xid=xid)

        cmd_display = " ".join(
            a if not a.startswith("-p") else "-p****" for a in args
        )
        self._info.set_text(f"  ▶  {cmd_display}")

        env = dict(os.environ)
        env.update(self._extra_env)

        try:
            self._proc = subprocess.Popen(
                args, preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env,
            )
            self._t_avvio = datetime.datetime.now()
            self._reparented = True
            from pcm_logging import get_logger
            get_logger(__name__).info("rdesktop avviato PID=%s XID=%s", self._proc.pid, xid)
        except Exception as e:
            self._mostra_errore(str(e))
            return

        self._monitor_source = GLib.timeout_add(3000, self._monitor_proc)

    # ------------------------------------------------------------------
    # Polling + Reparenting (xfreerdp)
    # ------------------------------------------------------------------

    def _cerca_e_reparenta(self) -> bool:
        self._poll_attempts += 1

        # Timeout 180s (360 × 500ms)
        if self._poll_attempts > 360:
            self._mostra_errore(t("rdp.embed.reparent_failed"))
            return False  # stop

        # Processo morto: aspetta ancora qualche ciclo (finestra può comparire dopo)
        if self._proc and self._proc.poll() is not None:
            if not hasattr(self, "_processo_morto_al"):
                self._processo_morto_al = self._poll_attempts
            elif self._poll_attempts - self._processo_morto_al > 20:
                return False  # stop

        wid = self._trova_finestra()
        if not wid:
            dots = "." * (self._poll_attempts % 4)
            sec  = int(self._poll_attempts * 0.5)
            self._lbl_attesa.set_text(f"{t('rdp.embed.waiting')}{dots}  ({sec}s)")
            return True  # continua polling

        # Finestra trovata
        self._wid_rdp = wid
        self._esegui_reparent(wid)
        return False  # stop polling

    def _trova_finestra(self) -> str | None:
        """
        Cerca la finestra xfreerdp per nome.
        xdotool search --pid NON funziona con xfreerdp3 (la finestra X11
        viene creata da un thread interno con PID diverso).
        """
        host = self._rdp_host

        # Titolo esatto: "FreeRDP: <host>"
        if host:
            wid = self._xdotool_search("--name", f"FreeRDP: {host}")
            if wid:
                return wid
            wid = self._xdotool_search("--name", host)
            if wid:
                return wid

        # Tutte le finestre FreeRDP, escluse le preesistenti
        try:
            out = subprocess.check_output(
                ["xdotool", "search", "--name", "FreeRDP"],
                stderr=subprocess.DEVNULL, timeout=2, text=True
            ).strip()
            if out:
                for wid in out.split():
                    if wid not in self._wid_esistenti:
                        return wid
        except Exception as e:
            _get_log(__name__).debug("xdotool search FreeRDP fallito: %s", e)

    def _xdotool_search(self, *args) -> str | None:
        try:
            out = subprocess.check_output(
                ["xdotool", "search"] + list(args),
                stderr=subprocess.DEVNULL, timeout=2, text=True
            ).strip()
            if out:
                return out.split("\n")[0].strip()
        except Exception as e:
            _get_log(__name__).debug("xdotool search PID fallito: %s", e)
        return None

    def _esegui_reparent(self, wid_rdp: str):
        """Reparenta la finestra xfreerdp dentro il Gtk.Socket."""
        self._log_container.set_visible(False)
        self._socket.set_visible(True)
        self._socket.show()

        # Forza la realizzazione del socket per ottenere l'XID
        self._socket.realize()

        xid = self._socket.get_id()
        if not xid:
            self._mostra_errore(t("rdp.embed.reparent_failed"))
            return

        alloc = self._socket.get_allocation()
        w = max(alloc.width,  800)
        h = max(alloc.height, 600)

        # Esegui il reparenting in passi asincroni con GLib.timeout_add
        # per evitare time.sleep() nel thread principale GTK
        def _step1():
            try:
                subprocess.run(["xdotool", "windowunmap", wid_rdp],
                               timeout=3, capture_output=True)
            except Exception as e:
                _get_log(__name__).debug("xdotool windowunmap fallito: %s", e)
            GLib.timeout_add(150, _step2)
            return False

        def _step2():
            try:
                result = subprocess.run(
                    ["xdotool", "windowreparent", wid_rdp, str(xid)],
                    timeout=3, capture_output=True
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.decode().strip())
            except Exception as e:
                print(f"[rdp_widget] reparent error: {e}")
                GLib.idle_add(self._mostra_errore,
                    f"{t('rdp.embed.reparent_failed')} — finestra RDP aperta esternamente")
                return False
            GLib.timeout_add(100, _step3)
            return False

        def _step3():
            subprocess.run(["xdotool", "windowmove", wid_rdp, "0", "0"],
                           timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["xdotool", "windowsize", wid_rdp, str(w), str(h)],
                           timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            GLib.timeout_add(100, _step4)
            return False

        def _step4():
            try:
                subprocess.run(["xdotool", "windowmap", wid_rdp],
                               timeout=3, capture_output=True)
            except Exception as e:
                _get_log(__name__).debug("xdotool windowmap fallito: %s", e)
            GLib.timeout_add(150, _step5)
            return False

        def _step5():
            subprocess.run(["xdotool", "windowfocus", wid_rdp],
                           timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._reparented = True
            host = self._rdp_host
            self._info.set_text(f"  ●  RDP → {host}")
            self._info.get_style_context().add_class("rdp-connected")
            return False

        GLib.idle_add(_step1)

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def do_size_allocate(self, allocation):
        Gtk.Box.do_size_allocate(self, allocation)
        if not self._reparented or not self._wid_rdp:
            return
        if hasattr(self, "_socket"):
            a = self._socket.get_allocation()
            w = max(a.width,  320)
            h = max(a.height, 240)
            if hasattr(self, "_resize_pending") and self._resize_pending:
                return
            self._resize_pending = True

            def _do_resize():
                self._resize_pending = False
                if self._reparented and self._wid_rdp and hasattr(self, "_socket"):
                    a = self._socket.get_allocation()
                    w2 = max(a.width, 320)
                    h2 = max(a.height, 240)
                    subprocess.run(
                        ["xdotool", "windowsize", self._wid_rdp, str(w2), str(h2)],
                        timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                return False
            GLib.timeout_add(150, _do_resize)

    # ------------------------------------------------------------------
    # Monitor processo
    # ------------------------------------------------------------------

    def _monitor_proc(self) -> bool:
        if not self._proc:
            return False
        if self._proc.poll() is None:
            return True  # ancora in vita

        # Processo terminato
        durata = (datetime.datetime.now() - self._t_avvio).total_seconds() \
                 if self._t_avvio else 99
        client = self._client_name

        if durata < 15 and not self._reparented:
            # Fallimento rapido — suggerisci alternativa
            if client == "rdesktop":
                alt = "xfreerdp3" if shutil.which("xfreerdp3") else "xfreerdp"
            else:
                alt = "rdesktop" if shutil.which("rdesktop") else ""
            if alt:
                msg = t("rdp.embed.failed_suggest", client=client, alt=alt)
            else:
                msg = t("rdp.embed.failed_noalt", client=client)
            self._mostra_errore(msg)
        else:
            self._info.set_text(t("terminal.session_ended"))

        self._proc = None
        self.emit("processo-terminato")
        return False  # stop monitor

    # ------------------------------------------------------------------
    # Segnali Socket
    # ------------------------------------------------------------------

    def _on_plug_added(self, socket):
        self._info.set_text(f"  ●  RDP → {self._rdp_host}")
        # rdesktop usa XEMBED: appena il plug si connette, GTK può ricevere
        # il focus e forwardarlo correttamente all'embedded window
        GLib.idle_add(self._socket.grab_focus)

    def _on_plug_removed(self, socket):
        self._info.set_text(f"  ✖  RDP disconnesso")
        return True

    def _on_socket_click(self, widget, event):
        """Click sul socket → sposta il focus X11 alla finestra RDP embedded."""
        if self._wid_rdp:
            subprocess.run(["xdotool", "windowfocus", self._wid_rdp],
                           timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return False

    def _on_socket_focus_in(self, widget, event):
        """Il socket GTK riceve il focus → re-forwardalo alla finestra RDP."""
        if self._wid_rdp:
            subprocess.run(["xdotool", "windowfocus", self._wid_rdp],
                           timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def chiudi_processo(self):
        if self._poll_source:
            GLib.source_remove(self._poll_source)
            self._poll_source = None
        if self._monitor_source:
            GLib.source_remove(self._monitor_source)
            self._monitor_source = None
        if self._proc:
            try:
                pgid = os.getpgid(self._proc.pid)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self._proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            except Exception as e:
                print(f"[rdp_widget] Errore chiusura: {e}")
            finally:
                self._proc = None

    # ------------------------------------------------------------------
    # Output log (internal mode)
    # ------------------------------------------------------------------

    def _on_rdp_output(self, fd, condition):
        import os as _os
        if condition & GLib.IO_IN:
            try:
                data = _os.read(fd, 4096)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    buf = self._log_view.get_buffer()
                    buf.insert(buf.get_end_iter(), text)
                    GLib.idle_add(self._scroll_log_bottom)
            except OSError:
                return False
        return not bool(condition & (GLib.IO_HUP | GLib.IO_ERR))

    def _scroll_log_bottom(self):
        adj = self._log_scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _mostra_errore(self, msg: str):
        if hasattr(self, "_lbl_attesa"):
            self._lbl_attesa.set_text(f"⚠  {msg}")
            self._lbl_attesa.set_visible(True)
        if hasattr(self, "_log_container"):
            self._log_container.set_visible(True)
        if hasattr(self, "_socket"):
            self._socket.set_visible(False)
        self._info.set_text(f"  ✖  {msg}")


# ---------------------------------------------------------------------------
# Funzione pubblica usata da PCM._apri_rdp per la modalità external
# ---------------------------------------------------------------------------

def _build_freerdp_cmd(profilo: dict) -> list[str]:
    """
    Costruisce argv per xfreerdp/xfreerdp3/rdesktop in modalità external.
    Aggiunge /auth-pkg-list:ntlm quando è presente un dominio per evitare
    il timeout Kerberos su reti senza KDC raggiungibile.
    """
    client = profilo.get("rdp_client", "xfreerdp3")
    if not _rdp_tool_available(client):
        for alt in ("xfreerdp3", "xfreerdp", "rdesktop"):
            if _rdp_tool_available(alt):
                client = alt
                break

    return build_rdp_args(profilo, client, exe=_resolve_rdp_exe(client))
