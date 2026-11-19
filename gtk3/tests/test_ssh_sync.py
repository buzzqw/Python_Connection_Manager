"""
Test della sincronizzazione con ~/.ssh/config: tag di provenienza, confronto
campo per campo e applicazione non distruttiva.
"""
import os
import textwrap

import pytest

import config_manager
import crypto_manager
import exporter
import importer


@pytest.fixture
def temp_files(monkeypatch, tmp_path):
    """Isola connections.json e pcm_settings.json in una cartella temporanea."""
    monkeypatch.setattr(config_manager, "SESSIONS_FILE",
                        str(tmp_path / "connections.json"))
    monkeypatch.setattr(config_manager, "SETTINGS_FILE",
                        str(tmp_path / "pcm_settings.json"))
    monkeypatch.setattr(config_manager, "_AUDIT_FILE",
                        str(tmp_path / "audit_log.json"))
    monkeypatch.setattr(config_manager, "CRYPTO_TRANSACTION_FILE",
                        str(tmp_path / "crypto_transaction.json"))
    config_manager._invalidate_caches()
    settings = config_manager.load_settings()
    settings.pop("crypto", None)
    config_manager.save_settings(settings)
    crypto_manager.lock()
    config_manager._invalidate_caches()
    yield tmp_path
    config_manager._invalidate_caches()


def _config(tmp_path, testo: str) -> str:
    percorso = tmp_path / "config"
    percorso.write_text(textwrap.dedent(testo), encoding="utf-8")
    return str(percorso)


def _salva(profili: dict):
    assert config_manager.save_profiles(profili)
    config_manager._invalidate_caches()


class TestSorgente:
    def test_import_targhetta_la_sorgente(self, tmp_path):
        cfg = _config(tmp_path, """\
            Host web
                HostName 10.0.0.1
        """)
        profili = importer.importa_ssh_config(cfg)
        assert profili["web"]["_sorgente"] == "sshconfig"
        assert profili["web"]["group"] == "SSH Config"

    def test_riconosce_profili_importati_prima_del_tag(self, temp_files):
        # Profilo creato da una versione precedente: nessun _sorgente, ma
        # gruppo e nota sono quelli generati dall'importatore.
        _salva({"web": {
            "protocol": "ssh", "host": "10.0.0.1", "port": "22",
            "user": "", "group": "SSH Config",
            "notes": "Importato da config (alias: web)",
        }})
        piano = importer.confronta_ssh_config({"web": {
            "protocol": "ssh", "host": "10.0.0.2", "port": "22",
            "user": "", "group": "SSH Config",
            "notes": "Importato da config (alias: web)",
            "_sorgente": "sshconfig",
        }})
        assert [v["nome"] for v in piano["aggiornati"]] == ["web"]
        assert piano["nuovi"] == []


class TestConfronto:
    def test_aggiornamento_campo_per_campo(self, temp_files):
        _salva({"web": {
            "protocol": "ssh", "host": "old.example", "port": "22",
            "user": "mario", "jump_host": "old-bastion", "jump_port": "22",
            "group": "Produzione/Web", "tags": ["prod"],
            "password": "segreta", "notes": "nota scritta da me",
            "_sorgente": "sshconfig",
        }})
        profili = importer.importa_ssh_config(_config(temp_files, """\
            Host web
                HostName new.example
                Port 2222
                ProxyJump admin@gw:2200
        """))
        piano = importer.confronta_ssh_config(profili)

        assert piano["nuovi"] == []
        assert piano["rimossi"] == []
        voce = piano["aggiornati"][0]
        assert voce["nome"] == "web"
        assert set(voce["campi"]) == {
            "host", "user", "port", "jump_host", "jump_user", "jump_port"}
        assert voce["campi"]["host"] == ("old.example", "new.example")

    def test_host_invariato_non_genera_modifiche(self, temp_files):
        profili = importer.importa_ssh_config(_config(temp_files, """\
            Host db
                HostName 10.0.0.5
                User postgres
        """))
        _salva(profili)
        piano = importer.confronta_ssh_config(profili)
        assert piano["aggiornati"] == []
        assert piano["nuovi"] == []
        assert [v["nome"] for v in piano["invariati"]] == ["db"]

    def test_host_rimossi_dalla_config(self, temp_files):
        _salva({
            "vecchio": {"protocol": "ssh", "host": "1.1.1.1",
                        "_sorgente": "sshconfig"},
            "manuale": {"protocol": "ssh", "host": "2.2.2.2"},
        })
        piano = importer.confronta_ssh_config({})
        assert [v["nome"] for v in piano["rimossi"]] == ["vecchio"]

    def test_match_case_insensitive(self, temp_files):
        _salva({"Web": {"protocol": "ssh", "host": "1.1.1.1",
                        "_sorgente": "sshconfig"}})
        profilo = importer.importa_ssh_config(_config(temp_files, """\
            Host web
                HostName 1.1.1.2
        """))
        piano = importer.confronta_ssh_config(profilo)
        assert piano["nuovi"] == []
        assert piano["aggiornati"][0]["nome"] == "Web"

    def test_match_dopo_rinomina_in_pcm(self, temp_files):
        # L'alias SSH resta l'identità anche se la sessione è stata
        # rinominata in PCM: niente doppioni.
        _salva({"Server Web": {
            "protocol": "ssh", "host": "old", "port": "22",
            "group": "Produzione", "notes": "nota mia",
            "_sorgente": "sshconfig", "_ssh_alias": "web",
        }})
        profilo = importer.importa_ssh_config(_config(temp_files, """\
            Host web
                HostName new
        """))
        piano = importer.confronta_ssh_config(profilo)
        assert piano["nuovi"] == []
        assert piano["aggiornati"][0]["nome"] == "Server Web"

    def test_collisione_con_profilo_di_altra_sorgente(self, temp_files):
        _salva({"web": {"protocol": "rdp", "host": "rdp-host"}})
        profilo = importer.importa_ssh_config(_config(temp_files, """\
            Host web
                HostName 10.0.0.1
        """))
        piano = importer.confronta_ssh_config(profilo)
        assert piano["nuovi"][0]["nome"] == "web (2)"


class TestApplicazione:
    def test_preserva_personalizzazioni_e_credenziali(self, temp_files):
        _salva({"web": {
            "protocol": "ssh", "host": "old", "port": "22", "user": "mario",
            "group": "Produzione/Web", "tags": ["prod"],
            "password": "segreta", "totp_secret": "TOTP",
            "private_key": "~/.ssh/id_web",
            "keepalive": True, "notes": "nota mia",
            "_sorgente": "sshconfig",
        }})
        profili = importer.importa_ssh_config(_config(temp_files, """\
            Host web
                HostName new
                ProxyJump bastion
        """))
        piano = importer.confronta_ssh_config(profili)
        risultato = importer.applica_piano_ssh_config(piano)
        assert risultato["aggiornati"] == 1

        profilo = config_manager.load_profiles()["web"]
        assert profilo["host"] == "new"
        assert profilo["jump_host"] == "bastion"
        # Campi non gestiti da SSH config: intatti.
        assert profilo["group"] == "Produzione/Web"
        assert profilo["tags"] == ["prod"]
        assert profilo["password"] == "segreta"
        assert profilo["totp_secret"] == "TOTP"
        assert profilo["keepalive"] is True
        assert profilo["notes"] == "nota mia"

    def test_la_nota_generata_viene_aggiornata(self, temp_files):
        _salva({"web": {
            "protocol": "ssh", "host": "old", "port": "22",
            "group": "SSH Config",
            "notes": "Importato da vecchio-config (alias: web)",
            "_sorgente": "sshconfig",
        }})
        profili = importer.importa_ssh_config(_config(temp_files, """\
            Host web
                HostName new
        """))
        importer.applica_piano_ssh_config(
            importer.confronta_ssh_config(profili))
        assert "vecchio-config" not in \
            config_manager.load_profiles()["web"]["notes"]

    def test_rimozione_solo_su_richiesta(self, temp_files):
        _salva({"vecchio": {"protocol": "ssh", "host": "1.1.1.1",
                            "_sorgente": "sshconfig"}})
        piano = importer.confronta_ssh_config({})
        importer.applica_piano_ssh_config(piano)
        assert "vecchio" in config_manager.load_profiles()

        importer.applica_piano_ssh_config(piano, rimuovi=True)
        assert "vecchio" not in config_manager.load_profiles()

    def test_non_rimuove_profili_di_altre_sorgenti(self, temp_files):
        _salva({"manuale": {"protocol": "ssh", "host": "1.1.1.1"}})
        piano = importer.confronta_ssh_config({})
        resultado = importer.applica_piano_ssh_config(piano, rimuovi=True)
        assert resultado["rimossi"] == 0
        assert "manuale" in config_manager.load_profiles()

    def test_nuovi_host_con_rinomina(self, temp_files):
        _salva({"web": {"protocol": "rdp", "host": "rdp"}})
        profili = importer.importa_ssh_config(_config(temp_files, """\
            Host web
                HostName 10.0.0.1
        """))
        piano = importer.confronta_ssh_config(profili)
        risultato = importer.applica_piano_ssh_config(piano)
        assert risultato["aggiunti"] == 1
        assert risultato["rinominati"] == [("web", "web (2)")]
        assert config_manager.load_profiles()["web"]["protocol"] == "rdp"
        assert config_manager.load_profiles()["web (2)"]["host"] == "10.0.0.1"

    def test_unisci_con_sovrascrittura_usa_il_merge_ssh(self, temp_files):
        _salva({"web": {
            "protocol": "ssh", "host": "old", "port": "22",
            "group": "Produzione", "tags": ["p"], "password": "pw",
            "_sorgente": "sshconfig",
        }})
        profili = importer.importa_ssh_config(_config(temp_files, """\
            Host web
                HostName new
        """))
        importer.unisci_in_pcm(profili, sostituzione=True)
        profilo = config_manager.load_profiles()["web"]
        assert profilo["host"] == "new"
        assert profilo["group"] == "Produzione"
        assert profilo["tags"] == ["p"]
        assert profilo["password"] == "pw"

    def test_sincronizza_ssh_config_end_to_end(self, temp_files):
        cfg = _config(temp_files, """\
            Include conf.d/*.conf

            Host srv
                HostName 10.0.0.9
                ProxyJump gw
        """)
        (temp_files / "conf.d").mkdir()
        (temp_files / "conf.d" / "extra.conf").write_text(
            "Host solo-include\n    HostName 10.0.0.10\n", encoding="utf-8")

        risultato = importer.sincronizza_ssh_config(cfg)
        assert risultato["aggiunti"] == 2
        profili = config_manager.load_profiles()
        assert profili["solo-include"]["host"] == "10.0.0.10"
        assert profili["srv"]["jump_host"] == "gw"

        # Seconda passata: nessuna modifica.
        secondo = importer.sincronizza_ssh_config(cfg)
        assert secondo["salvato"] is False


class TestExportJump:
    def test_proxyjump_completo(self):
        testo, n = exporter.esporta_ssh_config({"srv": {
            "protocol": "ssh", "host": "10.0.0.1",
            "jump_host": "bastion", "jump_user": "admin",
            "jump_port": "2200",
        }})
        assert n == 1
        assert "ProxyJump admin@bastion:2200" in testo

    def test_proxyjump_ipv6(self):
        testo, _ = exporter.esporta_ssh_config({"srv": {
            "protocol": "ssh", "host": "10.0.0.1",
            "jump_host": "2001:db8::1", "jump_user": "admin",
            "jump_port": "2200",
        }})
        assert "ProxyJump admin@[2001:db8::1]:2200" in testo

    def test_proxyjump_senza_utente_ne_porta(self):
        testo, _ = exporter.esporta_ssh_config({"srv": {
            "protocol": "ssh", "host": "10.0.0.1",
            "jump_host": "bastion",
        }})
        assert "ProxyJump bastion" in testo
