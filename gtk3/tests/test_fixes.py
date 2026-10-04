"""
test_fixes.py - Tests for bug fixes and stability improvements.
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Vte

import config_manager
import session_dialog
import sftp_browser
import sftp_editor
from terminal_highlight import Highlighter


class TestFixes:
    def test_session_dialog_has_subprocess(self):
        """Verifica che subprocess sia importato nel modulo session_dialog."""
        assert hasattr(session_dialog, "subprocess")
        assert session_dialog.subprocess is not None

    def test_terminal_highlighter_initialization(self):
        """Verifica che Highlighter si inizializzi correttamente con VTE senza errori."""
        v = Vte.Terminal()
        hl = Highlighter(v)
        assert hl.is_enabled()
        assert len(hl._match_tags) > 0

        # Toggle disable e enable
        hl.set_enabled(False)
        assert len(hl._match_tags) == 0
        hl.set_enabled(True)
        assert len(hl._match_tags) > 0

    def test_sftp_browser_has_chiudi_processo(self):
        """Verifica che SftpBrowserWidget e FtpBrowserWidget espongano chiudi_processo."""
        assert hasattr(sftp_browser.SftpBrowserWidget, "chiudi_processo")
        assert hasattr(sftp_browser.FtpBrowserWidget, "chiudi_processo")

    def test_save_profiles_strips_runtime_inheritance_metadata(self, tmp_path, monkeypatch):
        """Verifica che save_profiles elimini _inherits_from prima di salvare su disco."""
        test_file = str(tmp_path / "test_connections.json")
        monkeypatch.setattr(config_manager, "SESSIONS_FILE", test_file)

        profiles = {
            "Template_A": {
                "protocol": "ssh",
                "is_template": True,
                "user": "admin",
            },
            "Server_1": {
                "protocol": "ssh",
                "template_name": "Template_A",
                "user": "admin",
                "_inherits_from": "Template_A",
            }
        }

        success = config_manager.save_profiles(profiles)
        assert success

        # Legge il file grezzo direttamente da disco
        import json
        with open(test_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert "_inherits_from" not in saved_data["Server_1"]

    def test_sftp_editor_wait_flag_for_gui_editors(self, monkeypatch):
        """Verifica che editor come 'code' ricevano il flag --wait se non presente."""
        editor = sftp_editor.SftpEditorWidget(None, "/remote/path.txt")
        editor._tmp_path = "/tmp/dummy_test_file.txt"
        editor._ext_editor = "code"

        launched_cmd = []

        def mock_popen(cmd):
            launched_cmd.extend(cmd)
            class MockProc:
                def wait(self):
                    pass
            return MockProc()

        monkeypatch.setattr(sftp_editor.subprocess, "Popen", mock_popen)
        editor._open_ext_editor()

        assert "--wait" in launched_cmd
        assert "/tmp/dummy_test_file.txt" in launched_cmd
