"""
test_cluster.py - Test per dialog cluster e selettore sessioni.
"""

import pytest
import os
import json

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import config_manager
from PCM import _SessionPickerDialog


@pytest.fixture
def sample_profiles():
    return {
        "SSH Server": {"protocol": "ssh", "host": "192.168.1.1", "port": "22", "user": "admin"},
        "RDP Desktop": {"protocol": "rdp", "host": "10.0.0.5", "port": "3389", "user": "user"},
        "VNC Server": {"protocol": "vnc", "host": "192.168.1.20", "port": "5900", "password": "pwd"},
        "SFTP NAS": {"protocol": "file_transfer", "host": "nas.local", "port": "22", "user": "backup"},
        "Telnet Switch": {"protocol": "telnet", "host": "switch.local", "port": "23"},
        "Serial Device": {"protocol": "serial", "device": "/dev/ttyUSB0", "baud": "115200"},
    }


class TestSessionPicker:
    def test_dialog_creates_with_profiles(self, sample_profiles):
        """Verifica che il dialog venga creato e popolato con le sessioni."""
        w = Gtk.Window()
        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        assert len(dlg._all_items) == 6
        assert len(dlg._store) == 6
        dlg.destroy()

    def test_no_selection_by_default(self, sample_profiles):
        """Nessuna sessione selezionata all'apertura."""
        w = Gtk.Window()
        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        assert dlg.get_selected() == []
        dlg.destroy()

    def test_toggle_selection(self, sample_profiles):
        """Toggle di un checkbox seleziona/deseleziona una sessione."""
        w = Gtk.Window()
        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        row = dlg._store[0]
        assert row[0] is False
        dlg._store[0][0] = True
        assert dlg.get_selected() == [row[1]]
        dlg._store[0][0] = False
        assert dlg.get_selected() == []
        dlg.destroy()

    def test_multi_selection(self, sample_profiles):
        """Selezione multipla di sessioni."""
        w = Gtk.Window()
        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        dlg._store[0][0] = True
        dlg._store[2][0] = True
        dlg._store[4][0] = True
        selected = dlg.get_selected()
        assert len(selected) == 3
        assert dlg._store[0][1] in selected
        assert dlg._store[2][1] in selected
        assert dlg._store[4][1] in selected
        dlg.destroy()

    def test_filter_filters_sessions(self, sample_profiles):
        """Il filtro riduce le sessioni visibili."""
        w = Gtk.Window()
        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        dlg._do_rebuild("nas")
        assert len(dlg._store) == 1
        assert "SFTP NAS" in [row[1] for row in dlg._store]
        dlg.destroy()

    def test_filter_case_insensitive(self, sample_profiles):
        """Il filtro è case-insensitive."""
        w = Gtk.Window()
        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        dlg._do_rebuild("RDP")
        assert len(dlg._store) == 1
        dlg._do_rebuild("rdp")
        assert len(dlg._store) == 1
        dlg.destroy()

    def test_empty_filter_shows_all(self, sample_profiles):
        """Filtro vuoto mostra tutte le sessioni."""
        w = Gtk.Window()
        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        dlg._do_rebuild("")
        assert len(dlg._store) == 6
        dlg.destroy()

    def test_save_and_load_cluster(self, sample_profiles):
        """Salvataggio e caricamento di un cluster."""
        w = Gtk.Window()
        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        
        # Select some sessions
        dlg._store[0][0] = True
        dlg._store[1][0] = True
        selected = dlg.get_selected()
        assert len(selected) == 2

        # Simulate save
        s = config_manager.load_settings()
        clusters = s.get("saved_clusters", {})
        clusters["test-cluster"] = {"sessions": selected}
        s["saved_clusters"] = clusters
        config_manager.save_settings(s)
        dlg.destroy()

        # Open new dialog — should see saved cluster
        dlg2 = _SessionPickerDialog(parent=w, profili=sample_profiles)
        assert "test-cluster" in dlg2._saved_clusters
        assert dlg2._saved_clusters["test-cluster"]["sessions"] == selected

        # Load cluster
        dlg2._load_cluster("test-cluster")
        loaded = dlg2.get_selected()
        assert set(loaded) == set(selected)

        # Cleanup
        s = config_manager.load_settings()
        s.get("saved_clusters", {}).pop("test-cluster", None)
        config_manager.save_settings(s)
        dlg2.destroy()

    def test_delete_cluster(self, sample_profiles):
        """Eliminazione di un cluster salvato."""
        w = Gtk.Window()
        s = config_manager.load_settings()
        s["saved_clusters"] = {"to-delete": {"sessions": ["SSH Server"]}}
        config_manager.save_settings(s)

        dlg = _SessionPickerDialog(parent=w, profili=sample_profiles)
        assert "to-delete" in dlg._saved_clusters
        dlg._saved_clusters.pop("to-delete")
        assert "to-delete" not in dlg._saved_clusters

        s = config_manager.load_settings()
        s.get("saved_clusters", {}).pop("to-delete", None)
        config_manager.save_settings(s)
        dlg.destroy()


class TestClusterDialog:
    def test_dialog_creates_with_single_session(self):
        """Creazione dialog con una sessione."""
        from cluster_dialog import ClusterDialog
        sessions = {"Test SSH": {"protocol": "ssh", "host": "10.0.0.1", "port": "22", "user": "root"}}
        w = Gtk.Window()
        dlg = ClusterDialog(parent=w, sessions=sessions)
        assert len(dlg._host_entries) == 1
        assert "Test SSH" in dlg._host_entries
        dlg.destroy()

    def test_dialog_creates_with_multiple_sessions(self):
        """Creazione dialog con più sessioni (notebook)."""
        from cluster_dialog import ClusterDialog
        sessions = {
            "Web Server": {"protocol": "ssh", "host": "10.0.0.1", "port": "22", "user": "admin"},
            "DB Server": {"protocol": "ssh", "host": "10.0.0.2", "port": "22", "user": "admin"},
            "Monitor": {"protocol": "vnc", "host": "10.0.0.3", "port": "5900"},
        }
        w = Gtk.Window()
        dlg = ClusterDialog(parent=w, sessions=sessions)
        assert len(dlg._host_entries) == 3
        assert len(dlg._keep_user_chks) == 3
        assert len(dlg._keep_port_chks) == 3
        dlg.destroy()

    def test_get_hosts_from_text(self):
        """Estrazione host da TextView."""
        from cluster_dialog import ClusterDialog
        tv = Gtk.TextView()
        tv.get_buffer().set_text("10.0.0.1\n10.0.0.2:2222\n# comment\n\n10.0.0.3")
        hosts = ClusterDialog._get_hosts_from_text(tv)
        assert hosts == ["10.0.0.1", "10.0.0.2:2222", "10.0.0.3"]

    def test_get_cluster_plan(self):
        """Il piano cluster include tutti i dati necessari."""
        from cluster_dialog import ClusterDialog
        sessions = {
            "Server A": {"protocol": "ssh", "host": "10.0.0.1", "port": "22", "user": "a"},
        }
        w = Gtk.Window()
        dlg = ClusterDialog(parent=w, sessions=sessions)
        dlg._host_entries["Server A"].get_buffer().set_text("10.0.0.1\n10.0.0.2")
        plan = dlg.get_cluster_plan()
        assert "Server A" in plan
        assert plan["Server A"]["hosts"] == ["10.0.0.1", "10.0.0.2"]
        assert plan["Server A"]["dati"] == sessions["Server A"]
        assert plan["Server A"]["keep_user"] is True
        assert plan["Server A"]["keep_port"] is True
        dlg.destroy()
