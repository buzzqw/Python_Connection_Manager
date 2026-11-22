"""Regressioni sulla sicurezza dell'associazione KeePassXC."""

import json
import os
import time
from types import SimpleNamespace

import pytest

import config_manager
import crypto_manager
import keepassxc_manager as kp


@pytest.fixture
def settings_isolati(tmp_path, monkeypatch):
    path = tmp_path / "pcm_settings.json"
    monkeypatch.setattr(config_manager, "SETTINGS_FILE", str(path))
    config_manager._invalidate_caches()
    yield path
    config_manager._invalidate_caches()


class TestAssociazione:
    def test_key_non_salvata_in_chiaro_con_pcm_bloccato(self, settings_isolati, monkeypatch):
        monkeypatch.setattr(crypto_manager, "is_enabled", lambda: True)
        monkeypatch.setattr(crypto_manager, "is_unlocked", lambda: False)

        kp._save_assoc({"id": "abc", "idKey": "S3cr3tSharedKey"})

        settings = (json.loads(settings_isolati.read_text(encoding="utf-8"))
                    if settings_isolati.exists() else {})
        assert "keepassxc_assoc" not in settings

    def test_key_gia_cifrata_puo_essere_risalvata_bloccata(self, settings_isolati, monkeypatch):
        monkeypatch.setattr(crypto_manager, "is_enabled", lambda: True)
        monkeypatch.setattr(crypto_manager, "is_unlocked", lambda: False)

        kp._save_assoc({"id": "abc", "idKey": "ENC:abcdef"})

        settings = json.loads(settings_isolati.read_text(encoding="utf-8"))
        assert settings["keepassxc_assoc"]["idKey"] == "ENC:abcdef"

    def test_assoc_bloccata_rilevata(self, settings_isolati, monkeypatch):
        settings_isolati.write_text(json.dumps({
            "keepassxc_assoc": {"id": "abc", "idKey": "ENC:abcdef"},
        }), encoding="utf-8")
        monkeypatch.setattr(crypto_manager, "is_enabled", lambda: True)
        monkeypatch.setattr(crypto_manager, "is_unlocked", lambda: False)
        assert kp._assoc_locked() is True

        monkeypatch.setattr(crypto_manager, "is_unlocked", lambda: True)
        assert kp._assoc_locked() is False


class TestLetturaFrame:
    def test_frame_parziale_non_blocca(self, monkeypatch):
        """select() pronto ma meno byte del previsto: serve un timeout, non read() bloccante."""
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"ab")  # solo 2 dei 4 byte attesi
        client = kp.KeePassXCClient()
        client._proc = SimpleNamespace(stdout=os.fdopen(read_fd, "rb", buffering=0))
        try:
            with pytest.raises(ConnectionError):
                client._read_exact(4, deadline=time.monotonic() + 0.05)
        finally:
            os.close(write_fd)
            client._proc.stdout.close()

    def test_read_exact_legge_byte_sufficienti(self):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"abcdef")
        client = kp.KeePassXCClient()
        client._proc = SimpleNamespace(stdout=os.fdopen(read_fd, "rb", buffering=0))
        try:
            assert client._read_exact(6, deadline=time.monotonic() + 1) == b"abcdef"
        finally:
            os.close(write_fd)
            client._proc.stdout.close()
