"""
plugin_manager.py - Plugin discovery, loading, and lifecycle management.

Scans the built-in, system and ~/.local/share/pcm/plugins/ directories
for plugin directories containing plugin.json metadata. External plugins
require explicit approval before their Python code is executed.
"""

from __future__ import annotations

import json
import hashlib
import os
import importlib
import importlib.util
import sys
from typing import Optional

from pcm_logging import get_logger as _get_log

from plugins.plugin_base import (
    PluginInfo, ProtocolPlugin, ToolPlugin,
    pcm_register_protocol, pcm_register_tool,
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


def _plugin_fingerprint(plugin_path: str) -> str:
    """Fingerprint plugin sources before asking the user to trust them."""
    digest = hashlib.sha256()
    for root, dirs, files in os.walk(plugin_path):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for filename in sorted(files):
            if filename.endswith(('.pyc', '.pyo')):
                continue
            path = os.path.join(root, filename)
            if not os.path.isfile(path):
                continue
            relative = os.path.relpath(path, plugin_path).replace(os.sep, "/")
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            with open(path, "rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def _is_builtin_plugin(plugin_path: str) -> bool:
    return os.path.dirname(os.path.realpath(plugin_path)) == os.path.realpath(
        get_builtin_plugin_dir()
    )


def _trusted_plugins() -> dict:
    try:
        import config_manager
        trusted = config_manager.load_settings().get("trusted_plugins", {})
        return trusted if isinstance(trusted, dict) else {}
    except Exception as exc:
        _get_log(__name__).warning("Unable to read trusted plugins: %s", exc)
        return {}


def _remember_trusted_plugin(plugin_id: str, fingerprint: str) -> None:
    try:
        import config_manager
        settings = config_manager.load_settings()
        trusted = settings.setdefault("trusted_plugins", {})
        trusted[plugin_id] = fingerprint
        config_manager.save_settings(settings)
    except Exception as exc:
        _get_log(__name__).warning("Unable to save plugin trust: %s", exc)


def discover_plugins() -> dict[str, PluginInfo]:
    """Discover all available plugins without loading them.
    
    Searches: built-in dir, system dir, and user dir.
    Returns dict of plugin_id -> PluginInfo for all discovered plugins.
    """
    discovered: dict[str, PluginInfo] = {}
    # Built-ins win over externally supplied plugins with the same ID.
    search_paths = [get_builtin_plugin_dir(), get_system_plugin_dir(), get_plugin_dir()]

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


def load_plugins(disabled: list[str] | None = None, confirm=None) -> list[PluginInfo]:
    """Discover and load all available plugins.

    Args:
        disabled: List of plugin IDs to skip.
        confirm: Callback ``(info, fingerprint) -> bool`` used to approve
            external plugins whose source has not been trusted yet.

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

        if not _is_builtin_plugin(info.plugin_path):
            fingerprint = _plugin_fingerprint(info.plugin_path)
            if _trusted_plugins().get(plugin_id) != fingerprint:
                if confirm is None or not confirm(info, fingerprint):
                    _get_log(__name__).warning(
                        "Skipping untrusted external plugin: %s", plugin_id
                    )
                    continue
                _remember_trusted_plugin(plugin_id, fingerprint)

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
