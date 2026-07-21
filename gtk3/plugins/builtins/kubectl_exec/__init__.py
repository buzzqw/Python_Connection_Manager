"""
Kubectl Exec Plugin for PCM - Execute commands in Kubernetes pods.
Requires: kubectl installed and configured.
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
        "k8s_namespace", "k8s_container", "k8s_context", "startup_cmd", "notes",
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

    def create_dialog_pages(self, dialog: Gtk.Dialog, profilo: dict) -> list[tuple[str, Gtk.Widget]]:
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        grid.set_margin_top(12)

        self._dlg_k8s_ns = Gtk.Entry()
        self._dlg_k8s_ns.set_text(profilo.get("k8s_namespace", ""))
        self._dlg_k8s_ns.set_placeholder_text("es. default, kube-system")
        _row(grid, 0, "Namespace:", self._dlg_k8s_ns)

        self._dlg_k8s_container = Gtk.Entry()
        self._dlg_k8s_container.set_text(profilo.get("k8s_container", ""))
        self._dlg_k8s_container.set_placeholder_text("es. nginx (vuoto = primo container)")
        _row(grid, 1, "Container:", self._dlg_k8s_container)

        self._dlg_k8s_context = Gtk.Entry()
        self._dlg_k8s_context.set_text(profilo.get("k8s_context", ""))
        self._dlg_k8s_context.set_placeholder_text("es. prod-cluster (vuoto = contesto corrente)")
        _row(grid, 2, "Context:", self._dlg_k8s_context)

        self._dlg_startup_cmd = Gtk.Entry()
        self._dlg_startup_cmd.set_text(profilo.get("startup_cmd", ""))
        self._dlg_startup_cmd.set_placeholder_text("es. /bin/bash (default /bin/sh)")
        _row(grid, 3, "Shell:", self._dlg_startup_cmd)

        info = Gtk.Label()
        info.set_markup("<small><i>L'host è il nome del pod (es. my-app-7d4f8b9c-abc12).\n"
                        "Richiede kubectl installato e configurato.</i></small>")
        info.set_xalign(0.0)
        info.set_line_wrap(True)
        info.set_margin_start(12)
        info.set_margin_top(12)
        grid.attach(info, 0, 4, 2, 1)

        return [("Kubectl", grid)]

    def on_dialog_save(self, profilo: dict) -> dict:
        if hasattr(self, '_dlg_k8s_ns'):
            profilo["k8s_namespace"] = self._dlg_k8s_ns.get_text().strip()
        if hasattr(self, '_dlg_k8s_container'):
            profilo["k8s_container"] = self._dlg_k8s_container.get_text().strip()
        if hasattr(self, '_dlg_k8s_context'):
            profilo["k8s_context"] = self._dlg_k8s_context.get_text().strip()
        if hasattr(self, '_dlg_startup_cmd'):
            profilo["startup_cmd"] = self._dlg_startup_cmd.get_text().strip()
        return profilo


plugin = KubectlExecPlugin()


def register():
    return plugin
