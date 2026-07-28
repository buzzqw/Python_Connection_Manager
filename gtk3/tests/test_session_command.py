import json
import tempfile

import pytest
import session_command


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
