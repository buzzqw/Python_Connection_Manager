"""
export_dialog.py - Dialogo per esportazione sessioni (OpenSSH config, CSV, JSON, mRemoteNG)
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
import config_manager
import exporter
from gi.repository import Gtk
from translations import t


class ExportDialog(Gtk.Dialog):
    """Dialog per esportare le connessioni PCM in vari formati standard."""

    def __init__(self, parent: Gtk.Window | None = None):
        super().__init__(
            title=t("export.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(480, 0)
        self._profili = config_manager.load_profiles()
        self._build_ui()
        self.show_all()

    def _build_ui(self):
        area = self.get_content_area()
        area.set_spacing(10)
        area.set_margin_start(16)
        area.set_margin_end(16)
        area.set_margin_top(16)
        area.set_margin_bottom(8)

        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{t('export.title')}</b>")
        lbl.set_xalign(0.0)
        area.pack_start(lbl, False, False, 0)

        # Griglia form
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)

        # 1. Selezione formato
        lbl_fmt = Gtk.Label(label=t("export.format_lbl"), xalign=0.0)
        self._combo_fmt = Gtk.ComboBoxText()
        self._combo_fmt.append_text(t("export.format_ssh"))
        self._combo_fmt.append_text(t("export.format_csv"))
        self._combo_fmt.append_text(t("export.format_json"))
        self._combo_fmt.append_text(t("export.format_mrng"))
        self._combo_fmt.set_active(0)
        self._combo_fmt.set_hexpand(True)
        self._combo_fmt.connect("changed", self._on_format_changed)

        grid.attach(lbl_fmt, 0, 0, 1, 1)
        grid.attach(self._combo_fmt, 1, 0, 1, 1)

        # 2. Selezione gruppo
        lbl_grp = Gtk.Label(label=t("export.group_lbl"), xalign=0.0)
        self._combo_grp = Gtk.ComboBoxText()
        self._combo_grp.append_text(t("export.group_all"))
        gruppi = sorted({d.get("group", "") for d in self._profili.values() if isinstance(d, dict) and d.get("group")})
        for g in gruppi:
            self._combo_grp.append_text(g)
        self._combo_grp.set_active(0)
        self._combo_grp.set_hexpand(True)

        grid.attach(lbl_grp, 0, 1, 1, 1)
        grid.attach(self._combo_grp, 1, 1, 1, 1)

        area.pack_start(grid, False, False, 0)

        # 3. Checkbox password
        self._chk_pwd = Gtk.CheckButton(label=t("export.include_passwords"))
        self._chk_pwd.set_active(False)
        self._chk_pwd.set_sensitive(False)
        area.pack_start(self._chk_pwd, False, False, 0)

        # 4. Label di risultato / info
        self._lbl_result = Gtk.Label(label="")
        self._lbl_result.set_xalign(0.0)
        self._lbl_result.set_line_wrap(True)
        area.pack_start(self._lbl_result, False, False, 0)

        # Pulsanti
        btn_export = self.add_button(t("export.save_btn"), Gtk.ResponseType.APPLY)
        btn_export.get_style_context().add_class("suggested-action")
        self.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)

        btn_export.connect("clicked", self._esegui_esportazione)

    def _on_format_changed(self, combo: Gtk.ComboBoxText):
        idx = combo.get_active()
        self._chk_pwd.set_sensitive(idx in (2, 3))

    def _esegui_esportazione(self, _btn):
        fmt_idx = self._combo_fmt.get_active()
        grp_idx = self._combo_grp.get_active()
        grp = None if grp_idx == 0 else self._combo_grp.get_active_text()
        inc_pwd = self._chk_pwd.get_active()

        if fmt_idx == 0:
            contenuto, n = exporter.esporta_ssh_config(self._profili, grp)
            def_name = "config"
            filtri = [("OpenSSH Config", "*"), (t("import.filter_all"), "*")]
        elif fmt_idx == 1:
            contenuto, n = exporter.esporta_csv(self._profili, grp)
            def_name = "pcm_sessions.csv"
            filtri = [("CSV", "*.csv"), (t("import.filter_all"), "*")]
        elif fmt_idx == 2:
            contenuto, n = exporter.esporta_json(self._profili, grp, include_passwords=inc_pwd)
            def_name = "pcm_export.json"
            filtri = [("JSON", "*.json"), (t("import.filter_all"), "*")]
        else:
            contenuto, n = exporter.esporta_mremoteng(self._profili, grp)
            def_name = "confCons.xml"
            filtri = [("mRemoteNG XML", "*.xml"), (t("import.filter_all"), "*")]

        if n == 0:
            self._lbl_result.set_markup(f"<span foreground='orange'>{t('export.no_sessions')}</span>")
            return

        # Apri FileChooserDialog per salvare
        fc = Gtk.FileChooserDialog(
            title=t("export.title"),
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        fc.add_buttons(
            t("sd.cancel"), Gtk.ResponseType.CANCEL,
            t("export.save_btn"), Gtk.ResponseType.OK,
        )
        fc.set_do_overwrite_confirmation(True)
        fc.set_current_name(def_name)

        for nome_f, pat in filtri:
            ff = Gtk.FileFilter()
            ff.set_name(nome_f)
            ff.add_pattern(pat)
            fc.add_filter(ff)

        resp = fc.run()
        path = fc.get_filename()
        fc.destroy()

        if resp == Gtk.ResponseType.OK and path:
            try:
                exporter.esporta_su_file(contenuto, path)
                msg = t("export.done_msg", n=n, path=path)
                self._lbl_result.set_markup(f"<span foreground='green'>✓ {msg}</span>")
            except Exception as e:  # noqa: BLE001
                self._lbl_result.set_markup(f"<span foreground='red'>{t('error.export')}: {e}</span>")
