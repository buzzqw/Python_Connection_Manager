"""
AWS SSM Plugin for PCM - Connect to EC2 instances via AWS Systems Manager.
Requires: awscli + session-manager-plugin installed on the system.
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


class AwsSsmPlugin(ProtocolPlugin):
    plugin_info = PluginInfo(
        plugin_id="aws_ssm",
        name="AWS SSM",
        version="1.0.0",
        description="Connect to EC2 instances via AWS Systems Manager Session Manager",
        author="PCM Contributors",
    )
    protocol_ids = ["aws_ssm"]
    profile_fields = {
        "host", "port", "user", "password", "private_key",
        "aws_region", "aws_profile", "startup_cmd", "notes",
    }
    default_port = ""

    def build_command(self, profilo: dict) -> tuple[Optional[str], str]:
        instance_id = profilo.get("host", "").strip()
        region = profilo.get("aws_region", "").strip()
        profile = profilo.get("aws_profile", "").strip()
        startup_cmd = profilo.get("startup_cmd", "").strip()

        if not instance_id:
            return None, "none"

        ssm_exe = shutil.which("aws") or "aws"
        args = [ssm_exe, "ssm", "start-session", "--target", instance_id]

        if region:
            args.extend(["--region", region])
        if profile:
            args.extend(["--profile", profile])
        if startup_cmd:
            args.extend(["--document-name", "AWS-StartInteractiveCommand",
                         "--parameters", f'{{"command":["{shlex.quote(startup_cmd)}"]}}'])

        return " ".join(shlex.quote(a) for a in args), "embedded"

    def create_widget(self, profilo: dict, parent_window):
        return None

    def create_dialog_pages(self, dialog: Gtk.Dialog, profilo: dict) -> list[tuple[str, Gtk.Widget]]:
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        grid.set_margin_top(12)

        self._dlg_aws_region = Gtk.Entry()
        self._dlg_aws_region.set_text(profilo.get("aws_region", ""))
        self._dlg_aws_region.set_placeholder_text("es. us-east-1")
        _row(grid, 0, "Regione AWS:", self._dlg_aws_region)

        self._dlg_aws_profile = Gtk.Entry()
        self._dlg_aws_profile.set_text(profilo.get("aws_profile", ""))
        self._dlg_aws_profile.set_placeholder_text("es. production (vuoto = default)")
        _row(grid, 1, "Profilo AWS:", self._dlg_aws_profile)

        self._dlg_startup_cmd = Gtk.Entry()
        self._dlg_startup_cmd.set_text(profilo.get("startup_cmd", ""))
        self._dlg_startup_cmd.set_placeholder_text("es. bash -l (vuoto = shell interattiva)")
        _row(grid, 2, "Comando avvio:", self._dlg_startup_cmd)

        info = Gtk.Label()
        info.set_markup("<small><i>L'host è l'ID dell'istanza EC2 (es. i-0abc123def456).\n"
                        "Richiede awscli + session-manager-plugin installati.</i></small>")
        info.set_xalign(0.0)
        info.set_line_wrap(True)
        info.set_margin_start(12)
        info.set_margin_top(12)
        grid.attach(info, 0, 3, 2, 1)

        return [("AWS SSM", grid)]

    def on_dialog_save(self, profilo: dict) -> dict:
        if hasattr(self, '_dlg_aws_region'):
            profilo["aws_region"] = self._dlg_aws_region.get_text().strip()
        if hasattr(self, '_dlg_aws_profile'):
            profilo["aws_profile"] = self._dlg_aws_profile.get_text().strip()
        if hasattr(self, '_dlg_startup_cmd'):
            profilo["startup_cmd"] = self._dlg_startup_cmd.get_text().strip()
        return profilo


plugin = AwsSsmPlugin()


def register():
    return plugin
