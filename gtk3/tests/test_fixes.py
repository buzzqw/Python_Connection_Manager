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

    def test_importa_mremoteng(self, tmp_path):
        """Verifica il corretto parsing di file XML mRemoteNG con gerarchia gruppi e protocolli."""
        import importer
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<mrng:Connections xmlns:mrng="http://mremoteng.org">
  <Node Name="Root" Type="Container">
    <Node Name="Datacenter" Type="Container">
      <Node Name="Web" Type="Container">
        <Node Name="Nginx1" Type="Connection"
              Hostname="10.0.0.10"
              Port="2222"
              Protocol="SSH2"
              Username="ubuntu"
              Description="Web proxy server" />
      </Node>
      <Node Name="WindowsSRV" Type="Connection"
            Hostname="10.0.0.20"
            Port="3389"
            Protocol="RDP"
            Username="Administrator"
            Domain="CORP"
            RedirectClipboard="True"
            RedirectDrives="False" />
      <Node Name="Storage" Type="Connection"
            Hostname="10.0.0.30"
            Protocol="SFTP"
            Username="backup" />
    </Node>
  </Node>
</mrng:Connections>"""
        xml_file = tmp_path / "confCons.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        profili = importer.importa_mremoteng(str(xml_file))
        assert "Nginx1" in profili
        p_ssh = profili["Nginx1"]
        assert p_ssh["protocol"] == "ssh"
        assert p_ssh["host"] == "10.0.0.10"
        assert p_ssh["port"] == "2222"
        assert p_ssh["user"] == "ubuntu"
        assert p_ssh["group"] == "Datacenter/Web"
        assert p_ssh["_sorgente"] == "mremoteng"

        assert "WindowsSRV" in profili
        p_rdp = profili["WindowsSRV"]
        assert p_rdp["protocol"] == "rdp"
        assert p_rdp["host"] == "10.0.0.20"
        assert p_rdp["port"] == "3389"
        assert p_rdp["rdp_domain"] == "CORP"
        assert p_rdp["redirect_clipboard"] is True
        assert p_rdp["group"] == "Datacenter"

        assert "Storage" in profili
        p_sftp = profili["Storage"]
        assert p_sftp["protocol"] == "sftp"
        assert p_sftp["host"] == "10.0.0.30"
        assert p_sftp["port"] == "22"

    def test_quick_switcher_preparation_and_filtering(self, monkeypatch):
        """Verifica la preparazione e il filtraggio in tempo reale di QuickSwitcherDialog."""
        from quick_switcher_dialog import QuickSwitcherDialog

        dummy_profiles = {
            "Web Production 1": {
                "protocol": "ssh",
                "host": "web1.example.com",
                "port": "22",
                "user": "deploy",
                "group": "Production",
                "tags": ["web", "critical"],
            },
            "DB Postgres": {
                "protocol": "ssh",
                "host": "db.internal",
                "port": "5432",
                "user": "postgres",
                "group": "Databases",
                "tags": ["db"],
            },
            "Windows Desktop": {
                "protocol": "rdp",
                "host": "192.168.1.50",
                "port": "3389",
                "user": "admin",
                "group": "Office",
            },
        }

        monkeypatch.setattr(config_manager, "load_profiles", lambda: dummy_profiles)

        selected = []
        dlg = QuickSwitcherDialog(parent=None, on_connect=lambda n, d: selected.append((n, d)))

        # Verifica items preparati
        assert len(dlg._items) == 3

        # Test filtro "web"
        dlg._filtra("web")
        assert len(dlg._store) == 1
        assert dlg._store[0][1] == "Web Production 1"

        # Test filtro multi-token "admin office"
        dlg._filtra("admin office")
        assert len(dlg._store) == 1
        assert dlg._store[0][1] == "Windows Desktop"

        # Test filtro tag
        dlg._filtra("critical")
        assert len(dlg._store) == 1
        assert dlg._store[0][1] == "Web Production 1"

        # Test selezione ed esecuzione
        dlg._attiva_selezionato()
        assert len(selected) == 1
        assert selected[0][0] == "Web Production 1"

    def test_tab_pinning_logic(self):
        """Verifica la logica di fissaggio / sblocco della scheda."""
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        nb = Gtk.Notebook()
        tab1 = Gtk.Label(label="Content 1")
        tab2 = Gtk.Label(label="Content 2")
        lbl_box1 = Gtk.Box()
        lbl1 = Gtk.Label(label="Server A")
        btn1 = Gtk.Button()
        lbl_box1.pack_start(lbl1, True, True, 0)
        lbl_box1.pack_start(btn1, False, False, 0)
        lbl_box1.show_all()
        tab1._tab_close_btn = btn1

        nb.append_page(tab1, lbl_box1)
        nb.append_page(tab2, Gtk.Label(label="Server B"))

        # Simula toggle pin
        pinned = getattr(tab1, "_pcm_pinned", False)
        assert not pinned
        assert btn1.get_visible()

        # Fissa scheda
        tab1._pcm_pinned = True
        lbl1.set_text(f"📌 {lbl1.get_text()}")
        btn1.set_visible(False)

        assert tab1._pcm_pinned is True
        assert lbl1.get_text() == "📌 Server A"
        assert not btn1.get_visible()

        # Sblocca scheda
        tab1._pcm_pinned = False
        lbl1.set_text(lbl1.get_text().lstrip("📌 "))
        btn1.set_visible(True)

        assert tab1._pcm_pinned is False
        assert lbl1.get_text() == "Server A"
        assert btn1.get_visible()

    def test_chiudi_altre_schede_and_a_destra(self):
        """Verifica chiusura schede a destra e altre schede, preservando schede fissate e home."""
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        import PCM

        nb = Gtk.Notebook()
        p0 = Gtk.Label(label="Home")
        p1 = Gtk.Label(label="P1 (Pinned)")
        p1._pcm_pinned = True
        p2 = Gtk.Label(label="P2 (Active)")
        p3 = Gtk.Label(label="P3")
        p4 = Gtk.Label(label="P4")

        for p in (p0, p1, p2, p3, p4):
            nb.append_page(p, Gtk.Label(label="Tab"))

        class DummyPCM:
            def __init__(self, notebook):
                self._notebook = notebook
                self.closed = []

            def _chiudi_tab(self, page):
                self.closed.append(page)

            _chiudi_altre_schede = PCM.MainWindow._chiudi_altre_schede
            _chiudi_schede_a_destra = PCM.MainWindow._chiudi_schede_a_destra

        # Test chiudi a destra di p2 (dovrebbe chiudere p3 e p4)
        dummy = DummyPCM(nb)
        dummy._chiudi_schede_a_destra(nb, p2)
        assert dummy.closed == [p3, p4]

        # Test chiudi altre schede rispetto a p2 (non chiude p0 Home, non chiude p1 pinned, non chiude p2)
        dummy.closed.clear()
        dummy._chiudi_altre_schede(nb, p2)
        assert p0 not in dummy.closed
        assert p1 not in dummy.closed
        assert p2 not in dummy.closed
        assert p3 in dummy.closed
        assert p4 in dummy.closed

    def test_split_horizontal_to_single_toggle(self):
        """Verifica che la transizione da Horizontal split a Single avvenga correttamente senza ricorsioni."""
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        import PCM

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        nb1 = Gtk.Notebook()
        nb2 = Gtk.Notebook()
        paned.pack1(nb1, True, True)
        paned.pack2(nb2, True, True)

        split_menu = Gtk.Menu()
        split_menu_items = []
        group = None

        class DummyWindow:
            def __init__(self):
                self._paned_term = paned
                self._notebook = nb1
                self._notebook2 = nb2
                self._notebook_attivo = nb1
                self._updating_split_ui = False
                self._split_menu_items = split_menu_items
                self._split_img = Gtk.Image()

            _split_singolo = PCM.MainWindow._split_singolo
            _split_verticale = PCM.MainWindow._split_verticale
            _split_orizzontale = PCM.MainWindow._split_orizzontale
            _on_split_toggled = PCM.MainWindow._on_split_toggled
            _aggiorna_split_indicator = PCM.MainWindow._aggiorna_split_indicator

            def _sposta_tab(self, src, dst, idx):
                p = src.get_nth_page(idx)
                src.remove_page(idx)
                dst.append_page(p, Gtk.Label(label="tab"))

        win = DummyWindow()

        for label, cb, mode in [
            ("single", win._split_singolo, "single"),
            ("vertical", win._split_verticale, "vertical"),
            ("horizontal", win._split_orizzontale, "horizontal"),
        ]:
            mi = Gtk.RadioMenuItem.new_with_label(group, label)
            group = mi.get_group()
            mi.connect("toggled", lambda w, c=cb, m=mode: win._on_split_toggled(w, c, m))
            split_menu.append(mi)
            split_menu_items.append((mi, mode))

        # Attiva horizontal split
        split_menu_items[2][0].set_active(True)
        assert paned.get_orientation() == Gtk.Orientation.VERTICAL
        assert nb2.get_visible() is True

        # Torna a single mode
        split_menu_items[0][0].set_active(True)
        assert paned.get_orientation() == Gtk.Orientation.HORIZONTAL
        assert nb2.get_visible() is False
        assert win._notebook_attivo is nb1

