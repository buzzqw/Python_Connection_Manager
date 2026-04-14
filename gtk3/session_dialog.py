"""
session_dialog.py - Dialog creazione/modifica sessione PCM (GTK3)

Gtk.Dialog con Gtk.Notebook. Adatta i widget visibili al protocollo scelto.
Corrisponde 1:1 all'originale PyQt6.
"""

import os
import shutil

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import config_manager
from themes import TERMINAL_THEMES
from translations import t
from session_command import installed_tools as _installed_tools

_HERE      = os.path.dirname(os.path.abspath(__file__))
_ICONS_DIR = os.path.join(_HERE, "icons")

PROTOCOLLI = ["ssh", "telnet", "sftp", "ftp", "rdp", "vnc", "mosh", "serial"]
PROTO_LABEL = {
    "ssh": "SSH", "telnet": "Telnet", "sftp": "SFTP",
    "ftp": "FTP / FTPS", "rdp": "RDP", "vnc": "VNC",
    "mosh": "Mosh", "serial": "Seriale",
}


def _available_tools(candidates: list, always_include: list | None = None) -> list:
    found = [c for c in candidates if shutil.which(c)]
    if always_include:
        result = list(always_include) + [c for c in found if c not in always_include]
    else:
        result = found
    return result or [candidates[0]]


def _make_grid() -> Gtk.Grid:
    g = Gtk.Grid()
    g.set_row_spacing(8)
    g.set_column_spacing(8)
    g.set_margin_start(12)
    g.set_margin_end(12)
    g.set_margin_top(12)
    g.set_margin_bottom(12)
    return g


def _form_row(label_text: str, widget: Gtk.Widget, grid: Gtk.Grid, row: int):
    lbl = Gtk.Label(label=label_text)
    lbl.set_xalign(1.0)
    lbl.set_margin_end(6)
    grid.attach(lbl, 0, row, 1, 1)
    grid.attach(widget, 1, row, 1, 1)


def _entry(placeholder: str = "", password: bool = False) -> Gtk.Entry:
    e = Gtk.Entry()
    e.set_hexpand(True)
    if placeholder:
        e.set_placeholder_text(placeholder)
    if password:
        e.set_visibility(False)
        e.set_input_purpose(Gtk.InputPurpose.PASSWORD)
    return e


def _combo(*items) -> Gtk.ComboBoxText:
    c = Gtk.ComboBoxText()
    for item in items:
        c.append_text(str(item))
    if items:
        c.set_active(0)
    c.set_hexpand(True)
    return c


def _check(label: str) -> Gtk.CheckButton:
    return Gtk.CheckButton(label=label)


class SessionDialog(Gtk.Dialog):

    def __init__(self, parent=None, nome: str = "", dati: dict = None):
        super().__init__(
            title=t("sd.new_title") if not nome else t("sd.edit_title", name=nome),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self._nome_originale = nome
        self._dati_originali = dati or {}
        self._macros: list[dict] = []

        self.set_default_size(780, 680)
        self._init_ui()
        if nome and dati:
            self._popola(nome, dati)
        self.show_all()
        # idle_add: GTK ha già disegnato tutto, ora nascondiamo i frame non pertinenti
        GLib.idle_add(self._aggiorna_proto_fields)

    # ------------------------------------------------------------------
    # UI principale
    # ------------------------------------------------------------------

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.set_margin_top(12)
        area.set_margin_bottom(8)

        # --- Riga nome + gruppo + protocollo ---
        top_grid = _make_grid()

        self.entry_nome = _entry(t("sd.session_name_ph"))
        _form_row(t("sd.session_name"), self.entry_nome, top_grid, 0)

        self.combo_gruppo = Gtk.ComboBoxText.new_with_entry()
        self.combo_gruppo.set_hexpand(True)
        self._carica_gruppi()
        _form_row(t("sd.group"), self.combo_gruppo, top_grid, 1)

        self.combo_proto = Gtk.ComboBoxText()
        for k in PROTOCOLLI:
            self.combo_proto.append_text(PROTO_LABEL[k])
        self.combo_proto.set_active(0)
        self.combo_proto.set_hexpand(True)
        self.combo_proto.connect("changed", lambda c: self._aggiorna_proto_fields())
        _form_row(t("sd.protocol"), self.combo_proto, top_grid, 2)

        area.pack_start(top_grid, False, False, 0)

        # --- Notebook tab ---
        self._nb = Gtk.Notebook()
        area.pack_start(self._nb, True, True, 0)

        self._nb.append_page(self._build_tab_connessione(), Gtk.Label(label=t("sd.tab.connection")))
        self._nb.append_page(self._build_tab_terminale(),   Gtk.Label(label=t("sd.tab.terminal")))
        self._nb.append_page(self._build_tab_advanced(),    Gtk.Label(label=t("sd.tab.advanced")))
        self._nb.append_page(self._build_tab_tunnel(),      Gtk.Label(label=t("sd.tab.tunnel")))
        self._nb.append_page(self._build_tab_macros(),      Gtk.Label(label=t("sd.tab.macros")))
        self._nb.append_page(self._build_tab_notes(),       Gtk.Label(label=t("sd.tab.notes")))

        # Pulsanti
        self.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        save_btn = self.add_button(t("sd.save"), Gtk.ResponseType.OK)
        save_btn.get_style_context().add_class("suggested-action")
        self.connect("response", self._on_response)

    # ------------------------------------------------------------------
    # Tab Connessione
    # ------------------------------------------------------------------

    @staticmethod
    def _conn_row(label_text: str, widget: Gtk.Widget) -> Gtk.Box:
        """Riga label+widget nascondibile come unità."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(4); box.set_margin_end(4)
        lbl = Gtk.Label(label=label_text)
        lbl.set_xalign(1.0); lbl.set_width_chars(14); lbl.set_margin_end(4)
        box.pack_start(lbl, False, False, 0)
        box.pack_start(widget, True, True, 0)
        return box

    def _build_tab_connessione(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(12); vbox.set_margin_end(12)
        vbox.set_margin_top(12);  vbox.set_margin_bottom(12)

        self.entry_host = _entry("es. 192.168.1.100")
        self._row_host = self._conn_row(t("sd.host"), self.entry_host)
        vbox.pack_start(self._row_host, False, False, 0)

        self.entry_port = _entry("22")
        self.entry_port.set_width_chars(8); self.entry_port.set_hexpand(False)
        self._row_port = self._conn_row(t("sd.port"), self.entry_port)
        vbox.pack_start(self._row_port, False, False, 0)

        self.entry_user = _entry()
        self._row_user = self._conn_row(t("sd.user"), self.entry_user)
        vbox.pack_start(self._row_user, False, False, 0)

        self.entry_password = _entry(password=True)
        self._row_password = self._conn_row(t("sd.password"), self.entry_password)
        vbox.pack_start(self._row_password, False, False, 0)

        pkey_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.entry_pkey = _entry()
        btn_pkey = Gtk.Button(label="…")
        btn_pkey.connect("clicked", self._sfoglia_pkey)
        pkey_box.pack_start(self.entry_pkey, True, True, 0)
        pkey_box.pack_start(btn_pkey, False, False, 0)
        self._row_pkey = self._conn_row(t("sd.private_key"), pkey_box)
        vbox.pack_start(self._row_pkey, False, False, 0)

        # Seriale
        self.entry_serial_dev = _entry("/dev/ttyUSB0")
        self._row_serial_dev = self._conn_row("Dispositivo:", self.entry_serial_dev)
        vbox.pack_start(self._row_serial_dev, False, False, 0)

        self.combo_baud = _combo("9600","19200","38400","57600","115200","230400","460800","921600")
        self.combo_baud.set_tooltip_text("Velocità in bit/sec. 115200 per dispositivi moderni.")
        self._row_baud = self._conn_row("Baud rate (bps):", self.combo_baud)
        vbox.pack_start(self._row_baud, False, False, 0)

        self.combo_data_bits = _combo("8","7","6","5")
        self.combo_data_bits.set_tooltip_text("Bit per carattere. Quasi sempre 8.")
        self._row_data_bits = self._conn_row("Bit di dati:", self.combo_data_bits)
        vbox.pack_start(self._row_data_bits, False, False, 0)

        self.combo_parity = _combo("None","Even","Odd","Mark","Space")
        self.combo_parity.set_tooltip_text("Parità. None=nessuno (comune), Even/Odd=pari/dispari.")
        self._row_parity = self._conn_row("Parità:", self.combo_parity)
        vbox.pack_start(self._row_parity, False, False, 0)

        self.combo_stop_bits = _combo("1","1.5","2")
        self.combo_stop_bits.set_tooltip_text("Stop bit. Quasi sempre 1.")
        self._row_stop_bits = self._conn_row("Stop bit:", self.combo_stop_bits)
        vbox.pack_start(self._row_stop_bits, False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(vbox)
        return sw

    # ------------------------------------------------------------------
    # Tab Terminale
    # ------------------------------------------------------------------

    def _build_tab_terminale(self) -> Gtk.Widget:
        grid = _make_grid()
        row = 0

        self.combo_tema = _combo(*TERMINAL_THEMES.keys())
        _form_row("Tema:", self.combo_tema, grid, row); row += 1

        self.combo_font = Gtk.ComboBoxText.new_with_entry()
        for f in ["Monospace","DejaVu Sans Mono","Hack","JetBrains Mono",
                  "Fira Code","Source Code Pro","Inconsolata","Terminus"]:
            self.combo_font.append_text(f)
        self.combo_font.set_hexpand(True)
        _form_row("Font:", self.combo_font, grid, row); row += 1

        self.spin_font_size = Gtk.SpinButton.new_with_range(6, 32, 1)
        self.spin_font_size.set_value(11)
        _form_row("Dimensione:", self.spin_font_size, grid, row); row += 1

        self.chk_log = _check("Registra output")
        grid.attach(self.chk_log, 0, row, 2, 1); row += 1

        log_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.entry_log_dir = _entry("/tmp/pcm_logs")
        btn_log = Gtk.Button(label="…")
        btn_log.connect("clicked", lambda b: self._browse_dir(self.entry_log_dir, "Log folder"))
        log_box.pack_start(self.entry_log_dir, True, True, 0)
        log_box.pack_start(btn_log, False, False, 0)
        _form_row("Cartella log:", log_box, grid, row); row += 1

        # Terminale esterno
        ext_tools = _available_tools(
            ["xterm","gnome-terminal","konsole","xfce4-terminal","alacritty","kitty","foot"],
            always_include=["Terminale Interno"]
        )
        self.combo_term_ext = _combo(*ext_tools)
        _form_row("Terminale:", self.combo_term_ext, grid, row); row += 1

        # Modalità apertura SSH
        self.combo_ssh_open = _combo("Terminale interno", "Terminale esterno")
        _form_row("Apertura SSH:", self.combo_ssh_open, grid, row); row += 1

        # Modalità apertura SFTP
        self.combo_sftp_open = _combo("Browser interno", "Browser esterno (Nautilus/Dolphin)")
        _form_row("Apertura SFTP:", self.combo_sftp_open, grid, row); row += 1

        return grid

    # ------------------------------------------------------------------
    # Tab Avanzate
    # ------------------------------------------------------------------

    @staticmethod
    def _section_frame(title: str) -> tuple:
        frame = Gtk.Frame()
        frame.set_margin_start(6); frame.set_margin_end(6)
        frame.set_margin_top(6);  frame.set_margin_bottom(2)
        lbl = Gtk.Label(); lbl.set_markup(f"<b> {title} </b>")
        frame.set_label_widget(lbl); frame.set_label_align(0.02, 0.5)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_margin_start(8); vbox.set_margin_end(8)
        vbox.set_margin_top(6);  vbox.set_margin_bottom(8)
        frame.add(vbox)
        return frame, vbox

    @staticmethod
    def _adv_row(label_text: str, widget: Gtk.Widget) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label(label=label_text)
        lbl.set_xalign(1.0); lbl.set_width_chars(16)
        box.pack_start(lbl, False, False, 0)
        box.pack_start(widget, True, True, 0)
        return box

    def _build_tab_advanced(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ── SSH / Mosh / Telnet ──────────────────────────────────────
        self._frame_ssh, vbox = self._section_frame("SSH / Mosh / Telnet")
        outer.pack_start(self._frame_ssh, False, False, 0)
        self.chk_x11         = _check("X11 forwarding")
        self.chk_compression = _check("Compressione")
        self.chk_keepalive   = _check("Keepalive")
        self.chk_strict_host = _check("Strict host check")
        self.chk_sftp_browser= _check("Browser SFTP laterale")
        for chk in [self.chk_x11, self.chk_compression, self.chk_keepalive,
                    self.chk_strict_host, self.chk_sftp_browser]:
            vbox.pack_start(chk, False, False, 0)
        self.entry_startup_cmd = _entry("es. htop")
        self.entry_jump_host   = _entry("jump.example.com")
        self.entry_jump_user   = _entry()
        self.entry_jump_port   = _entry("22")
        vbox.pack_start(self._adv_row("Startup cmd:", self.entry_startup_cmd), False, False, 0)
        vbox.pack_start(self._adv_row("Jump host:",   self.entry_jump_host),   False, False, 0)
        vbox.pack_start(self._adv_row("Jump user:",   self.entry_jump_user),   False, False, 0)
        vbox.pack_start(self._adv_row("Jump port:",   self.entry_jump_port),   False, False, 0)

        # ── RDP ──────────────────────────────────────────────────────
        self._frame_rdp, vbox = self._section_frame("RDP")
        outer.pack_start(self._frame_rdp, False, False, 0)
        rdp_clients = _available_tools(["xfreerdp3","xfreerdp","rdesktop"])
        self.combo_rdp_client = _combo(*rdp_clients)
        self.combo_rdp_auth   = _combo("NLA (default)","TLS","RDP classic")
        self.entry_rdp_domain = _entry()
        self.chk_rdp_fs       = _check("Schermo intero")
        self.chk_rdp_clip     = _check("Condividi clipboard")
        self.chk_rdp_drives   = _check("Condividi cartelle")
        self.combo_rdp_open   = _combo("Finestra esterna","Pannello interno")
        vbox.pack_start(self._adv_row("Client RDP:",     self.combo_rdp_client), False, False, 0)
        vbox.pack_start(self._adv_row("Autenticazione:", self.combo_rdp_auth),   False, False, 0)
        vbox.pack_start(self._adv_row("Dominio:",        self.entry_rdp_domain), False, False, 0)
        for chk in [self.chk_rdp_fs, self.chk_rdp_clip, self.chk_rdp_drives]:
            vbox.pack_start(chk, False, False, 0)
        vbox.pack_start(self._adv_row("Apertura RDP:", self.combo_rdp_open), False, False, 0)

        # ── VNC ──────────────────────────────────────────────────────
        self._frame_vnc, vbox = self._section_frame("VNC")
        outer.pack_start(self._frame_vnc, False, False, 0)
        self.combo_vnc_mode = _combo("Client esterno", "noVNC integrato (WebKit)")
        self.combo_vnc_mode.set_tooltip_text(
            "Client esterno: vncviewer/tigervnc/remmina/krdc installato.\n"
            "noVNC integrato: viewer HTML5 via WebKit2 (richiede novnc)."
        )
        vnc_clients = _available_tools(
            ["vncviewer","tigervnc","realvnc-viewer","remmina","krdc","xvnc4viewer"],
            always_include=[]
        ) or ["vncviewer"]
        self.combo_vnc_client  = _combo(*vnc_clients)
        self.combo_vnc_client.set_tooltip_text(
            "Client VNC trovati nel PATH. Puoi digitare un percorso personalizzato."
        )
        self.combo_vnc_color   = _combo("Truecolor (32 bpp)","High (16 bpp)","Low (8 bpp)")
        self.combo_vnc_quality = _combo("Migliore","Buona","Veloce")
        vbox.pack_start(self._adv_row("Modalità:",   self.combo_vnc_mode),   False, False, 0)
        vbox.pack_start(self._adv_row("Client VNC:", self.combo_vnc_client), False, False, 0)
        vbox.pack_start(self._adv_row("Colori:",     self.combo_vnc_color),  False, False, 0)
        vbox.pack_start(self._adv_row("Qualità:",    self.combo_vnc_quality),False, False, 0)
        self.combo_vnc_mode.connect("changed", self._on_vnc_mode_changed)
        self.chk_vnc_internal = _check("")
        self.chk_vnc_internal.set_no_show_all(True)

        # ── FTP / FTPS ───────────────────────────────────────────────
        self._frame_ftp, vbox = self._section_frame("FTP / FTPS")
        outer.pack_start(self._frame_ftp, False, False, 0)
        self.chk_ftp_tls     = _check("FTPS (TLS)")
        self.chk_ftp_passive = _check("Modalità passiva")
        self.chk_ftp_passive.set_active(True)
        self.combo_ftp_open  = _combo("Browser interno","Client esterno")
        for chk in [self.chk_ftp_tls, self.chk_ftp_passive]:
            vbox.pack_start(chk, False, False, 0)
        vbox.pack_start(self._adv_row("Apertura FTP:", self.combo_ftp_open), False, False, 0)

        # ── Wake-on-LAN ──────────────────────────────────────────────
        self._frame_wol, vbox = self._section_frame("Wake-on-LAN")
        outer.pack_start(self._frame_wol, False, False, 0)
        self.chk_wol       = _check("Attiva WoL prima della connessione")
        self.entry_wol_mac = _entry("AA:BB:CC:DD:EE:FF")
        self.spin_wol_wait = Gtk.SpinButton.new_with_range(0, 120, 1)
        self.spin_wol_wait.set_value(20)
        vbox.pack_start(self.chk_wol, False, False, 0)
        vbox.pack_start(self._adv_row("MAC address:", self.entry_wol_mac),   False, False, 0)
        vbox.pack_start(self._adv_row("Attesa (sec):", self.spin_wol_wait),  False, False, 0)

        # ── Pre-comando locale ───────────────────────────────────────
        self._frame_precmd, vbox = self._section_frame("Pre-comando locale")
        outer.pack_start(self._frame_precmd, False, False, 0)
        self.entry_pre_cmd = _entry("es. vpn-up.sh")
        self.spin_pre_cmd_timeout = Gtk.SpinButton.new_with_range(0, 120, 1)
        self.spin_pre_cmd_timeout.set_value(15)
        vbox.pack_start(self._adv_row("Comando:",       self.entry_pre_cmd),         False, False, 0)
        vbox.pack_start(self._adv_row("Timeout (sec):", self.spin_pre_cmd_timeout),  False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(outer)
        return sw

    # ------------------------------------------------------------------
    # Tab Tunnel
    # ------------------------------------------------------------------

    def _build_tab_tunnel(self) -> Gtk.Widget:
        grid = _make_grid()
        row = 0

        self.combo_tunnel_type = _combo(
            "Proxy SOCKS (-D)", "Locale (-L)", "Remoto (-R)"
        )
        _form_row("Tipo:", self.combo_tunnel_type, grid, row); row += 1

        self.entry_tunnel_lport = _entry("1080")
        _form_row("Porta locale:", self.entry_tunnel_lport, grid, row); row += 1

        self.entry_tunnel_rhost = _entry("host.interno")
        _form_row("Host remoto:", self.entry_tunnel_rhost, grid, row); row += 1

        self.entry_tunnel_rport = _entry("80")
        _form_row("Porta remota:", self.entry_tunnel_rport, grid, row); row += 1

        return grid

    # ------------------------------------------------------------------
    # Tab Macro
    # ------------------------------------------------------------------

    def _build_tab_macros(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)

        # Lista macro
        self._macro_store = Gtk.ListStore(str, str)  # nome, cmd
        self._macro_view = Gtk.TreeView(model=self._macro_store)
        self._macro_view.set_headers_visible(True)

        for i, title in enumerate(["Nome", "Comando"]):
            cell = Gtk.CellRendererText()
            cell.set_property("editable", True)
            col = Gtk.TreeViewColumn(title, cell, text=i)
            col.set_expand(True)
            self._macro_view.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(150)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._macro_view)
        box.pack_start(scroll, True, True, 0)

        # Toolbar macro
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_add = Gtk.Button(label="Aggiungi")
        btn_add.connect("clicked", self._macro_aggiungi)
        btn_del = Gtk.Button(label="Rimuovi")
        btn_del.connect("clicked", self._macro_rimuovi)
        tb.pack_start(btn_add, False, False, 0)
        tb.pack_start(btn_del, False, False, 0)
        box.pack_start(tb, False, False, 0)

        return box

    def _macro_aggiungi(self, btn):
        self._macro_store.append(["Nuova macro", ""])

    def _macro_rimuovi(self, btn):
        sel = self._macro_view.get_selection()
        model, it = sel.get_selected()
        if it:
            model.remove(it)

    # ------------------------------------------------------------------
    # Tab Note
    # ------------------------------------------------------------------

    def _build_tab_notes(self) -> Gtk.Widget:
        self._textview_notes = Gtk.TextView()
        self._textview_notes.set_wrap_mode(Gtk.WrapMode.WORD)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(self._textview_notes)
        return sw

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _on_vnc_mode_changed(self, combo):
        is_external = combo.get_active() == 0
        self.combo_vnc_client.set_visible(is_external)
        self.chk_vnc_internal.set_active(not is_external)

    def _sfoglia_pkey(self, btn):
        dlg = Gtk.FileChooserDialog(
            title="Chiave privata SSH",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons("_Annulla", Gtk.ResponseType.CANCEL, "_Apri", Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            self.entry_pkey.set_text(dlg.get_filename())
        dlg.destroy()

    def _browse_dir(self, entry: Gtk.Entry, title: str):
        dlg = Gtk.FileChooserDialog(
            title=title, parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dlg.add_buttons("_Annulla", Gtk.ResponseType.CANCEL, "_Seleziona", Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            entry.set_text(dlg.get_filename())
        dlg.destroy()

    def _carica_gruppi(self):
        profili = config_manager.load_profiles()
        gruppi = sorted({d.get("group", "") for d in profili.values() if d.get("group")})
        for g in gruppi:
            self.combo_gruppo.append_text(g)

    def _aggiorna_proto_fields(self):
        """Mostra/nasconde campi e sezioni in base al protocollo selezionato."""
        proto = PROTOCOLLI[self.combo_proto.get_active()]
        is_serial = proto == "serial"
        is_net    = not is_serial
        has_pkey  = proto in ("ssh", "sftp", "mosh")

        # Tab Connessione: righe rete vs seriale
        self._row_host.set_visible(is_net)
        self._row_port.set_visible(is_net)
        self._row_user.set_visible(is_net)
        self._row_password.set_visible(is_net)
        self._row_pkey.set_visible(has_pkey)
        self._row_serial_dev.set_visible(is_serial)
        self._row_baud.set_visible(is_serial)
        self._row_data_bits.set_visible(is_serial)
        self._row_parity.set_visible(is_serial)
        self._row_stop_bits.set_visible(is_serial)

        # Tab Avanzate: mostra solo il/i frame pertinente/i al protocollo
        self._frame_ssh.set_visible(proto in ("ssh","mosh","telnet","sftp","serial"))
        self._frame_rdp.set_visible(proto == "rdp")
        self._frame_vnc.set_visible(proto == "vnc")
        self._frame_ftp.set_visible(proto in ("ftp","sftp"))
        self._frame_wol.set_visible(is_net)
        self._frame_precmd.set_visible(True)
        # Porta di default
        default_port = {
            "ssh":"22","telnet":"23","sftp":"22","ftp":"21",
            "rdp":"3389","vnc":"5900","mosh":"22","serial":""
        }
        if not self.entry_port.get_text():
            self.entry_port.set_text(default_port.get(proto, ""))

    def _set_combo_active_text(self, combo: Gtk.ComboBoxText, text: str):
        model = combo.get_model()
        for i, row in enumerate(model):
            if row[0] == text:
                combo.set_active(i)
                return

    # ------------------------------------------------------------------
    # Popola dai dati esistenti
    # ------------------------------------------------------------------

    def _popola(self, nome: str, dati: dict):
        self.entry_nome.set_text(nome)

        gruppo = dati.get("group", "")
        child = self.combo_gruppo.get_child()
        if child:
            child.set_text(gruppo)

        proto = dati.get("protocol", "ssh")
        if proto in PROTOCOLLI:
            self.combo_proto.set_active(PROTOCOLLI.index(proto))

        self.entry_host.set_text(dati.get("host", ""))
        self.entry_port.set_text(str(dati.get("port", "")))
        self.entry_user.set_text(dati.get("user", ""))
        self.entry_password.set_text(dati.get("password", ""))
        self.entry_pkey.set_text(dati.get("private_key", ""))

        # Terminale
        self._set_combo_active_text(self.combo_tema, dati.get("term_theme", "Scuro (Default)"))
        font_child = self.combo_font.get_child()
        if font_child:
            font_child.set_text(dati.get("term_font", "Monospace"))
        self.spin_font_size.set_value(int(dati.get("term_size", 11)))
        self.entry_startup_cmd.set_text(dati.get("startup_cmd", ""))

        # Avanzate SSH
        self.chk_x11.set_active(dati.get("x11", False))
        self.chk_compression.set_active(dati.get("compression", False))
        self.chk_keepalive.set_active(dati.get("keepalive", False))
        self.chk_strict_host.set_active(dati.get("strict_host", False))
        self.chk_sftp_browser.set_active(dati.get("sftp_browser", True))

        # Jump
        self.entry_jump_host.set_text(dati.get("jump_host", ""))
        self.entry_jump_user.set_text(dati.get("jump_user", ""))
        self.entry_jump_port.set_text(str(dati.get("jump_port", "22")))

        # RDP
        self._set_combo_active_text(self.combo_rdp_client, dati.get("rdp_client", "xfreerdp"))
        self.chk_rdp_fs.set_active(dati.get("fullscreen", True))
        self.chk_rdp_clip.set_active(dati.get("redirect_clipboard", True))
        self.chk_rdp_drives.set_active(dati.get("redirect_drives", False))
        self.entry_rdp_domain.set_text(dati.get("rdp_domain", ""))
        rdp_open = dati.get("rdp_open_mode", "external")
        self.combo_rdp_open.set_active(1 if rdp_open == "internal" else 0)

        # VNC
        self.chk_vnc_internal.set_active(dati.get("vnc_internal", True))
        self._set_combo_active_text(self.combo_vnc_client, dati.get("vnc_client", "vncviewer"))

        # FTP
        self.chk_ftp_tls.set_active(dati.get("ftp_tls", False))
        self.chk_ftp_passive.set_active(dati.get("ftp_passive", True))

        # WoL
        self.chk_wol.set_active(dati.get("wol_enabled", False))
        self.entry_wol_mac.set_text(dati.get("wol_mac", ""))
        self.spin_wol_wait.set_value(int(dati.get("wol_wait", 20)))

        # Seriale
        self.entry_serial_dev.set_text(dati.get("device", "/dev/ttyUSB0"))
        self._set_combo_active_text(self.combo_baud, str(dati.get("baud", "115200")))

        # Tunnel
        self._set_combo_active_text(self.combo_tunnel_type, dati.get("tunnel_type", "Proxy SOCKS (-D)"))
        self.entry_tunnel_lport.set_text(str(dati.get("tunnel_local_port", "1080")))
        self.entry_tunnel_rhost.set_text(dati.get("tunnel_remote_host", ""))
        self.entry_tunnel_rport.set_text(str(dati.get("tunnel_remote_port", "")))

        # Modalità apertura (tab Terminale)
        self._set_combo_active_text(
            self.combo_ssh_open, dati.get("ssh_open_mode", "Terminale interno"))
        self._set_combo_active_text(
            self.combo_sftp_open, dati.get("sftp_open_mode", "Browser interno"))
        self._set_combo_active_text(
            self.combo_term_ext, dati.get("terminal_type", "Terminale Interno"))
        self.chk_log.set_active(dati.get("log_output", False))
        self.entry_log_dir.set_text(dati.get("log_dir", "/tmp/pcm_logs"))

        # VNC
        is_internal = dati.get("vnc_internal", False)
        self.combo_vnc_mode.set_active(1 if is_internal else 0)
        self.chk_vnc_internal.set_active(is_internal)
        self.combo_vnc_client.set_visible(not is_internal)
        self._set_combo_active_text(self.combo_vnc_client, dati.get("vnc_client", "vncviewer"))

        # Pre-cmd
        self.entry_pre_cmd.set_text(dati.get("pre_cmd", ""))
        self.spin_pre_cmd_timeout.set_value(int(dati.get("pre_cmd_timeout", 15)))

        # Macro
        self._macro_store.clear()
        for m in dati.get("macros", []):
            self._macro_store.append([m.get("nome", ""), m.get("cmd", "")])

        # Note
        buf = self._textview_notes.get_buffer()
        buf.set_text(dati.get("notes", ""))

    # ------------------------------------------------------------------
    # Validazione e raccolta dati
    # ------------------------------------------------------------------

    def _on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            nome = self.entry_nome.get_text().strip()
            proto = PROTOCOLLI[self.combo_proto.get_active()]
            if not nome:
                self.entry_nome.grab_focus()
                # evidenzia il campo
                ctx = self.entry_nome.get_style_context()
                ctx.add_class("error")
                GLib.timeout_add(2000, lambda: ctx.remove_class("error"))
                self.stop_emission_by_name("response")
                return
            if proto != "serial" and not self.entry_host.get_text().strip():
                self.entry_host.grab_focus()
                self.stop_emission_by_name("response")
                return

    def get_data(self) -> tuple[str, dict]:
        """Restituisce (nome, dizionario_dati)."""
        proto = PROTOCOLLI[self.combo_proto.get_active()]
        gruppo_child = self.combo_gruppo.get_child()
        gruppo = gruppo_child.get_text().strip() if gruppo_child else ""
        buf = self._textview_notes.get_buffer()
        notes = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

        macros = []
        for row in self._macro_store:
            macros.append({"nome": row[0], "cmd": row[1]})

        d = {
            "protocol":       proto,
            "group":          gruppo,
            "host":           self.entry_host.get_text().strip(),
            "port":           self.entry_port.get_text().strip(),
            "user":           self.entry_user.get_text().strip(),
            "password":       self.entry_password.get_text(),
            "private_key":    self.entry_pkey.get_text().strip(),
            "jump_host":      self.entry_jump_host.get_text().strip(),
            "jump_user":      self.entry_jump_user.get_text().strip(),
            "jump_port":      self.entry_jump_port.get_text().strip(),
            "term_theme":     self.combo_tema.get_active_text() or "Scuro (Default)",
            "term_font":      (self.combo_font.get_child().get_text()
                               if self.combo_font.get_child() else "Monospace"),
            "term_size":      int(self.spin_font_size.get_value()),
            "startup_cmd":    self.entry_startup_cmd.get_text().strip(),
            "sftp_browser":   self.chk_sftp_browser.get_active(),
            "log_output":     self.chk_log.get_active(),
            "log_dir":        self.entry_log_dir.get_text().strip(),
            "x11":            self.chk_x11.get_active(),
            "compression":    self.chk_compression.get_active(),
            "keepalive":      self.chk_keepalive.get_active(),
            "strict_host":    self.chk_strict_host.get_active(),
            "rdp_client":     self.combo_rdp_client.get_active_text() or "xfreerdp",
            "rdp_auth":       ["ntlm","tls","rdp"][self.combo_rdp_auth.get_active()],
            "fullscreen":     self.chk_rdp_fs.get_active(),
            "redirect_clipboard": self.chk_rdp_clip.get_active(),
            "redirect_drives":    self.chk_rdp_drives.get_active(),
            "rdp_domain":     self.entry_rdp_domain.get_text().strip(),
            "rdp_open_mode":  "internal" if self.combo_rdp_open.get_active() == 1 else "external",
            "vnc_internal":   self.combo_vnc_mode.get_active() == 1,
            "vnc_client":     self.combo_vnc_client.get_active_text() or "vncviewer",
            "vnc_color":      self.combo_vnc_color.get_active_text() or "Truecolor (32 bpp)",
            "vnc_quality":    self.combo_vnc_quality.get_active_text() or "Buona",
            "ssh_open_mode":  self.combo_ssh_open.get_active_text() or "Terminale interno",
            "sftp_open_mode": self.combo_sftp_open.get_active_text() or "Browser interno",
            "ftp_open_mode":  self.combo_ftp_open.get_active_text() or "Browser interno",
            "ftp_tls":        self.chk_ftp_tls.get_active(),
            "ftp_passive":    self.chk_ftp_passive.get_active(),
            "tunnel_type":    self.combo_tunnel_type.get_active_text() or "Proxy SOCKS (-D)",
            "tunnel_local_port": self.entry_tunnel_lport.get_text().strip(),
            "tunnel_remote_host": self.entry_tunnel_rhost.get_text().strip(),
            "tunnel_remote_port": self.entry_tunnel_rport.get_text().strip(),
            "device":         self.entry_serial_dev.get_text().strip(),
            "baud":           self.combo_baud.get_active_text() or "115200",
            "data_bits":      self.combo_data_bits.get_active_text() or "8",
            "parity":         self.combo_parity.get_active_text() or "None",
            "stop_bits":      self.combo_stop_bits.get_active_text() or "1",
            "terminal_type":  self.combo_term_ext.get_active_text() or "Terminale Interno",
            "wol_enabled":    self.chk_wol.get_active(),
            "wol_mac":        self.entry_wol_mac.get_text().strip(),
            "wol_wait":       int(self.spin_wol_wait.get_value()),
            "pre_cmd":        self.entry_pre_cmd.get_text().strip(),
            "pre_cmd_timeout": int(self.spin_pre_cmd_timeout.get_value()),
            "notes":          notes,
            "macros":         macros,
        }
        return self.entry_nome.get_text().strip(), d
