"""
Test del parser ~/.ssh/config di importer.py.

Copre la semantica OpenSSH usata realmente da `ssh -G`:
Include ricorsivi, alias multipli, default globali/Host *, "prima
occorrenza vince", token e ProxyJump.
"""
import os
import textwrap
from pathlib import Path

import importer


def _write(path, testo: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(testo), encoding="utf-8")
    return str(path)


class TestSshConfigBase:
    def test_blocco_semplice(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv1
                HostName 10.0.0.1
                User mario
                Port 2222
                IdentityFile ~/.ssh/id_srv1
        """)
        p = importer.importa_ssh_config(cfg)
        assert list(p) == ["srv1"]
        assert p["srv1"]["host"] == "10.0.0.1"
        assert p["srv1"]["port"] == "2222"
        assert p["srv1"]["user"] == "mario"
        assert p["srv1"]["private_key"] == os.path.expanduser("~/.ssh/id_srv1")
        assert p["srv1"]["protocol"] == "ssh"

    def test_hostname_default_e_alias(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host without-hostname
                User x
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["without-hostname"]["host"] == "without-hostname"

    def test_file_inesistente(self, tmp_path):
        assert importer.importa_ssh_config(str(tmp_path / "nope")) == {}


class TestAliasEMultiHost:
    def test_alias_multipli_generano_sessioni_separate(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv1 srv1.corp alias-db
                HostName 10.0.0.5
                User db
        """)
        p = importer.importa_ssh_config(cfg)
        assert set(p) == {"srv1", "srv1.corp", "alias-db"}
        for nome in p:
            assert p[nome]["host"] == "10.0.0.5"
            assert p[nome]["user"] == "db"
            # L'alias deve essere tracciato nelle note, non nel nome host
            assert nome in p[nome]["notes"]

    def test_wildcard_non_genera_sessioni(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host *
                User globale

            Host 192.168.*
                User lan

            Host reale
                HostName reale.corp
        """)
        p = importer.importa_ssh_config(cfg)
        assert set(p) == {"reale"}
        # Il default globale si applica comunque
        assert p["reale"]["user"] == "globale"


class TestSemanticaOpenSSH:
    def test_prima_occorrenza_vince(self, tmp_path):
        """Come ssh: la prima direttiva trovata vince, anche se meno specifica."""
        cfg = _write(tmp_path / "config", """\
            User primo
            Port 2200

            Host srv
                HostName srv.corp
                User secondo
                Port 2222
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["user"] == "primo"
        assert p["srv"]["port"] == "2200"

    def test_host_specifico_prima_del_default(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                HostName srv.corp
                User specifico

            Host *
                User default
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["user"] == "specifico"

    def test_negazione_esclude_host(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host prod
                HostName prod.corp

            Host * !prod
                User nonprod
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["prod"]["user"] == ""
        assert p["prod"]["host"] == "prod.corp"

    def test_match_ignorato_senza_rompere_i_blocchi(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                HostName srv.corp
                User prima

            Match host qualcosa
                User non-deve-finire-in-srv

            Host dopo
                HostName dopo.corp
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["user"] == "prima"
        assert p["dopo"]["user"] == ""
        assert p["dopo"]["host"] == "dopo.corp"


class TestToken:
    def test_token_h_p_r_nella_identityfile(self, tmp_path, monkeypatch):
        monkeypatch.setenv("USER", "locale")
        cfg = _write(tmp_path / "config", """\
            Host srv
                HostName 10.0.0.9
                User remoto
                Port 2022
                IdentityFile ~/.ssh/%r_%h_%p_%n
        """)
        p = importer.importa_ssh_config(cfg)
        atteso = os.path.expanduser("~/.ssh/remoto_10.0.0.9_2022_srv")
        assert p["srv"]["private_key"] == atteso

    def test_token_nel_hostname(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                HostName %h.example.com
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["host"] == "srv.example.com"

    def test_token_sconosciuto_preservato(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                IdentityFile /tmp/%C_key
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["private_key"] == "/tmp/%C_key"

    def test_percento_escapato(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                IdentityFile /tmp/100%%_key
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["private_key"] == "/tmp/100%_key"


class TestInclude:
    def test_include_glob_assoluto(self, tmp_path):
        _write(tmp_path / "conf.d" / "a.conf", """\
            Host da-a
                HostName a.corp
        """)
        _write(tmp_path / "conf.d" / "b.conf", """\
            Host da-b
                HostName b.corp
        """)
        cfg = _write(tmp_path / "config", f"""\
            Host principale
                HostName main.corp

            Include {tmp_path}/conf.d/*.conf
        """)
        p = importer.importa_ssh_config(cfg)
        assert set(p) == {"principale", "da-a", "da-b"}
        assert p["da-a"]["host"] == "a.corp"

    def test_include_relativo_alla_cartella_del_file(self, tmp_path, monkeypatch):
        # Nessun ~/.ssh/conf.d corrispondente: fallback sulla cartella del file
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home" / ".ssh").mkdir(parents=True)
        _write(tmp_path / "config" / "conf.d" / "x.conf", """\
            Host relativo
                HostName rel.corp
        """)
        cfg = _write(tmp_path / "config" / "config", """\
            Include conf.d/*.conf
        """)
        p = importer.importa_ssh_config(cfg)
        assert "relativo" in p
        assert p["relativo"]["host"] == "rel.corp"

    def test_include_ripetuto_in_blocchi_diversi(self, tmp_path):
        """Lo stesso file Include dentro due Host va applicato a entrambi."""
        comune = _write(tmp_path / "common.conf", """\
            User foo
            Port 4242
        """)
        cfg = _write(tmp_path / "config", f"""\
            Host a
                HostName a.example
                Include {comune}

            Host b
                HostName b.example
                Include {comune}
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["a"]["user"] == "foo"
        assert p["a"]["port"] == "4242"
        assert p["b"]["user"] == "foo"
        assert p["b"]["port"] == "4242"

    def test_include_ciclico_non_va_in_loop(self, tmp_path):
        a = tmp_path / "a.conf"
        b = tmp_path / "b.conf"
        _write(a, f"""\
            Include {b}
            Host host-a
                HostName a.corp
        """)
        _write(b, f"""\
            Include {a}
            Host host-b
                HostName b.corp
        """)
        p = importer.importa_ssh_config(str(a))
        assert set(p) == {"host-a", "host-b"}

    def test_include_non_esistente_ignorato(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Include /nonexistent/pcm/*.conf
            Host srv
                HostName srv.corp
        """)
        p = importer.importa_ssh_config(cfg)
        assert set(p) == {"srv"}


class TestProxyJump:
    def test_jump_semplice(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                HostName srv.corp
                ProxyJump bastion
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["jump_host"] == "bastion"
        assert p["srv"]["jump_port"] == "22"

    def test_jump_con_utente_e_porta(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                ProxyJump admin@bastion:2200
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["jump_host"] == "bastion"
        assert p["srv"]["jump_user"] == "admin"
        assert p["srv"]["jump_port"] == "2200"

    def test_jump_ipv6_tra_parentesi(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                ProxyJump [admin@2001:db8::1]:2222
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["jump_host"] == "2001:db8::1"
        assert p["srv"]["jump_user"] == "admin"
        assert p["srv"]["jump_port"] == "2222"

    def test_catena_usa_primo_hop_e_lo_documenta(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                ProxyJump bastion1,bastion2
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["jump_host"] == "bastion1"
        assert "bastion1,bastion2" in p["srv"]["notes"]

    def test_proxyjump_none_disabilita_il_salto(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                ProxyJump none
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["jump_host"] == ""


class TestFormatoDirettive:
    def test_key_equals_value(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host=srv
            HostName=srv.corp
            User=mario
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["host"] == "srv.corp"
        assert p["srv"]["user"] == "mario"

    def test_valori_quotati(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                IdentityFile "/tmp/chiave con spazi"
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["private_key"] == "/tmp/chiave con spazi"

    def test_proxycommand_con_uguale_non_confonde_il_parsing(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            Host srv
                ProxyCommand ssh -W %h:%p -o ConnectTimeout=5 bastion
                User mario
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["user"] == "mario"

    def test_commenti_ignorati(self, tmp_path):
        cfg = _write(tmp_path / "config", """\
            # commento iniziale
            Host srv
                # altro commento
                HostName srv.corp
        """)
        p = importer.importa_ssh_config(cfg)
        assert p["srv"]["host"] == "srv.corp"


class TestRemminaParser:
    def test_server_ipv6_letterale_con_porta(self, tmp_path):
        f = _write(tmp_path / "v6.remmina", """\
            [remmina]
            name=Server IPv6
            protocol=SSH
            server=[2001:db8::1]:2222
            username=admin
        """)
        p = importer._parse_remmina_file(Path(f))
        assert p["host"] == "2001:db8::1"
        assert p["port"] == "2222"
        assert p["user"] == "admin"

    def test_server_ipv6_senza_porta(self, tmp_path):
        f = _write(tmp_path / "v6.remmina", """\
            [remmina]
            name=Server IPv6
            protocol=RDP
            server=[2001:db8::1]
        """)
        p = importer._parse_remmina_file(Path(f))
        assert p["host"] == "2001:db8::1"
        assert p["port"] == "3389"
