"""Test di robustezza della decifratura dei singoli campi."""

import base64

import pytest

import crypto_manager


class TestDecryptField:
    def test_non_ascii_token_is_reported_as_corrupt(self, monkeypatch):
        """Un token corrotto con caratteri non ASCII non deve far esplodere
        load_profiles(): deve essere segnalato come InvalidTokenError."""
        monkeypatch.setattr(
            crypto_manager, "_KEY", base64.urlsafe_b64encode(b"x" * 32)
        )
        with pytest.raises(crypto_manager.InvalidTokenError):
            crypto_manager.decrypt_field("ENC:é")

    def test_plain_value_is_returned_unchanged(self):
        assert crypto_manager.decrypt_field("plaintext") == "plaintext"
        assert crypto_manager.decrypt_field("") == ""
