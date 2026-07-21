"""
plugins/__init__.py - Plugin system for PCM.

Protocol plugins allow extending PCM with new connection types
(AWS SSM, kubectl, Docker, SPICE, etc.) without modifying core code.
"""

from plugins.plugin_base import (
    ProtocolPlugin,
    ToolPlugin,
    PluginInfo,
    pcm_register_protocol,
    pcm_register_tool,
    pcm_get_protocol_plugins,
    pcm_get_tool_plugins,
    pcm_get_plugin,
    pcm_list_plugins,
    pcm_build_command,
    pcm_create_widget,
    pcm_dialog_pages,
    pcm_protocol_fields,
    pcm_has_protocol,
    pcm_menu_items,
    pcm_context_actions,
    pcm_plugin_protocols,
)
from plugins.plugin_manager import (
    discover_plugins,
    load_plugins,
    get_plugin_dir,
)

__all__ = [
    "ProtocolPlugin",
    "ToolPlugin",
    "PluginInfo",
    "pcm_register_protocol",
    "pcm_register_tool",
    "pcm_get_protocol_plugins",
    "pcm_get_tool_plugins",
    "pcm_get_plugin",
    "pcm_list_plugins",
    "pcm_build_command",
    "pcm_create_widget",
    "pcm_dialog_pages",
    "pcm_protocol_fields",
    "pcm_has_protocol",
    "pcm_menu_items",
    "pcm_context_actions",
    "pcm_plugin_protocols",
    "discover_plugins",
    "load_plugins",
    "get_plugin_dir",
]
