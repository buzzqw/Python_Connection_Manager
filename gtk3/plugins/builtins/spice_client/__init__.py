"""
SPICE Client Plugin for PCM - Connect to KVM/QEMU virtual machines via SPICE.
Requires: spicy (spice-gtk) or remote-viewer (virt-viewer) installed.
"""
import shutil
import shlex
from typing import Optional

from plugins.plugin_base import ProtocolPlugin, PluginInfo


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
                return f'"{client}" "{uri}"', "external"

        return f'xdg-open "{uri}"', "external"

    def create_widget(self, profilo: dict, parent_window):
        return None


plugin = SpicePlugin()


def register():
    return plugin
