"""
vnc_widget.py - Viewer VNC integrato (GTK3)

Strategia con fallback automatico:
  1. gtk-vnc  (gir1.2-gtk-vnc-2.0)  — widget nativo, zero processi esterni
  2. Gtk.Socket + vncviewer          — embedding X11 del client VNC installato
  3. Messaggio di errore con istruzioni

Dipendenze per metodo 1 (raccomandato):
  sudo apt install gir1.2-gtk-vnc-2.0

Dipendenze per metodo 2 (fallback):
  uno qualsiasi tra: vncviewer, xtightvncviewer, tigervnc-viewer, xvnc4viewer
"""

import os
import shutil
import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

# Prova a caricare gtk-vnc
_GTKV_OK = False
try:
    gi.require_version("GtkVnc", "2.0")
    from gi.repository import GtkVnc
    _GTKV_OK = True
except Exception:
    pass


def _find_vnc_client() -> str | None:
    for c in ["vncviewer", "xtightvncviewer", "xvnc4viewer",
              "tigervnc", "xtigervncviewer", "krdc", "remmina"]:
        if shutil.which(c):
            return c
    return None


# Keysyms X11 per send_keys
_KEY_CTRL  = 0xffe3
_KEY_ALT   = 0xffe9
_KEY_DEL   = 0xffff
_KEY_F1    = 0xffbe
_KEY_ESC   = 0xff1b
_KEY_SUPER = 0xffeb


# ---------------------------------------------------------------------------
# Metodo 1: gtk-vnc nativo
# ---------------------------------------------------------------------------

class _VncGtkVnc(Gtk.Box):

    def __init__(self, host, port, password, color_depth=0, quality=2, on_save_password=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._host = host
        self._port = str(port)
        self._password = password
        self._on_save_password = on_save_password
        self._closed = False
        self._scaling = True
        self._pointer_local = False
        self._keyboard_grab = False
        self._read_only = False
        # 0=32bpp, 1=16bpp, 2=8bpp  |  0=best, 1=good, 2=fast
        self._color_depth = int(color_depth) if color_depth is not None else 0
        self._quality = int(quality) if quality is not None else 2
        self._build()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self):
        # ── Barra superiore: stato + toolbar ─────────────────────────
        topbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        topbar.get_style_context().add_class("vnc-topbar")

        # Label stato (sx)
        self._lbl = Gtk.Label(label=f"VNC — {self._host}:{self._port}  connessione…")
        self._lbl.set_xalign(0.0)
        self._lbl.set_hexpand(True)
        self._lbl.set_margin_start(8)
        topbar.pack_start(self._lbl, True, True, 0)

        # Toolbar pulsanti (dx)
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        tb.set_margin_start(4)
        tb.set_margin_end(4)
        tb.set_margin_top(2)
        tb.set_margin_bottom(2)

        # Adatta schermo (scaling)
        self._btn_scale = Gtk.ToggleButton()
        self._btn_scale.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_scale.set_tooltip_text("Adatta schermo alla finestra")
        self._btn_scale.add(Gtk.Image.new_from_icon_name(
            "zoom-fit-best-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        self._btn_scale.set_active(self._scaling)
        self._btn_scale.connect("toggled", self._on_scale_toggled)
        tb.pack_start(self._btn_scale, False, False, 0)

        # Puntatore locale/remoto
        self._btn_ptr = Gtk.ToggleButton()
        self._btn_ptr.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_ptr.set_tooltip_text("Puntatore: locale / remoto")
        self._btn_ptr.add(Gtk.Image.new_from_icon_name(
            "input-mouse-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        self._btn_ptr.set_active(self._pointer_local)
        self._btn_ptr.connect("toggled", self._on_pointer_toggled)
        tb.pack_start(self._btn_ptr, False, False, 0)

        # Grab tastiera
        self._btn_kb = Gtk.ToggleButton()
        self._btn_kb.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_kb.set_tooltip_text("Cattura tastiera (intercetta scorciatoie di sistema)")
        self._btn_kb.add(Gtk.Image.new_from_icon_name(
            "input-keyboard-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        self._btn_kb.set_active(self._keyboard_grab)
        self._btn_kb.connect("toggled", self._on_keyboard_toggled)
        tb.pack_start(self._btn_kb, False, False, 0)

        # Sola lettura
        self._btn_ro = Gtk.ToggleButton()
        self._btn_ro.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_ro.set_tooltip_text("Sola lettura (nessun input al server)")
        self._btn_ro.add(Gtk.Image.new_from_icon_name(
            "changes-prevent-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        self._btn_ro.set_active(self._read_only)
        self._btn_ro.connect("toggled", self._on_readonly_toggled)
        tb.pack_start(self._btn_ro, False, False, 0)

        tb.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)

        # Ctrl+Alt+Del
        btn_cad = Gtk.Button()
        btn_cad.set_relief(Gtk.ReliefStyle.NONE)
        btn_cad.set_tooltip_text("Invia Ctrl+Alt+Canc")
        btn_cad.add(Gtk.Image.new_from_icon_name(
            "system-restart-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        btn_cad.connect("clicked", lambda b: self._send_ctrl_alt_del())
        tb.pack_start(btn_cad, False, False, 0)

        # Ctrl+Alt+F1..F7 (cambio VT)
        btn_vt = Gtk.MenuButton()
        btn_vt.set_relief(Gtk.ReliefStyle.NONE)
        btn_vt.set_tooltip_text("Invia Ctrl+Alt+Fn (cambio terminale virtuale)")
        btn_vt.add(Gtk.Image.new_from_icon_name(
            "computer-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        btn_vt.set_popup(self._build_vt_menu())
        tb.pack_start(btn_vt, False, False, 0)

        # Screenshot
        btn_ss = Gtk.Button()
        btn_ss.set_relief(Gtk.ReliefStyle.NONE)
        btn_ss.set_tooltip_text("Cattura screenshot del desktop remoto")
        btn_ss.add(Gtk.Image.new_from_icon_name(
            "camera-photo-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        btn_ss.connect("clicked", lambda b: self._screenshot())
        tb.pack_start(btn_ss, False, False, 0)

        tb.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)

        # Riconnetti
        btn_r = Gtk.Button()
        btn_r.set_relief(Gtk.ReliefStyle.NONE)
        btn_r.set_tooltip_text("Riconnetti al server VNC")
        btn_r.add(Gtk.Image.new_from_icon_name(
            "view-refresh-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        btn_r.connect("clicked", lambda b: self._riconnetti())
        tb.pack_start(btn_r, False, False, 0)

        topbar.pack_start(tb, False, False, 0)
        self.pack_start(topbar, False, False, 0)
        self.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            False, False, 0)

        # ── Display VNC ───────────────────────────────────────────────
        self._display = GtkVnc.Display()
        self._display.set_hexpand(True)
        self._display.set_vexpand(True)
        self._display.set_scaling(self._scaling)
        self._display.set_allow_resize(True)
        self._display.set_keep_aspect_ratio(True)
        self._display.set_pointer_local(self._pointer_local)
        self._display.set_keyboard_grab(self._keyboard_grab)
        self._display.set_read_only(self._read_only)
        # NON chiamare _applica_depth_quality qui: GtkVnc ignora set_depth
        # prima di vnc-initialized. Viene chiamata in _on_initialized.

        self._display.connect("vnc-connected",       self._on_connected)
        self._display.connect("vnc-initialized",     self._on_initialized)
        self._display.connect("vnc-disconnected",    self._on_disconnected)
        self._display.connect("vnc-error",           self._on_error)
        self._display.connect("vnc-auth-credential", self._on_auth)
        self._display.connect("vnc-auth-failure",    self._on_auth_failure)

        self.pack_start(self._display, True, True, 0)
        # Connetti solo dopo che il widget è realizzato
        self._display.connect("realize", lambda w: self._connetti())

    def _applica_depth_quality(self):
        """Imposta color depth e qualità compressione sul display GtkVnc."""
        # depth: 0→32bpp, 1→16bpp, 2→8bpp
        depth_map = {0: 32, 1: 16, 2: 8}
        depth_bits = depth_map.get(self._color_depth, 32)
        try:
            self._display.set_depth(GtkVnc.DisplayDepth(depth_bits))
        except Exception:
            try:
                self._display.set_depth(depth_bits)
            except Exception:
                pass
        # quality: usa lossy encoding solo in modalità fast
        try:
            self._display.set_lossy_encoding(self._quality == 2)
        except Exception:
            pass

    def _build_vt_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()
        for n in range(1, 8):
            key = getattr(GtkVnc, f'_KEY_F{n}', _KEY_F1 + n - 1) if False else (_KEY_F1 + n - 1)
            mi = Gtk.MenuItem(label=f"Ctrl+Alt+F{n}  (VT{n})")
            mi.connect("activate", lambda _, k=key: self._send_keys([_KEY_CTRL, _KEY_ALT, k]))
            menu.append(mi)
        menu.show_all()
        return menu

    # ------------------------------------------------------------------
    # Connessione
    # ------------------------------------------------------------------

    def _connetti(self):
        try:
            # open_host() è il metodo corretto per connessioni TCP con GtkVnc.
            # open_fd() con socket Python causa problemi di negoziazione del
            # protocollo perché GtkVnc non controlla il fd direttamente.
            self._display.open_host(self._host, str(self._port))
        except Exception as e:
            self._lbl.set_text(f"VNC — errore connessione: {e}")

    def _riconnetti(self):
        if not self._closed:
            try:
                self._display.close()
            except Exception:
                pass
            self._lbl.set_text(f"VNC — {self._host}:{self._port}  riconnessione…")
            GLib.timeout_add(800, lambda: self._connetti() or False)

    # ------------------------------------------------------------------
    # Segnali GtkVnc
    # ------------------------------------------------------------------

    def _on_connected(self, d):
        self._lbl.set_text(f"VNC — {self._host}:{self._port}  autenticazione…")

    def _on_initialized(self, d):
        # Applica depth/quality ora che la connessione è stabilita.
        # GtkVnc ignora set_depth prima di questo segnale.
        self._applica_depth_quality()
        nome = ""
        try:
            nome = self._display.get_name() or ""
        except Exception:
            pass
        self._lbl.set_text(
            f"VNC — {self._host}:{self._port}"
            + (f"  [{nome}]" if nome else "")
        )

    def _on_disconnected(self, d):
        if not self._closed:
            self._lbl.set_text(f"VNC — {self._host}:{self._port}  disconnesso")

    def _on_error(self, d, msg):
        self._lbl.set_text(f"VNC errore: {msg}")

    def _on_auth_failure(self, d, msg):
        self._lbl.set_text(f"VNC — autenticazione fallita: {msg}")

    def _on_auth(self, display, credlist):
        cred = GtkVnc.DisplayCredential
        needs_password = False
        needs_username = False
        for i in range(credlist.n_values):
            v = credlist.get_nth(i)
            if v == cred.PASSWORD:
                needs_password = True
            elif v == cred.USERNAME:
                needs_username = True
        if needs_password:
            pwd = self._password
            if not pwd:
                pwd = self._chiedi_password(display)
            if pwd is not None:
                display.set_credential(cred.PASSWORD, pwd)
        if needs_username:
            display.set_credential(cred.USERNAME, "")

    def _chiedi_password(self, display) -> str | None:
        """Dialog modale che chiede la password VNC con opzione di salvataggio."""
        toplevel = self.get_toplevel()
        dlg = Gtk.Dialog(
            title="Password VNC",
            transient_for=toplevel if isinstance(toplevel, Gtk.Window) else None,
            modal=True,
        )
        dlg.set_default_size(360, -1)
        dlg.add_button("_Annulla", Gtk.ResponseType.CANCEL)
        dlg.add_button("_Connetti", Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)

        box = dlg.get_content_area()
        box.set_spacing(8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(12)
        box.set_margin_bottom(8)

        lbl = Gtk.Label(label=f"Password per {self._host}:{self._port}")
        lbl.set_xalign(0.0)
        box.pack_start(lbl, False, False, 0)

        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_activates_default(True)
        box.pack_start(entry, False, False, 0)

        chk = Gtk.CheckButton(label="Salva password nel profilo")
        box.pack_start(chk, False, False, 0)

        box.show_all()
        risposta = dlg.run()
        pwd = entry.get_text()
        salva = chk.get_active()
        dlg.destroy()

        if risposta != Gtk.ResponseType.OK or not pwd:
            return None

        self._password = pwd
        if salva and self._on_save_password:
            try:
                self._on_save_password(pwd)
            except Exception:
                pass
        return pwd

    # ------------------------------------------------------------------
    # Azioni toolbar
    # ------------------------------------------------------------------

    def _on_scale_toggled(self, btn):
        self._scaling = btn.get_active()
        try:
            self._display.set_scaling(self._scaling)
            self._display.set_keep_aspect_ratio(self._scaling)
        except Exception:
            pass

    def _on_pointer_toggled(self, btn):
        self._pointer_local = btn.get_active()
        try:
            self._display.set_pointer_local(self._pointer_local)
        except Exception:
            pass

    def _on_keyboard_toggled(self, btn):
        self._keyboard_grab = btn.get_active()
        try:
            self._display.set_keyboard_grab(self._keyboard_grab)
        except Exception:
            pass

    def _on_readonly_toggled(self, btn):
        self._read_only = btn.get_active()
        try:
            self._display.set_read_only(self._read_only)
        except Exception:
            pass

    def _send_keys(self, keysyms: list):
        try:
            self._display.send_keys(keysyms)
        except Exception:
            pass

    def _send_ctrl_alt_del(self):
        self._send_keys([_KEY_CTRL, _KEY_ALT, _KEY_DEL])

    def _screenshot(self):
        try:
            pixbuf = self._display.capture_screenshot()
            if pixbuf is None:
                return
            import time
            from gi.repository import GdkPixbuf
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.expanduser(f"~/vnc_screenshot_{self._host}_{ts}.png")
            pixbuf.savev(path, "png", [], [])
            # Notifica utente
            dlg = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                modal=False,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.CLOSE,
                text=f"Screenshot salvato:\n{path}"
            )
            dlg.connect("response", lambda d, r: d.destroy())
            dlg.show()
        except Exception as e:
            self._lbl.set_text(f"Screenshot errore: {e}")

    # ------------------------------------------------------------------
    # Chiusura
    # ------------------------------------------------------------------

    def chiudi_processo(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._display.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Metodo 2: Gtk.Socket + vncviewer esterno (XEmbed)
# ---------------------------------------------------------------------------

class _VncSocket(Gtk.Box):

    _EMBED = {
        "vncviewer":       ("--EmbedIn={}",  None),
        "xtigervncviewer": ("--EmbedIn={}",  None),
        "xtightvncviewer": ("-Parent {}",    "-passwd {}"),
        "xvnc4viewer":    ("-Parent {}",    "-passwd {}"),
    }

    def __init__(self, host, port, password):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._host = host
        self._port = str(port)
        self._password = password
        self._client = _find_vnc_client()
        self._proc = None
        self._closed = False
        self._passwd_file = None
        self._build()

    def _build(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.set_margin_start(8); bar.set_margin_end(8)
        bar.set_margin_top(4);   bar.set_margin_bottom(4)
        self._lbl = Gtk.Label(label=f"VNC → {self._host}:{self._port}  avvio…")
        self._lbl.set_xalign(0.0); self._lbl.set_hexpand(True)
        bar.pack_start(self._lbl, True, True, 0)

        btn_r = Gtk.Button()
        btn_r.set_relief(Gtk.ReliefStyle.NONE)
        btn_r.set_tooltip_text("Riconnetti")
        btn_r.add(Gtk.Image.new_from_icon_name(
            "view-refresh-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        btn_r.connect("clicked", lambda b: self._avvia_client())
        bar.pack_start(btn_r, False, False, 0)

        self.pack_start(bar, False, False, 0)
        self.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            False, False, 0)

        self._socket = Gtk.Socket()
        self._socket.set_hexpand(True)
        self._socket.set_vexpand(True)
        self._socket.connect("plug-added",   self._on_plug_added)
        self._socket.connect("plug-removed", self._on_plug_removed)
        self.pack_start(self._socket, True, True, 0)
        self._socket.connect("realize", lambda w: GLib.idle_add(self._avvia_client))

    def _avvia_client(self):
        if self._closed:
            return False
        if not self._client:
            self._errore(
                "Nessun client VNC trovato nel PATH.\n"
                "Installa: sudo apt install tigervnc-viewer\n"
                "     o:   sudo apt install gir1.2-gtk-vnc-2.0"
            )
            return False

        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._proc = None

        xid = self._socket.get_id()
        if not xid:
            return False

        embed_fmt, passwd_fmt = self._EMBED.get(self._client, ("--EmbedIn={}", None))
        cmd = [self._client]

        if self._password:
            if passwd_fmt:
                pf = self._write_passwd_file(self._password)
                if pf:
                    self._passwd_file = pf
                    cmd.append(passwd_fmt.format(pf))
            elif self._client in ("vncviewer", "xtigervncviewer"):
                pf = self._write_passwd_file(self._password)
                if pf:
                    self._passwd_file = pf
                    cmd += ["--PasswordFile", pf]

        cmd.append(embed_fmt.format(xid))
        cmd.append(f"{self._host}:{self._port}")

        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._lbl.set_text(
                f"VNC → {self._host}:{self._port}  ({self._client})")
            GLib.timeout_add(3000, self._check_proc)
        except Exception as e:
            self._errore(f"Errore avvio {self._client}:\n{e}")
        return False

    def _check_proc(self):
        if self._closed or self._proc is None:
            return False
        if self._proc.poll() is not None:
            if not self._closed:
                self._lbl.set_text(
                    f"VNC → {self._host}:{self._port}  disconnesso")
            return False
        return True

    @staticmethod
    def _write_passwd_file(password):
        try:
            import tempfile
            key = [23, 82, 107, 6, 35, 78, 88, 7]
            pw = (password.encode()[:8]).ljust(8, b'\x00')
            enc = bytes(b ^ key[i] for i, b in enumerate(pw))
            fd, path = tempfile.mkstemp(prefix="pcm_vnc_", suffix=".passwd")
            with os.fdopen(fd, 'wb') as f:
                f.write(enc)
            return path
        except Exception:
            return None

    def _on_plug_added(self, s):
        self._lbl.set_text(f"VNC → {self._host}:{self._port}")

    def _on_plug_removed(self, s):
        if not self._closed:
            self._lbl.set_text(
                f"VNC → {self._host}:{self._port}  disconnesso")
        return True

    def _errore(self, msg):
        lbl = Gtk.Label(label=msg)
        lbl.set_line_wrap(True); lbl.set_xalign(0.0)
        lbl.set_valign(Gtk.Align.CENTER); lbl.set_vexpand(True)
        lbl.set_margin_start(12)
        self.pack_start(lbl, True, True, 0)
        self.show_all()

    def chiudi_processo(self):
        if self._closed:
            return
        self._closed = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            except Exception:
                pass
        if self._passwd_file and os.path.exists(self._passwd_file):
            try:
                os.unlink(self._passwd_file)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Metodo 3: nessun driver disponibile
# ---------------------------------------------------------------------------

class _VncNoDriver(Gtk.Box):

    def __init__(self, host, port, **_):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_margin_start(24); self.set_margin_end(24)
        lbl = Gtk.Label()
        lbl.set_markup(
            "<b>VNC integrato non disponibile</b>\n\n"
            "Installa uno dei seguenti pacchetti:\n\n"
            "<tt>sudo apt install gir1.2-gtk-vnc-2.0</tt>   (raccomandato)\n"
            "<tt>sudo apt install tigervnc-viewer</tt>       (alternativa)"
        )
        lbl.set_line_wrap(True); lbl.set_xalign(0.0)
        self.pack_start(lbl, False, False, 0)

    def chiudi_processo(self):
        pass


# ---------------------------------------------------------------------------
# Factory pubblica
# ---------------------------------------------------------------------------

def VncWebWidget(host: str, port: str = "5900", password: str = "",
                  color_depth: int = 0, quality: int = 2, on_save_password=None):
    """
    Restituisce il miglior widget VNC disponibile:
      1. gtk-vnc nativo (gir1.2-gtk-vnc-2.0)  — toolbar completa
      2. Gtk.Socket + client vncviewer         — embedding XEmbed
      3. Widget con istruzioni di installazione

    color_depth: 0=32bpp, 1=16bpp, 2=8bpp
    quality:     0=best,  1=good,  2=fast
    """
    if _GTKV_OK:
        return _VncGtkVnc(host=host, port=port, password=password,
                          color_depth=color_depth, quality=quality,
                          on_save_password=on_save_password)
    if _find_vnc_client():
        return _VncSocket(host=host, port=port, password=password)
    return _VncNoDriver(host=host, port=port)
