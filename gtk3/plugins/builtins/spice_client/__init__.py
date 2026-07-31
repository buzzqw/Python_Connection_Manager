"""
SPICE Client Plugin for PCM - Connect to KVM/QEMU virtual machines via SPICE.
Requires: spicy (spice-gtk) or remote-viewer (virt-viewer) installed.
"""
import shutil
import shlex
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from plugins.plugin_base import ProtocolPlugin, PluginInfo


def _row(grid, row, label_text, widget):
    lbl = Gtk.Label(label=label_text)
    lbl.set_xalign(1.0)
    lbl.set_margin_end(6)
    grid.attach(lbl, 0, row, 1, 1)
    grid.attach(widget, 1, row, 1, 1)
    widget.set_hexpand(True)


class SpicePlugin(ProtocolPlugin):
    plugin_info = PluginInfo(
        plugin_id="spice_client",
        name="SPICE",
        version="1.0.0",
        description="Connect to KVM/QEMU virtual machines via SPICE protocol",
        author="PCM Contributors",
    )
    protocol_ids = ["spice"]
    profile_fields = {
        "host", "port", "user", "password",
        "spice_tls", "notes",
    }
    default_port = "5901"

    def build_command(self, profilo: dict) -> tuple[Optional[str], str]:
        host = profilo.get("host", "").strip()
        port = profilo.get("port", "5901").strip()
        tls = profilo.get("spice_tls", False)

        if not host:
            return None, "none"

        uri = f"spice://{host}:{port}"
        if tls:
            uri = f"spice+tls://{host}:{port}"

        for client_name in ["spicy", "remote-viewer", "virt-viewer"]:
            client = shutil.which(client_name)
            if client:
                return f"{shlex.quote(client)} {shlex.quote(uri)}", "external"

        return f"xdg-open {shlex.quote(uri)}", "external"

    def create_widget(self, profilo: dict, parent_window):
        return None

    def create_dialog_pages(self, dialog: Gtk.Dialog, profilo: dict) -> list[tuple[str, Gtk.Widget]]:
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        grid.set_margin_top(12)

        self._dlg_spice_tls = Gtk.CheckButton(label="Usa TLS (spice+tls://)")
        self._dlg_spice_tls.set_active(profilo.get("spice_tls", False))
        grid.attach(self._dlg_spice_tls, 0, 0, 2, 1)

        info = Gtk.Label()
        info.set_markup("<small><i>La porta default è 5901 per la prima VM.\n"
                        "Richiede spicy (spice-gtk) o remote-viewer (virt-viewer).</i></small>")
        info.set_xalign(0.0)
        info.set_line_wrap(True)
        info.set_margin_start(12)
        info.set_margin_top(12)
        grid.attach(info, 0, 1, 2, 1)

        return [("SPICE", grid)]

    def on_dialog_save(self, profilo: dict) -> dict:
        if hasattr(self, '_dlg_spice_tls'):
            profilo["spice_tls"] = self._dlg_spice_tls.get_active()
        return profilo


plugin = SpicePlugin()


def register():
    return plugin
