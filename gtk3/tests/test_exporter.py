"""
test_exporter.py - Test per exporter e group health check
"""

import xml.etree.ElementTree as ET
import csv
import json
from pathlib import Path

import exporter
import group_health_dialog


SAMPLE_PROFILES = {
    "Web Server": {
        "protocol": "ssh",
        "host": "web.example.com",
        "port": 2222,
        "user": "deploy",
        "group": "Production/Web",
        "tags": ["prod", "frontend"],
        "notes": "Main web server\nHandle with care",
        "private_key": "~/.ssh/id_rsa_web",
        "jump_host": "bastion.example.com",
        "compression": True,
        "keepalive": True,
        "password": "secret_password",
        "_inherits_from": "Template_Linux",
    },
    "DB Server": {
        "protocol": "ssh",
        "host": "db.example.com",
        "port": 22,
        "user": "postgres",
        "group": "Production/Database",
        "tags": ["prod", "database"],
        "notes": "PostgreSQL Primary",
        "password": "db_password",
    },
    "Windows RDP": {
        "protocol": "rdp",
        "host": "win.example.com",
        "port": 3389,
        "user": "Administrator",
        "group": "Office",
        "rdp_domain": "CORP",
        "redirect_clipboard": True,
        "redirect_drives": True,
        "password": "win_password",
    },
    "No Host Profile": {
        "protocol": "ssh",
        "host": "",
        "group": "Staging",
    },
}


class TestExporter:
    def test_esporta_ssh_config(self):
        config_str, count = exporter.esporta_ssh_config(SAMPLE_PROFILES)
        assert count == 2  # Web Server and DB Server (Windows RDP skipped, No Host skipped)
        assert "Host Web_Server" in config_str
        assert "HostName web.example.com" in config_str
        assert "Port 2222" in config_str
        assert "User deploy" in config_str
        assert "IdentityFile ~/.ssh/id_rsa_web" in config_str
        assert "ProxyJump bastion.example.com" in config_str
        assert "Compression yes" in config_str
        assert "ServerAliveInterval 30" in config_str
        assert "Host DB_Server" in config_str
        # Default port 22 shouldn't emit Port 22 if omitted/standard
        assert "Host Windows_RDP" not in config_str

    def test_esporta_ssh_config_gruppo(self):
        config_str, count = exporter.esporta_ssh_config(SAMPLE_PROFILES, gruppo="Production/Web")
        assert count == 1
        assert "Host Web_Server" in config_str
        assert "Host DB_Server" not in config_str

    def test_esporta_csv(self):
        csv_str, count = exporter.esporta_csv(SAMPLE_PROFILES)
        assert count == 4  # All 4 profiles
        reader = csv.reader(csv_str.splitlines())
        rows = list(reader)
        header = rows[0]
        assert header == ["Nome", "Protocollo", "Host", "Porta", "Utente", "Gruppo", "Tag", "Note"]
        
        # Check Web Server row
        web_row = next(r for r in rows if r[0] == "Web Server")
        assert web_row[1] == "ssh"
        assert web_row[2] == "web.example.com"
        assert web_row[3] == "2222"
        assert web_row[4] == "deploy"
        assert web_row[5] == "Production/Web"
        assert "prod, frontend" in web_row[6]
        assert "Main web server Handle with care" in web_row[7]

    def test_esporta_csv_gruppo(self):
        csv_str, count = exporter.esporta_csv(SAMPLE_PROFILES, gruppo="Production")
        # Matches Production/Web and Production/Database
        assert count == 2
        assert "Web Server" in csv_str
        assert "DB Server" in csv_str
        assert "Windows RDP" not in csv_str

    def test_esporta_json_sanitized(self):
        json_str, count = exporter.esporta_json(SAMPLE_PROFILES, include_passwords=False)
        assert count == 4
        data = json.loads(json_str)
        assert "Web Server" in data
        assert data["Web Server"]["password"] == ""
        assert "_inherits_from" not in data["Web Server"]
        assert data["Web Server"]["host"] == "web.example.com"

    def test_esporta_json_include_passwords(self):
        json_str, count = exporter.esporta_json(SAMPLE_PROFILES, include_passwords=True)
        data = json.loads(json_str)
        assert data["Web Server"]["password"] == "secret_password"
        assert data["DB Server"]["password"] == "db_password"

    def test_esporta_mremoteng(self):
        xml_str, count = exporter.esporta_mremoteng(SAMPLE_PROFILES)
        assert count == 4
        root = ET.fromstring(xml_str)
        assert root.tag == "Connections"

        # Verify container hierarchy for Production/Web
        prod_containers = [n for n in root.findall("Node") if n.get("Name") == "Production"]
        assert len(prod_containers) == 1
        prod_container = prod_containers[0]
        assert prod_container.get("Type") == "Container"

        web_containers = [n for n in prod_container.findall("Node") if n.get("Name") == "Web"]
        assert len(web_containers) == 1
        web_container = web_containers[0]

        web_nodes = [n for n in web_container.findall("Node") if n.get("Name") == "Web Server"]
        assert len(web_nodes) == 1
        web_node = web_nodes[0]
        assert web_node.get("Type") == "Connection"
        assert web_node.get("Protocol") == "SSH2"
        assert web_node.get("Hostname") == "web.example.com"
        assert web_node.get("Port") == "2222"
        assert web_node.get("Username") == "deploy"

        # Verify RDP node
        office_containers = [n for n in root.findall("Node") if n.get("Name") == "Office"]
        assert len(office_containers) == 1
        rdp_nodes = [n for n in office_containers[0].findall("Node") if n.get("Name") == "Windows RDP"]
        assert len(rdp_nodes) == 1
        rdp_node = rdp_nodes[0]
        assert rdp_node.get("Protocol") == "RDP"
        assert rdp_node.get("Domain") == "CORP"
        assert rdp_node.get("RedirectClipboard") == "True"

    def test_esporta_su_file(self, tmp_path):
        target = tmp_path / "sub" / "export.txt"
        exporter.esporta_su_file("Hello World", target)
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "Hello World"


class TestGroupHealth:
    def test_trova_target(self, monkeypatch):
        # Create dialog instance with mocked profiles
        class DummyDialog(group_health_dialog.GroupHealthDialog):
            def __init__(self, gruppo):
                self._gruppo = gruppo
                self._profili = SAMPLE_PROFILES

        dlg_prod = DummyDialog("Production")
        targets_prod = dlg_prod._trova_target()
        nomi = [t["nome"] for t in targets_prod]
        assert "Web Server" in nomi
        assert "DB Server" in nomi
        assert "Windows RDP" not in nomi
        assert "No Host Profile" not in nomi  # Skipped because host is empty

        dlg_office = DummyDialog("Office")
        targets_office = dlg_office._trova_target()
        assert len(targets_office) == 1
        assert targets_office[0]["nome"] == "Windows RDP"
        assert targets_office[0]["port"] == 3389
