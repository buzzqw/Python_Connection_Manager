"""Dialog for launching configured external tools on a session."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import external_tools
from translations import t


class ExternalToolsDialog(Gtk.Dialog):
    def __init__(self, parent, profile: dict, session_name: str = ""):
        super().__init__(
            title=t("external_tools.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self._profile = {**profile, "name": session_name or profile.get("name", "")}
        self.set_default_size(520, 260)
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.set_margin_top(12)
        area.set_margin_bottom(8)

        target = Gtk.Label(label=t("external_tools.target").format(name=session_name or profile.get("host", "")))
        target.set_xalign(0.0)
        area.pack_start(target, False, False, 0)

        self._store = Gtk.ListStore(str, object)
        for tool in external_tools.load_tools():
            label = str(tool.get("label", "")).strip()
            if label:
                self._store.append([label, tool])
        view = Gtk.TreeView(model=self._store)
        view.set_headers_visible(False)
        renderer = Gtk.CellRendererText()
        view.append_column(Gtk.TreeViewColumn(t("external_tools.tool"), renderer, text=0))
        view.get_selection().connect("changed", self._on_selection_changed)
        area.pack_start(view, True, True, 0)

        self._status = Gtk.Label(label="")
        self._status.set_xalign(0.0)
        self._status.set_line_wrap(True)
        area.pack_start(self._status, False, False, 0)

        buttons = self.get_action_area()
        self._launch = Gtk.Button(label=t("external_tools.launch"))
        self._launch.get_style_context().add_class("suggested-action")
        self._launch.set_sensitive(False)
        self._launch.connect("clicked", lambda _button: self._launch_selected(view))
        buttons.pack_start(self._launch, False, False, 0)
        self.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)
        self.show_all()

    def _on_selection_changed(self, selection):
        _model, iterator = selection.get_selected()
        self._launch.set_sensitive(iterator is not None)

    def _launch_selected(self, view):
        model, iterator = view.get_selection().get_selected()
        if iterator is None:
            return
        tool = model[iterator][1]
        try:
            process = external_tools.launch(tool, self._profile)
            self._status.set_text(t("external_tools.started").format(pid=process.pid))
        except (external_tools.ExternalToolError, OSError) as exc:
            self._status.set_text(t("external_tools.error").format(error=exc))
