"""
plugin_manager.py - Plugin discovery, loading, and lifecycle management.

Scans ~/.local/share/pcm/plugins/ and /usr/share/pcm/plugins/ for
plugin directories containing plugin.json metadata.
"""

from __future__ import annotations

import json
import os
import importlib
import importlib.util
import sys
from typing import Optional

from pcm_logging import get_logger as _get_log

from plugins.plugin_base import (
    PluginInfo, ProtocolPlugin, ToolPlugin,
    pcm_register_protocol, pcm_register_tool,
    pcm_list_plugins,
)


def get_plugin_dir() -> str:
    """Get the user plugin directory, creating it if needed."""
    xdg_data = os.environ.get(
        "XDG_DATA_HOME",
        os.path.join(os.path.expanduser("~"), ".local", "share")
    )
    plugin_dir = os.path.join(xdg_data, "pcm", "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    return plugin_dir


def get_system_plugin_dir() -> str:
    return "/usr/share/pcm/plugins"


def get_builtin_plugin_dir() -> str:
    """Get the built-in plugins directory (shipped with PCM).
    
    Supports PyInstaller (sys._MEIPASS) and normal installs.
    """
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        return os.path.join(base, 'plugins', 'builtins')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "plugins", "builtins")


def discover_plugins() -> dict[str, PluginInfo]:
    """Discover all available plugins without loading them.
    
    Searches: user dir, system dir, and built-in dir.
    Returns dict of plugin_id -> PluginInfo for all discovered plugins.
    """
    discovered: dict[str, PluginInfo] = {}
    search_paths = [get_plugin_dir(), get_builtin_plugin_dir(), get_system_plugin_dir()]

    for base_dir in search_paths:
        if not os.path.isdir(base_dir):
            continue
        for entry in sorted(os.listdir(base_dir)):
            plugin_path = os.path.join(base_dir, entry)
            if not os.path.isdir(plugin_path):
                continue
            manifest = os.path.join(plugin_path, "plugin.json")
            if not os.path.isfile(manifest):
                continue
            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                info = PluginInfo(
                    plugin_id=meta.get("plugin_id", entry),
                    name=meta.get("name", entry),
                    version=meta.get("version", "0.1.0"),
                    description=meta.get("description", ""),
                    author=meta.get("author", ""),
                    plugin_path=plugin_path,
                )
                if info.plugin_id not in discovered:
                    discovered[info.plugin_id] = info
            except (json.JSONDecodeError, KeyError) as e:
                _get_log(__name__).warning("Invalid manifest in %s: %s", plugin_path, e)

    return discovered


def _load_plugin_from_path(plugin_path: str, info: PluginInfo) -> Optional[ProtocolPlugin | ToolPlugin]:
    """Load a plugin module from a directory path."""
    init_file = os.path.join(plugin_path, "__init__.py")
    if not os.path.isfile(init_file):
        _get_log(__name__).debug("No __init__.py in %s", plugin_path)
        return None

    module_name = f"pcm_plugin_{info.plugin_id}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, init_file)
        if spec is None or spec.loader is None:
            _get_log(__name__).warning("Failed to create spec for %s", plugin_path)
            return None

        module = importlib.util.module_from_spec(spec)

        # Inject the plugin path into sys.modules so relative imports work
        sys.modules[module_name] = module

        spec.loader.exec_module(module)

        # Look for plugin instance
        plugin = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, (ProtocolPlugin, ToolPlugin)):
                plugin = attr
                break

        if plugin is None:
            # Try calling a factory function
            for factory_name in ("create_plugin", "get_plugin", "register"):
                if hasattr(module, factory_name):
                    factory = getattr(module, factory_name)
                    result = factory()
                    if isinstance(result, (ProtocolPlugin, ToolPlugin)):
                        plugin = result
                        break

        if plugin is None:
            _get_log(__name__).warning("No plugin instance found in %s", plugin_path)
            return None

        plugin.plugin_info.plugin_path = plugin_path
        return plugin

    except Exception as e:
        _get_log(__name__).error("Error loading %s: %s", plugin_path, e, exc_info=True)
        return None


def load_plugins(disabled: list[str] | None = None) -> list[PluginInfo]:
    """Discover and load all available plugins.

    Args:
        disabled: List of plugin IDs to skip.

    Returns:
        List of PluginInfo for successfully loaded plugins.
    """
    disabled = disabled or []
    discovered = discover_plugins()
    loaded: list[PluginInfo] = []

    for plugin_id, info in discovered.items():
        if plugin_id in disabled:
            _get_log(__name__).info("Skipping disabled plugin: %s", plugin_id)
            continue

        plugin = _load_plugin_from_path(info.plugin_path, info)
        if plugin is None:
            continue

        try:
            if isinstance(plugin, ProtocolPlugin):
                pcm_register_protocol(plugin)
            elif isinstance(plugin, ToolPlugin):
                pcm_register_tool(plugin)
            loaded.append(info)
            _get_log(__name__).info("Loaded: %s v%s", plugin_id, info.version)
        except Exception as e:
            _get_log(__name__).error("Failed to register %s: %s", plugin_id, e, exc_info=True)

    return loaded


def reload_plugins(disabled: list[str] | None = None) -> list[PluginInfo]:
    """Reload all plugins (useful after installing/updating plugins)."""
    import plugins.plugin_base as base
    base._registry.clear()
    base._protocol_registry.clear()
    base._tool_registry.clear()
    return load_plugins(disabled)
