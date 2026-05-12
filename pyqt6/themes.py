"""
themes.py - Temi terminale e palette colori per PCM
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))

def _icon(name: str) -> str:
    """Percorso assoluto icona nella cartella icons/, con slash forward per Qt CSS."""
    return os.path.join(_HERE, "icons", name).replace("\\", "/")

# Temi terminale: (background, foreground)
TERMINAL_THEMES = {
    "Scuro (Default)":      ("#1e1e1e", "#cccccc"),
    "Chiaro (B/W)":         ("#ffffff", "#1a1a1a"),
    "Matrix (Verde)":       ("#000000", "#00ff00"),
    "Dracula":              ("#282a36", "#f8f8f2"),
    "Nord":                 ("#2e3440", "#d8dee9"),
    "Monokai":              ("#272822", "#f8f8f2"),
    "Solarized Dark":       ("#002b36", "#839496"),
    "Solarized Light":      ("#fdf6e3", "#657b83"),
    "One Dark":             ("#282c34", "#abb2bf"),
    "Gruvbox Dark":         ("#282828", "#ebdbb2"),
    "Gruvbox Light":        ("#fbf1c7", "#3c3836"),
    "Tomorrow Night":       ("#1d1f21", "#c5c8c6"),
    "Cobalt":               ("#002240", "#ffffff"),
    "Zenburn":              ("#3f3f3f", "#dcdccc"),
}

# Tema UI dell'applicazione - FORZATO CHIARO
def get_stylesheet() -> str:
    """Genera lo stylesheet con percorsi assoluti alle icone."""
    chk = _icon("checkmark.png")
    return f"""
QMainWindow, QDialog {{
    background-color: #f0f0f0;
    color: #111111;
}}

QMenuBar {{ background-color: #e4e4e4; color: #111111; border-bottom: 1px solid #ccc; }}
QMenu {{ background-color: #ffffff; color: #111111; border: 1px solid #ccc; }}
QMenu::item:selected {{ background-color: #4e7abc; color: #ffffff; }}

QToolBar {{ background-color: #e8e8e8; border-bottom: 1px solid #ccc; }}
QToolBar QToolButton {{ color: #111111; }}
QToolBar QToolButton:hover {{ background-color: #d0d0d0; border-radius: 3px; }}

QTreeWidget, QListWidget, QTableWidget, QTableView {{
    background-color: #ffffff;
    color: #111111;
    border: 1px solid #ccc;
    font-size: 13px;
}}
QTreeWidget::item:selected, QListWidget::item:selected,
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: #4e7abc;
    color: #ffffff;
}}
QTreeWidget::item:selected:!active, QListWidget::item:selected:!active,
QTableWidget::item:selected:!active, QTableView::item:selected:!active {{
    background-color: #3a5f8a;
    color: #ffffff;
}}

QTabWidget::pane {{ border: 1px solid #ccc; background-color: #fafafa; }}
QTabBar::tab {{
    background-color: #e4e4e4;
    color: #444444;
    border: 1px solid #ccc;
    padding: 6px 14px;
}}
QTabBar::tab:selected {{
    background-color: #fafafa;
    color: #111111;
    font-weight: bold;
    border-bottom: 1px solid #fafafa;
}}

QLineEdit, QComboBox, QSpinBox, QTextEdit {{
    background-color: #ffffff;
    color: #111111;
    border: 1px solid #aaa;
    border-radius: 3px;
    padding: 3px;
}}

QLabel {{ color: #111111; }}

QStatusBar {{ background-color: #e8e8e8; color: #333333; border-top: 1px solid #ccc; }}

QGroupBox {{
    border: 1px solid #bbb;
    border-radius: 4px;
    margin-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 3px;
    color: #4e7abc;
    font-weight: bold;
}}

QCheckBox {{ spacing: 6px; color: #111111; }}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 2px solid #888888;
    border-radius: 3px;
    background: #ffffff;
}}
QCheckBox::indicator:hover {{
    border-color: #0078d4;
    background: #e8f0fe;
}}
QCheckBox::indicator:checked {{
    background: #0078d4;
    border-color: #0057a8;
    image: url({chk});
}}
QCheckBox::indicator:checked:hover {{
    background: #006cbf;
    border-color: #004f9a;
    image: url({chk});
}}
"""

# Compatibilità: APP_STYLESHEET rimane disponibile per il codice esistente
APP_STYLESHEET = get_stylesheet()
