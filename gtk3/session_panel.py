"""
session_panel.py - Pannello sidebar sessioni PCM (GTK3)

Usa Gtk.TreeView + Gtk.TreeStore al posto di QTreeWidget.
Segnali emessi:
  - 'connetti'   (nome: str, dati: dict)
   - 'nuova'      ()
   - 'nuova-in-gruppo' (gruppo: str)
   - 'modifica'   (nome: str, dati: dict)
  - 'elimina'    (nome: str)
  - 'duplica'    (nome: str)
"""

import os
import threading
import time

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


_DEFAULT_PORT = {
    "ssh": 22, "mosh": 22, "sftp": 22, "file_transfer": 22, "telnet": 23,
    "ftp": 21, "ftps": 21, "rdp": 3389, "vnc": 5900, "spice": 5900,
}


class SessionPanel(Gtk.Box):

    __gsignals__ = {
        "connetti":     (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "nuova":        (GObject.SignalFlags.RUN_FIRST, None, ()),
        "nuova-in-gruppo": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "modifica":     (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "elimina":      (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "duplica":      (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "clona-modifica": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "ping-gruppo":    (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "apri-ft":      (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "ping":         (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-log":     (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-monitor": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-cron":    (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-cluster": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "apri-tools":   (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "preferiti-cambiati": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "apri-multiplo": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.get_style_context().add_class("session-sidebar")
        self._profili: dict = {}
        self._open_sessions: set = set()
        self._reach: dict = {}          # nome -> bool (raggiungibilita' host:porta)
        self._reach_enabled = bool(
            config_manager.load_settings().get("general", {}).get("sidebar_status", True))
        self._init_ui()
        self.aggiorna()
        if self._reach_enabled:
            self._reach_stop = False
            threading.Thread(target=self._reach_loop, daemon=True).start()
            self.connect("destroy", lambda *_: setattr(self, "_reach_stop", True))

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
        self._tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self._tree.set_has_tooltip(True)
        self._tree.connect("query-tooltip", self._on_query_tooltip)

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

        # Ricorda i gruppi chiusi dall'utente: expand_all() li riaprirebbe
        chiusi = set()
        it = self._store.get_iter_first()
        def _raccogli(it):
            while it:
                if self._store.get_value(it, 3):
                    pth = self._store.get_path(it)
                    if not self._tree.row_expanded(pth):
                        chiusi.add(self._store.get_value(it, 2))
                    ch = self._store.iter_children(it)
                    if ch:
                        _raccogli(ch)
                it = self._store.iter_next(it)
        _raccogli(it)

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

        # ── Sezione Preferiti (solo senza filtro) ─────────────────────────
        if not filtro and not tag_filter:
            favoriti = sorted(n for n, d in self._profili.items()
                              if isinstance(d, dict) and config_manager.is_favorite(d))
            if favoriti:
                fav_markup = f"<b><span foreground='#f5c518'>★ {GLib.markup_escape_text(t('sidebar.favorites_title'))}</span></b>"
                fav_iter = self._store.append(None, [folder_pb, fav_markup, "__favorites__", True])
                for nome in favoriti:
                    dati  = self._profili[nome]
                    proto = dati.get("protocol", "ssh")
                    host  = dati.get("host", "")
                    color = PROTO_COLOR.get(proto, "#888888")
                    proto_lbl = PROTO_LABEL.get(proto, proto.upper())
                    sub = f" <span foreground='gray' size='smaller'>({GLib.markup_escape_text(host)})</span>" if host else ""
                    dot = "<span foreground='#22cc55'>●</span> " if nome in self._open_sessions else ""
                    markup = (
                        f"<span foreground='{color}'><b>{GLib.markup_escape_text(proto_lbl)}</b></span> "
                        f"{dot}{GLib.markup_escape_text(nome)}{sub}"
                    )
                    pb = _load_pixbuf(PROTO_ICON_FILE.get(proto, "network.png"), 16)
                    self._store.append(fav_iter, [pb, markup, nome, False])

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
            if filtro and not all(term in config_manager.session_search_text(nome, dati)
                                  for term in filtro.split()):
                continue
            gruppo_raw = str(dati.get("group", "") or "").strip()
            gruppo = gruppo_raw or t("sidebar.no_group")
            gruppi.setdefault(gruppo, []).append(nome)

        group_iters = {}
        for gruppo in sorted(gruppi.keys()):
            parent = None
            path = []
            for segment in [part.strip() for part in gruppo.split("/") if part.strip()]:
                path.append(segment)
                group_key = "/".join(path)
                grp_iter = group_iters.get(group_key)
                if grp_iter is None:
                    grp_markup = f"<b>{GLib.markup_escape_text(segment)}</b>"
                    # Conserva il percorso del gruppo nel modello: serve al
                    # menu contestuale per sapere dove inserire la nuova
                    # connessione.
                    grp_iter = self._store.append(parent, [folder_pb, grp_markup,
                                                           group_key if gruppo != t("sidebar.no_group") else "", True])
                    group_iters[group_key] = grp_iter
                parent = grp_iter

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
                dot += self._reach_dot(nome)
                markup = (
                    f"<span foreground='{color}'><b>{GLib.markup_escape_text(proto_lbl)}</b></span> "
                    f"{dot}{GLib.markup_escape_text(nome)}{sub}"
                )

                pb = _load_pixbuf(PROTO_ICON_FILE.get(proto, "network.png"), 16)
                self._store.append(parent, [pb, markup, nome, False])

        self._tree.expand_all()
        if chiusi and not filtro:
            def _richiudi(it):
                while it:
                    if self._store.get_value(it, 3):
                        if self._store.get_value(it, 2) in chiusi:
                            self._tree.collapse_row(self._store.get_path(it))
                        else:
                            ch = self._store.iter_children(it)
                            if ch:
                                _richiudi(ch)
                    it = self._store.iter_next(it)
            _richiudi(self._store.get_iter_first())

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
            elif chiave == "__favorites__":
                return False
            else:
                self._mostra_menu_gruppo(event, chiave)
            return True
        sel_model, sel_paths = self._tree.get_selection().get_selected_rows()
        selezionati = [sel_model.get_value(sel_model.get_iter(pth), 2) for pth in sel_paths
                       if not sel_model.get_value(sel_model.get_iter(pth), 3)]
        if len(selezionati) > 1 and path in sel_paths:
            self._mostra_menu_selezione(event, selezionati)
            return True
        nome = self._store.get_value(it, 2)
        dati = self._profili.get(nome, {})
        parent = self._store.iter_parent(it)
        in_recent = bool(parent and self._store.get_value(parent, 2) == "__recent__")
        self._mostra_menu(event, nome, dati, in_recent)
        return True

    def _mostra_menu_recent(self, event):
        menu = Gtk.Menu()
        mi = Gtk.MenuItem(label=t("sidebar.recent_clear"))
        mi.connect("activate", lambda _: self._cancella_recenti())
        menu.append(mi)
        menu.show_all()
        menu.popup_at_pointer(event)

    def _mostra_menu_gruppo(self, event, gruppo: str):
        """Mostra le azioni disponibili per una cartella di sessioni."""
        menu = Gtk.Menu()
        nome_gruppo = gruppo or t("sidebar.no_group").strip()
        label = t("panel.new_in_group", group=nome_gruppo)
        mi = Gtk.MenuItem(label=label)
        mi.connect("activate", lambda _: self.emit("nuova-in-gruppo", gruppo))
        menu.append(mi)

        mi_all = Gtk.MenuItem(label=t("panel.open_group_all"))
        mi_all.connect("activate", lambda _: self._apri_gruppo(gruppo))
        menu.append(mi_all)

        mi_ping = Gtk.MenuItem(label=t("panel.ping_group"))
        mi_ping.connect("activate", lambda _: self.emit("ping-gruppo", gruppo))
        menu.append(mi_ping)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _cancella_recenti(self):
        config_manager.clear_recent()
        self.aggiorna()

    # ------------------------------------------------------------------
    # Raggiungibilita' host (pallino in sidebar) e tooltip
    # ------------------------------------------------------------------

    _REACH_INTERVAL = 60
    _REACH_SKIP_PROTO = {"serial", "exec", "local"}

    def _reach_dot(self, nome: str) -> str:
        ok = self._reach.get(nome)
        if ok is None:
            return ""
        colore = "#4caf50" if ok else "#e55353"
        return f"<span foreground='{colore}' size='x-small'>▪</span> "

    def _reach_targets(self) -> dict:
        targets = {}
        for nome, d in self._profili.items():
            if not isinstance(d, dict):
                continue
            host = str(d.get("host", "") or "").strip()
            if (not host or d.get("protocol", "ssh") in self._REACH_SKIP_PROTO
                    or str(d.get("jump_host", "")).strip() or host.startswith("ENC:")
                    or str(d.get("pre_cmd", "")).strip() or d.get("wol_enabled")):
                continue
            porta = d.get("port") or _DEFAULT_PORT.get(d.get("protocol", "ssh"), 22)
            try:
                targets[nome] = (host, int(porta))
            except (TypeError, ValueError):
                pass
        return targets

    def _reach_loop(self):
        import socket
        from concurrent.futures import ThreadPoolExecutor

        def _check(item):
            nome, (host, porta) = item
            try:
                with socket.create_connection((host, porta), timeout=1.5):
                    return nome, True
            except OSError:
                return nome, False

        while not self._reach_stop:
            targets = dict(self._reach_targets())
            if targets:
                with ThreadPoolExecutor(max_workers=8) as ex:
                    risultati = dict(ex.map(_check, targets.items()))
                if risultati != self._reach:
                    self._reach = risultati
                    GLib.idle_add(self._reach_refresh)
            for _ in range(self._REACH_INTERVAL * 2):
                if self._reach_stop:
                    return
                time.sleep(0.5)

    def _reach_refresh(self):
        self._ricostruisci(self._search.get_text())
        return False

    def _on_query_tooltip(self, tree, x, y, keyboard, tooltip):
        info = tree.get_path_at_pos(*tree.convert_widget_to_bin_window_coords(x, y))
        if not info:
            return False
        it = self._store.get_iter(info[0])
        if it is None or self._store.get_value(it, 3):
            return False
        nome = self._store.get_value(it, 2)
        dati = self._profili.get(nome, {})
        righe = [nome]
        host = dati.get("host", "")
        if host:
            righe.append(f"{dati.get('protocol', 'ssh').upper()}  {host}")
        st = config_manager.get_session_stats(nome)
        if st:
            righe.append(t("sidebar.tt_stats", count=st.get("count", 0), last=st.get("last", "")))
        ok = self._reach.get(nome)
        if ok is not None:
            righe.append(t("sidebar.tt_reachable") if ok else t("sidebar.tt_unreachable"))
        tooltip.set_text("\n".join(righe))
        tree.set_tooltip_row(tooltip, info[0])
        return True

    def _apri_gruppo(self, gruppo: str):
        nomi = []
        for nome, d in sorted(self._profili.items()):
            g = str(d.get("group", "") or "").strip()
            if gruppo == "" and g == "" or g == gruppo or (gruppo and g.startswith(gruppo + "/")):
                nomi.append(nome)
        if nomi:
            self.emit("apri-multiplo", nomi)

    def _mostra_menu_selezione(self, event, nomi: list):
        menu = Gtk.Menu()
        mi = Gtk.MenuItem(label=t("panel.open_selected", n=len(nomi)))
        mi.connect("activate", lambda _: self.emit("apri-multiplo", nomi))
        menu.append(mi)
        menu.show_all()
        menu.popup_at_pointer(event)

    def _toggle_preferito(self, nome: str):
        profili = config_manager.toggle_favorite(nome)
        if profili is not None:
            self.aggiorna(profili)
            self.emit("preferiti-cambiati")

    def _rimuovi_recente(self, nome: str):
        config_manager.remove_recent(nome)
        self.aggiorna()
        self.emit("preferiti-cambiati")

    def _mostra_menu(self, event, nome: str, dati: dict, in_recent: bool = False):
        menu = Gtk.Menu()

        def _item(label, callback):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: callback())
            menu.append(mi)

        _item(t("panel.connect"),   lambda: self.emit("connetti", nome, dati))
        _item(t("panel.unfavorite") if config_manager.is_favorite(dati) else t("panel.favorite"),
              lambda: self._toggle_preferito(nome))
        if in_recent:
            _item(t("sidebar.recent_remove"), lambda: self._rimuovi_recente(nome))
        menu.append(Gtk.SeparatorMenuItem())
        _item(t("panel.edit"),      lambda: self.emit("modifica", nome, dati))
        _item(t("panel.duplicate"), lambda: self.emit("duplica", nome))
        _item(t("panel.clone_edit"), lambda: self.emit("clona-modifica", nome, dati))
        _item(t("panel.external_tools"), lambda: self.emit("apri-tools", nome, dati))
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
