"""test_cli_uri.py - Regressioni per l'apertura di connessioni via URI CLI."""

import pytest

import PCM
import config_manager
import crypto_manager


@pytest.fixture
def finestra(monkeypatch):
    """Istanza minima di MainWindow: serve solo il metodo apri_da_cli."""
    win = PCM.MainWindow.__new__(PCM.MainWindow)
    monkeypatch.setattr(crypto_manager, "is_enabled", lambda: False)
    monkeypatch.setattr(config_manager, "load_profiles", lambda: {})
    monkeypatch.setattr(config_manager, "audit_append", lambda *a, **k: None)
    return win


class TestUriCli:
    @pytest.mark.parametrize("uri", [
        "ssh://host:abc",
        "ssh://host:99999",
        "ssh://user@host:-1",
    ])
    def test_porta_non_valida_non_solleva(self, finestra, monkeypatch, uri):
        avvisi = []
        monkeypatch.setattr(finestra, "_warn", avvisi.append)
        connesse = []
        monkeypatch.setattr(finestra, "_on_connetti",
                            lambda *a: connesse.append(a))

        finestra.apri_da_cli(uri)

        assert avvisi and "Porta non valida" in avvisi[0]
        assert connesse == []

    def test_uri_valida_con_porta(self, finestra, monkeypatch):
        connesse = []
        monkeypatch.setattr(finestra, "_on_connetti",
                            lambda *a: connesse.append(a))

        finestra.apri_da_cli("ssh://admin@server.example:2222")

        assert len(connesse) == 1
        dati = connesse[0][2]
        assert dati["host"] == "server.example"
        assert dati["port"] == "2222"
        assert dati["user"] == "admin"

    def test_uri_senza_porta_usa_default(self, finestra, monkeypatch):
        connesse = []
        monkeypatch.setattr(finestra, "_on_connetti",
                            lambda *a: connesse.append(a))

        finestra.apri_da_cli("rdp://server.example")

        assert connesse[0][2]["port"] == "3389"
