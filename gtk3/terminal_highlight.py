"""
terminal_highlight.py - Syntax highlighting per terminale VTE PCM.

Usa Vte.Terminal.match_add_regex() per evidenziare pattern nel testo.
Funziona con VTE >= 0.46. Su versioni precedenti il modulo viene disabilitato.
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, GLib, Vte


DEFAULT_PATTERNS = {
    "error": {
        "patterns": [
            r"\b(ERROR|FAILED|FATAL|CRITICAL|CRIT)\b",
            r"\b(segmentation fault|core dumped|SIGSEGV|SIGABRT)\b",
            r"\b(permission denied|access denied|connection refused|no route to host)\b",
            r"\b(command not found|No such file|not found)\b",
            r"\berror\b",
        ],
        "color": "#ff4444",
    },
    "warning": {
        "patterns": [
            r"\b(WARNING|WARN|CAUTION)\b",
            r"\b(deprecated|obsolete)\b",
            r"\b(timeout|timed out)\b",
            r"\b(retry|retrying)\b",
        ],
        "color": "#ffaa00",
    },
    "success": {
        "patterns": [
            r"\b(SUCCESS|OK|DONE|COMPLETED|READY|finished)\b",
            r"\b(accepted|authenticated|authorized|connected|established)\b",
            r"\b(active \(running\)|is running)\b",
        ],
        "color": "#44cc44",
    },
    "ip_address": {
        "patterns": [
            r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
            r"\b([0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b",
        ],
        "color": "#44aadd",
    },
    "url": {
        "patterns": [
            r"\bhttps?://[^\s()<>\"']+\b",
            r"\bftp://[^\s()<>\"']+\b",
        ],
        "color": "#8888ff",
    },
    "number": {
        "patterns": [
            r"\b\d+\.\d{2,}\b",
            r"\b\d{4,}\b",
            r"\b0x[0-9a-fA-F]+\b",
        ],
        "color": "#aa88cc",
    },
    "path": {
        "patterns": [
            r"(?:^|\s)(/~?[/\w.-]+)",
            r"(?:^|\s)(/[/\w.-]+)",
        ],
        "color": "#44bbbb",
    },
    "timestamp": {
        "patterns": [
            r"\b\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}\b",
            r"\b\d{2}:\d{2}:\d{2}\.\d+\b",
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b",
        ],
        "color": "#888888",
    },
    "keyword": {
        "patterns": [
            r"\b(killed|terminated|stopped|starting|restarting|reloading)\b",
            r"\b(listening|binding|listening on)\b",
            r"\b(fork|exec|spawn|launch)\b",
        ],
        "color": "#ddaa44",
    },
}


class Highlighter:
    def __init__(self, vte_terminal: Vte.Terminal):
        self._vte = vte_terminal
        self._enabled = True
        self._categories: dict[str, bool] = {}
        self._custom_patterns: list[dict] = []
        self._match_tags: list[int] = []
        self._build()

    def _build(self):
        self._clear_all()
        if not self._enabled:
            return
        patterns = dict(DEFAULT_PATTERNS)
        for cp in self._custom_patterns:
            cat = cp.get("category", "custom")
            pat = cp.get("pattern", "")
            col = cp.get("color", "#ff88ff")
            if cat not in patterns:
                patterns[cat] = {"patterns": [], "color": col}
            patterns[cat]["patterns"].append(pat)

        for cat_name, cat_data in patterns.items():
            if cat_name in self._categories and not self._categories[cat_name]:
                continue
            try:
                rgba = Gdk.RGBA()
                if not rgba.parse(cat_data["color"]):
                    rgba.parse("#ffffff")
                tag = self._vte.match_add_regex(
                    GLib.Regex.new("|".join(cat_data["patterns"]),
                                   GLib.RegexCompileFlags.OPTIMIZE |
                                   GLib.RegexCompileFlags.MULTILINE,
                                   0),
                    Vte.RegexMatchFlags(0),
                )
                if tag >= 0:
                    self._vte.match_set_cursor_type(tag, Gdk.CursorType.XTERM)
                    self._match_tags.append(tag)
            except Exception:
                pass

    def _clear_all(self):
        for tag in self._match_tags:
            try:
                self._vte.match_remove(tag)
            except Exception:
                pass
        self._match_tags.clear()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self._build()

    def is_enabled(self) -> bool:
        return self._enabled

    def set_category(self, name: str, enabled: bool):
        self._categories[name] = enabled
        self._build()

    def set_custom_patterns(self, patterns: list[dict]):
        self._custom_patterns = patterns
        self._build()

    @staticmethod
    def get_presets() -> dict:
        return {k: {"color": v["color"], "count": len(v["patterns"])}
                for k, v in DEFAULT_PATTERNS.items()}

    @staticmethod
    def get_preset_color(name: str) -> str:
        cat = DEFAULT_PATTERNS.get(name, {})
        return cat.get("color", "#ffffff")


def _hex_to_rgba(hex_color: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(hex_color)
    return rgba
