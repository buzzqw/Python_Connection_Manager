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
from gi.repository import Gtk, GdkPixbuf, GObject, Pango, GLib

import config_manager
import protocols
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


PROTO_COLOR = protocols.PROTO_COLOR
PROTO_ICON_FILE = protocols.PROTO_ICON_FILE
PROTO_LABEL = {k: v for k, v in protocols.PROTO_LABEL.items()}
# Aggiungi chiavi legacy per backward compat nella sidebar
PROTO_LABEL.update({"sftp": "SFTP", "ftp": "FTP"})


class SessionPanel(Gtk.Box):

    __gsignals__ = {
        "connetti":     (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "nuova":        (GObject.SignalFlags.RUN_FIRST, None, ()),
        "modifica":     (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "elimina":      (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "duplica":      (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "apri-ft":      (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "ping":         (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-log":     (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-monitor": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-cron":    (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-cluster": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.get_style_context().add_class("session-sidebar")
        self._profili: dict = {}
        self._open_sessions: set = set()
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
        self._search.set_margin_bottom(2)
        self._search.connect("search-changed", self._on_filter_changed)
        self.pack_start(self._search, False, False, 0)

        # Filtro tag
        self._tag_combo = Gtk.ComboBoxText()
        self._tag_combo.append("", t("sidebar.tag_filter_all"))
        self._tag_combo.set_margin_start(6)
        self._tag_combo.set_margin_end(6)
        self._tag_combo.set_margin_bottom(4)
        self._tag_combo.set_active(0)
        self._tag_combo.connect("changed", self._on_filter_changed)
        self.pack_start(self._tag_combo, False, False, 0)

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

        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scroll.add(self._tree)
        self.pack_start(self._scroll, True, True, 0)

    # ------------------------------------------------------------------
    # Aggiornamento modello
    # ------------------------------------------------------------------

    def aggiorna(self, profili=None):
        self._profili = profili if profili is not None else config_manager.load_profiles()
        self._aggiorna_tag_combo()
        self._ricostruisci(self._search.get_text())

    def _aggiorna_tag_combo(self):
        """Popola il combobox dei tag con tutti i tag disponibili."""
        current = self._tag_combo.get_active_text() if self._tag_combo.get_active() >= 0 else ""
        self._tag_combo.handler_block_by_func(self._on_filter_changed)
        self._tag_combo.remove_all()
        self._tag_combo.append("", t("sidebar.tag_filter_all"))
        all_tags = set()
        for dati in self._profili.values():
            tags_raw = dati.get("tags", "")
            if isinstance(tags_raw, str) and tags_raw.strip():
                for tag in tags_raw.split(","):
                    tag = tag.strip()
                    if tag:
                        all_tags.add(tag)
            elif isinstance(tags_raw, list):
                for tag in tags_raw:
                    tag = str(tag).strip()
                    if tag:
                        all_tags.add(tag)
        for tag in sorted(all_tags):
            self._tag_combo.append(tag, tag)
        # Ripristina selezione precedente se ancora presente
        if current:
            for i in range(self._tag_combo.get_model().iter_n_children(None)):
                if self._tag_combo.get_model()[i][0] == current:
                    self._tag_combo.set_active(i)
                    break
            else:
                self._tag_combo.set_active(0)
        else:
            self._tag_combo.set_active(0)
        self._tag_combo.handler_unblock_by_func(self._on_filter_changed)

    def _on_filter_changed(self, *args):
        self._ricostruisci(self._search.get_text())

    def aggiorna_sessioni_aperte(self, open_sessions: set):
        """Aggiorna solo l'indicatore sessioni aperte senza ricaricare profili da disco."""
        self._open_sessions = open_sessions
        self._ricostruisci(self._search.get_text())

    def _ricostruisci(self, filtro: str = ""):
        adj = self._scroll.get_vadjustment()
        saved_scroll = adj.get_value()

        self._store.clear()
        filtro = filtro.strip().lower()
        tag_filter = self._tag_combo.get_active_text() or ""
        tag_filter = tag_filter.strip() if tag_filter != t("sidebar.tag_filter_all") else ""

        def _match_tag(dati: dict) -> bool:
            if not tag_filter:
                return True
            tags_raw = dati.get("tags", "")
            if isinstance(tags_raw, str):
                tags = {t.strip() for t in tags_raw.split(",") if t.strip()}
            elif isinstance(tags_raw, list):
                tags = {str(t).strip() for t in tags_raw if str(t).strip()}
            else:
                return False
            return tag_filter in tags

        folder_pb = _load_pixbuf("folder.png", 16)

        # ── Sezione Recenti (solo senza filtro) ───────────────────────────
        if not filtro and not tag_filter:
            recenti = config_manager.load_recent()
            if recenti:
                recent_markup = f"<b><span foreground='#e8a020'>⏱ {GLib.markup_escape_text(t('sidebar.recent_title'))}</span></b>"
                rec_iter = self._store.append(None, [folder_pb, recent_markup, "__recent__", True])
                for r in recenti:
                    nome = r.get("name", "")
                    if nome not in self._profili:
                        continue
                    dati  = self._profili[nome]
                    proto = dati.get("protocol", "ssh")
                    host  = dati.get("host", "")
                    user  = str(dati.get("user") or "")
                    color = PROTO_COLOR.get(proto, "#888888")
                    proto_lbl = PROTO_LABEL.get(proto, proto.upper())
                    user_display = "" if user.startswith("ENC:") else user
                    user_host = f"{GLib.markup_escape_text(user_display + '@' if user_display else '')}{GLib.markup_escape_text(host)}"
                    sub = f" <span foreground='gray' size='smaller'>({user_host})</span>" if host else ""
                    ts_sub = f" <span foreground='#666' size='smaller'>{GLib.markup_escape_text(r.get('ts', ''))}</span>"
                    dot = "<span foreground='#22cc55'>●</span> " if nome in self._open_sessions else ""
                    markup = (
                        f"<span foreground='{color}'><b>{GLib.markup_escape_text(proto_lbl)}</b></span> "
                        f"{dot}{GLib.markup_escape_text(nome)}{sub}{ts_sub}"
                    )
                    pb = _load_pixbuf(PROTO_ICON_FILE.get(proto, "network.png"), 16)
                    self._store.append(rec_iter, [pb, markup, nome, False])

        # ── Sessioni per gruppo ───────────────────────────────────────────
        gruppi: dict[str, list[str]] = {}
        for nome, dati in self._profili.items():
            if not _match_tag(dati):
                continue
            if filtro and filtro not in nome.lower():
                host = dati.get("host", "")
                user = str(dati.get("user") or "")
                if filtro not in host.lower() and filtro not in user.lower():
                    continue
            gruppo = dati.get("group", "") or t("sidebar.no_group")
            gruppi.setdefault(gruppo, []).append(nome)

        for gruppo in sorted(gruppi.keys()):
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
                user_host = f"{GLib.markup_escape_text(user_display + '@' if user_display else '')}{GLib.markup_escape_text(host)}"
                sub = f" <span foreground='gray' size='smaller'>({user_host})</span>" if host else ""
                dot = "<span foreground='#22cc55'>●</span> " if nome in self._open_sessions else ""
                markup = (
                    f"<span foreground='{color}'><b>{GLib.markup_escape_text(proto_lbl)}</b></span> "
                    f"{dot}{GLib.markup_escape_text(nome)}{sub}"
                )

                pb = _load_pixbuf(PROTO_ICON_FILE.get(proto, "network.png"), 16)
                self._store.append(grp_iter, [pb, markup, nome, False])

        self._tree.expand_all()

        if saved_scroll > 0:
            GLib.idle_add(adj.set_value, saved_scroll)

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
            chiave = self._store.get_value(it, 2)
            if chiave == "__recent__":
                self._mostra_menu_recent(event)
            return False
        nome = self._store.get_value(it, 2)
        dati = self._profili.get(nome, {})
        self._mostra_menu(event, nome, dati)
        return True

    def _mostra_menu_recent(self, event):
        menu = Gtk.Menu()
        mi = Gtk.MenuItem(label=t("sidebar.recent_clear"))
        mi.connect("activate", lambda _: self._cancella_recenti())
        menu.append(mi)
        menu.show_all()
        menu.popup_at_pointer(event)

    def _cancella_recenti(self):
        config_manager.clear_recent()
        self.aggiorna()

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

        proto = dati.get("protocol", "")
        if proto in ("ssh", "telnet", "mosh", "serial"):
            menu.append(Gtk.SeparatorMenuItem())
            _item(t("panel.open_ft_here"), lambda: self.emit("apri-ft", nome, dati))

        if proto == "ssh":
            _item(t("panel.apri_log"),     lambda: self.emit("apri-log",     nome, dati))
            _item(t("panel.apri_monitor"), lambda: self.emit("apri-monitor", nome, dati))
            _item(t("panel.apri_cron"),    lambda: self.emit("apri-cron",    nome, dati))

        if proto in ("ssh", "telnet", "mosh", "rdp", "vnc", "file_transfer"):
            _item(t("panel.apri_cluster"), lambda: self.emit("apri-cluster", nome, dati))

        host = dati.get("host", "")
        if host and proto not in ("serial", "exec"):
            menu.append(Gtk.SeparatorMenuItem())
            _item(t("sidebar.ping_btn"), lambda: self.emit("ping", nome, dati))

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
