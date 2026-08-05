"""
welcome_widget.py - Schermata di benvenuto PCM (GTK3)
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, GLib

from translations import t
import config_manager
import protocols


class WelcomeWidget(Gtk.Box):

    __gsignals__ = {
        "nuova-sessione": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "terminale-locale": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "apri-sessione": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.set_margin_top(40)
        self.set_margin_bottom(40)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self._build()

    def _crea_btn_grande(self, icon_name: str, testo: str) -> Gtk.Button:
        """Pulsante grande con icona simbolica (si ricolora col tema) + testo."""
        btn = Gtk.Button()
        btn.set_size_request(160, 48)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
        box.pack_start(img, False, False, 0)
        lbl = Gtk.Label(label=testo)
        lbl.set_justify(Gtk.Justification.CENTER)
        box.pack_start(lbl, False, False, 0)
        btn.add(box)
        return btn

    def _build(self):
        title = Gtk.Label(label=t("app.title"))
        title.get_style_context().add_class("section-header")
        self.pack_start(title, False, False, 0)

        subtitle = Gtk.Label()
        subtitle.set_markup(f"<small>{t('welcome.subtitle')}</small>")
        subtitle.set_halign(Gtk.Align.CENTER)
        self.pack_start(subtitle, False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)

        btn_new = self._crea_btn_grande("list-add-symbolic", t("welcome.btn_new_session"))
        btn_new.get_style_context().add_class("connect-button")
        btn_new.connect("clicked", lambda b: self.emit("nuova-sessione"))

        btn_term = self._crea_btn_grande("utilities-terminal-symbolic", t("welcome.btn_local_terminal"))
        btn_term.connect("clicked", lambda b: self.emit("terminale-locale"))

        btn_box.pack_start(btn_new,  False, False, 0)
        btn_box.pack_start(btn_term, False, False, 0)
        self.pack_start(btn_box, False, False, 0)

        self._recent_list = Gtk.ListBox()
        self._recent_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._recent_list.set_halign(Gtk.Align.CENTER)
        self._recent_list.set_size_request(440, -1)
        self._recent_list.connect("row-activated", self._on_recent_activated)

        rec_frame = Gtk.Frame()
        rec_frame.set_margin_top(12)
        rec_label = Gtk.Label()
        rec_label.set_markup(f"<b>{t('welcome.recent_title')}</b>")
        rec_label.set_xalign(0.0)
        rec_label.set_margin_start(8)
        rec_label.set_margin_top(6)
        rec_label.set_margin_bottom(4)
        rec_frame.set_label_widget(rec_label)

        rec_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        rec_inner.set_margin_start(8)
        rec_inner.set_margin_end(8)
        rec_inner.set_margin_bottom(8)

        rec_scroll = Gtk.ScrolledWindow()
        rec_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rec_scroll.set_min_content_height(100)
        rec_scroll.set_max_content_height(240)
        rec_scroll.add(self._recent_list)
        rec_inner.pack_start(rec_scroll, True, True, 0)
        rec_frame.add(rec_inner)
        self.pack_start(rec_frame, True, False, 0)

        GLib.idle_add(self._popola_recenti)

    def aggiorna(self):
        GLib.idle_add(self._popola_recenti)

    def _popola_recenti(self):
        for w in self._recent_list.get_children():
            self._recent_list.remove(w)

        recenti = config_manager.load_recent()
        profili = config_manager.load_profiles()

        if not recenti:
            empty = Gtk.Label()
            empty.set_markup(f"<i><span foreground='#888'>{t('welcome.no_recent')}</span></i>")
            empty.set_margin_top(12)
            empty.set_margin_bottom(12)
            empty.show()
            self._recent_list.add(empty)
            self._recent_list.show_all()
            return False

        for r in recenti[:10]:
            nome = r.get("name", "")
            proto = r.get("proto", "")
            host = r.get("host", "")
            ts = r.get("ts", "")

            if nome not in profili:
                continue

            dati = profili[nome]
            proto_label = protocols.PROTO_LABEL.get(proto, proto.upper() if proto else "")
            proto_color = protocols.PROTO_COLOR.get(proto, "#888888")

            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_box.set_margin_top(3)
            row_box.set_margin_bottom(3)
            row_box.set_margin_start(6)
            row_box.set_margin_end(6)

            proto_lbl = Gtk.Label()
            proto_lbl.set_markup(f"<span foreground='{proto_color}'><b>[{proto_label}]</b></span>")
            proto_lbl.set_width_chars(8)
            proto_lbl.set_xalign(0.0)
            row_box.pack_start(proto_lbl, False, False, 0)

            name_lbl = Gtk.Label(label=nome)
            name_lbl.set_xalign(0.0)
            name_lbl.set_hexpand(True)
            row_box.pack_start(name_lbl, True, True, 0)

            ts_lbl = Gtk.Label()
            ts_lbl.set_markup(f"<small><span foreground='#888'>{ts}</span></small>")
            ts_lbl.set_xalign(1.0)
            row_box.pack_start(ts_lbl, False, False, 0)

            row.add(row_box)
            row._pcm_nome = nome
            row._pcm_dati = dati
            row.show_all()
            self._recent_list.add(row)

        self._recent_list.show_all()
        return False

    def _on_recent_activated(self, listbox, row):
        if not hasattr(row, "_pcm_nome"):
            return
        self.emit("apri-sessione", row._pcm_nome, row._pcm_dati)

