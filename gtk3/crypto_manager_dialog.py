import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from translations import t
from crypto_manager import is_enabled, setup, change_password, disable


class CryptoManagerDialog(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(
            title=t("crypto.custom.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True
        )
        self.set_default_size(400, 0)
        self._init_ui()
        self.show_all()

    def _init_ui(self):
        area = self.get_content_area()
        area.set_spacing(10)
        area.set_margin_start(16)
        area.set_margin_end(16)
        area.set_margin_top(16)
        area.set_margin_bottom(16)

        self.attiva = is_enabled()

        lbl = Gtk.Label()
        lbl.set_xalign(0.0)
        area.pack_start(lbl, False, False, 0)

        self.entry_pwd1 = Gtk.Entry()
        self.entry_pwd1.set_visibility(False)
        area.pack_start(self.entry_pwd1, False, False, 0)

        self.entry_pwd2 = Gtk.Entry()
        self.entry_pwd2.set_visibility(False)

        if not self.attiva:
            lbl.set_markup(f"<b>{t('crypto.custom.disabled_title')}</b>\n{t('crypto.custom.disabled_desc')}")
            self.entry_pwd1.set_placeholder_text(t("crypto.custom.new_pwd_ph"))
        else:
            lbl.set_markup(f"<b>{t('crypto.custom.active_title')}</b>\n{t('crypto.custom.active_desc')}")
            self.entry_pwd1.set_placeholder_text(t("crypto.custom.old_pwd_ph"))
            self.entry_pwd2.set_placeholder_text(t("crypto.custom.new_pwd_opt_ph"))
            area.pack_start(self.entry_pwd2, False, False, 0)

        self.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        btn_ok = self.add_button(t("crypto.custom.btn_apply"), Gtk.ResponseType.OK)
        btn_ok.get_style_context().add_class("suggested-action")

    def run(self):
        resp = super().run()
        if resp == Gtk.ResponseType.OK:
            p1 = self.entry_pwd1.get_text()
            p2 = self.entry_pwd2.get_text() if self.attiva else ""

            if not self.attiva:
                if p1:
                    setup(p1)
                    self._mostra_msg(t("crypto.custom.success"), t("crypto.custom.msg_enabled"))
            else:
                if p1 and p2:
                    if change_password(p1, p2):
                        self._mostra_msg(t("crypto.custom.success"), t("crypto.custom.msg_changed"))
                    else:
                        self._mostra_msg(t("crypto.custom.error"), t("crypto.custom.msg_wrong_old"))
                elif p1 and not p2:
                    if disable(p1):
                        self._mostra_msg(t("crypto.custom.success"), t("crypto.custom.msg_disabled"))
                    else:
                        self._mostra_msg(t("crypto.custom.error"), t("crypto.custom.msg_wrong"))
        return resp

    def _mostra_msg(self, titolo, testo):
        m_type = Gtk.MessageType.INFO if titolo == t("crypto.custom.success") else Gtk.MessageType.ERROR
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=m_type,
            buttons=Gtk.ButtonsType.OK, text=titolo
        )
        dlg.format_secondary_text(testo)
        dlg.run()
        dlg.destroy()
