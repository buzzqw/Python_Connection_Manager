"""
plugin_base.py - Plugin base classes and protocol registry for PCM.

ProtocolPlugin: add new connection protocols
ToolPlugin: add tools/panels/widgets to the UI
"""

from __future__ import annotations

import abc
import os
from typing import Optional, Callable, Any

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class PluginInfo:
    """Metadata about a loaded plugin."""
    def __init__(self, plugin_id: str, name: str, version: str = "0.1.0",
                 description: str = "", author: str = "",
                 plugin_path: str = ""):
        self.plugin_id = plugin_id
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.plugin_path = plugin_path


# ---------------------------------------------------------------------------
# Global plugin registry
# ---------------------------------------------------------------------------

_registry: dict[str, tuple[PluginInfo, ProtocolPlugin | ToolPlugin]] = {}
_protocol_registry: dict[str, ProtocolPlugin] = {}
_tool_registry: dict[str, ToolPlugin] = {}


def pcm_register_protocol(plugin: ProtocolPlugin) -> None:
    """Register a protocol plugin. Called by plugin __init__ or load."""
    info = plugin.plugin_info
    _registry[info.plugin_id] = (info, plugin)
    for proto_id in plugin.protocol_ids:
        _protocol_registry[proto_id] = plugin


def pcm_register_tool(plugin: ToolPlugin) -> None:
    """Register a tool plugin."""
    info = plugin.plugin_info
    _registry[info.plugin_id] = (info, plugin)
    _tool_registry[info.plugin_id] = plugin


def pcm_get_protocol_plugins() -> dict[str, ProtocolPlugin]:
    return dict(_protocol_registry)


def pcm_get_tool_plugins() -> dict[str, ToolPlugin]:
    return dict(_tool_registry)


def pcm_get_plugin(plugin_id: str) -> ProtocolPlugin | ToolPlugin | None:
    entry = _registry.get(plugin_id)
    return entry[1] if entry else None


def pcm_list_plugins() -> list[PluginInfo]:
    return [info for info, _ in _registry.values()]


def pcm_has_protocol(proto_id: str) -> bool:
    return proto_id in _protocol_registry


def pcm_plugin_protocols() -> list[str]:
    """Returns list of plugin-provided protocol IDs."""
    return list(_protocol_registry.keys())


def pcm_build_command(proto_id: str, profilo: dict) -> tuple[Optional[str], str]:
    """Build command for a plugin protocol. Returns (cmd, mode)."""
    plugin = _protocol_registry.get(proto_id)
    if plugin:
        return plugin.build_command(profilo)
    return None, "none"


def pcm_create_widget(proto_id: str, profilo: dict, parent_window) -> Optional[Gtk.Widget]:
    """Create the UI widget for a plugin protocol connection."""
    plugin = _protocol_registry.get(proto_id)
    if plugin:
        return plugin.create_widget(profilo, parent_window)
    return None


def pcm_dialog_pages(proto_id: str, dialog: Gtk.Dialog, profilo: dict) -> list[tuple[str, Gtk.Widget]]:
    """Get additional notebook pages for the session dialog from a plugin."""
    plugin = _protocol_registry.get(proto_id)
    if plugin:
        return plugin.create_dialog_pages(dialog, profilo)
    return []


def pcm_protocol_fields(proto_id: str) -> set[str]:
    """Get the JSON field keys for a plugin protocol profile."""
    plugin = _protocol_registry.get(proto_id)
    if plugin:
        return plugin.profile_fields
    return set()


def pcm_menu_items() -> list[tuple[str, str, Callable]]:
    """Get menu items from all tool plugins. Returns [(label, icon_name, callback), ...]."""
    items = []
    for p in _tool_registry.values():
        items.extend(p.get_menu_items())
    return items


def pcm_context_actions() -> list[tuple[str, str, Callable]]:
    """Get context menu actions from all plugins.
    Returns [(label, icon_name, callback(dati_sessione)), ...].
    """
    actions = []
    for p in _tool_registry.values():
        actions.extend(p.get_context_actions())
    return actions


# ---------------------------------------------------------------------------
# Abstract base classes
# ---------------------------------------------------------------------------


class ProtocolPlugin(abc.ABC):
    """Base class for protocol plugins.

    Subclass this to add a new connection protocol to PCM.
    Override the abstract methods and decorate the class with @pcm_protocol.

    Example:
        class AwsSsmPlugin(ProtocolPlugin):
            plugin_info = PluginInfo(
                plugin_id="aws_ssm",
                name="AWS SSM",
                version="1.0.0",
                description="Connect to EC2 instances via AWS SSM",
                author="PCM Contributors",
            )
            protocol_ids = ["aws_ssm"]
            profile_fields = {"host", "user", "password", "aws_region", "aws_profile"}
    """

    plugin_info: PluginInfo = None
    protocol_ids: list[str] = []
    profile_fields: set[str] = {"host", "port", "user", "password", "notes"}
    default_port: str = ""

    @abc.abstractmethod
    def build_command(self, profilo: dict) -> tuple[Optional[str], str]:
        """Build the shell command to execute for this protocol.

        Returns (command_string, mode) where mode is one of:
          - "embedded"  → run in internal VTE terminal
          - "external"  → run in external window
          - "panel"     → handled by create_widget()
          - "none"      → skip command execution

        Args:
            profilo: Session profile dict with connection parameters
        """
        ...

    def create_widget(self, profilo: dict, parent_window) -> Optional[Gtk.Widget]:
        """Create a custom GTK widget for this connection.

        Override if the protocol needs a custom UI (graphical viewer, etc.)
        rather than a terminal.
        Return None to use the terminal-based approach.
        """
        return None

    def create_dialog_pages(self, dialog: Gtk.Dialog, profilo: dict) -> list[tuple[str, Gtk.Widget]]:
        """Create additional notebook pages for the session edit dialog.

        Override to add protocol-specific configuration UI.

        Returns:
            List of (page_name, widget) tuples to add as notebook tabs.
        """
        return []

    def on_connected(self, profilo: dict, widget: Gtk.Widget) -> None:
        """Called after a connection is established. Override for post-connect hooks."""
        pass

    def on_disconnected(self, profilo: dict, widget: Gtk.Widget) -> None:
        """Called when a connection is closed. Override for cleanup."""
        pass


class ToolPlugin(abc.ABC):
    """Base class for tool/utility plugins.

    Tool plugins add features to the UI: extra menu items, toolbar buttons,
    context menu actions, panels, etc.
    """

    plugin_info: PluginInfo = None

    @abc.abstractmethod
    def get_menu_items(self) -> list[tuple[str, str, Callable]]:
        """Return menu items to add to the Tools menu.
        Each item: (label, icon_name, callback)
        """
        ...

    def get_context_actions(self) -> list[tuple[str, str, Callable]]:
        """Return context menu actions for session right-click.
        Each item: (label, icon_name, callback(session_data_dict))
        """
        return []

    def get_toolbar_buttons(self) -> list[tuple[str, str, Gtk.Widget]]:
        """Return toolbar buttons to add to the headerbar.
        Each item: (tooltip, icon_name, button_widget)
        """
        return []
