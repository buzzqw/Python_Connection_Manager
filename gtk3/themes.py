"""
themes.py - Temi terminale e palette colori per PCM (GTK3)

I temi terminale definiscono i colori per VTE.
Il tema UI viene applicato tramite Gtk.CssProvider.
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _icon(name: str) -> str:
    return os.path.join(_HERE, "icons", name)


# ---------------------------------------------------------------------------
# Temi terminale VTE: chiavi EN stabili (usate nel JSON dei profili)
# I valori sono (background, foreground) come stringhe hex
# ---------------------------------------------------------------------------

TERMINAL_THEMES: dict[str, tuple[str, str]] = {
    "Dark (Default)":    ("#1e1e1e", "#cccccc"),
    "Light (B/W)":       ("#ffffff", "#1a1a1a"),
    "Matrix (Green)":    ("#000000", "#00ff00"),
    "Dracula":           ("#282a36", "#f8f8f2"),
    "Nord":              ("#2e3440", "#d8dee9"),
    "Monokai":           ("#272822", "#f8f8f2"),
    "Solarized Dark":    ("#002b36", "#839496"),
    "Solarized Light":   ("#fdf6e3", "#657b83"),
    "One Dark":          ("#282c34", "#abb2bf"),
    "Gruvbox Dark":      ("#282828", "#ebdbb2"),
    "Gruvbox Light":     ("#fbf1c7", "#3c3836"),
    "Tomorrow Night":    ("#1d1f21", "#c5c8c6"),
    "Cobalt":            ("#002240", "#ffffff"),
    "Zenburn":           ("#3f3f3f", "#dcdccc"),
}

# Mapping da chiavi vecchie (italiano) a chiavi nuove (EN) per migrazione profili
_THEME_MIGRATION: dict[str, str] = {
    "Scuro (Default)":  "Dark (Default)",
    "Chiaro (B/W)":     "Light (B/W)",
    "Matrix (Verde)":   "Matrix (Green)",
}


def migrate_theme_name(name: str) -> str:
    """Converte un vecchio nome tema in italiano al nome EN stabile."""
    return _THEME_MIGRATION.get(name, name)




def hex_to_gdk_rgba(hex_color: str):
    """Converte stringa '#rrggbb' in Gdk.RGBA."""
    from gi.repository import Gdk
    rgba = Gdk.RGBA()
    rgba.parse(hex_color)
    return rgba


# ---------------------------------------------------------------------------
# CSS GTK3 — tema UI chiaro (base) e scuro (override)
# ---------------------------------------------------------------------------

APP_CSS_BASE = """
window, dialog {
    background-color: #f0f0f0;
    color: #111111;
}

headerbar {
    background-color: #e0e0e0;
    color: #111111;
    border-bottom: 1px solid #bbb;
}

headerbar button,
headerbar menubutton button {
    color: #111111;
    background-color: #d4d4d4;
    border: 1px solid #aaa;
    border-radius: 4px;
    padding: 3px 8px;
    min-height: 28px;
}
headerbar button:hover,
headerbar menubutton button:hover {
    background-color: #b8b8b8;
    color: #000000;
}
headerbar button image,
headerbar menubutton button image,
headerbar button label,
headerbar menubutton button label {
    color: #111111;
}
/* Tooltip globale: sfondo scuro testo chiaro */
tooltip {
    background-color: #2a2a2a;
    color: #f0f0f0;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px 8px;
}
tooltip label {
    color: #f0f0f0;
    font-size: 12px;
}

toolbar {
    background-color: #e8e8e8;
    border-bottom: 1px solid #ccc;
}

treeview {
    background-color: #ffffff;
    color: #111111;
}
treeview:selected {
    background-color: #4e7abc;
    color: #ffffff;
}

notebook > header > tabs > tab {
    background-color: #e4e4e4;
    color: #444444;
    padding: 4px 12px;
}
notebook > header > tabs > tab:checked {
    background-color: #fafafa;
    color: #111111;
    font-weight: bold;
}

entry, spinbutton, combobox {
    background-color: #ffffff;
    color: #111111;
    border: 1px solid #aaa;
    border-radius: 3px;
}

label {
    color: #111111;
}

statusbar {
    background-color: #e8e8e8;
    color: #333333;
    border-top: 1px solid #ccc;
}

frame > border {
    border: 1px solid #bbb;
    border-radius: 4px;
}

checkbutton {
    color: #111111;
}

button {
    background-color: #e0e0e0;
    color: #111111;
    border: 1px solid #aaa;
    border-radius: 3px;
    padding: 3px 10px;
}
button:hover {
    background-color: #d0d0d0;
}
button:active {
    background-color: #b8b8b8;
}

/* Sidebar sessioni */
.session-sidebar {
    background-color: #f5f5f5;
    border-right: 1px solid #cccccc;
}

/* (infobar terminale rimossa — le stat live sono nella statusbar globale) */

/* Etichette header sezioni */
.section-header {
    color: #4e7abc;
    font-size: 14px;
    font-weight: bold;
    padding: 8px;
}

/* Pulsante connetti evidenziato */
.connect-button {
    background-color: #0078d4;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 4px;
    padding: 5px 16px;
}
.connect-button:hover {
    background-color: #006cbf;
}

/* Barra inferiore: statusbar + pulsante chiudi */
.bottom-bar {
    background-color: #e8e8e8;
    border-top: 1px solid #ccc;
}
statusbar {
    font-family: monospace;
    font-size: 12px;
    color: #222222;
}
.bottom-close-btn {
    color: #444444;
    font-size: 12px;
    padding: 2px 12px;
    border-left: 1px solid #ccc;
    border-radius: 0;
    background: transparent;
}
.bottom-close-btn:hover {
    background-color: #cc3333;
    color: #ffffff;
}
.bottom-close-btn:disabled {
    color: #aaaaaa;
}

/* Tab notebook: nomi sessioni */
notebook > header > tabs > tab {
    padding: 4px 10px;
}
notebook > header > tabs > tab:checked {
    font-weight: bold;
    color: #0078d4;
}

/* Indicatore tunnel attivi nella toolbar */
.tunnel-active {
    color: #22cc55;
}

/* Toast notifications */
.toast-warning {
    background-color: #e8a020;
    color: #ffffff;
    border-radius: 4px;
}
.toast-warning label {
    color: #ffffff;
}
.toast-error {
    background-color: #cc4444;
    color: #ffffff;
    border-radius: 4px;
}
.toast-error label {
    color: #ffffff;
}
.toast-info {
    background-color: #4e7abc;
    color: #ffffff;
    border-radius: 4px;
}
.toast-info label {
    color: #ffffff;
}

"""


APP_CSS_DARK = """
window, dialog {
    background-color: #2a2a2a;
    color: #e0e0e0;
}

headerbar {
    background-color: #333333;
    color: #e0e0e0;
    border-bottom: 1px solid #555;
}

headerbar button,
headerbar menubutton button {
    color: #e0e0e0;
    background-color: #3a3a3a;
    border: 1px solid #555;
}
headerbar button:hover,
headerbar menubutton button:hover {
    background-color: #4a4a4a;
    color: #ffffff;
}
headerbar button image,
headerbar menubutton button image,
headerbar button label,
headerbar menubutton button label {
    color: #e0e0e0;
}

treeview {
    background-color: #2a2a2a;
    color: #e0e0e0;
}
treeview:selected {
    background-color: #4e7abc;
    color: #ffffff;
}

notebook > header > tabs > tab {
    background-color: #2e2e2e;
    color: #aaaaaa;
}
notebook > header > tabs > tab:checked {
    background-color: #3a3a3a;
    color: #e0e0e0;
    font-weight: bold;
}

entry, spinbutton, combobox {
    background-color: #3a3a3a;
    color: #e0e0e0;
    border: 1px solid #555;
}

label {
    color: #e0e0e0;
}

statusbar {
    background-color: #333333;
    color: #cccccc;
}

button {
    background-color: #3a3a3a;
    color: #e0e0e0;
    border: 1px solid #555;
}
button:hover {
    background-color: #4a4a4a;
}

.session-sidebar {
    background-color: #252525;
    border-right: 1px solid #444;
}

.section-header {
    color: #4e7abc;
}

.bottom-bar {
    background-color: #333333;
    border-top: 1px solid #444;
}
statusbar {
    font-family: monospace;
    font-size: 12px;
    color: #cccccc;
}

notebook > header > tabs > tab:checked {
    color: #5aa2e0;
}

"""


def apply_css(app=None):
    """
    Applica il CSS globale all'applicazione GTK3.
    Chiamare una volta all'avvio, dopo Gtk.Application.__init__().
    """
    from gi.repository import Gtk, Gdk
    provider = Gtk.CssProvider()
    css = _get_current_css()
    provider.load_from_data(css.encode("utf-8"))
    display = Gdk.Display.get_default()
    screen = display.get_default_screen()
    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def _get_current_css() -> str:
    """Restituisce APP_CSS o APP_CSS_DARK in base alle impostazioni."""
    try:
        import config_manager
        s = config_manager.load_settings()
        if s.get("display", {}).get("dark_mode", False):
            return _merge_css(APP_CSS_BASE, APP_CSS_DARK)
    except Exception:
        pass
    return APP_CSS_BASE


def _merge_css(base: str, dark: str) -> str:
    """Combina il CSS base con le override dark."""
    return base + "\n/* === Dark mode overrides === */\n" + dark
