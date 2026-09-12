"""GTK dialog for bounded TCP discovery and profile import."""

from __future__ import annotations

import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import port_scanner
from translations import t


class PortScanDialog(Gtk.Dialog):
    def __init__(self, parent, on_import):
        super().__init__(
            title=t("port_scan.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self._on_import_callback = on_import
        self._stop_event = threading.Event()
        self._scanning = False
        self._closed = False
        self.set_default_size(650, 500)
        self._build_ui()
        self.show_all()

    def _build_ui(self):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12); area.set_margin_end(12)
        area.set_margin_top(12); area.set_margin_bottom(8)

        grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        fields = []
        for row, (label, value) in enumerate([
            (t("port_scan.first_ip"), "192.168.1.1"),
            (t("port_scan.last_ip"), "192.168.1.254"),
            (t("port_scan.ports"), "22,23,3389,5900"),
            (t("port_scan.timeout"), "0.5"),
        ]):
            lbl = Gtk.Label(label=f"{label}:", xalign=1.0)
            entry = Gtk.Entry(text=value)
            entry.set_hexpand(True)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(entry, 1, row, 1, 1)
            fields.append(entry)
        self._first_ip, self._last_ip, self._ports, self._timeout = fields

        self._protocol = Gtk.ComboBoxText()
        self._protocols = [("ssh", "SSH"), ("rdp", "RDP"), ("vnc", "VNC"), ("telnet", "Telnet")]
        for _value, label in self._protocols:
            self._protocol.append_text(label)
        self._protocol.set_active(0)
        grid.attach(Gtk.Label(label=f"{t('port_scan.protocol')}:", xalign=1.0), 0, 4, 1, 1)
        grid.attach(self._protocol, 1, 4, 1, 1)
        area.pack_start(grid, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._scan_button = Gtk.Button(label=t("port_scan.start"))
        self._scan_button.get_style_context().add_class("suggested-action")
        self._scan_button.connect("clicked", lambda _button: self._start_scan())
        self._stop_button = Gtk.Button(label=t("port_scan.stop"))
        self._stop_button.set_sensitive(False)
        self._stop_button.connect("clicked", lambda _button: self._stop_scan())
        buttons.pack_start(self._scan_button, False, False, 0)
        buttons.pack_start(self._stop_button, False, False, 0)
        area.pack_start(buttons, False, False, 0)

        self._store = Gtk.ListStore(bool, str, str)
        view = Gtk.TreeView(model=self._store)
        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self._toggle_result)
        view.append_column(Gtk.TreeViewColumn(t("port_scan.select"), toggle, active=0))
        view.append_column(Gtk.TreeViewColumn("Host", Gtk.CellRendererText(), text=1))
        view.append_column(Gtk.TreeViewColumn("Port", Gtk.CellRendererText(), text=2))
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(view)
        area.pack_start(scroll, True, True, 0)

        self._status = Gtk.Label(label=t("port_scan.ready"))
        self._status.set_xalign(0.0)
        area.pack_start(self._status, False, False, 0)

        action_area = self.get_action_area()
        self._import_button = Gtk.Button(label=t("port_scan.import"))
        self._import_button.connect("clicked", lambda _button: self._import_selected())
        action_area.pack_start(self._import_button, False, False, 0)
        self.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)
        self.connect("response", self._on_response)

    def _toggle_result(self, _renderer, path):
        iterator = self._store.get_iter(path)
        if iterator is not None:
            self._store[iterator][0] = not self._store[iterator][0]

    def _start_scan(self):
        try:
            ports = port_scanner.parse_ports(self._ports.get_text())
            timeout = float(self._timeout.get_text().strip())
            port_scanner.parse_hosts(self._first_ip.get_text(), self._last_ip.get_text())
        except (port_scanner.ScanError, ValueError) as exc:
            self._status.set_text(str(exc))
            return

        self._store.clear()
        self._stop_event.clear()
        self._scanning = True
        self._scan_button.set_sensitive(False)
        self._stop_button.set_sensitive(True)
        self._status.set_text(t("port_scan.scanning"))

        def worker():
            count = 0
            try:
                for result in port_scanner.scan_range(
                    self._first_ip.get_text(), self._last_ip.get_text(), ports,
                    timeout=timeout, stop_event=self._stop_event,
                ):
                    count += 1
                    GLib.idle_add(self._append_result, result)
            except port_scanner.ScanError as exc:
                GLib.idle_add(self._scan_finished, str(exc), count)
                return
            GLib.idle_add(self._scan_finished, None, count)

        threading.Thread(target=worker, daemon=True).start()

    def _append_result(self, result):
        if self._closed:
            return False
        self._store.append([True, result["host"], str(result["port"])])
        return False

    def _scan_finished(self, error, count):
        if self._closed:
            return False
        self._scanning = False
        self._scan_button.set_sensitive(True)
        self._stop_button.set_sensitive(False)
        if error:
            self._status.set_text(error)
        else:
            self._status.set_text(t("port_scan.finished").format(count=count))
        return False

    def _stop_scan(self):
        self._stop_event.set()
        self._status.set_text(t("port_scan.stopping"))

    def _import_selected(self):
        protocol = self._protocols[self._protocol.get_active()][0]
        results = [
            {"host": row[1], "port": int(row[2])}
            for row in self._store if row[0]
        ]
        self._on_import_callback(results, protocol)
        self._store.clear()
        self._status.set_text(t("port_scan.imported").format(count=len(results)))

    def _on_response(self, _dialog, response):
        if response == Gtk.ResponseType.CLOSE:
            self._closed = True
            self._stop_event.set()
            self.hide()
