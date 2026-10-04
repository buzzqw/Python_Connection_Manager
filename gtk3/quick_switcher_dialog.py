"""
quick_switcher_dialog.py - Command Palette / Quick Session Switcher
Consente la ricerca rapida in tempo reale (Ctrl+Shift+P / Ctrl+P) fra tutte le sessioni configurate
per nome, host, utente, porta, protocollo, gruppo o tag, con apertura immediata premendo Invio.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
import config_manager
import protocols
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango
from translations import t

_HERE = os.path.dirname(os.path.abspath(__file__))
_ICONS = os.path.join(_HERE, "icons")

_pixbuf_cache: dict[str, GdkPixbuf.Pixbuf | None] = {}


def _get_icon_pixbuf(proto: str) -> GdkPixbuf.Pixbuf | None:
    icon_filename = protocols.PROTO_ICON_FILE.get(proto, "network.png")
    if icon_filename in _pixbuf_cache:
        return _pixbuf_cache[icon_filename]
    path = os.path.join(_ICONS, icon_filename)
    pb = None
    if os.path.isfile(path):
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 16, 16)
        except (GLib.Error, OSError):
            pb = None
    _pixbuf_cache[icon_filename] = pb
    return pb


class QuickSwitcherDialog(Gtk.Dialog):
    """Dialog compatto in stile Spotlight/Command-Palette per ricerca rapida sessioni."""

    def __init__(self, parent: Gtk.Window | None, on_connect: Callable[[str, dict], None]):
        super().__init__(
            title=t("quick_switcher.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self._on_connect = on_connect
        self.set_default_size(580, 420)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        # Carica profili
        self._profili = config_manager.load_profiles()
        self._items = self._prepara_items(self._profili)

        self._build_ui()
        self._filtra("")
        self.show_all()

    def _prepara_items(self, profili: dict) -> list[dict]:
        items = []
        for nome, dati in profili.items():
            if not isinstance(dati, dict):
                continue
            proto = dati.get("protocol", "ssh")
            host = dati.get("host", "")
            port = str(dati.get("port", ""))
            user = dati.get("user", "")
            group = dati.get("group", "")
            tags = dati.get("tags", [])
            if isinstance(tags, str):
                tags_list = [tg.strip() for tg in tags.split(",") if tg.strip()]
            elif isinstance(tags, list):
                tags_list = [str(tg).strip() for tg in tags if str(tg).strip()]
            else:
                tags_list = []

            # Stringa di dettaglio user@host:port
            detail = ""
            if user and host:
                detail = f"{user}@{host}"
            elif host:
                detail = host
            if port and port not in ("22", "3389", "5900", "23", "21") and detail:
                detail = f"{detail}:{port}"

            # Group e tags
            meta_parts = []
            if group:
                meta_parts.append(f"📁 {group}")
            if tags_list:
                meta_parts.append(" ".join(f"#{tg}" for tg in tags_list))
            meta_str = "  ".join(meta_parts)

            proto_label = protocols.PROTO_LABEL.get(proto, proto.upper())

            # Testo per la ricerca indicizzato minuscolo
            searchable = f"{nome} {host} {user} {port} {proto} {proto_label} {group} {' '.join(tags_list)}".lower()

            items.append({
                "nome": nome,
                "dati": dati,
                "proto": proto,
                "proto_label": proto_label,
                "detail": detail,
                "meta": meta_str,
                "searchable": searchable,
            })

        # Ordina alfabeticamente per nome di default
        items.sort(key=lambda x: x["nome"].lower())
        return items

    def _build_ui(self):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.set_margin_top(12)
        area.set_margin_bottom(8)

        # Search Entry
        self._entry = Gtk.SearchEntry()
        self._entry.set_placeholder_text(t("quick_switcher.placeholder"))
        self._entry.connect("search-changed", self._on_search_changed)
        self._entry.connect("key-press-event", self._on_entry_key_press)
        area.pack_start(self._entry, False, False, 0)

        # Scrolled window con TreeView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scrolled.set_vexpand(True)
        area.pack_start(scrolled, True, True, 0)

        # Modello ListStore:
        # 0: Pixbuf (icona)
        # 1: Nome sessione (str)
        # 2: Protocollo (str, es. "SSH")
        # 3: Dettaglio (str, es. "root@192.168.1.10")
        # 4: Meta (str, es. "📁 Web #prod")
        # 5: Nome chiave (str)
        self._store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str, str, str)
        self._tree = Gtk.TreeView(model=self._store)
        self._tree.set_headers_visible(False)
        self._tree.set_activate_on_single_click(False)
        self._tree.connect("row-activated", self._on_row_activated)
        scrolled.add(self._tree)

        # Colonna Icona + Protocollo
        col_proto = Gtk.TreeViewColumn()
        col_proto.set_spacing(4)
        cell_icon = Gtk.CellRendererPixbuf()
        col_proto.pack_start(cell_icon, False)
        col_proto.add_attribute(cell_icon, "pixbuf", 0)

        cell_proto = Gtk.CellRendererText()
        cell_proto.set_property("scale", 0.85)
        cell_proto.set_property("foreground", "#888888")
        col_proto.pack_start(cell_proto, False)
        col_proto.add_attribute(cell_proto, "text", 2)
        self._tree.append_column(col_proto)

        # Colonna Nome (grassetto)
        col_name = Gtk.TreeViewColumn()
        cell_name = Gtk.CellRendererText()
        cell_name.set_property("weight", int(Pango.Weight.BOLD))
        col_name.pack_start(cell_name, True)
        col_name.add_attribute(cell_name, "text", 1)
        self._tree.append_column(col_name)

        # Colonna Dettaglio host/user
        col_detail = Gtk.TreeViewColumn()
        cell_detail = Gtk.CellRendererText()
        cell_detail.set_property("foreground", "#666666")
        col_detail.pack_start(cell_detail, True)
        col_detail.add_attribute(cell_detail, "text", 3)
        self._tree.append_column(col_detail)

        # Colonna Gruppo / Tag
        col_meta = Gtk.TreeViewColumn()
        cell_meta = Gtk.CellRendererText()
        cell_meta.set_property("scale", 0.85)
        cell_meta.set_property("foreground", "#777777")
        col_meta.pack_start(cell_meta, False)
        col_meta.add_attribute(cell_meta, "text", 4)
        self._tree.append_column(col_meta)

        # Bottom bar con suggerimenti tastiera
        lbl_hint = Gtk.Label(label=t("quick_switcher.hint"))
        lbl_hint.set_xalign(0.5)
        lbl_hint.get_style_context().add_class("dim-label")
        area.pack_start(lbl_hint, False, False, 2)

    def _filtra(self, query: str):
        query = query.strip().lower()
        terms = query.split()

        self._store.clear()
        matches = []
        for item in self._items:
            if not terms:
                matches.append((0, item))
                continue
            # Verifica che tutti i termini corrispondano
            if all(term in item["searchable"] for term in terms):
                score = 0
                nome_low = item["nome"].lower()
                if query and nome_low == query:
                    score += 100
                elif query and nome_low.startswith(query):
                    score += 50
                elif query and query in nome_low:
                    score += 25
                matches.append((score, item))

        if terms:
            matches.sort(key=lambda m: (-m[0], m[1]["nome"].lower()))

        for _score, item in matches:
            pb = _get_icon_pixbuf(item["proto"])
            self._store.append([
                pb,
                item["nome"],
                item["proto_label"],
                item["detail"],
                item["meta"],
                item["nome"],
            ])

        # Seleziona la prima riga
        if len(self._store) > 0:
            first_path = Gtk.TreePath.new_first()
            self._tree.get_selection().select_path(first_path)
            self._tree.set_cursor(first_path, None, False)

    def _on_search_changed(self, entry: Gtk.SearchEntry):
        self._filtra(entry.get_text())

    def _on_entry_key_press(self, widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        kv = event.keyval
        if kv in (Gdk.KEY_Down, Gdk.KEY_Up):
            sel = self._tree.get_selection()
            model, cur_iter = sel.get_selected()
            if not cur_iter:
                if len(self._store) > 0:
                    first_path = Gtk.TreePath.new_first()
                    sel.select_path(first_path)
                    self._tree.set_cursor(first_path, None, False)
                return True

            path = model.get_path(cur_iter)
            idx = path.get_indices()[0]
            if kv == Gdk.KEY_Down and idx < len(self._store) - 1:
                next_path = Gtk.TreePath.new_from_indices([idx + 1])
                sel.select_path(next_path)
                self._tree.set_cursor(next_path, None, False)
                self._tree.scroll_to_cell(next_path, None, False, 0.0, 0.0)
            elif kv == Gdk.KEY_Up and idx > 0:
                prev_path = Gtk.TreePath.new_from_indices([idx - 1])
                sel.select_path(prev_path)
                self._tree.set_cursor(prev_path, None, False)
                self._tree.scroll_to_cell(prev_path, None, False, 0.0, 0.0)
            return True

        elif kv in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._attiva_selezionato()
            return True

        elif kv == Gdk.KEY_Escape:
            self.destroy()
            return True

        return False

    def _on_row_activated(self, tree: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn):
        self._attiva_selezionato()

    def _attiva_selezionato(self):
        sel = self._tree.get_selection()
        model, cur_iter = sel.get_selected()
        if not cur_iter:
            return
        nome = model.get_value(cur_iter, 5)
        dati = self._profili.get(nome)
        if dati:
            self.destroy()
            self._on_connect(nome, dati)
