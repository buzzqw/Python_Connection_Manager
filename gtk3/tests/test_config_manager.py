import json
import os
import tempfile
import pytest

import config_manager
import crypto_manager


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
    old_tx = config_manager.CRYPTO_TRANSACTION_FILE

    config_manager.SESSIONS_FILE = sessions_path
    config_manager.SETTINGS_FILE = settings_path
    config_manager._AUDIT_FILE = audit_path
    config_manager.CRYPTO_TRANSACTION_FILE = os.path.join(tmpdir, "crypto_transaction.json")
    config_manager._invalidate_caches()

    yield tmpdir

    config_manager.SESSIONS_FILE = old_s
    config_manager.SETTINGS_FILE = old_se
    config_manager._AUDIT_FILE = old_au
    config_manager.CRYPTO_TRANSACTION_FILE = old_tx
    config_manager._invalidate_caches()

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
        assert s["ssh"]["strict_host_check"] is False

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

    def test_deep_merge_does_not_alias_base(self, temp_files):
        base = {"b": {"x": 10}}
        merged = config_manager._deep_merge(base, {"a": 1})
        merged["b"]["x"] = 999
        assert base["b"]["x"] == 10

    def test_default_settings_not_mutated_by_load(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["language"] = "XX"
        s["terminal"]["default_font"] = "Hacked"
        assert config_manager.DEFAULT_SETTINGS["general"]["language"] == "it"
        assert config_manager.DEFAULT_SETTINGS["terminal"]["default_font"] == "Monospace"

    def test_read_json_default_is_independent_copy(self, temp_files):
        a = config_manager._read_json("/nonexistent/x.json", config_manager.DEFAULT_SETTINGS)
        a["general"]["language"] = "ZZ"
        assert config_manager.DEFAULT_SETTINGS["general"]["language"] == "it"


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
        assert config_manager.audit_verify()
        log[1]["ts"] = "modified"
        with open(config_manager._AUDIT_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f)
        assert not config_manager.audit_verify()

    def test_audit_verify_false_on_corrupt_file(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["audit_log_enabled"] = True
        config_manager.save_settings(s)
        config_manager.audit_append({"ts": "2025-01-01"})
        with open(config_manager._AUDIT_FILE, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        assert config_manager.audit_verify() is False
        assert config_manager.audit_load() == []

    def test_audit_write_is_atomic(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["audit_log_enabled"] = True
        config_manager.save_settings(s)
        config_manager.audit_append({"ts": "2025-01-01"})
        d = os.path.dirname(config_manager._AUDIT_FILE)
        assert not any(n.startswith(".tmp_") for n in os.listdir(d))
        assert config_manager.audit_load()[0]["ts"] == "2025-01-01"

    def test_audit_clear(self, temp_files):
        s = config_manager.load_settings()
        s["general"]["audit_log_enabled"] = True
        config_manager.save_settings(s)
        config_manager.audit_append({"ts": "test"})
        config_manager.audit_clear()
        assert len(config_manager.audit_load()) == 0


class TestCredentialProfiles:
    def test_roundtrip_without_crypto(self, temp_files):
        crypto_manager.lock()
        s = config_manager.load_settings()
        s.pop("crypto", None)
        config_manager.save_settings(s)
        profiles = [{"name": "p", "password": "pw"}]
        assert config_manager.save_credential_profiles(profiles)
        assert config_manager.load_credential_profiles() == profiles

    def test_save_refused_while_locked(self, temp_files):
        crypto_manager.lock()
        crypto_manager.setup("master-pass")
        crypto_manager.lock()
        assert config_manager.save_credential_profiles(
            [{"name": "p", "password": "x"}]) is False


class TestCryptoTransitions:
    def test_change_and_disable_password_keep_profiles_readable(self, temp_files):
        crypto_manager.lock()
        crypto_manager.setup("old-password")
        profiles = {"server": {"protocol": "ssh", "user": "alice", "password": "secret"}}
        assert config_manager.save_profiles(profiles)

        assert crypto_manager.change_password("old-password", "new-password")
        crypto_manager.lock()
        assert not crypto_manager.unlock("old-password")
        assert crypto_manager.unlock("new-password")
        assert config_manager.load_profiles()["server"]["password"] == "secret"

        assert crypto_manager.disable("new-password")
        assert not crypto_manager.is_enabled()
        assert config_manager.load_profiles() == profiles

    def test_save_profiles_refused_while_locked(self, temp_files):
        """Con cifratura attiva ma bloccata, save_profiles non deve mai
        scrivere in chiaro i profili (bypass della cifratura)."""
        crypto_manager.lock()
        crypto_manager.setup("master-pass")
        profiles = {"s": {"protocol": "ssh", "user": "alice", "password": "secret"}}
        assert config_manager.save_profiles(profiles)

        crypto_manager.lock()
        # Profilo in chiaro in ingresso: il salvataggio deve essere rifiutato.
        assert config_manager.save_profiles(
            {"s": {"protocol": "ssh", "user": "bob", "password": "pw"}}) is False

        with open(config_manager.SESSIONS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        assert raw["s"]["user"].startswith("ENC:")
        assert raw["s"]["password"].startswith("ENC:")

    def test_unlock_refreshes_profiles_cached_while_locked(self, temp_files):
        """Se load_profiles() viene chiamato mentre il crypto è ancora bloccato
        (es. durante la costruzione della UI, prima del dialog di sblocco),
        i profili restano cifrati (ENC:...) e la cache non deve "congelarsi":
        dopo unlock(), load_profiles() deve restituire i valori in chiaro."""
        crypto_manager.lock()
        crypto_manager.setup("master-pass")
        profiles = {"server": {"protocol": "ssh", "user": "alice", "password": "secret"}}
        assert config_manager.save_profiles(profiles)

        crypto_manager.lock()
        # Simula una lettura che avviene prima che l'utente sblocchi il crypto
        cached_while_locked = config_manager.load_profiles()
        assert cached_while_locked["server"]["user"].startswith("ENC:")

        assert crypto_manager.unlock("master-pass")
        refreshed = config_manager.load_profiles()
        assert refreshed["server"]["user"] == "alice"
        assert refreshed["server"]["password"] == "secret"

    def test_corrupted_profile_does_not_block_others(self, temp_files):
        """Un singolo profilo con token cifrato corrotto (es. chiave cambiata
        a metà, file mescolato da un'altra installazione) non deve impedire
        la decifratura degli altri profili: l'errore va isolato per-profilo."""
        crypto_manager.lock()
        crypto_manager.setup("master-pass")
        assert crypto_manager.unlock("master-pass")

        good_user = crypto_manager.encrypt_field("alice")
        profiles_raw = {
            "good": {"protocol": "ssh", "user": good_user, "password": ""},
            "bad":  {"protocol": "ssh", "user": "ENC:not-a-valid-fernet-token==", "password": ""},
        }
        with open(config_manager.SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles_raw, f)
        config_manager._invalidate_caches()

        profili = config_manager.load_profiles()
        assert profili["good"]["user"] == "alice"
        assert profili["bad"]["user"] == "ENC:not-a-valid-fernet-token=="
        assert config_manager.decrypt_failures() == ["bad"]

    def test_decrypt_failures_cleared_on_next_call_even_if_it_errors(self, temp_files):
        """decrypt_failures() non deve restare "incollato" a un vecchio
        risultato: se una load_profiles() successiva fallisce prima di
        arrivare alla decifratura (es. connections.json corrotto), la
        lista va svuotata comunque, non lasciata con i valori della
        chiamata precedente."""
        crypto_manager.lock()
        crypto_manager.setup("master-pass")
        assert crypto_manager.unlock("master-pass")

        profiles_raw = {"bad": {"protocol": "ssh", "user": "ENC:not-a-valid-fernet-token==", "password": ""}}
        with open(config_manager.SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles_raw, f)
        config_manager._invalidate_caches()
        config_manager.load_profiles()
        assert config_manager.decrypt_failures() == ["bad"]

        with open(config_manager.SESSIONS_FILE, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        config_manager._invalidate_caches()
        config_manager.load_profiles()
        assert config_manager.decrypt_failures() == []

    def test_load_tunnels_does_not_crash_while_locked(self, temp_files):
        """load_tunnels() non deve sollevare CryptoError se chiamato mentre
        il crypto è ancora bloccato: deve restituire i campi ancora cifrati."""
        crypto_manager.lock()
        crypto_manager.setup("master-pass")
        assert crypto_manager.unlock("master-pass")
        s = config_manager.load_settings()
        s["tunnels"] = [{"name": "t1", "password": crypto_manager.encrypt_field("secret")}]
        config_manager.save_settings(s)

        crypto_manager.lock()
        tunnels = config_manager.load_tunnels()
        assert tunnels[0]["password"].startswith("ENC:")

    def test_load_tunnels_handles_corrupted_token(self, temp_files):
        crypto_manager.lock()
        crypto_manager.setup("master-pass")
        assert crypto_manager.unlock("master-pass")
        s = config_manager.load_settings()
        s["tunnels"] = [{"name": "bad", "password": "ENC:not-a-valid-fernet-token=="}]
        config_manager.save_settings(s)

        tunnels = config_manager.load_tunnels()
        assert tunnels[0]["password"] == "ENC:not-a-valid-fernet-token=="
