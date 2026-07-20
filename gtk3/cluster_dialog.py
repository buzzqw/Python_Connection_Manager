"""
cluster_dialog.py - Dialog per connessioni cluster PCM.

Supporta connessioni cluster multi-sessione: ogni sessione selezionata
ha i propri host configurabili, con opzioni indipendenti.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from translations import t


class ClusterDialog(Gtk.Dialog):
    def __init__(self, parent, sessions: dict):
        super().__init__(
            title=t("cluster.title_multi"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self._sessions = sessions
        self._host_entries: dict[str, Gtk.TextView] = {}
        self._keep_user_chks: dict[str, Gtk.CheckButton] = {}
        self._keep_port_chks: dict[str, Gtk.CheckButton] = {}
        self.set_default_size(560, 500)

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(16); area.set_margin_end(16)
        area.set_margin_top(12); area.set_margin_bottom(8)

        title = Gtk.Label()
        title.set_markup(f"<b>{t('cluster.title_multi')}</b>")
        title.set_xalign(0.0)
        area.pack_start(title, False, False, 0)

        # Istruzioni
        instr = Gtk.Label()
        instr.set_markup(f"<small><i>{t('cluster.instr_multi')}</i></small>")
        instr.set_xalign(0.0); instr.set_line_wrap(True)
        instr.set_margin_bottom(4)
        area.pack_start(instr, False, False, 0)

        # Notebook per sessioni multiple
        if len(sessions) == 1:
            nb = None
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self._build_session_page(list(sessions.items())[0], main_box)
            area.pack_start(main_box, True, True, 0)
        else:
            nb = Gtk.Notebook()
            nb.set_scrollable(True)
            for nome, dati in sorted(sessions.items()):
                page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                page.set_margin_start(6); page.set_margin_end(6)
                page.set_margin_top(4); page.set_margin_bottom(4)
                self._build_session_page((nome, dati), page)
                proto = dati.get("protocol", "")
                tab_label = Gtk.Label(label=f"{nome}  ({proto})")
                nb.append_page(page, tab_label)
            area.pack_start(nb, True, True, 0)

        # Opzioni globali
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4)
        area.pack_start(sep, False, False, 0)

        glob_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        glob_box.set_margin_top(4)
        self._chk_broadcast = Gtk.CheckButton(label=t("cluster.enable_broadcast"))
        self._chk_broadcast.set_active(False)
        glob_box.pack_start(self._chk_broadcast, False, False, 0)

        delay_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_delay = Gtk.Label(label=t("cluster.delay"))
        self._spin_delay = Gtk.SpinButton.new_with_range(0, 30, 0.5)
        self._spin_delay.set_value(1.0); self._spin_delay.set_digits(1)
        delay_box.pack_start(lbl_delay, False, False, 0)
        delay_box.pack_start(self._spin_delay, False, False, 0)
        glob_box.pack_start(delay_box, False, False, 0)
        area.pack_start(glob_box, False, False, 0)

        self.add_button(t("sd.cancel"), Gtk.ResponseType.CANCEL)
        btn_conn = self.add_button(t("cluster.connect_all"), Gtk.ResponseType.OK)
        btn_conn.get_style_context().add_class("suggested-action")

    def _build_session_page(self, item: tuple, box: Gtk.Box):
        nome, dati = item
        user = str(dati.get("user", ""))
        port = str(dati.get("port", ""))
        proto = dati.get("protocol", "")

        info = Gtk.Label()
        info.set_markup(
            f"<small><b>{t('sd.protocol')}:</b> {proto}    "
            f"<b>{t('sd.user')}:</b> {user or '—'}    "
            f"<b>{t('sd.port')}:</b> {port or '—'}</small>"
        )
        info.set_xalign(0.0)
        box.pack_start(info, False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(60)

        tv = Gtk.TextView()
        tv.set_wrap_mode(Gtk.WrapMode.NONE)
        tv.set_monospace(True)
        tv.set_left_margin(8); tv.set_top_margin(4)
        tv.get_buffer().set_text(dati.get("host", ""))
        sw.add(tv)
        box.pack_start(sw, True, True, 0)
        self._host_entries[nome] = tv

        count_lbl = Gtk.Label()
        count_lbl.set_xalign(0.0)
        count_lbl.set_margin_top(2)
        box.pack_start(count_lbl, False, False, 0)

        def _update_count(buf=None):
            hosts = self._get_hosts_from_text(tv)
            n = len(hosts)
            if n == 0:
                count_lbl.set_markup(f"<small><span foreground='#888'>{t('cluster.count_none')}</span></small>")
            elif n == 1:
                count_lbl.set_markup(f"<small>{t('cluster.count_one')}</small>")
            else:
                count_lbl.set_markup(f"<small><b>{t('cluster.count_many', n=n)}</b></small>")
        tv.get_buffer().connect("changed", _update_count)
        GLib.idle_add(_update_count)

        opts = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        chk_user = Gtk.CheckButton(label=t("cluster.keep_user"))
        chk_user.set_active(True)
        chk_port = Gtk.CheckButton(label=t("cluster.keep_port"))
        chk_port.set_active(True)
        opts.pack_start(chk_user, False, False, 0)
        opts.pack_start(chk_port, False, False, 0)
        box.pack_start(opts, False, False, 0)
        self._keep_user_chks[nome] = chk_user
        self._keep_port_chks[nome] = chk_port

    @staticmethod
    def _get_hosts_from_text(tv: Gtk.TextView) -> list[str]:
        buf = tv.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        hosts = []
        for line in text.strip().split("\n"):
            h = line.strip()
            if h and not h.startswith("#"):
                hosts.append(h)
        return hosts

    def get_cluster_plan(self) -> dict:
        plan = {}
        for nome, dati in self._sessions.items():
            hosts = self._get_hosts_from_text(self._host_entries[nome])
            if not hosts:
                continue
            plan[nome] = {
                "dati": dati,
                "hosts": hosts,
                "keep_user": self._keep_user_chks[nome].get_active(),
                "keep_port": self._keep_port_chks[nome].get_active(),
            }
        return plan

    def enable_broadcast(self) -> bool:
        return self._chk_broadcast.get_active()

    def get_delay(self) -> float:
        return self._spin_delay.get_value()

    def run(self):
        self.show_all()
        return super().run()
