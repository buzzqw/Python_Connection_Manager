"""
snippets_dialog.py — Libreria globale di snippet/comandi per PCM (GTK3)

Salva in pcm_settings.json["snippets"] come lista di dict:
  {"nome": str, "categoria": str, "cmd": str}
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import config_manager


def load_snippets() -> list:
    return list(config_manager.load_settings().get("snippets", []))


def save_snippets(snippets: list):
    s = config_manager.load_settings()
    s["snippets"] = snippets
    config_manager.save_settings(s)


# ---------------------------------------------------------------------------
# Dialog add/edit singolo snippet
# ---------------------------------------------------------------------------

class _SnippetEditDialog(Gtk.Dialog):

    def __init__(self, parent, snippet=None):
        title = "Nuovo snippet" if snippet is None else "Modifica snippet"
        super().__init__(title=title, transient_for=parent, modal=True)
        self.add_buttons("_Annulla", Gtk.ResponseType.CANCEL,
                         "_OK",      Gtk.ResponseType.OK)
        self.set_default_size(500, 200)

        grid = Gtk.Grid(column_spacing=8, row_spacing=6,
                        margin_start=12, margin_end=12,
                        margin_top=8,   margin_bottom=8)

        def _lbl(txt):
            l = Gtk.Label(label=txt, xalign=1.0)
            l.set_width_chars(12)
            return l

        self._e_nome = Gtk.Entry(); self._e_nome.set_hexpand(True)
        self._e_cat  = Gtk.Entry()
        self._e_cat.set_placeholder_text("es. SSH, Monitoraggio, Admin…")
        self._e_cmd  = Gtk.Entry(); self._e_cmd.set_hexpand(True)

        if snippet:
            self._e_nome.set_text(snippet.get("nome", ""))
            self._e_cat.set_text(snippet.get("categoria", ""))
            self._e_cmd.set_text(snippet.get("cmd", ""))

        grid.attach(_lbl("Nome:"),      0, 0, 1, 1); grid.attach(self._e_nome, 1, 0, 1, 1)
        grid.attach(_lbl("Categoria:"), 0, 1, 1, 1); grid.attach(self._e_cat,  1, 1, 1, 1)
        grid.attach(_lbl("Comando:"),   0, 2, 1, 1); grid.attach(self._e_cmd,  1, 2, 1, 1)

        self.get_content_area().add(grid)
        grid.show_all()
        self.set_default_response(Gtk.ResponseType.OK)
        self._e_cmd.connect("activate", lambda _: self.response(Gtk.ResponseType.OK))

    def get_snippet(self) -> dict:
        return {
            "nome":      self._e_nome.get_text().strip(),
            "categoria": self._e_cat.get_text().strip(),
            "cmd":       self._e_cmd.get_text(),
        }


# ---------------------------------------------------------------------------
# Dialog principale libreria
# ---------------------------------------------------------------------------

class SnippetsDialog(Gtk.Dialog):
    """
    Dialog per gestire la libreria globale di snippet.
    on_invia: callable(cmd: str) — chiamato quando l'utente clicca
              "Invia al terminale" o fa doppio click su una riga.
    """

    def __init__(self, parent, on_invia=None):
        super().__init__(title="Libreria snippet", transient_for=parent, modal=True)
        self.add_button("_Chiudi", Gtk.ResponseType.CLOSE)
        self.set_default_size(640, 420)
        self._on_invia   = on_invia
        self._snippets   = load_snippets()
        self._build()

    def _build(self):
        box = self.get_content_area()
        box.set_spacing(0)

        # ── Toolbar ──────────────────────────────────────────────────────
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_margin_start(8); tb.set_margin_top(8); tb.set_margin_bottom(4)

        btn_add  = Gtk.Button(label="+ Aggiungi")
        btn_edit = Gtk.Button(label="✎ Modifica")
        btn_del  = Gtk.Button(label="✕ Elimina")
        btn_add.connect("clicked",  self._on_add)
        btn_edit.connect("clicked", self._on_edit)
        btn_del.connect("clicked",  self._on_delete)

        self._btn_invia = Gtk.Button(label="▶ Invia al terminale")
        self._btn_invia.set_sensitive(False)
        if self._on_invia:
            self._btn_invia.connect("clicked", self._esegui_invia)
        else:
            self._btn_invia.set_no_show_all(True)
            self._btn_invia.hide()

        tb.pack_start(btn_add,           False, False, 0)
        tb.pack_start(btn_edit,          False, False, 0)
        tb.pack_start(btn_del,           False, False, 0)
        tb.pack_end(self._btn_invia,     False, False, 0)
        box.pack_start(tb, False, False, 0)

        # ── TreeView ──────────────────────────────────────────────────────
        # cols: categoria(0), nome(1), cmd(2)
        self._store = Gtk.ListStore(str, str, str)
        self._view  = Gtk.TreeView(model=self._store)
        self._view.set_headers_visible(True)

        for i, (h, expand) in enumerate([("Categoria", False), ("Nome", False), ("Comando", True)]):
            cell = Gtk.CellRendererText()
            col  = Gtk.TreeViewColumn(h, cell, text=i)
            col.set_resizable(True)
            if expand:
                col.set_expand(True)
            else:
                col.set_min_width(110)
            self._view.append_column(col)

        self._view.connect("row-activated", lambda _v, _p, _c: self._esegui_invia())
        self._view.get_selection().connect("changed", self._on_sel_changed)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._view)
        scroll.set_vexpand(True)
        box.pack_start(scroll, True, True, 0)

        self._popola()
        box.show_all()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _popola(self):
        self._store.clear()
        for s in sorted(self._snippets,
                        key=lambda x: (x.get("categoria", ""), x.get("nome", ""))):
            self._store.append([s.get("categoria", ""), s.get("nome", ""), s.get("cmd", "")])

    def _sel_row(self) -> tuple:
        """Ritorna (model, iter) della riga selezionata o (None, None)."""
        return self._view.get_selection().get_selected()

    def _on_sel_changed(self, sel):
        self._btn_invia.set_sensitive(sel.get_selected()[1] is not None)

    # ── CRUD ─────────────────────────────────────────────────────────────

    def _on_add(self, _btn):
        dlg = _SnippetEditDialog(parent=self)
        if dlg.run() == Gtk.ResponseType.OK:
            s = dlg.get_snippet()
            if s["nome"] or s["cmd"]:
                self._snippets.append(s)
                save_snippets(self._snippets)
                self._popola()
        dlg.destroy()

    def _on_edit(self, _btn=None):
        model, it = self._sel_row()
        if it is None:
            return
        snippet = {"categoria": model[it][0], "nome": model[it][1], "cmd": model[it][2]}
        dlg = _SnippetEditDialog(parent=self, snippet=snippet)
        if dlg.run() == Gtk.ResponseType.OK:
            nuovo = dlg.get_snippet()
            for i, s in enumerate(self._snippets):
                if s.get("nome") == snippet["nome"] and s.get("cmd") == snippet["cmd"]:
                    self._snippets[i] = nuovo
                    break
            save_snippets(self._snippets)
            self._popola()
        dlg.destroy()

    def _on_delete(self, _btn=None):
        model, it = self._sel_row()
        if it is None:
            return
        nome = model[it][1]; cmd = model[it][2]
        self._snippets = [s for s in self._snippets
                          if not (s.get("nome") == nome and s.get("cmd") == cmd)]
        save_snippets(self._snippets)
        self._popola()

    def _esegui_invia(self, _btn=None):
        if not self._on_invia:
            return
        model, it = self._sel_row()
        if it is not None:
            self._on_invia(model[it][2])
