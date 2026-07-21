"""
Docker Container Plugin for PCM - Attach or exec into Docker containers.
Requires: docker CLI installed.
"""
import shutil
import shlex
from typing import Optional

from plugins.plugin_base import ProtocolPlugin, PluginInfo


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
        "docker_mode", "notes",
    }
    default_port = ""

    def build_command(self, profilo: dict) -> tuple[Optional[str], str]:
        container_id = profilo.get("host", "").strip()
        mode = profilo.get("docker_mode", "exec").strip()  # "exec" or "attach"
        user = profilo.get("user", "").strip()
        startup_cmd = profilo.get("startup_cmd", "").strip() or "/bin/sh"

        if not container_id:
            return None, "none"

        docker = shutil.which("docker") or "docker"

        if mode == "attach":
            args = [docker, "container", "attach"]
            if container_id:
                args.append(container_id)
        else:
            args = [docker, "exec", "-it"]
            if user:
                args.extend(["-u", user])
            args.append(container_id)
            if startup_cmd:
                args.append(startup_cmd)
            else:
                args.append("/bin/sh")

        return " ".join(shlex.quote(a) for a in args), "embedded"

    def create_widget(self, profilo: dict, parent_window):
        return None


plugin = DockerContainerPlugin()


def register():
    return plugin
