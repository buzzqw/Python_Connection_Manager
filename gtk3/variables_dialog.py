import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import config_manager
from translations import t

class VariablesDialog(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(
            title=t("variables.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.set_default_size(450, 350)
        
        # Recupera le variabili salvate (gestisce sia se sono in un file separato sia se sono nei settings)
        try:
            self._vars = config_manager.load_variables()
        except AttributeError:
            s = config_manager.load_settings()
            self._vars = s.get("variables", {})

        self._init_ui()
        self.show_all()

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12); area.set_margin_end(12)
        area.set_margin_top(12); area.set_margin_bottom(8)

        lbl = Gtk.Label(label="Le variabili nel formato {NOME} verranno sostituite automaticamente nei comandi della sessione.")
        lbl.set_xalign(0.0)
        lbl.set_line_wrap(True)
        area.pack_start(lbl, False, False, 0)

        # Tabella con 2 colonne: Nome e Valore
        self._store = Gtk.ListStore(str, str)
        for k, v in self._vars.items():
            self._store.append([k, v])

        self._view = Gtk.TreeView(model=self._store)
        
        # Colonna Nome (modificabile)
        renderer_k = Gtk.CellRendererText()
        renderer_k.set_property("editable", True)
        renderer_k.connect("edited", self._on_name_edited)
        col_k = Gtk.TreeViewColumn(t("variables.col_name"), renderer_k, text=0)
        col_k.set_expand(True)
        self._view.append_column(col_k)

        # Colonna Valore (modificabile)
        renderer_v = Gtk.CellRendererText()
        renderer_v.set_property("editable", True)
        renderer_v.connect("edited", self._on_value_edited)
        col_v = Gtk.TreeViewColumn(t("variables.col_value"), renderer_v, text=1)
        col_v.set_expand(True)
        self._view.append_column(col_v)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add(self._view)
        area.pack_start(scroll, True, True, 0)

        # Pulsanti per aggiungere o rimuovere righe
        bbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_add = Gtk.Button(label=t("variables.add"))
        btn_add.connect("clicked", self._on_add)
        btn_del = Gtk.Button(label=t("variables.delete"))
        btn_del.connect("clicked", self._on_delete)
        bbox.pack_start(btn_add, False, False, 0)
        bbox.pack_start(btn_del, False, False, 0)
        area.pack_start(bbox, False, False, 0)

        self.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button(t("sd.save"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")

    def _on_name_edited(self, renderer, path, text):
        self._store[path][0] = text

    def _on_value_edited(self, renderer, path, text):
        self._store[path][1] = text

    def _on_add(self, btn):
        # Aggiunge una riga vuota pronta per essere modificata
        self._store.append(["NUOVA_VAR", "valore"])

    def _on_delete(self, btn):
        sel = self._view.get_selection()
        model, treeiter = sel.get_selected()
        if treeiter:
            model.remove(treeiter)

    def run(self):
        resp = super().run()
        if resp == Gtk.ResponseType.OK:
            nuove_vars = {}
            for row in self._store:
                k, v = row[0].strip(), row[1].strip()
                if k:  # Salva solo se il nome non è vuoto
                    nuove_vars[k] = v
            
            # Tenta di salvare usando config_manager
            try:
                config_manager.save_variables(nuove_vars)
            except AttributeError:
                # Fallback se la funzione non esiste: lo salva nei settings generali
                s = config_manager.load_settings()
                s["variables"] = nuove_vars
                config_manager.save_settings(s)
                
        return resp
