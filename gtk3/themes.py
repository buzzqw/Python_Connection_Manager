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
# Temi terminale VTE: (background, foreground) come stringhe hex
# ---------------------------------------------------------------------------

TERMINAL_THEMES: dict[str, tuple[str, str]] = {
    "Scuro (Default)":   ("#1e1e1e", "#cccccc"),
    "Chiaro (B/W)":      ("#ffffff", "#1a1a1a"),
    "Matrix (Verde)":    ("#000000", "#00ff00"),
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


def hex_to_gdk_rgba(hex_color: str):
    """Converte stringa '#rrggbb' in Gdk.RGBA."""
    from gi.repository import Gdk
    rgba = Gdk.RGBA()
    rgba.parse(hex_color)
    return rgba


# ---------------------------------------------------------------------------
# CSS GTK3 — tema UI chiaro
# ---------------------------------------------------------------------------

APP_CSS = """
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


"""


def apply_css(app=None):
    """
    Applica il CSS globale all'applicazione GTK3.
    Chiamare una volta all'avvio, dopo Gtk.Application.__init__().
    """
    from gi.repository import Gtk, Gdk
    provider = Gtk.CssProvider()
    provider.load_from_data(APP_CSS.encode("utf-8"))
    screen = Gdk.Screen.get_default()
    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
