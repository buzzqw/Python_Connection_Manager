"""
Kubectl Exec Plugin for PCM - Execute commands in Kubernetes pods.
Requires: kubectl installed and configured.
"""
import shutil
import shlex
from typing import Optional

from plugins.plugin_base import ProtocolPlugin, PluginInfo


class KubectlExecPlugin(ProtocolPlugin):
    plugin_info = PluginInfo(
        plugin_id="kubectl_exec",
        name="Kubectl Exec",
        version="1.0.0",
        description="Execute commands in Kubernetes pods via kubectl exec",
        author="PCM Contributors",
    )
    protocol_ids = ["kubectl_exec"]
    profile_fields = {
        "host", "port", "user", "password", "private_key",
        "k8s_namespace", "k8s_container", "k8s_context", "notes",
    }
    default_port = ""

    def build_command(self, profilo: dict) -> tuple[Optional[str], str]:
        pod_name = profilo.get("host", "").strip()
        namespace = profilo.get("k8s_namespace", "").strip()
        container = profilo.get("k8s_container", "").strip()
        context = profilo.get("k8s_context", "").strip()
        startup_cmd = profilo.get("startup_cmd", "").strip() or "/bin/sh"

        if not pod_name:
            return None, "none"

        kubectl = shutil.which("kubectl") or "kubectl"
        args = [kubectl, "exec", "-it"]

        if namespace:
            args.extend(["-n", namespace])
        if container:
            args.extend(["-c", container])
        if context:
            args.extend(["--context", context])

        args.append(pod_name)
        args.extend(["--", startup_cmd])

        return " ".join(shlex.quote(a) for a in args), "embedded"

    def create_widget(self, profilo: dict, parent_window):
        return None


plugin = KubectlExecPlugin()


def register():
    return plugin
