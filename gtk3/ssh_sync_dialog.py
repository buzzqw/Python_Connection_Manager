"""
ssh_sync_dialog.py - Sincronizzazione dei profili con ~/.ssh/config.

Mostra in anteprima cosa cambierebbe (host nuovi, aggiornati campo per campo,
profili non più presenti nella config) e applica solo le voci selezionate.
"""

from __future__ import annotations

import os
import threading

import gi

gi.require_version("Gtk", "3.0")
import importer
from gi.repository import GLib, Gtk
from translations import t

# Colonne del ListStore
_C_ATTIVO, _C_TIPO, _C_AZIONE, _C_NOME, _C_DETTAGLI = range(5)

# Etichette con i nomi reali delle direttive OpenSSH: restano uguali in tutte
# le lingue, come nel file di configurazione.
_ETICHETTE_CAMPI = {
    "protocol":       "Protocol",
    "host":           "HostName",
    "port":           "Port",
    "user":           "User",
    "private_key":    "IdentityFile",
    "jump_host":      "ProxyJump",
    "jump_user":      "ProxyJump user",
    "jump_port":      "ProxyJump port",
    "notes":          "Notes",
}

_AZIONE = {
    "nuovo":     ("sshsync.act_new", "#2e7d32"),
    "aggiornato": ("sshsync.act_upd", "#1565c0"),
    "rimosso":   ("sshsync.act_rem", "#c62828"),
}


def _abbrevia(valore, limite: int = 60) -> str:
    testo = "" if valore is None else str(valore)
    if len(testo) > limite:
        return testo[:limite - 1] + "…"
    return testo


def _mostra_valore(valore) -> str:
    testo = _abbrevia(valore)
    return testo if testo else "—"


def _dettagli_campi(campi: dict) -> str:
    parti = []
    for campo, (vecchio, nuovo) in campi.items():
        etichetta = _ETICHETTE_CAMPI.get(campo, campo)
        parti.append(f"{etichetta}: {_mostra_valore(vecchio)} → "
                     f"{_mostra_valore(nuovo)}")
    return " · ".join(parti)


def _descrizione_host(dati: dict) -> str:
    host = (dati.get("host") or "").strip()
    porta = str(dati.get("port") or "22").strip()
    utente = (dati.get("user") or "").strip()
    destinazione = f"{utente}@{host}" if utente else host
    if porta and porta != "22":
        destinazione += f":{porta}"
    return destinazione


class SshSyncDialog(Gtk.Dialog):
    """Anteprima e applicazione delle differenze con ~/.ssh/config."""

    def __init__(self, parent: Gtk.Window | None = None,
                 percorso: str | None = None, on_applied=None):
        super().__init__(
            title=t("sshsync.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(760, 520)
        self._vivo = True
        self._on_applied = on_applied
        self._piano: dict | None = None
        self._store = Gtk.ListStore(bool, str, str, str, str)
        self._build_ui(percorso or "~/.ssh/config")
        self.connect("destroy", self._on_destroy)
        self.show_all()
        self._rileggi()

    # ------------------------------------------------------------------
    # Costruzione UI
    # ------------------------------------------------------------------

    def _build_ui(self, percorso: str):
        area = self.get_content_area()
        area.set_spacing(10)
        area.set_margin_start(16)
        area.set_margin_end(16)
        area.set_margin_top(16)
        area.set_margin_bottom(8)

        titolo = Gtk.Label(xalign=0.0)
        titolo.set_markup(f"<b>{t('sshsync.title')}</b>")
        area.pack_start(titolo, False, False, 0)

        intro = Gtk.Label(label=t("sshsync.intro"), xalign=0.0)
        intro.set_line_wrap(True)
        area.pack_start(intro, False, False, 0)

        # Riga percorso: entry + sfoglia + ricarica + spinner
        riga = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        riga.pack_start(Gtk.Label(label=t("sshsync.path_lbl")), False, False, 0)

        self._entry_path = Gtk.Entry(text=percorso)
        self._entry_path.set_hexpand(True)
        self._entry_path.connect("activate", lambda _e: self._rileggi())
        riga.pack_start(self._entry_path, True, True, 0)

        btn_sfoglia = Gtk.Button(label="…")
        btn_sfoglia.set_tooltip_text(t("sshsync.browse"))
        btn_sfoglia.connect("clicked", self._on_sfoglia)
        riga.pack_start(btn_sfoglia, False, False, 0)

        self._btn_ricarica = Gtk.Button.new_from_icon_name(
            "view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self._btn_ricarica.set_tooltip_text(t("sshsync.rescan"))
        self._btn_ricarica.connect("clicked", lambda _b: self._rileggi())
        riga.pack_start(self._btn_ricarica, False, False, 0)

        self._spinner = Gtk.Spinner()
        riga.pack_start(self._spinner, False, False, 0)

        area.pack_start(riga, False, False, 0)

        # Riepilogo
        self._lbl_riepilogo = Gtk.Label(xalign=0.0)
        self._lbl_riepilogo.set_line_wrap(True)
        self._lbl_riepilogo.set_markup(
            f"<span foreground='#666'>{t('sshsync.scanning')}</span>")
        area.pack_start(self._lbl_riepilogo, False, False, 0)

        # Filtri per categoria: attivano/disattivano interi gruppi
        filtri = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self._chk_new = Gtk.CheckButton(label=t("sshsync.cat_new", n=0))
        self._chk_upd = Gtk.CheckButton(label=t("sshsync.cat_upd", n=0))
        self._chk_rem = Gtk.CheckButton(label=t("sshsync.cat_rem", n=0))
        self._chk_new.set_active(True)
        self._chk_upd.set_active(True)
        self._chk_rem.set_active(False)
        for chk, tipo in ((self._chk_new, "nuovo"),
                          (self._chk_upd, "aggiornato"),
                          (self._chk_rem, "rimosso")):
            chk.connect("toggled", self._on_categoria, tipo)
            filtri.pack_start(chk, False, False, 0)
        area.pack_start(filtri, False, False, 0)

        # Tabella delle differenze
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.set_size_request(-1, 300)

        self._tree = Gtk.TreeView(model=self._store)
        self._tree.set_tooltip_column(_C_DETTAGLI)

        render_toggle = Gtk.CellRendererToggle()
        render_toggle.set_activatable(True)
        render_toggle.connect("toggled", self._on_toggle_riga)
        self._tree.append_column(Gtk.TreeViewColumn(
            "", render_toggle, active=_C_ATTIVO))

        for titolo_col, colonna, expand, markup in (
                (t("sshsync.col_action"), _C_AZIONE, False, True),
                (t("sshsync.col_name"), _C_NOME, False, False),
                (t("sshsync.col_details"), _C_DETTAGLI, True, False)):
            render = Gtk.CellRendererText()
            if colonna == _C_AZIONE:
                render.set_property("weight", 700)
            vista = Gtk.TreeViewColumn(titolo_col, render)
            if markup:
                vista.add_attribute(render, "markup", colonna)
            else:
                vista.add_attribute(render, "text", colonna)
            vista.set_expand(expand)
            vista.set_resizable(True)
            self._tree.append_column(vista)

        scroll.add(self._tree)
        area.pack_start(scroll, True, True, 0)

        nota = Gtk.Label(label=t("sshsync.hint"), xalign=0.0)
        nota.set_line_wrap(True)
        nota.get_style_context().add_class("dim-label")
        area.pack_start(nota, False, False, 0)

        self._lbl_result = Gtk.Label(xalign=0.0)
        self._lbl_result.set_line_wrap(True)
        area.pack_start(self._lbl_result, False, False, 0)

        # Pulsante di applicazione: non è un widget di risposta, così il
        # dialogo resta aperto per mostrare l'esito.
        self._btn_apply = Gtk.Button(label=t("sshsync.apply"))
        self._btn_apply.get_style_context().add_class("suggested-action")
        self._btn_apply.set_sensitive(False)
        self._btn_apply.connect("clicked", self._on_apply)
        self.get_action_area().pack_start(self._btn_apply, False, False, 0)

        self.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)

    # ------------------------------------------------------------------
    # Lettura e confronto
    # ------------------------------------------------------------------

    def _on_destroy(self, _w):
        self._vivo = False

    def _on_sfoglia(self, _btn):
        dlg = Gtk.FileChooserDialog(
            title=t("sshsync.browse"), parent=self,
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(t("sd.cancel"), Gtk.ResponseType.CANCEL,
                        t("sshsync.open"), Gtk.ResponseType.OK)
        cartella = os.path.dirname(os.path.expanduser(self._entry_path.get_text()))
        if os.path.isdir(cartella):
            dlg.set_current_folder(cartella)
        if dlg.run() == Gtk.ResponseType.OK:
            self._entry_path.set_text(dlg.get_filename() or "")
            dlg.destroy()
            self._rileggi()
            return
        dlg.destroy()

    def _rileggi(self):
        percorso = self._entry_path.get_text().strip() or "~/.ssh/config"
        self._piano = None
        self._store.clear()
        self._btn_apply.set_sensitive(False)
        self._lbl_riepilogo.set_markup(
            f"<span foreground='#666'>{t('sshsync.scanning')}</span>")
        for chk in (self._chk_new, self._chk_upd, self._chk_rem):
            chk.set_sensitive(False)
        self._spinner.start()
        self._btn_ricarica.set_sensitive(False)

        def _worker():
            try:
                espanso = os.path.expanduser(percorso)
                if not os.path.isfile(espanso):
                    GLib.idle_add(self._fine_lettura, None,
                                  t("sshsync.no_file", path=percorso))
                    return
                profili = importer.importa_ssh_config(espanso)
                piano = importer.confronta_ssh_config(
                    profili, percorso=espanso)
                GLib.idle_add(self._fine_lettura, piano, None)
            except Exception as e:  # noqa: BLE001
                GLib.idle_add(self._fine_lettura, None,
                              t("sshsync.error", e=e))

        threading.Thread(target=_worker, daemon=True).start()

    def _fine_lettura(self, piano, errore):
        if not self._vivo:
            return False
        self._spinner.stop()
        self._btn_ricarica.set_sensitive(True)
        if errore:
            self._lbl_riepilogo.set_markup(
                "<span foreground='#c62828'>"
                f"{GLib.markup_escape_text(errore)}</span>")
            return False

        self._piano = piano
        self._popola(piano)
        return False

    def _popola(self, piano: dict):
        self._store.clear()
        for voce in piano.get("nuovi", []):
            descrizione = _descrizione_host(voce["dati"])
            if voce["nome"] != voce["alias"]:
                descrizione += " · " + t("sshsync.renamed", nome=voce["nome"])
            self._aggiungi_riga("nuovo", voce["nome"], descrizione, True)
        for voce in piano.get("aggiornati", []):
            dettagli = _dettagli_campi(voce["campi"])
            self._aggiungi_riga("aggiornato", voce["nome"], dettagli, True)
        for voce in piano.get("rimossi", []):
            self._aggiungi_riga("rimosso", voce["nome"],
                                t("sshsync.detail_removed"), False)

        n_new = len(piano.get("nuovi", []))
        n_upd = len(piano.get("aggiornati", []))
        n_rem = len(piano.get("rimossi", []))
        n_same = len(piano.get("invariati", []))

        self._chk_new.set_label(t("sshsync.cat_new", n=n_new))
        self._chk_upd.set_label(t("sshsync.cat_upd", n=n_upd))
        self._chk_rem.set_label(t("sshsync.cat_rem", n=n_rem))
        for chk, n in ((self._chk_new, n_new), (self._chk_upd, n_upd),
                       (self._chk_rem, n_rem)):
            chk.set_sensitive(n > 0)
        self._chk_new.set_active(True)
        self._chk_upd.set_active(True)
        self._chk_rem.set_active(False)

        if n_new or n_upd or n_rem:
            self._lbl_riepilogo.set_markup(t(
                "sshsync.summary", new=n_new, updated=n_upd,
                removed=n_rem, same=n_same))
        else:
            self._lbl_riepilogo.set_markup(
                f"<span foreground='#2e7d32'>{t('sshsync.empty')}</span>")
        self._aggiorna_stato()

    def _aggiungi_riga(self, tipo: str, nome: str, dettagli: str, attivo: bool):
        chiave, colore = _AZIONE[tipo]
        azione = f"<span foreground='{colore}'>{t(chiave)}</span>"
        self._store.append([attivo, tipo, azione, nome, dettagli])

    # ------------------------------------------------------------------
    # Selezione
    # ------------------------------------------------------------------

    def _on_toggle_riga(self, _renderer, path):
        self._store[path][_C_ATTIVO] = \
            not self._store[path][_C_ATTIVO]
        self._aggiorna_stato()

    def _on_categoria(self, chk, tipo: str):
        attivo = chk.get_active()
        for riga in self._store:
            if riga[_C_TIPO] == tipo:
                riga[_C_ATTIVO] = attivo
        self._aggiorna_stato()

    def _selezionati(self) -> int:
        return sum(1 for riga in self._store if riga[_C_ATTIVO])

    def _aggiorna_stato(self):
        self._btn_apply.set_sensitive(
            self._piano is not None and self._selezionati() > 0)

    # ------------------------------------------------------------------
    # Applicazione
    # ------------------------------------------------------------------

    def _on_apply(self, _btn):
        if not self._piano:
            return

        selezionati = {(riga[_C_TIPO], riga[_C_NOME])
                       for riga in self._store if riga[_C_ATTIVO]}

        parziale = {
            "percorso": self._piano.get("percorso", ""),
            "nuovi": [v for v in self._piano.get("nuovi", [])
                      if ("nuovo", v["nome"]) in selezionati],
            "aggiornati": [v for v in self._piano.get("aggiornati", [])
                           if ("aggiornato", v["nome"]) in selezionati],
            "rimossi": [v for v in self._piano.get("rimossi", [])
                        if ("rimosso", v["nome"]) in selezionati],
            "invariati": self._piano.get("invariati", []),
        }
        if not (parziale["nuovi"] or parziale["aggiornati"]
                or parziale["rimossi"]):
            self._lbl_result.set_markup(
                f"<span foreground='orange'>{t('sshsync.no_selection')}</span>")
            return

        self._btn_apply.set_sensitive(False)
        try:
            risultato = importer.applica_piano_ssh_config(
                parziale, rimuovi=bool(parziale["rimossi"]))
        except Exception as e:  # noqa: BLE001
            self._lbl_result.set_markup(
                "<span foreground='#c62828'>"
                f"{GLib.markup_escape_text(t('sshsync.error', e=e))}</span>")
            self._aggiorna_stato()
            return

        messaggio = t("sshsync.done", new=risultato["aggiunti"],
                      updated=risultato["aggiornati"],
                      removed=risultato["rimossi"])
        extra = ""
        if risultato["rinominati"]:
            extra = " — " + ", ".join(
                f"{vecchio} → {nuovo}"
                for vecchio, nuovo in risultato["rinominati"])
        self._lbl_result.set_markup(
            "<span foreground='#2e7d32'>✓ "
            f"{GLib.markup_escape_text(messaggio + extra)}</span>")

        if self._on_applied is not None:
            self._on_applied()
        self._rileggi()
