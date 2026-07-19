"""
quick_connect_dialog.py - Quick connect dialog for PCM (GTK3)

Gtk.Dialog that lets the user pick a protocol, host, port, username and password
without saving a session.  Returns the connection data tuple or None.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from translations import t
from session_dialog import PROTOCOLLI, PROTO_LABEL


class QuickConnectDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(
            title=t("quickconn.title"), transient_for=parent,
            modal=True, destroy_with_parent=True,
        )
        self.set_default_size(420, 0)

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

        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(8)

        def _lbl(txt):
            l = Gtk.Label(label=txt)
            l.set_xalign(1.0)
            return l

        self._combo_proto = Gtk.ComboBoxText()
        for k in PROTOCOLLI:
            if k != "exec":
                self._combo_proto.append_text(PROTO_LABEL[k])
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

        grid.attach(_lbl(t("quickconn.proto_lbl")), 0, 0, 1, 1)
        grid.attach(self._combo_proto, 1, 0, 1, 1)
        grid.attach(_lbl(t("quickconn.host_lbl")), 0, 1, 1, 1)
        grid.attach(self._entry_host, 1, 1, 1, 1)
        grid.attach(_lbl(t("quickconn.port_lbl")), 0, 2, 1, 1)
        grid.attach(self._entry_port, 1, 2, 1, 1)
        grid.attach(_lbl(t("quickconn.user_lbl")), 0, 3, 1, 1)
        grid.attach(self._entry_user, 1, 3, 1, 1)
        grid.attach(_lbl(t("quickconn.pass_lbl")), 0, 4, 1, 1)
        grid.attach(self._entry_pass, 1, 4, 1, 1)
        area.pack_start(grid, False, False, 0)

        self._lbl_err = Gtk.Label(label="")
        self._lbl_err.set_xalign(0.0)
        area.pack_start(self._lbl_err, False, False, 0)

        btn_conn = self.add_button(t("quickconn.connect"), Gtk.ResponseType.OK)
        btn_conn.get_style_context().add_class("suggested-action")
        self.add_button(t("dialog.cancel"), Gtk.ResponseType.CANCEL)

        _default_port = {
            "SSH": "22", "Telnet": "23", "FTP/SFTP": "22",
            "RDP": "3389", "VNC": "5900", "Mosh": "22", "Seriale": "",
        }

        def _on_proto(_c):
            lbl_p = PROTO_LABEL.get(PROTOCOLLI[self._combo_proto.get_active()], "")
            self._entry_port.set_text(_default_port.get(lbl_p, ""))

        self._combo_proto.connect("changed", _on_proto)

    def run_and_get(self):
        self.show_all()
        response = self.run()

        if response != Gtk.ResponseType.OK:
            self.destroy()
            return None

        host = self._entry_host.get_text().strip()
        if not host:
            self._lbl_err.set_markup(
                f"<span foreground='red'>{t('quickconn.no_host')}</span>"
            )
            self.destroy()
            return None

        proto_idx = self._combo_proto.get_active()
        proto_lbls = [PROTO_LABEL[k] for k in PROTOCOLLI if k != "exec"]
        proto_lbl = proto_lbls[proto_idx] if proto_idx >= 0 else "SSH"
        proto = next(
            (k for k, v in PROTO_LABEL.items() if v == proto_lbl), "ssh"
        )

        dati = {
            "protocol": proto,
            "host": host,
            "port": self._entry_port.get_text().strip(),
            "user": self._entry_user.get_text().strip(),
            "password": self._entry_pass.get_text(),
            "sftp_browser": False,
        }
        nome_tab = f"{proto_lbl}: {host}"

        self.destroy()
        return proto, nome_tab, dati
