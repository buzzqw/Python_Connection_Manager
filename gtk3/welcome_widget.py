"""
welcome_widget.py - Schermata di benvenuto PCM (GTK3)
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

from translations import t


class WelcomeWidget(Gtk.Box):

    nuova_sessione   = GObject.Signal("nuova-sessione")
    terminale_locale = GObject.Signal("terminale-locale")

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self._build()

    def _build(self):
        title = Gtk.Label(label=t("app.title"))
        title.get_style_context().add_class("section-header")
        self.pack_start(title, False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        btn_box.set_halign(Gtk.Align.CENTER)

        btn_new = Gtk.Button(label=t("welcome.btn_new_session"))
        btn_new.get_style_context().add_class("connect-button")
        btn_new.set_size_request(160, 48)
        btn_new.connect("clicked", lambda b: self.emit("nuova-sessione"))

        btn_term = Gtk.Button(label=t("welcome.btn_local_terminal"))
        btn_term.set_size_request(160, 48)
        btn_term.connect("clicked", lambda b: self.emit("terminale-locale"))

        btn_box.pack_start(btn_new,  False, False, 0)
        btn_box.pack_start(btn_term, False, False, 0)
        self.pack_start(btn_box, False, False, 0)
