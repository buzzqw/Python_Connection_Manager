import json
import os
import shlex
import subprocess
import tempfile

import pytest
import session_command
import winscp_widget
from rdp_widget import _build_freerdp_cmd


class TestBuildCommand:
    def test_ssh_internal(self):
        cmd, mode = session_command.build_command({
            "protocol": "ssh", "host": "example.com", "port": "22",
            "ssh_open_mode": "internal",
        })
        assert "ssh" in cmd
        assert "example.com" in cmd
        assert mode == "embedded"

    def test_ssh_external(self):
        cmd, mode = session_command.build_command({
            "protocol": "ssh", "host": "example.com",
            "ssh_open_mode": "external",
        })
        assert mode == "ssh_term_ext"

    def test_telnet(self):
        cmd, mode = session_command.build_command({
            "protocol": "telnet", "host": "test.com", "port": "23",
        })
        assert "telnet" in cmd.lower() or "echo" in cmd.lower()
        assert mode == "embedded"

    def test_rdp(self):
        cmd, mode = session_command.build_command({
            "protocol": "rdp", "host": "win.example.com",
            "rdp_open_mode": "external",
        })
        if cmd is not None:
            assert "win.example.com" in cmd
        assert mode == "external"

    def test_rdp_internal_returns_none(self):
        cmd, mode = session_command.build_command({
            "protocol": "rdp", "host": "win.example.com",
            "rdp_open_mode": "internal",
        })
        assert cmd is None
        assert mode == "rdp_embedded"

    def test_rdp_never_ignores_certificates(self):
        cmd, _ = session_command.build_command({
            "protocol": "rdp", "host": "win.example.com",
            "rdp_open_mode": "external", "rdp_ignore_cert": True,
        })
        assert "/cert:ignore" not in cmd

    def test_mosh(self):
        cmd, mode = session_command.build_command({
            "protocol": "mosh", "host": "example.com",
            "ssh_open_mode": "internal",
        })
        assert "mosh" in cmd.lower() or "echo" in cmd.lower()

    def test_serial(self):
        cmd, mode = session_command.build_command({
            "protocol": "serial", "device": "/dev/ttyUSB0", "baud": "115200",
        })
        assert mode == "serial"
        assert "ttyUSB0" in cmd

    def test_serial_picocom_applies_all_line_settings(self, monkeypatch):
        monkeypatch.setattr(session_command, "_tool_exists", lambda tool: tool == "picocom")
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: f"/usr/bin/{tool}")
        cmd, _ = session_command.build_command({
            "protocol": "serial", "device": "/dev/ttyUSB0", "baud": "9600",
            "data_bits": "7", "parity": "Even", "stop_bits": "2",
        })
        assert shlex.split(cmd) == [
            "/usr/bin/picocom", "-b", "9600", "--databits", "7",
            "--parity", "even", "--stopbits", "2", "/dev/ttyUSB0",
        ]

    def test_exec(self):
        cmd, mode = session_command.build_command({
            "protocol": "exec", "exec_cmd": "htop",
        })
        assert cmd == "htop"
        assert mode == "embedded"

    def test_exec_empty(self):
        cmd, mode = session_command.build_command({
            "protocol": "exec", "exec_cmd": "",
        })
        assert "Nessun comando" in cmd
        assert mode == "embedded"


class TestPreCommand:
    def test_wrap_pre(self):
        cmd = session_command._wrap_pre("ssh test.com", {
            "pre_cmd": "echo hello",
        })
        assert "echo hello" in cmd
        assert "ssh test.com" in cmd

    def test_wrap_pre_none(self):
        cmd = session_command._wrap_pre("ssh test.com", {})
        assert cmd == "ssh test.com"


class TestEscaping:
    def test_shlex_quote_handles_spaces(self):
        import shlex
        assert shlex.quote("file name") == "'file name'"

    def test_esc_single_quotes(self):
        result = session_command._esc("te'st")
        assert result == "te'\\''st"

    def test_vnc_quotes_endpoint_and_cleans_password_file(self, monkeypatch, tmp_path):
        marker = tmp_path / "injected"
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: "/bin/true")
        cmd = session_command._build_vnc({
            "host": f"host; touch {marker}", "port": "5900",
            "password": "secret", "vnc_client": "tigervnc",
        })
        assert "rm -f --" in cmd
        subprocess.run(["/bin/sh", "-c", cmd], check=True)
        assert not marker.exists()


class TestFileTransferSecurity:
    def test_ftps_profile_enables_tls_without_legacy_flag(self):
        from protocols import is_ftps

        assert is_ftps({"ft_protocol": "FTPS"})
        assert is_ftps({"ftp_tls": True})
        assert not is_ftps({"ft_protocol": "FTP"})

    def test_ftp_factory_enables_tls_and_passive_mode(self, monkeypatch):
        calls = []

        class FakeFtp:
            def connect(self, host, port, timeout):
                calls.append(("connect", host, port, timeout))

            def login(self, user, password):
                calls.append(("login", user, password))

            def prot_p(self):
                calls.append(("prot_p",))

            def set_pasv(self, passive):
                calls.append(("set_pasv", passive))

        monkeypatch.setattr(winscp_widget.ftplib, "FTP_TLS", FakeFtp)
        widget = winscp_widget.FtpWinScpWidget.__new__(winscp_widget.FtpWinScpWidget)
        widget._profilo = {
            "host": "ftp.example", "port": "21", "user": "alice",
            "password": "secret", "ft_protocol": "FTPS", "ftp_passive": False,
        }

        widget._ftp_factory()
        assert ("prot_p",) in calls
        assert ("set_pasv", False) in calls

    def test_external_ftp_uri_is_shell_quoted(self, monkeypatch, tmp_path):
        marker = tmp_path / "injected"
        monkeypatch.setattr(session_command, "_tool_exists", lambda tool: tool == "xdg-open")
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: "/bin/true")
        cmd = session_command._build_ftp({
            "host": f"host; touch {marker}", "port": "21", "user": "alice",
        }, modalita="browser_ext")
        subprocess.run(["/bin/sh", "-c", cmd], check=True)
        assert not marker.exists()


class TestRdpSecurity:
    def test_rdesktop_password_is_not_added_to_argv(self, monkeypatch):
        import rdp_widget

        monkeypatch.setattr(
            rdp_widget.shutil, "which",
            lambda tool: "/usr/bin/rdesktop" if tool == "rdesktop" else None,
        )
        args = _build_freerdp_cmd({
            "rdp_client": "rdesktop", "host": "rdp.example", "password": "secret",
        })
        assert not any(arg.startswith("-p") for arg in args)

    def test_xfreerdp_uses_cert_tofu_not_full_ignore(self, monkeypatch):
        """/cert:tofu valida comunque il certificato dopo il primo collegamento;
        non deve mai regredire a /cert:ignore (bypass totale)."""
        import rdp_widget
        monkeypatch.setattr(rdp_widget, "_freerdp_major_version", lambda c: 3)
        args = _build_freerdp_cmd({
            "rdp_client": "xfreerdp3", "host": "rdp.example", "password": "secret",
        })
        assert "/cert:tofu" in args
        assert "/cert:ignore" not in args

    def test_xfreerdp_drive_redirect_uses_real_home(self, monkeypatch):
        """La condivisione unità deve puntare alla home dell'utente corrente,
        non alla cartella /home che contiene le home di tutti gli utenti."""
        import rdp_widget
        monkeypatch.setattr(rdp_widget, "_freerdp_major_version", lambda c: 3)
        args = _build_freerdp_cmd({
            "rdp_client": "xfreerdp3", "host": "rdp.example",
            "redirect_drives": True,
        })
        drive_arg = next(a for a in args if a.startswith("/drive:"))
        assert drive_arg == f"/drive:home,{os.path.expanduser('~')}"
        assert drive_arg != "/drive:home,/home"

    def test_xfreerdp_multimon_reaches_real_command(self, monkeypatch):
        """rdp_monitor_mode deve incidere sul comando davvero eseguito
        (non solo sull'anteprima mostrata nell'editor sessione)."""
        import rdp_widget
        monkeypatch.setattr(rdp_widget, "_freerdp_major_version", lambda c: 3)
        args = _build_freerdp_cmd({
            "rdp_client": "xfreerdp3", "host": "rdp.example",
            "rdp_monitor_mode": "all",
        })
        assert "/multimon" in args

        args = _build_freerdp_cmd({
            "rdp_client": "xfreerdp3", "host": "rdp.example",
            "rdp_monitor_mode": "custom", "rdp_monitor_ids": "0,1",
        })
        assert "/monitors:0,1" in args
