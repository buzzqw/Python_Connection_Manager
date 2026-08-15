import json
import os
import shlex
import subprocess
import tempfile

import pytest
import config_manager
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

    def test_ssh_keepalive_interval_from_session_is_honored(self):
        """Lo spinner 'keepalive_interval' nell'editor sessione (0 = disabilitato)
        deve incidere sul comando reale: prima veniva salvato nel profilo ma
        nessun builder lo leggeva mai."""
        cmd = session_command._build_ssh({
            "host": "example.com", "keepalive": True, "keepalive_interval": 45,
        })
        assert "-o ServerAliveInterval=45" in cmd

    def test_ssh_keepalive_interval_zero_disables_it(self):
        cmd = session_command._build_ssh({
            "host": "example.com", "keepalive": True, "keepalive_interval": 0,
        })
        assert "ServerAliveInterval" not in cmd

    def test_mosh_keepalive_interval_from_session_is_honored(self, monkeypatch):
        monkeypatch.setattr(session_command, "_tool_exists", lambda cmd_id: True)
        cmd = session_command._build_mosh({
            "host": "example.com", "keepalive": True, "keepalive_interval": 45,
        })
        assert "ServerAliveInterval=45" in cmd

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

    def test_serial_mark_space_parity_rejected_instead_of_crashing_picocom(self, monkeypatch):
        """picocom (v3.1, verificato empiricamente) accetta solo none/even/odd
        per --parity: legge solo la prima lettera del valore e la confronta
        con n/e/o. "Mark"/"Space" (prima lettera m/s) non hanno alcun
        equivalente e prima venivano comunque passati, facendo fallire
        picocom con 'Invalid --parity' invece di aprire la sessione."""
        monkeypatch.setattr(session_command, "_tool_exists", lambda tool: tool == "picocom")
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: f"/usr/bin/{tool}")
        for parity in ("Mark", "Space"):
            cmd, _ = session_command.build_command({
                "protocol": "serial", "device": "/dev/ttyUSB0", "parity": parity,
            })
            assert "picocom" not in cmd
            assert parity in cmd

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


class TestVncPasswordObfuscation:
    def test_returns_none_without_vncpasswd(self, monkeypatch):
        monkeypatch.setattr(session_command.shutil, "which", lambda tool: None)
        assert session_command._vnc_obfuscate_password("secret") is None

    def test_uses_vncpasswd_binary_not_plaintext(self, monkeypatch):
        """-passwd si aspetta l'output di 'vncpasswd -f' (formato offuscato),
        non la password in chiaro: verifica che venga davvero invocato quel
        comando con la password su stdin, e che l'output binario non sia la
        password in chiaro riscritta tale e quale."""
        monkeypatch.setattr(session_command.shutil, "which",
                             lambda tool: "/usr/bin/vncpasswd" if tool == "vncpasswd" else None)

        captured = {}

        def fake_run(args, input, stdout, stderr, timeout, check):
            captured["args"] = args
            captured["input"] = input
            return subprocess.CompletedProcess(args, 0, stdout=b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22")

        monkeypatch.setattr(session_command.subprocess, "run", fake_run)
        result = session_command._vnc_obfuscate_password("secret")
        assert captured["args"] == ["/usr/bin/vncpasswd", "-f"]
        assert captured["input"] == b"secret"
        assert result == b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22"
        assert result != b"secret"


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
        monkeypatch.setattr(session_command, "_vnc_obfuscate_password",
                             lambda pwd: b"\x00" * 8)
        cmd = session_command._build_vnc({
            "host": f"host; touch {marker}", "port": "5900",
            "password": "secret", "vnc_client": "tigervnc",
        })
        assert "rm -f --" in cmd
        subprocess.run(["/bin/sh", "-c", cmd], check=True)
        assert not marker.exists()

    def test_vnc_without_vncpasswd_skips_password_file(self, monkeypatch, tmp_path):
        """Senza vncpasswd non si deve scrivere un file password in chiaro:
        -passwd si aspetta il formato offuscato, un file in chiaro non
        funzionerebbe comunque (bug precedente) e romperebbe la connessione
        ogni volta che è impostata una password."""
        marker = tmp_path / "injected"
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: "/bin/true")
        monkeypatch.setattr(session_command, "_vnc_obfuscate_password", lambda pwd: None)
        cmd = session_command._build_vnc({
            "host": f"host; touch {marker}", "port": "5900",
            "password": "secret", "vnc_client": "tigervnc",
        })
        assert "-passwd" not in cmd
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

    def test_sftp_panel_relaxed_strict_host_asks_instead_of_autoadd(self):
        """Con strict_host disattivato il client NON deve usare AutoAddPolicy
        né WarningPolicy (accettano host sconosciuti/modificati in modo
        silenzioso, esponendo a MITM): deve chiedere conferma e rifiutare la
        connessione se l'utente non conferma. Solo strict=True usa
        RejectPolicy."""
        import paramiko

        class FakeKey:
            def get_name(self):
                return "ssh-rsa"

        # strict=False -> policy di conferma (non Auto/Warning/Reject)
        client = session_command.make_ssh_client({"strict_host": False})
        policy = client._policy
        assert not isinstance(policy, paramiko.AutoAddPolicy)
        assert not isinstance(policy, paramiko.WarningPolicy)
        assert not isinstance(policy, paramiko.RejectPolicy)

        # conferma rifiutata -> connessione bloccata
        with pytest.raises(paramiko.SSHException):
            policy.missing_host_key(client, "new-host.example", FakeKey())

        # conferma accettata -> chiave memorizzata senza errori
        client2 = session_command.make_ssh_client(
            {"strict_host": False}, confirm_host_key=lambda h, k: True)
        client2.get_host_keys().save = lambda *a, **k: None
        client2._policy.missing_host_key(client2, "new-host.example", FakeKey())
        assert client2.get_host_keys().lookup("new-host.example") is not None

        # strict=True -> RejectPolicy
        client3 = session_command.make_ssh_client({"strict_host": True})
        assert isinstance(client3._policy, paramiko.RejectPolicy)

    def test_external_ftp_uri_is_shell_quoted(self, monkeypatch, tmp_path):
        marker = tmp_path / "injected"
        monkeypatch.setattr(session_command, "_tool_exists", lambda tool: tool == "xdg-open")
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: "/bin/true")
        cmd = session_command._build_ftp({
            "host": f"host; touch {marker}", "port": "21", "user": "alice",
        }, modalita="browser_ext")
        subprocess.run(["/bin/sh", "-c", cmd], check=True)
        assert not marker.exists()

    @staticmethod
    def _cleanup_pcm_tmp(cmd: str):
        """I builder scrivono un file privato reale in ~/.cache/pcm; nei
        test che ispezionano solo la stringa (senza eseguirla) il comando
        di pulizia embedded non gira mai, quindi va rimosso a mano per non
        lasciare file nella cache reale dell'utente a ogni run dei test."""
        import re
        for m in re.finditer(r"(\S*pcm_(?:ftp|lftp)_\S+\.tmp)", cmd):
            path = m.group(1).strip("'\"")
            if os.path.exists(path):
                os.unlink(path)

    def test_ftp_lftp_password_not_in_argv(self, monkeypatch, tmp_path):
        """La password non deve comparire nella riga di comando: sarebbe
        visibile a chiunque sulla macchina tramite 'ps aux' per tutta la
        durata del processo. Deve invece finire in un file privato (0600)
        referenziato da 'source', letto e poi ripulito da lftp stesso."""
        monkeypatch.setattr(session_command, "_tool_exists", lambda tool: tool == "lftp")
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: "/usr/bin/lftp")
        cmd = session_command._build_ftp({
            "host": "ftp.example.com", "port": "21",
            "user": "alice", "password": "S3cr3t!",
        }, modalita="term_int")
        try:
            assert "S3cr3t!" not in cmd
            assert "source " in cmd
            assert "rm -f --" in cmd
        finally:
            self._cleanup_pcm_tmp(cmd)

    def test_sftp_cli_lftp_password_not_in_argv(self, monkeypatch):
        monkeypatch.setattr(session_command, "_tool_exists", lambda tool: tool == "lftp")
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: "/usr/bin/lftp")
        cmd = session_command._build_sftp_cli({
            "host": "sftp.example.com", "port": "22",
            "user": "alice", "password": "S3cr3t!",
        })
        try:
            assert "S3cr3t!" not in cmd
            assert "source " in cmd
        finally:
            self._cleanup_pcm_tmp(cmd)

    def test_ftp_plain_binary_password_not_in_argv(self, monkeypatch):
        monkeypatch.setattr(session_command, "_tool_exists", lambda tool: tool == "ftp")
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: "/usr/bin/ftp")
        cmd = session_command._build_ftp({
            "host": "ftp.example.com", "port": "21",
            "user": "alice", "password": "S3cr3t!",
        }, modalita="term_int")
        try:
            assert "S3cr3t!" not in cmd
            assert " < " in cmd
        finally:
            self._cleanup_pcm_tmp(cmd)

    def test_lftp_script_file_actually_contains_credentials(self, monkeypatch):
        """Verifica end-to-end che il file referenziato da 'source' contenga
        davvero il comando 'open' con le credenziali, e che il comando lo
        cancelli dopo l'uso."""
        monkeypatch.setattr(session_command, "_tool_exists", lambda tool: tool == "lftp")
        monkeypatch.setattr(session_command, "_get_tool", lambda tool: "/bin/true")
        cmd = session_command._build_ftp({
            "host": "ftp.example.com", "port": "21",
            "user": "alice", "password": "sekret123",
        }, modalita="term_int")

        import re
        m = re.search(r"source (\S+)'", cmd)
        assert m
        script_path = m.group(1)
        with open(script_path) as f:
            content = f.read()
        assert "sekret123" in content
        assert content.startswith("open ftp://")

        subprocess.run(["/bin/sh", "-c", cmd], check=True)
        assert not os.path.exists(script_path)


class TestRdpUnifiedBuilder:
    """Anteprima (session_command._build_rdp) e connessione reale
    (rdp_widget._build_freerdp_cmd / build_rdp_args) condividono ora la
    stessa funzione: verifica che non possano più divergere."""

    def test_preview_matches_real_command_args(self, monkeypatch):
        import rdp_widget
        monkeypatch.setattr(rdp_widget, "_freerdp_major_version", lambda exe: 3)
        monkeypatch.setattr(rdp_widget.shutil, "which", lambda tool: f"/usr/bin/{tool}")

        profile = {
            "protocol": "rdp", "host": "win.example.com", "port": "3389",
            "user": "alice", "password": "sekret", "rdp_domain": "CORP",
            "rdp_client": "xfreerdp3", "fullscreen": True,
            "redirect_clipboard": True, "redirect_drives": True,
            "rdp_monitor_mode": "custom", "rdp_monitor_ids": "0,1",
        }
        preview = session_command._build_rdp(profile)
        real = " ".join(_build_freerdp_cmd(profile))

        # argv[0] can differ (preview resolves an absolute path via _get_tool,
        # the real launch relies on PATH); every other flag must be identical.
        assert preview.split(None, 1)[1] == real.split(None, 1)[1]

    def test_custom_tool_path_is_honored_by_real_connection(self, monkeypatch, tmp_path):
        """Un path custom impostato in Impostazioni > Dipendenze deve valere
        anche per il lancio reale, non solo per l'anteprima (bug precedente:
        solo _get_tool(), usato dall'anteprima, lo rispettava)."""
        import rdp_widget
        settings_file = tmp_path / "pcm_settings.json"
        monkeypatch.setattr(config_manager, "SETTINGS_FILE", str(settings_file))
        config_manager._invalidate_caches()
        s = config_manager.load_settings()
        s["tool_paths"] = {"xfreerdp3": "/opt/custom/xfreerdp3"}
        config_manager.save_settings(s)

        monkeypatch.setattr(rdp_widget.shutil, "which",
                             lambda tool: tool if tool == "/opt/custom/xfreerdp3" else None)
        monkeypatch.setattr(rdp_widget, "_freerdp_major_version", lambda exe: 3)

        args = _build_freerdp_cmd({"rdp_client": "xfreerdp3", "host": "rdp.example"})
        assert args[0] == "/opt/custom/xfreerdp3"
        config_manager._invalidate_caches()


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
