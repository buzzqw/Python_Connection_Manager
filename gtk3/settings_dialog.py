"""
settings_dialog.py - Impostazioni globali PCM (GTK3)

Gtk.Dialog con Gtk.Notebook (tab).
Tab: Generale, Terminale, SSH, Scorciatoie.
"""

import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import config_manager
from themes import TERMINAL_THEMES
from translations import t, AVAILABLE_LANGUAGES, set_lang


class SettingsDialog(Gtk.Dialog):

    def __init__(self, parent=None):
        super().__init__(
            title=t("settings.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.set_default_size(580, 520)
        self._settings = config_manager.load_settings()
        self._init_ui()
        self._popola()
        self.show_all()

    # ------------------------------------------------------------------
    # Struttura principale
    # ------------------------------------------------------------------

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.set_margin_top(12)
        area.set_margin_bottom(8)

        hdr = Gtk.Label(label=t("settings.header"))
        hdr.get_style_context().add_class("section-header")
        hdr.set_xalign(0.0)
        area.pack_start(hdr, False, False, 0)

        self._notebook = Gtk.Notebook()
        area.pack_start(self._notebook, True, True, 0)

        self._notebook.append_page(self._build_generale(),    Gtk.Label(label=t("settings.tab.general")))
        self._notebook.append_page(self._build_terminale(),   Gtk.Label(label=t("settings.tab.terminal")))
        self._notebook.append_page(self._build_ssh(),         Gtk.Label(label=t("settings.tab.ssh")))
        self._notebook.append_page(self._build_scorciatoie(), Gtk.Label(label=t("settings.tab.shortcuts")))
        self._notebook.append_page(self._build_strumenti(),   Gtk.Label(label=t("settings.tab.tools")))

        self.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        ok_btn = self.add_button("OK", Gtk.ResponseType.OK)
        ok_btn.get_style_context().add_class("suggested-action")
        self.connect("response", self._on_response)

    # ------------------------------------------------------------------
    # Helper form row
    # ------------------------------------------------------------------

    @staticmethod
    def _form_row(label_text: str, widget: Gtk.Widget, grid: Gtk.Grid, row: int):
        lbl = Gtk.Label(label=label_text)
        lbl.set_xalign(1.0)
        lbl.set_margin_end(8)
        grid.attach(lbl, 0, row, 1, 1)
        grid.attach(widget, 1, row, 1, 1)

    @staticmethod
    def _make_grid() -> Gtk.Grid:
        g = Gtk.Grid()
        g.set_row_spacing(8)
        g.set_column_spacing(8)
        g.set_margin_start(12)
        g.set_margin_end(12)
        g.set_margin_top(12)
        g.set_margin_bottom(12)
        g.set_column_homogeneous(False)
        return g

    @staticmethod
    def _browse_dir(entry: Gtk.Entry, title: str, parent):
        dlg = Gtk.FileChooserDialog(
            title=title,
            parent=parent,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dlg.add_buttons(
            "_Annulla", Gtk.ResponseType.CANCEL,
            "_Seleziona", Gtk.ResponseType.OK
        )
        if dlg.run() == Gtk.ResponseType.OK:
            entry.set_text(dlg.get_filename())
        dlg.destroy()

    # ------------------------------------------------------------------
    # Tab Generale
    # ------------------------------------------------------------------

    def _build_generale(self) -> Gtk.Widget:
        grid = self._make_grid()
        row = 0

        # Home dir
        home_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.entry_home = Gtk.Entry()
        self.entry_home.set_hexpand(True)
        btn_home = Gtk.Button(label="…")
        btn_home.connect("clicked", lambda b: self._browse_dir(
            self.entry_home, "Home directory", self))
        home_box.pack_start(self.entry_home, True, True, 0)
        home_box.pack_start(btn_home, False, False, 0)
        self._form_row(t("settings.general.home_dir"), home_box, grid, row); row += 1

        # Editor
        self.combo_editor = Gtk.ComboBoxText.new_with_entry()
        for ed in ["nano", "vim", "vi", "gedit", "kate", "code", "mousepad"]:
            self.combo_editor.append_text(ed)
        self.combo_editor.set_hexpand(True)
        self._form_row(t("settings.general.editor"), self.combo_editor, grid, row); row += 1

        # Conferma uscita
        self.chk_confirm_exit = Gtk.CheckButton(label=t("settings.general.confirm_exit"))
        grid.attach(self.chk_confirm_exit, 0, row, 2, 1); row += 1

        # Separatore
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        grid.attach(sep, 0, row, 2, 1); row += 1

        # Lingua
        self.combo_lingua = Gtk.ComboBoxText()
        self._lang_codes = []
        for code, label in AVAILABLE_LANGUAGES.items():
            self.combo_lingua.append_text(label)
            self._lang_codes.append(code)
        self._form_row("Language / Lingua:", self.combo_lingua, grid, row); row += 1

        note_lbl = Gtk.Label(label=t("settings.general.language_note"))
        note_lbl.set_xalign(0.0)
        note_lbl.get_style_context().add_class("dim-label")
        grid.attach(note_lbl, 0, row, 2, 1); row += 1

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(grid)
        return sw

    # ------------------------------------------------------------------
    # Tab Terminale
    # ------------------------------------------------------------------

    def _build_terminale(self) -> Gtk.Widget:
        grid = self._make_grid()
        row = 0

        self.combo_tema = Gtk.ComboBoxText()
        for nome in TERMINAL_THEMES.keys():
            self.combo_tema.append_text(nome)
        self._form_row(t("settings.terminal.default_theme"), self.combo_tema, grid, row); row += 1

        self.combo_font = Gtk.ComboBoxText.new_with_entry()
        for f in ["Monospace", "DejaVu Sans Mono", "Hack", "JetBrains Mono",
                  "Fira Code", "Source Code Pro", "Inconsolata", "Terminus"]:
            self.combo_font.append_text(f)
        self._form_row(t("settings.terminal.default_font"), self.combo_font, grid, row); row += 1

        self.spin_font_size = Gtk.SpinButton.new_with_range(6, 32, 1)
        self._form_row(t("settings.terminal.font_size"), self.spin_font_size, grid, row); row += 1

        # Scrollback infinito checkbox
        self.chk_infinite_scrollback = Gtk.CheckButton(label=t("settings.terminal.infinite_scrollback"))
        grid.attach(self.chk_infinite_scrollback, 0, row, 2, 1); row += 1
        
        # Scrollback lines (disabilitato se infinito è attivo)
        self.spin_scrollback = Gtk.SpinButton.new_with_range(100, 100000, 1000)
        self._form_row(t("settings.terminal.scrollback"), self.spin_scrollback, grid, row); row += 1
        
        # Connetti il segnale per abilitare/disabilitare lo spin button
        self.chk_infinite_scrollback.connect("toggled", self._on_infinite_scrollback_toggled)

        self.chk_confirm_close = Gtk.CheckButton(label=t("settings.terminal.confirm_close"))
        grid.attach(self.chk_confirm_close, 0, row, 2, 1); row += 1

        self.chk_warn_paste = Gtk.CheckButton(label=t("settings.terminal.warn_paste"))
        grid.attach(self.chk_warn_paste, 0, row, 2, 1); row += 1

        self.chk_log = Gtk.CheckButton(label=t("settings.terminal.log_output"))
        grid.attach(self.chk_log, 0, row, 2, 1); row += 1

        log_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.entry_log_dir = Gtk.Entry()
        self.entry_log_dir.set_hexpand(True)
        btn_log = Gtk.Button(label="…")
        btn_log.connect("clicked", lambda b: self._browse_dir(
            self.entry_log_dir, "Log folder", self))
        log_box.pack_start(self.entry_log_dir, True, True, 0)
        log_box.pack_start(btn_log, False, False, 0)
        self._form_row(t("settings.terminal.log_dir"), log_box, grid, row); row += 1

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(grid)
        return sw

    def _on_infinite_scrollback_toggled(self, checkbox):
        """Abilita/disabilita lo spin button quando il checkbox scrollback infinito viene attivato/disattivato."""
        is_infinite = checkbox.get_active()
        self.spin_scrollback.set_sensitive(not is_infinite)

    # ------------------------------------------------------------------
    # Tab SSH
    # ------------------------------------------------------------------

    def _build_ssh(self) -> Gtk.Widget:
        grid = self._make_grid()
        row = 0

        self.spin_ka = Gtk.SpinButton.new_with_range(0, 3600, 1)
        self._form_row(t("settings.ssh.keepalive"), self.spin_ka, grid, row); row += 1

        self.chk_strict = Gtk.CheckButton(label=t("settings.ssh.strict"))
        grid.attach(self.chk_strict, 0, row, 2, 1); row += 1

        self.chk_sftp_auto = Gtk.CheckButton(label=t("settings.ssh.sftp_auto"))
        grid.attach(self.chk_sftp_auto, 0, row, 2, 1); row += 1

        return grid

    # ------------------------------------------------------------------
    # Tab Strumenti personalizzati (VNC / RDP)
    # ------------------------------------------------------------------

    def _build_strumenti(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_start(12); outer.set_margin_end(12)
        outer.set_margin_top(12);   outer.set_margin_bottom(12)

        for category, label in [("vnc", t("settings.tools.vnc_group")),
                                 ("rdp", t("settings.tools.rdp_group"))]:
            grp = Gtk.Frame()
            grp_lbl = Gtk.Label(label=f"<b>{label}</b>")
            grp_lbl.set_use_markup(True)
            grp.set_label_widget(grp_lbl)
            grp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            grp_box.set_margin_start(8); grp_box.set_margin_end(8)
            grp_box.set_margin_top(4);   grp_box.set_margin_bottom(8)

            # TreeView: Etichetta, Percorso, Sintassi
            store = Gtk.ListStore(str, str, str)
            view  = Gtk.TreeView(model=store)
            view.set_headers_visible(True)
            view.set_size_request(-1, 110)

            for i, col_title in enumerate([t("settings.tools.col_label"),
                                           t("settings.tools.col_path"),
                                           t("settings.tools.col_syntax")]):
                cell = Gtk.CellRendererText()
                cell.set_property("editable", True)
                cell.connect("edited", self._on_tool_cell_edited, store, i)
                col = Gtk.TreeViewColumn(col_title, cell, text=i)
                col.set_expand(i == 1)
                col.set_resizable(True)
                view.append_column(col)

            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.add(view)
            grp_box.pack_start(scroll, True, True, 0)

            # Toolbar
            tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            btn_add = Gtk.Button(label=t("settings.tools.add"))
            btn_rem = Gtk.Button(label=t("settings.tools.remove"))
            btn_add.connect("clicked", lambda b, s=store, c=category: self._aggiungi_tool(s, c))
            btn_rem.connect("clicked", lambda b, v=view, s=store: self._rimuovi_tool(v, s))
            tb.pack_start(btn_add, False, False, 0)
            tb.pack_start(btn_rem, False, False, 0)
            grp_box.pack_start(tb, False, False, 0)

            grp.add(grp_box)
            outer.pack_start(grp, False, False, 0)

            # Salva riferimento store per popola/salva
            if category == "vnc":
                self._store_vnc = store
            else:
                self._store_rdp = store

        nota = Gtk.Label(label=t("settings.tools.note"))
        nota.set_xalign(0.0)
        nota.get_style_context().add_class("dim-label")
        nota.set_line_wrap(True)
        outer.pack_start(nota, False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(outer)
        return sw

    def _on_tool_cell_edited(self, cell, path, new_text, store, col):
        it = store.get_iter_from_string(path)
        if it is not None:
            store.set_value(it, col, new_text)

    def _aggiungi_tool(self, store: Gtk.ListStore, category: str):
        syntaxes_vnc = ["TigerVNC", "RealVNC", "Remmina", "Generico"]
        syntaxes_rdp = ["xfreerdp", "rdesktop", "Generico"]
        syntaxes = syntaxes_vnc if category == "vnc" else syntaxes_rdp
        title_key = "settings.tools.dlg_title_vnc" if category == "vnc" else "settings.tools.dlg_title_rdp"

        dlg = Gtk.Dialog(title=t(title_key), transient_for=self, modal=True)
        dlg.set_default_size(400, -1)
        area = dlg.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12); area.set_margin_end(12)
        area.set_margin_top(12);   area.set_margin_bottom(8)

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)

        def _lbl(txt):
            l = Gtk.Label(label=txt)
            l.set_xalign(1.0)
            return l

        entry_label = Gtk.Entry()
        entry_label.set_hexpand(True)
        entry_label.set_placeholder_text("UltraVNC, AnyDesk…")
        grid.attach(_lbl(t("settings.tools.lbl_label")), 0, 0, 1, 1)
        grid.attach(entry_label, 1, 0, 1, 1)

        path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        entry_path = Gtk.Entry()
        entry_path.set_hexpand(True)
        entry_path.set_placeholder_text("/usr/bin/vncviewer")
        btn_browse = Gtk.Button(label="…")
        btn_browse.connect("clicked", lambda b: self._browse_exe(entry_path))
        path_box.pack_start(entry_path,  True,  True,  0)
        path_box.pack_start(btn_browse,  False, False, 0)
        grid.attach(_lbl(t("settings.tools.lbl_path")), 0, 1, 1, 1)
        grid.attach(path_box, 1, 1, 1, 1)

        combo_syntax = Gtk.ComboBoxText()
        for s in syntaxes:
            combo_syntax.append_text(s)
        combo_syntax.set_active(0)
        combo_syntax.set_hexpand(True)
        grid.attach(_lbl(t("settings.tools.lbl_syntax")), 0, 2, 1, 1)
        grid.attach(combo_syntax, 1, 2, 1, 1)

        area.pack_start(grid, False, False, 0)
        area.show_all()

        dlg.add_buttons(t("sd.cancel"), Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            label   = entry_label.get_text().strip()
            path    = entry_path.get_text().strip()
            syntax  = combo_syntax.get_active_text() or syntaxes[0]
            if label and path:
                store.append([label, path, syntax])
        dlg.destroy()

    def _rimuovi_tool(self, view: Gtk.TreeView, store: Gtk.ListStore):
        sel = view.get_selection()
        model, it = sel.get_selected()
        if it:
            store.remove(it)

    def _browse_exe(self, entry: Gtk.Entry):
        dlg = Gtk.FileChooserDialog(
            title=t("settings.tools.browse"),
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons(t("sd.cancel"), Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        dlg.set_current_folder("/usr/bin")
        if dlg.run() == Gtk.ResponseType.OK:
            entry.set_text(dlg.get_filename())
        dlg.destroy()

    # ------------------------------------------------------------------
    # Tab Scorciatoie
    # ------------------------------------------------------------------

    def _build_scorciatoie(self) -> Gtk.Widget:
        grid = self._make_grid()
        self._shortcut_entries: dict[str, Gtk.Entry] = {}
        row = 0

        labels = {
            "new_terminal":   "settings.shortcuts.new_terminal",
            "close_tab":      "settings.shortcuts.close_tab",
            "prev_tab":       "settings.shortcuts.prev_tab",
            "next_tab":       "settings.shortcuts.next_tab",
            "new_session":    "settings.shortcuts.new_session",
            "toggle_sidebar": "settings.shortcuts.toggle_sidebar",
            "find":           "settings.shortcuts.find",
            "fullscreen":     "settings.shortcuts.fullscreen",
        }
        for key, t_key in labels.items():
            entry = Gtk.Entry()
            entry.set_width_chars(20)
            self._shortcut_entries[key] = entry
            self._form_row(f"{t(t_key)}:", entry, grid, row)
            row += 1

        note = Gtk.Label(label=t("settings.shortcuts.note"))
        note.set_xalign(0.0)
        note.get_style_context().add_class("dim-label")
        grid.attach(note, 0, row, 2, 1)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(grid)
        return sw

    # ------------------------------------------------------------------
    # Popola / Salva
    # ------------------------------------------------------------------

    def _popola(self):
        g = self._settings.get("general", {})
        self.entry_home.set_text(g.get("home_dir", os.path.expanduser("~")))

        # editor
        ed = g.get("default_editor", "nano")
        child = self.combo_editor.get_child()
        if child:
            child.set_text(ed)

        self.chk_confirm_exit.set_active(g.get("confirm_on_exit", True))

        lang_code = g.get("language", "it")
        if lang_code in self._lang_codes:
            self.combo_lingua.set_active(self._lang_codes.index(lang_code))

        term = self._settings.get("terminal", {})
        self._set_combo_text(self.combo_tema, term.get("default_theme", "Dark (Default)"))
        font_child = self.combo_font.get_child()
        if font_child:
            font_child.set_text(term.get("default_font", "Monospace"))
        self.spin_font_size.set_value(term.get("default_font_size", 11))
        
        # Gestione scrollback infinito
        infinite_scrollback = term.get("infinite_scrollback", False)
        self.chk_infinite_scrollback.set_active(infinite_scrollback)
        if infinite_scrollback:
            self.spin_scrollback.set_sensitive(False)
        else:
            self.spin_scrollback.set_value(term.get("scrollback_lines", 10000))
        
        self.chk_confirm_close.set_active(term.get("confirm_on_close", True))
        self.chk_warn_paste.set_active(term.get("warn_multiline_paste", True))
        self.chk_log.set_active(term.get("log_output", False))
        self.entry_log_dir.set_text(term.get("log_dir", "/tmp/pcm_logs"))

        ssh = self._settings.get("ssh", {})
        self.spin_ka.set_value(ssh.get("keepalive_interval", 60))
        self.chk_strict.set_active(ssh.get("strict_host_check", False))
        self.chk_sftp_auto.set_active(ssh.get("default_sftp_browser", True))

        sc = self._settings.get("shortcuts", {})
        for key, entry in self._shortcut_entries.items():
            entry.set_text(sc.get(key, ""))

        ct = self._settings.get("custom_tools", {"vnc": [], "rdp": []})
        for store, key in [(self._store_vnc, "vnc"), (self._store_rdp, "rdp")]:
            store.clear()
            for e in ct.get(key, []):
                store.append([e.get("label", ""), e.get("path", ""), e.get("syntax", "")])

    @staticmethod
    def _set_combo_text(combo: Gtk.ComboBoxText, value: str):
        model = combo.get_model()
        for i, row in enumerate(model):
            if row[0] == value:
                combo.set_active(i)
                return

    def _on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            self._salva()

    def _salva(self):
        s = self._settings

        s["general"]["home_dir"]       = self.entry_home.get_text().strip()
        ed_child = self.combo_editor.get_child()
        s["general"]["default_editor"] = ed_child.get_text() if ed_child else "nano"
        s["general"]["confirm_on_exit"] = self.chk_confirm_exit.get_active()

        idx_lang = self.combo_lingua.get_active()
        if 0 <= idx_lang < len(self._lang_codes):
            lang = self._lang_codes[idx_lang]
            s["general"]["language"] = lang
            set_lang(lang)

        s["terminal"]["default_theme"]        = self.combo_tema.get_active_text() or "Dark (Default)"
        font_child = self.combo_font.get_child()
        s["terminal"]["default_font"]         = font_child.get_text() if font_child else "Monospace"
        s["terminal"]["default_font_size"]    = int(self.spin_font_size.get_value())
        # Gestione scrollback infinito nel salvataggio
        s["terminal"]["infinite_scrollback"] = self.chk_infinite_scrollback.get_active()
        if not self.chk_infinite_scrollback.get_active():
            s["terminal"]["scrollback_lines"] = int(self.spin_scrollback.get_value())
        
        s["terminal"]["confirm_on_close"]     = self.chk_confirm_close.get_active()
        s["terminal"]["warn_multiline_paste"] = self.chk_warn_paste.get_active()
        s["terminal"]["log_output"]           = self.chk_log.get_active()
        s["terminal"]["log_dir"]              = self.entry_log_dir.get_text().strip()

        s["ssh"]["keepalive_interval"]   = int(self.spin_ka.get_value())
        s["ssh"]["strict_host_check"]    = self.chk_strict.get_active()
        s["ssh"]["default_sftp_browser"] = self.chk_sftp_auto.get_active()

        for key, entry in self._shortcut_entries.items():
            s["shortcuts"][key] = entry.get_text().strip()

        s["custom_tools"] = {
            "vnc": [{"label": r[0], "path": r[1], "syntax": r[2]}
                    for r in self._store_vnc if r[0] and r[1]],
            "rdp": [{"label": r[0], "path": r[1], "syntax": r[2]}
                    for r in self._store_rdp if r[0] and r[1]],
        }

        config_manager.save_settings(s)
