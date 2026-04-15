import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject
import shutil
import config_manager
from translations import t

class DepsConfigDialog(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(title="Configurazione Dipendenze", transient_for=parent, modal=True)
        self.set_default_size(600, 400)
        self._settings = config_manager.load_settings()
        self._custom_paths = self._settings.get("tool_paths", {})
        
        self._tools = {
            "ssh": "SSH client", "scp": "SCP", "sftp": "SFTP client",
            "telnet": "Telnet", "ftp": "FTP client", "xfreerdp3": "FreeRDP 3.x",
            "xtigervncviewer": "TigerVNC", "xdotool": "xdotool", "wol": "Wake-on-LAN"
        }
        
        self._init_ui()
        self.show_all()

    def _init_ui(self):
        area = self.get_content_area()
        area.set_margin_start(10); area.set_margin_end(10); area.set_margin_top(10)

        # Store: [Icona, Descrizione, Comando Base, Percorso Rilevato/Custom, ID_Comando]
        self._store = Gtk.ListStore(str, str, str, str, str)
        self._ricarica_lista()

        self._view = Gtk.TreeView(model=self._store)
        
        # Colonne
        self._add_col("Status", 0, False)
        self._add_col("Componente", 1, False)
        self._add_col("Comando Default", 2, False)
        
        # Colonna EDITABILE per il percorso
        renderer = Gtk.CellRendererText()
        renderer.set_property("editable", True)
        renderer.connect("edited", self._on_path_edited)
        col = Gtk.TreeViewColumn("Percorso Personalizzato (doppio clic)", renderer, text=3)
        col.set_expand(True)
        self._view.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self._view)
        area.pack_start(scroll, True, True, 0)

        self.add_button("Annulla", Gtk.ResponseType.CANCEL)
        self.add_button("Salva", Gtk.ResponseType.OK)

    def _add_col(self, title, idx, expand):
        col = Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=idx)
        col.set_expand(expand)
        self._view.append_column(col)

    def _ricarica_lista(self):
        self._store.clear()
        for cmd_id, desc in self._tools.items():
            # Se l'utente ha salvato un percorso, usa quello, altrimenti shutil.which
            custom = self._custom_paths.get(cmd_id, "")
            detected = custom if custom else (shutil.which(cmd_id) or "Non trovato")
            icon = "✓" if (custom or shutil.which(cmd_id)) else "✗"
            self._store.append([icon, desc, cmd_id, custom, cmd_id])

    def _on_path_edited(self, renderer, path, new_text):
        it = self._store.get_iter(path)
        cmd_id = self._store.get_value(it, 4)
        if new_text.strip():
            self._custom_paths[cmd_id] = new_text.strip()
        else:
            self._custom_paths.pop(cmd_id, None)
        self._ricarica_lista()

    def run(self):
        resp = super().run()
        if resp == Gtk.ResponseType.OK:
            self._settings["tool_paths"] = self._custom_paths
            config_manager.save_settings(self._settings)
        return resp
