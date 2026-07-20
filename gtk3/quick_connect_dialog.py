"""
quick_connect_dialog.py - Quick connect dialog for PCM (GTK3)

Gtk.Dialog that lets the user pick a protocol, host, port, username and password
without saving a session.  Returns the connection data tuple or None.
Includes an expandable advanced options section with protocol-specific fields.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from translations import t
import protocols


class QuickConnectDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(
            title=t("quickconn.title"), transient_for=parent,
            modal=True, destroy_with_parent=True,
        )
        self.set_default_size(460, 0)

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(16)
        area.set_margin_end(16)
        area.set_margin_top(12)
        area.set_margin_bottom(8)

        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{t('quickconn.title')}</b>\n<small>{t('quickconn.subtitle')}</small>")
        lbl.set_xalign(0.0)
        area.pack_start(lbl, False, False, 0)

        self._grid = Gtk.Grid()
        self._grid.set_row_spacing(6)
        self._grid.set_column_spacing(8)
        self._row = 0

        def _lbl(txt):
            l = Gtk.Label(label=txt)
            l.set_xalign(1.0)
            return l

        def _add_row(label, widget):
            self._grid.attach(_lbl(label), 0, self._row, 1, 1)
            self._grid.attach(widget, 1, self._row, 1, 1)
            self._row += 1
            return widget

        def _add_row_full(label, widget):
            self._grid.attach(_lbl(label), 0, self._row, 1, 1)
            self._grid.attach(widget, 1, self._row, 1, 1)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            box.pack_start(Gtk.Label(label=label), False, False, 0)
            box.pack_start(widget, True, True, 0)
            self._row += 1
            return widget

        self._combo_proto = Gtk.ComboBoxText()
        for k in protocols.PROTOCOLS:
            self._combo_proto.append_text(protocols.PROTO_LABEL[k])
        self._combo_proto.set_active(0)
        self._combo_proto.set_hexpand(True)

        self._entry_host = Gtk.Entry()
        self._entry_host.set_hexpand(True)
        self._entry_host.set_placeholder_text("hostname / IP")

        self._entry_port = Gtk.Entry()
        self._entry_port.set_text("22")
        self._entry_port.set_width_chars(6)

        self._entry_user = Gtk.Entry()
        self._entry_user.set_hexpand(True)

        self._entry_pass = Gtk.Entry()
        self._entry_pass.set_visibility(False)
        self._entry_pass.set_hexpand(True)

        # Rows base
        self._row_proto = _add_row(t("quickconn.proto_lbl"), self._combo_proto)
        self._row_host  = _add_row(t("quickconn.host_lbl"), self._entry_host)
        self._row_port  = _add_row(t("quickconn.port_lbl"), self._entry_port)
        self._row_user  = _add_row(t("quickconn.user_lbl"), self._entry_user)
        self._row_pass  = _add_row(t("quickconn.pass_lbl"), self._entry_pass)

        area.pack_start(self._grid, False, False, 0)

        # ── Opzioni avanzate (expander) ────────────────────────────────
        exp = Gtk.Expander(label=t("quickconn.advanced"))
        exp.set_margin_top(4)
        adv_grid = Gtk.Grid()
        adv_grid.set_row_spacing(6)
        adv_grid.set_column_spacing(8)
        adv_grid.set_margin_start(8)
        adv_grid.set_margin_end(8)
        adv_grid.set_margin_top(4)
        adv_grid.set_margin_bottom(4)

        adv_row = [0]

        def _adv_lbl(txt):
            l = Gtk.Label(label=txt)
            l.set_xalign(1.0)
            return l

        def _adv_add(label, widget):
            adv_grid.attach(_adv_lbl(label), 0, adv_row[0], 1, 1)
            adv_grid.attach(widget, 1, adv_row[0], 1, 1)
            adv_row[0] += 1

        # SSH
        self._chk_ssh_pkey = Gtk.CheckButton(label=t("sd.private_key"))
        self._entry_ssh_pkey = Gtk.Entry()
        self._entry_ssh_pkey.set_placeholder_text("~/.ssh/id_ed25519")
        self._entry_ssh_pkey.set_sensitive(False)
        self._entry_ssh_pkey.set_hexpand(True)
        _pkey_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        _pkey_box.pack_start(self._chk_ssh_pkey, False, False, 0)
        _pkey_box.pack_start(self._entry_ssh_pkey, True, True, 0)
        self._row_adv_pkey = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._row_adv_pkey.pack_start(_adv_lbl(t("sd.private_key")), False, False, 0)
        self._row_adv_pkey.pack_start(_pkey_box, True, True, 0)

        self._chk_ssh_pkey.connect("toggled", lambda b: self._entry_ssh_pkey.set_sensitive(b.get_active()))
        _adv_add("", self._row_adv_pkey)

        # RDP
        self._chk_rdp_fs = Gtk.CheckButton(label=t("sd.rdp.fullscreen"))
        self._chk_rdp_fs.set_active(True)
        self._row_adv_rdp_fs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._row_adv_rdp_fs.pack_start(self._chk_rdp_fs, False, False, 0)
        _adv_add("", self._row_adv_rdp_fs)

        # VNC
        self._chk_vnc_internal = Gtk.CheckButton(label=t("sd.vnc.novnc"))
        self._row_adv_vnc_int = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._row_adv_vnc_int.pack_start(self._chk_vnc_internal, False, False, 0)
        _adv_add("", self._row_adv_vnc_int)

        # Seriale
        self._entry_serial_dev = Gtk.Entry()
        self._entry_serial_dev.set_text("/dev/ttyUSB0")
        self._entry_serial_dev.set_hexpand(True)
        self._row_adv_serial_dev = _adv_lbl(t("sd.serial.device"))
        self._row_adv_serial_dev_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._row_adv_serial_dev_box.pack_start(_adv_lbl(t("sd.serial.device")), False, False, 0)
        self._row_adv_serial_dev_box.pack_start(self._entry_serial_dev, True, True, 0)

        self._combo_serial_baud = Gtk.ComboBoxText()
        for b in ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]:
            self._combo_serial_baud.append_text(b)
        self._combo_serial_baud.set_active(4)
        self._row_adv_serial_baud = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._row_adv_serial_baud.pack_start(_adv_lbl(t("sd.serial.baud")), False, False, 0)
        self._row_adv_serial_baud.pack_start(self._combo_serial_baud, True, True, 0)

        # Exec
        self._entry_exec_cmd = Gtk.Entry()
        self._entry_exec_cmd.set_hexpand(True)
        self._entry_exec_cmd.set_placeholder_text("es. htop")
        self._row_adv_exec_cmd = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._row_adv_exec_cmd.pack_start(_adv_lbl(t("sd.exec.cmd")), False, False, 0)
        self._row_adv_exec_cmd.pack_start(self._entry_exec_cmd, True, True, 0)

        exp.add(adv_grid)
        area.pack_start(exp, False, False, 0)

        self._lbl_err = Gtk.Label(label="")
        self._lbl_err.set_xalign(0.0)
        area.pack_start(self._lbl_err, False, False, 0)

        btn_conn = self.add_button(t("quickconn.connect"), Gtk.ResponseType.OK)
        btn_conn.get_style_context().add_class("suggested-action")
        self.add_button(t("dialog.cancel"), Gtk.ResponseType.CANCEL)

        # Salviamo riferimenti per visibilità
        self._adv_pkey     = self._row_adv_pkey
        self._adv_rdp_fs   = self._row_adv_rdp_fs
        self._adv_vnc_int  = self._row_adv_vnc_int
        self._adv_serial_dev = self._row_adv_serial_dev_box
        self._adv_serial_baud = self._row_adv_serial_baud
        self._adv_exec_cmd   = self._row_adv_exec_cmd

        self._combo_proto.connect("changed", self._on_proto_changed)
        self._on_proto_changed(self._combo_proto)

    def _on_proto_changed(self, combo):
        proto = protocols.PROTOCOLS[combo.get_active()]
        is_net = proto not in ("serial", "exec")
        is_serial = proto == "serial"
        is_exec = proto == "exec"
        is_ssh = proto in ("ssh", "mosh", "file_transfer")
        is_rdp = proto == "rdp"
        is_vnc = proto == "vnc"

        for w in (self._entry_host, self._entry_user, self._entry_pass):
            w.set_sensitive(is_net)
        self._row_host.set_visible(is_net)
        self._row_port.set_visible(not is_exec)
        self._row_user.set_visible(is_net)
        self._row_pass.set_visible(is_net)

        self._adv_pkey.set_visible(is_ssh)
        self._adv_rdp_fs.set_visible(is_rdp)
        self._adv_vnc_int.set_visible(is_vnc)
        self._adv_serial_dev.set_visible(is_serial)
        self._adv_serial_baud.set_visible(is_serial)
        self._adv_exec_cmd.set_visible(is_exec)

        if combo.get_active() >= 0:
            default = protocols.DEFAULT_PORT.get(proto, "")
            self._entry_port.set_text(default)

    def run_and_get(self):
        self.show_all()
        response = self.run()

        if response != Gtk.ResponseType.OK:
            self.destroy()
            return None

        proto_idx = self._combo_proto.get_active()
        proto = protocols.PROTOCOLS[proto_idx] if proto_idx >= 0 else "ssh"
        proto_lbl = protocols.PROTO_LABEL.get(proto, proto)

        host = self._entry_host.get_text().strip()

        if proto not in ("serial", "exec") and not host:
            self._lbl_err.set_markup(
                f"<span foreground='red'>{t('quickconn.no_host')}</span>"
            )
            self.destroy()
            return None

        dati = {
            "protocol": proto,
            "host": host,
            "port": self._entry_port.get_text().strip(),
            "user": self._entry_user.get_text().strip(),
            "password": self._entry_pass.get_text(),
            "sftp_browser": False,
        }

        if proto in ("ssh", "mosh", "file_transfer"):
            pkey = self._entry_ssh_pkey.get_text().strip()
            if pkey:
                dati["private_key"] = pkey
        if proto == "rdp":
            dati["fullscreen"] = self._chk_rdp_fs.get_active()
        if proto == "vnc":
            dati["vnc_internal"] = self._chk_vnc_internal.get_active()
        if proto == "serial":
            dati["device"] = self._entry_serial_dev.get_text().strip()
            dati["baud"] = self._combo_serial_baud.get_active_text() or "115200"
            nome_tab = f"{proto_lbl}: {dati['device']}"
        elif proto == "exec":
            dati["exec_cmd"] = self._entry_exec_cmd.get_text().strip()
            nome_tab = f"Exec: {dati['exec_cmd'][:30]}" if dati["exec_cmd"] else "Exec"
        else:
            nome_tab = f"{proto_lbl}: {host}"

        self.destroy()
        return proto, nome_tab, dati
