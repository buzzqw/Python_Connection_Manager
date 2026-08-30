"""
Docker Container Plugin for PCM - Attach or exec into Docker containers.
Requires: docker CLI installed.
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


class DockerContainerPlugin(ProtocolPlugin):
    plugin_info = PluginInfo(
        plugin_id="docker_container",
        name="Docker Container",
        version="1.0.0",
        description="Attach or exec into Docker containers",
        author="PCM Contributors",
    )
    protocol_ids = ["docker_container"]
    profile_fields = {
        "host", "port", "user", "password", "private_key",
        "docker_mode", "startup_cmd", "notes",
    }
    default_port = ""

    def build_command(self, profilo: dict) -> tuple[Optional[str], str]:
        container_id = profilo.get("host", "").strip()
        mode = profilo.get("docker_mode", "exec").strip()
        user = profilo.get("user", "").strip()
        startup_cmd = profilo.get("startup_cmd", "").strip() or "/bin/sh"

        if not container_id:
            return None, "none"

        docker = shutil.which("docker") or "docker"

        if mode == "attach":
            args = [docker, "container", "attach"]
            args.append(container_id)
        else:
            try:
                command_args = shlex.split(startup_cmd)
            except ValueError as exc:
                message = f"Comando shell non valido: {exc}"
                return f"printf '%s\\n' {shlex.quote(message)}", "embedded"
            args = [docker, "exec", "-it"]
            if user:
                args.extend(["-u", user])
            args.append(container_id)
            args.extend(command_args or ["/bin/sh"])

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

        self._dlg_docker_mode = Gtk.ComboBoxText()
        self._dlg_docker_mode.append("exec", "exec — esegui comando interattivo")
        self._dlg_docker_mode.append("attach", "attach — attacca alla console")
        current_mode = profilo.get("docker_mode", "exec")
        self._dlg_docker_mode.set_active_id(current_mode if current_mode in ("exec", "attach") else "exec")
        _row(grid, 0, "Modalità:", self._dlg_docker_mode)

        self._dlg_startup_cmd = Gtk.Entry()
        self._dlg_startup_cmd.set_text(profilo.get("startup_cmd", ""))
        self._dlg_startup_cmd.set_placeholder_text("es. /bin/bash (default /bin/sh)")
        _row(grid, 1, "Shell:", self._dlg_startup_cmd)

        info = Gtk.Label()
        info.set_markup("<small><i>L'host è il nome o ID del container (es. my-app o abc123def).\n"
                        "L'utente è opzionale (-u) per eseguire comandi come utente specifico.\n"
                        "Richiede docker CLI installato.</i></small>")
        info.set_xalign(0.0)
        info.set_line_wrap(True)
        info.set_margin_start(12)
        info.set_margin_top(12)
        grid.attach(info, 0, 2, 2, 1)

        return [("Docker", grid)]

    def on_dialog_save(self, profilo: dict) -> dict:
        if hasattr(self, '_dlg_docker_mode'):
            profilo["docker_mode"] = self._dlg_docker_mode.get_active_id() or "exec"
        if hasattr(self, '_dlg_startup_cmd'):
            profilo["startup_cmd"] = self._dlg_startup_cmd.get_text().strip()
        return profilo


plugin = DockerContainerPlugin()


def register():
    return plugin
