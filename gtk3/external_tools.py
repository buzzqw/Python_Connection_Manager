"""Generic, shell-free external tools for session profiles."""

from __future__ import annotations

import os
import shlex
import subprocess
from string import Formatter

import config_manager


class ExternalToolError(ValueError):
    """Raised when an external tool definition is invalid."""


_FIELDS = {
    "NAME": "name",
    "HOST": "host",
    "PORT": "port",
    "USER": "user",
    "DOMAIN": "domain",
    "DESCRIPTION": "notes",
    "GROUP": "group",
    "TAGS": "tags",
}


def _values(profile: dict, tool: dict) -> dict[str, str]:
    values = {
        name: str(profile.get(key, "") or "")
        for name, key in _FIELDS.items()
    }
    values.update({str(k).upper(): str(v) for k, v in config_manager.load_variables().items()})
    tool_variables = tool.get("variables", {})
    if isinstance(tool_variables, dict):
        values.update({str(k).upper(): str(v) for k, v in tool_variables.items()})
    values.update({key.lower(): value for key, value in values.items()})
    return values


def _expand(value: str, values: dict[str, str]) -> str:
    """Expand only simple named placeholders; never evaluate expressions."""
    if "{PASSWORD}" in value.upper() or "{SECRET}" in value.upper():
        raise ExternalToolError("Le credenziali non possono essere passate agli strumenti esterni")

    formatter = Formatter()
    try:
        parsed = formatter.parse(value)
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if format_spec or conversion or not field_name.isidentifier():
                raise ExternalToolError(f"Segnaposto non valido: {{{field_name}}}")
            if field_name.upper() not in values:
                raise ExternalToolError(f"Segnaposto sconosciuto: {{{field_name}}}")
    except ValueError as exc:
        raise ExternalToolError(f"Segnaposto non valido: {exc}") from exc
    try:
        return value.format_map({key: value for key, value in values.items()})
    except (KeyError, ValueError) as exc:
        raise ExternalToolError(f"Espansione segnaposto fallita: {exc}") from exc


def build_argv(tool: dict, profile: dict) -> list[str]:
    """Return a safe argv list for *tool* and *profile*.

    ``arguments`` is preferred as a list.  The legacy-friendly ``args`` string
    is accepted and parsed with shlex, never passed to a shell.
    """
    if not isinstance(tool, dict):
        raise ExternalToolError("Definizione strumento non valida")
    command = str(tool.get("command", tool.get("path", "")) or "").strip()
    if not command:
        raise ExternalToolError("Comando strumento mancante")
    values = _values(profile, tool)
    command = _expand(command, values)

    raw_arguments = tool.get("arguments", tool.get("args", []))
    if isinstance(raw_arguments, str):
        try:
            raw_arguments = shlex.split(raw_arguments)
        except ValueError as exc:
            raise ExternalToolError(f"Argomenti non validi: {exc}") from exc
    if not isinstance(raw_arguments, (list, tuple)):
        raise ExternalToolError("Gli argomenti devono essere una lista o una stringa")
    arguments = [_expand(str(argument), values) for argument in raw_arguments]
    return [command, *arguments]


def load_tools() -> list[dict]:
    tools = config_manager.load_settings().get("external_tools", [])
    return [tool for tool in tools if isinstance(tool, dict)]


def save_tools(tools: list[dict]) -> bool:
    settings = config_manager.load_settings()
    settings["external_tools"] = tools
    return config_manager.save_settings(settings)


def launch(tool: dict, profile: dict) -> subprocess.Popen:
    argv = build_argv(tool, profile)
    cwd = str(tool.get("working_directory", "") or "").strip()
    if cwd:
        cwd = os.path.expanduser(cwd)
        if not os.path.isdir(cwd):
            raise ExternalToolError(f"Directory di lavoro inesistente: {cwd}")
    try:
        return subprocess.Popen(
            argv,
            cwd=cwd or None,
            stdin=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        raise ExternalToolError(f"Avvio strumento fallito: {exc}") from exc
