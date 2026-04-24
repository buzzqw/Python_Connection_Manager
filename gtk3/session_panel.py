"""
session_panel.py - Pannello sidebar sessioni PCM (GTK3)

Usa Gtk.TreeView + Gtk.TreeStore al posto di QTreeWidget.
Segnali emessi:
  - 'connetti'   (nome: str, dati: dict)
  - 'nuova'      ()
  - 'modifica'   (nome: str, dati: dict)
  - 'elimina'    (nome: str)
  - 'duplica'    (nome: str)
"""

import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject, Pango, GLib

import config_manager
from translations import t

_HERE  = os.path.dirname(os.path.abspath(__file__))
_ICONS = os.path.join(_HERE, "icons")


def _load_pixbuf(filename: str, size: int = 16) -> GdkPixbuf.Pixbuf | None:
    path = os.path.join(_ICONS, filename)
    if not os.path.isfile(path):
        return None
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
    except Exception:
        return None


PROTO_COLOR = {
    "ssh":    "#4ec9b0", "telnet": "#c9b458", "sftp":   "#6ab187",
    "ftp":    "#b87a00", "rdp":    "#0078d4", "vnc":    "#e8a020",
    "mosh":   "#5aadad", "serial": "#888888",
}
PROTO_ICON_FILE = {
    "ssh":    "ssh.png",    "telnet": "network.png", "sftp":  "folder.png",
    "ftp":    "folder.png", "rdp":    "monitor.png", "vnc":   "vnc.png",
    "mosh":   "flash.png",  "serial": "cable.png",
}
PROTO_LABEL = {
    "ssh": "SSH", "telnet": "Telnet", "sftp": "SFTP",
    "ftp": "FTP", "rdp": "RDP",       "vnc":  "VNC",
    "mosh": "Mosh", "serial": "Seriale",
}


class SessionPanel(Gtk.Box):

    __gsignals__ = {
        "connetti": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "nuova":    (GObject.SignalFlags.RUN_FIRST, None, ()),
        "modifica": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "elimina":  (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "duplica":  (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.get_style_context().add_class("session-sidebar")
        self._profili: dict = {}
        self._init_ui()
        self.aggiorna()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _init_ui(self):
        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header.set_margin_start(6)
        header.set_margin_end(6)
        header.set_margin_top(6)
        header.set_margin_bottom(4)

        lbl = Gtk.Label(label=t("sidebar.sessions"))
        lbl.get_style_context().add_class("section-header")
        lbl.set_hexpand(True)
        lbl.set_xalign(0.0)
        header.pack_start(lbl, True, True, 0)

        btn_new = Gtk.Button()
        btn_new.set_relief(Gtk.ReliefStyle.NONE)
        btn_new.set_tooltip_text(t("sidebar.new_session_tooltip"))
        icon_new = Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
        btn_new.add(icon_new)
        btn_new.connect("clicked", lambda b: self.emit("nuova"))
        header.pack_start(btn_new, False, False, 0)

        self.pack_start(header, False, False, 0)

        # Barra ricerca
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(t("sidebar.search_placeholder"))
        self._search.set_margin_start(6)
        self._search.set_margin_end(6)
        self._search.set_margin_bottom(4)
        self._search.connect("search-changed", self._on_search)
        self.pack_start(self._search, False, False, 0)

        # Separatore
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(sep, False, False, 0)

        # TreeStore: [Pixbuf icona, str nome_display, str nome_chiave, bool è_gruppo]
        self._store = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, str, bool)

        self._tree = Gtk.TreeView(model=self._store)
        self._tree.set_headers_visible(False)
        self._tree.set_enable_search(False)
        self._tree.set_activate_on_single_click(False)

        # Colonna unica: icona + testo
        col = Gtk.TreeViewColumn()
        cell_pix = Gtk.CellRendererPixbuf()
        cell_txt = Gtk.CellRendererText()
        
        # OTTIMIZZAZIONE LAYOUT: 
        # 1. Troncamento testo troppo lungo
        cell_txt.set_property("ellipsize", Pango.EllipsizeMode.END)
        # 2. Riduciamo il padding verticale della riga (compattezza estrema)
        cell_txt.set_property("ypad", 1)  
        cell_pix.set_property("ypad", 1)

        col.pack_start(cell_pix, False)
        col.pack_start(cell_txt, True)
        col.add_attribute(cell_pix, "pixbuf", 0)
        col.add_attribute(cell_txt, "markup", 1)
        self._tree.append_column(col)

        self._tree.connect("row-activated", self._on_row_activated)
        self._tree.connect("button-press-event", self._on_button_press)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._tree)
        self.pack_start(scroll, True, True, 0)

    # ------------------------------------------------------------------
    # Aggiornamento modello
    # ------------------------------------------------------------------

    def aggiorna(self, profili=None):
        self._profili = profili if profili is not None else config_manager.load_profiles()
        self._ricostruisci(self._search.get_text())

    def _ricostruisci(self, filtro: str = ""):
        self._store.clear()
        filtro = filtro.strip().lower()

        # Raggruppa per gruppo
        gruppi: dict[str, list[str]] = {}
        for nome, dati in self._profili.items():
            if filtro and filtro not in nome.lower():
                host = dati.get("host", "")
                user = str(dati.get("user") or "")
                if filtro not in host.lower() and filtro not in user.lower():
                    continue
            gruppo = dati.get("group", "") or t("sidebar.no_group")
            gruppi.setdefault(gruppo, []).append(nome)

        folder_pb = _load_pixbuf("folder.png", 16)

        for gruppo in sorted(gruppi.keys()):
            # Riga gruppo
            grp_markup = f"<b>{GLib.markup_escape_text(gruppo)}</b>"
            grp_iter = self._store.append(None, [folder_pb, grp_markup, "", True])

            for nome in sorted(gruppi[gruppo]):
                dati = self._profili[nome]
                proto = dati.get("protocol", "ssh")
                host  = dati.get("host", "")
                user  = str(dati.get("user") or "")
                color = PROTO_COLOR.get(proto, "#888888")
                proto_lbl = PROTO_LABEL.get(proto, proto.upper())

                user_display = "" if user.startswith("ENC:") else user
                
                # OTTIMIZZAZIONE TESTO: Nessun "a capo" (\n), target sulla stessa riga e sbiadito
                user_host = f"{GLib.markup_escape_text(user_display + '@' if user_display else '')}{GLib.markup_escape_text(host)}"
                sub = f" <span foreground='gray' size='smaller'>({user_host})</span>" if host else ""
                
                markup = (
                    f"<span foreground='{color}'><b>{GLib.markup_escape_text(proto_lbl)}</b></span> "
                    f"{GLib.markup_escape_text(nome)}{sub}"
                )

                pb = _load_pixbuf(PROTO_ICON_FILE.get(proto, "network.png"), 16)
                self._store.append(grp_iter, [pb, markup, nome, False])

        self._tree.expand_all()

    def _on_search(self, entry):
        self._ricostruisci(entry.get_text())

    # ------------------------------------------------------------------
    # Interazioni
    # ------------------------------------------------------------------

    def _on_row_activated(self, tree, path, column):
        it = self._store.get_iter(path)
        if it is None:
            return
        is_group = self._store.get_value(it, 3)
        if is_group:
            if tree.row_expanded(path):
                tree.collapse_row(path)
            else:
                tree.expand_row(path, False)
            return
        nome = self._store.get_value(it, 2)
        dati = self._profili.get(nome, {})
        self.emit("connetti", nome, dati)

    def _on_button_press(self, tree, event):
        if event.button != 3:  # tasto destro
            return False
        info = tree.get_path_at_pos(int(event.x), int(event.y))
        if not info:
            return False
        path, _, _, _ = info
        it = self._store.get_iter(path)
        if it is None:
            return False
        is_group = self._store.get_value(it, 3)
        if is_group:
            return False
        nome = self._store.get_value(it, 2)
        dati = self._profili.get(nome, {})
        self._mostra_menu(event, nome, dati)
        return True

    def _mostra_menu(self, event, nome: str, dati: dict):
        menu = Gtk.Menu()

        def _item(label, callback):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: callback())
            menu.append(mi)

        _item(t("panel.connect"),   lambda: self.emit("connetti", nome, dati))
        menu.append(Gtk.SeparatorMenuItem())
        _item(t("panel.edit"),      lambda: self.emit("modifica", nome, dati))
        _item(t("panel.duplicate"), lambda: self.emit("duplica", nome))
        menu.append(Gtk.SeparatorMenuItem())
        _item(t("panel.delete"),    lambda: self._conferma_elimina(nome))

        menu.show_all()
        menu.popup_at_pointer(event)

    def _conferma_elimina(self, nome: str):
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=t("panel.delete_confirm", name=nome)
        )
        resp = dlg.run()
        dlg.destroy()
        if resp == Gtk.ResponseType.YES:
            self.emit("elimina", nome)
