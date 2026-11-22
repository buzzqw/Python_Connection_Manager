"""Regressioni su casi limite di caricamento/validazione configurazione."""

import pytest

import config_manager
import protocols


@pytest.fixture
def temp_files(tmp_path, monkeypatch):
    """Data file isolati, senza toccare la configurazione reale dell'utente."""
    monkeypatch.setattr(config_manager, "SESSIONS_FILE", str(tmp_path / "connections.json"))
    monkeypatch.setattr(config_manager, "SETTINGS_FILE", str(tmp_path / "pcm_settings.json"))
    monkeypatch.setattr(config_manager, "_AUDIT_FILE", str(tmp_path / "audit_log.json"))
    config_manager._invalidate_caches()
    yield tmp_path
    config_manager._invalidate_caches()


class TestCorruptConfig:
    def test_json_corrotto_restituisce_dizionario_vuoto(self, temp_files):
        (temp_files / "connections.json").write_text("{ non e json", encoding="utf-8")
        assert config_manager.load_profiles() == {}

    def test_json_corrotto_non_fa_crashare_get_templates(self, temp_files):
        (temp_files / "connections.json").write_text("{ non e json", encoding="utf-8")
        assert config_manager.get_templates() == {}


class TestValidation:
    def test_ipv6_letterale_e_zone_id_non_vengono_scartati(self):
        profili = {
            "v6": {"protocol": "ssh", "host": "[2001:db8::1]", "port": "22"},
            "v6zone": {"protocol": "ssh", "host": "fe80::1%eth0", "port": "22"},
        }
        validati = protocols.validate_profiles(profili)
        assert "v6" in validati
        assert "v6zone" in validati

    def test_porta_con_spazi_viene_normalizzata(self):
        validati = protocols.validate_profiles({
            "s": {"protocol": "ssh", "host": "h", "port": " 2222 "},
        })
        assert validati["s"]["port"] == "2222"

    def test_metacaratteri_pericolosi_restano_bloccati(self):
        validati = protocols.validate_profiles({
            "bad": {"protocol": "ssh", "host": "$(touch /tmp/x)"},
        })
        assert validati == {}

    def test_variabile_numerica_espandibile(self, temp_files, monkeypatch):
        monkeypatch.setattr(config_manager, "load_variables", lambda: {"PORTA": 22})
        assert config_manager.expand_variables("port={PORTA}") == "port=22"
