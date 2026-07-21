"""
AWS SSM Plugin for PCM - Connect to EC2 instances via AWS Systems Manager.
Requires: awscli + session-manager-plugin installed on the system.
"""
import shutil
import shlex
from typing import Optional

from plugins.plugin_base import ProtocolPlugin, PluginInfo


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
        "aws_region", "aws_profile", "notes",
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
        return None  # uses terminal


plugin = AwsSsmPlugin()


def register():
    return plugin
