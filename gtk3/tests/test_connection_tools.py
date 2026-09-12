import os
import socket
import shutil
import tempfile

import pytest

import config_manager
import external_tools
import port_scanner


@pytest.fixture
def temp_files(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="pcm_tools_test_")
    monkeypatch.setattr(config_manager, "SESSIONS_FILE", os.path.join(tmpdir, "connections.json"))
    monkeypatch.setattr(config_manager, "SETTINGS_FILE", os.path.join(tmpdir, "pcm_settings.json"))
    monkeypatch.setattr(config_manager, "_AUDIT_FILE", os.path.join(tmpdir, "audit_log.json"))
    monkeypatch.setattr(config_manager, "CRYPTO_TRANSACTION_FILE", os.path.join(tmpdir, "crypto_transaction.json"))
    config_manager._invalidate_caches()
    yield tmpdir
    config_manager._invalidate_caches()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_template_inheritance_supports_chains(temp_files):
    profiles = {
        "base": {"protocol": "ssh", "user": "admin", "keepalive": True, "is_template": True},
        "prod": {"protocol": "ssh", "template_name": "base", "host": "prod.example", "is_template": True},
        "db": {"protocol": "ssh", "template_name": "prod", "host": "db.example"},
    }
    config_manager.save_profiles(profiles)
    loaded = config_manager.load_profiles()
    assert loaded["db"]["user"] == "admin"
    assert loaded["db"]["keepalive"] is True
    assert loaded["db"]["host"] == "db.example"


def test_config_backups_are_rotated(temp_files):
    settings = config_manager.load_settings()
    settings["backups"] = {"enabled": True, "max_files": 2, "directory": ""}
    config_manager.save_settings(settings)
    for host in ("one", "two", "three", "four"):
        assert config_manager.save_profiles({"server": {"protocol": "ssh", "host": host}})
    backup_dir = os.path.join(temp_files, "backups")
    backups = [name for name in os.listdir(backup_dir) if name.startswith("connections-")]
    assert len(backups) == 2


def test_external_tools_build_shell_free_argv(temp_files):
    tool = {"command": "/usr/bin/ping", "args": "-c 1 {host}:{port}"}
    assert external_tools.build_argv(tool, {"host": "server", "port": 22}) == [
        "/usr/bin/ping", "-c", "1", "server:22"
    ]


def test_external_tools_reject_credentials(temp_files):
    with pytest.raises(external_tools.ExternalToolError):
        external_tools.build_argv(
            {"command": "/bin/sh", "args": ["-c", "{PASSWORD}"]},
            {"host": "server"},
        )


def test_port_scanner_enforces_port_bound(temp_files):
    with pytest.raises(port_scanner.ScanError):
        list(port_scanner.scan_range("192.0.2.1", "192.0.2.1", list(range(1, 258))))


def test_port_scanner_parsers_bound_work(temp_files):
    assert port_scanner.parse_ports("22,80-82") == [22, 80, 81, 82]
    assert port_scanner.parse_hosts("192.0.2.1", "192.0.2.3") == [
        "192.0.2.1", "192.0.2.2", "192.0.2.3"
    ]
    with pytest.raises(port_scanner.ScanError):
        port_scanner.parse_hosts("192.0.2.1", "192.0.2.1", max_hosts=0)


def test_port_scanner_finds_local_listener(temp_files):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        results = list(port_scanner.scan_range("127.0.0.1", "127.0.0.1", [port], timeout=1))
        assert results == [{"host": "127.0.0.1", "port": port}]
    finally:
        listener.close()
