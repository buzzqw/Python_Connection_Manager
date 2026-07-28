import json
import tempfile
import pytest

import config_manager


@pytest.fixture
def temp_files():
    """Sostituisce SESSIONS_FILE, SETTINGS_FILE e _AUDIT_FILE con file temporanei."""
    tmpdir = tempfile.mkdtemp(prefix="pcm_test_")
    sessions_path = os.path.join(tmpdir, "connections.json")
    settings_path = os.path.join(tmpdir, "pcm_settings.json")
    audit_path = os.path.join(tmpdir, "audit_log.json")

    old_s = config_manager.SESSIONS_FILE
    old_se = config_manager.SETTINGS_FILE
    old_au = config_manager._AUDIT_FILE

    config_manager.SESSIONS_FILE = sessions_path
    config_manager.SETTINGS_FILE = settings_path
    config_manager._AUDIT_FILE = audit_path

    yield tmpdir

    config_manager.SESSIONS_FILE = old_s
    config_manager.SETTINGS_FILE = old_se
    config_manager._AUDIT_FILE = old_au

    import shutil as _sh
    _sh.rmtree(tmpdir, ignore_errors=True)


class TestProfiles:
    def test_load_profiles_creates_default(self, temp_files):
        # Rimuovi il file per forzare la creazione delle sessioni default
        if os.path.exists(config_manager.SESSIONS_FILE):
            os.unlink(config_manager.SESSIONS_FILE)
        profili = config_manager.load_profiles()
        assert isinstance(profili, dict)
        assert len(profili) > 0
        for nome, dati in profili.items():
            assert "protocol" in dati

    def test_save_and_load_roundtrip(self, temp_files):
        original = {"test": {"protocol": "ssh", "host": "1.2.3.4"}}
        assert config_manager.save_profiles(original)
        loaded = config_manager.load_profiles()
        assert loaded == original

    def test_first_run_creates_defaults(self, temp_files):
        if os.path.exists(config_manager.SESSIONS_FILE):
            os.unlink(config_manager.SESSIONS_FILE)
        profili = config_manager.load_profiles()
        assert len(profili) >= 8


class TestSettings:
    def test_load_settings_returns_defaults(self, temp_files):
        path = config_manager.SETTINGS_FILE
        if os.path.exists(path):
            os.unlink(path)
        s = config_manager.load_settings()
        assert "general" in s
        assert "terminal" in s
        assert s["general"]["language"] in ("it", "en")

    def test_save_and_load_settings(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["language"] = "en"
        config_manager.save_settings(s)
        loaded = config_manager.load_settings()
        assert loaded["general"]["language"] == "en"

    def test_deep_merge_preserves_defaults(self, temp_files):
        base = {"a": 1, "b": {"x": 10}}
        override = {"b": {"y": 20}, "c": 3}
        merged = config_manager._deep_merge(base, override)
        assert merged == {"a": 1, "b": {"x": 10, "y": 20}, "c": 3}


class TestVariables:
    def test_expand_variables(self, temp_files):
        s = config_manager.load_settings()
        s["variables"] = {"HOME": "/home/user", "PROJECT": "pcm"}
        config_manager.save_settings(s)
        result = config_manager.expand_variables("cd {HOME}/{PROJECT}")
        assert result == "cd /home/user/pcm"

    def test_expand_no_match(self, temp_files):
        s = config_manager.load_settings()
        s["variables"] = {}
        config_manager.save_settings(s)
        result = config_manager.expand_variables("no match {UNKNOWN}")
        assert result == "no match {UNKNOWN}"


class TestRecentSessions:
    def test_add_and_load_recent(self, temp_files):
        config_manager.add_recent("TestSession", {"protocol": "ssh", "host": "test"})
        recent = config_manager.load_recent()
        assert len(recent) == 1
        assert recent[0]["name"] == "TestSession"
        assert recent[0]["proto"] == "ssh"

    def test_recent_max_limit(self, temp_files):
        for i in range(25):
            config_manager.add_recent(f"Session{i}", {"protocol": "ssh", "host": str(i)})
        assert len(config_manager.load_recent()) == 20

    def test_clear_recent(self, temp_files):
        config_manager.add_recent("A", {"protocol": "ssh"})
        config_manager.clear_recent()
        assert len(config_manager.load_recent()) == 0


class TestAuditLog:
    def test_audit_append_disabled(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["audit_log_enabled"] = False
        config_manager.save_settings(s)
        config_manager.audit_append({"test": "data"})
        log = config_manager.audit_load()
        assert len(log) == 0

    def test_audit_append_sanitizes_passwords(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["audit_log_enabled"] = True
        config_manager.save_settings(s)
        config_manager.audit_append({
            "ts": "2025-01-01 00:00:00",
            "session": "test",
            "password": "secret123",
        })
        log = config_manager.audit_load()
        assert len(log) == 1
        assert log[0]["password"] == "[REDACTED]"

    def test_audit_hash_chaining(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["audit_log_enabled"] = True
        config_manager.save_settings(s)
        config_manager.audit_append({"ts": "2025-01-01"})
        config_manager.audit_append({"ts": "2025-01-02"})
        log = config_manager.audit_load()
        assert len(log) == 2
        assert "_hash" in log[0]
        assert "_hash" in log[1]

    def test_audit_clear(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["audit_log_enabled"] = True
        config_manager.save_settings(s)
        config_manager.audit_append({"ts": "test"})
        config_manager.audit_clear()
        assert len(config_manager.audit_load()) == 0
