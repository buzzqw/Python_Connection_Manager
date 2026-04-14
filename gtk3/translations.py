"""
translations.py - Sistema i18n per PCM (GTK3 port — invariato rispetto a PyQt6)
"""

_LANG: str = "it"

AVAILABLE_LANGUAGES: dict[str, str] = {
    "it": "Italiano",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
}


def set_lang(code: str) -> None:
    global _LANG
    if code in AVAILABLE_LANGUAGES:
        _LANG = code


def get_lang() -> str:
    return _LANG


def init_from_settings() -> None:
    import config_manager
    s = config_manager.load_settings()
    set_lang(s.get("general", {}).get("language", "it"))


def t(key: str, **kwargs) -> str:
    entry = _T.get(key, {})
    text = entry.get(_LANG) or entry.get("en") or key
    if isinstance(text, list):
        return str(text)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def tl(key: str) -> list:
    entry = _T.get(key, {})
    result = entry.get(_LANG) or entry.get("en") or []
    return result if isinstance(result, list) else [result]


# ---------------------------------------------------------------------------
# Dizionario traduzioni (identico all'originale)
# ---------------------------------------------------------------------------
_T: dict = {
    # Generale
    "app.title":         {"it": "PCM - Python Connection Manager", "en": "PCM - Python Connection Manager"},
    "app.ready":         {"it": "Pronto", "en": "Ready"},
    "app.exit_confirm":  {"it": "Uscire da PCM?", "en": "Exit PCM?"},
    "app.exit_msg":      {"it": "Ci sono sessioni aperte. Vuoi davvero uscire?",
                          "en": "There are open sessions. Do you really want to exit?"},

    # Menu File
    "menu.file":              {"it": "File",           "en": "File"},
    "menu.new_session":       {"it": "Nuova sessione", "en": "New session"},
    "menu.new_terminal":      {"it": "Terminale locale","en": "Local terminal"},
    "menu.settings":          {"it": "Impostazioni",   "en": "Settings"},
    "menu.exit":              {"it": "Esci",            "en": "Exit"},

    # Menu Strumenti
    "menu.tools":             {"it": "Strumenti",          "en": "Tools"},
    "menu.tunnel_manager":    {"it": "Tunnel SSH",          "en": "SSH Tunnels"},
    "menu.ftp_server":        {"it": "Server FTP locale",   "en": "Local FTP server"},
    "menu.import_sessions":   {"it": "Importa sessioni…",   "en": "Import sessions…"},

    # Menu Vista
    "menu.view":              {"it": "Vista",           "en": "View"},
    "menu.sidebar":           {"it": "Barra sessioni",  "en": "Session sidebar"},
    "menu.toolbar":           {"it": "Barra strumenti", "en": "Toolbar"},

    # Toolbar
    "tb.new_session":   {"it": "Nuova sessione",   "en": "New session"},
    "tb.new_terminal":  {"it": "Terminale locale", "en": "Local terminal"},
    "tb.settings":      {"it": "Impostazioni",     "en": "Settings"},
    "tb.tunnels":       {"it": "Tunnel SSH",        "en": "SSH Tunnels"},

    # Schermata benvenuto
    "welcome.title":        {"it": "Benvenuto in PCM", "en": "Welcome to PCM"},
    "welcome.new_session":  {"it": "Nuova sessione",   "en": "New session"},
    "welcome.local_term":   {"it": "Terminale locale", "en": "Local terminal"},
    "welcome.recent":       {"it": "Sessioni recenti", "en": "Recent sessions"},

    # Pannello sessioni
    "sp.title":         {"it": "Sessioni",      "en": "Sessions"},
    "sp.search_ph":     {"it": "Cerca…",        "en": "Search…"},
    "sp.no_sessions":   {"it": "Nessuna sessione", "en": "No sessions"},
    "sp.connect":       {"it": "Connetti",      "en": "Connect"},
    "sp.edit":          {"it": "Modifica",      "en": "Edit"},
    "sp.duplicate":     {"it": "Duplica",       "en": "Duplicate"},
    "sp.delete":        {"it": "Elimina",       "en": "Delete"},
    "sp.delete_confirm":{"it": "Eliminare la sessione '{name}'?",
                         "en": "Delete session '{name}'?"},
    "sp.new_group":     {"it": "Nuovo gruppo",  "en": "New group"},
    "sp.ungrouped":     {"it": "(senza gruppo)", "en": "(ungrouped)"},

    # Dialog sessione
    "sd.new_title":       {"it": "Nuova sessione",         "en": "New session"},
    "sd.edit_title":      {"it": "Modifica — {name}",      "en": "Edit — {name}"},
    "sd.session_name":    {"it": "Nome sessione:",          "en": "Session name:"},
    "sd.session_name_ph": {"it": "es. Server produzione",  "en": "e.g. Production server"},
    "sd.group":           {"it": "Gruppo:",                 "en": "Group:"},
    "sd.group_ph":        {"it": "es. Lavoro",              "en": "e.g. Work"},
    "sd.protocol":        {"it": "Protocollo:",             "en": "Protocol:"},
    "sd.host":            {"it": "Host:",                   "en": "Host:"},
    "sd.port":            {"it": "Porta:",                  "en": "Port:"},
    "sd.user":            {"it": "Utente:",                 "en": "User:"},
    "sd.password":        {"it": "Password:",               "en": "Password:"},
    "sd.private_key":     {"it": "Chiave privata:",         "en": "Private key:"},
    "sd.notes":           {"it": "Note",                    "en": "Notes"},
    "sd.tab.connection":  {"it": "Connessione",             "en": "Connection"},
    "sd.tab.terminal":    {"it": "Terminale",               "en": "Terminal"},
    "sd.tab.advanced":    {"it": "Avanzate",                "en": "Advanced"},
    "sd.tab.tunnel":      {"it": "Tunnel",                  "en": "Tunnel"},
    "sd.tab.macros":      {"it": "Macro",                   "en": "Macros"},
    "sd.tab.notes":       {"it": "Note",                    "en": "Notes"},
    "sd.save":            {"it": "Salva",                   "en": "Save"},
    "sd.cancel":          {"it": "Annulla",                 "en": "Cancel"},

    # Terminale
    "terminal.xterm_missing":   {"it": "xterm non trovato",          "en": "xterm not found"},
    "terminal.xterm_install":   {"it": "Installa xterm",             "en": "Install xterm"},
    "terminal.deps_missing":    {"it": "Dipendenze mancanti",        "en": "Missing dependencies"},
    "terminal.install_xdotool": {"it": "Installa xdotool e xwininfo","en": "Install xdotool and xwininfo"},
    "terminal.clipboard_unavail":{"it": "Clipboard non disponibile", "en": "Clipboard unavailable"},
    "terminal.install_xclip":   {"it": "Installa xclip o xsel",     "en": "Install xclip or xsel"},
    "terminal.session_ended":   {"it": "  ✖  Sessione terminata",    "en": "  ✖  Session ended"},

    # Impostazioni
    "settings.title":              {"it": "Impostazioni",              "en": "Settings"},
    "settings.header":             {"it": "Impostazioni globali PCM",  "en": "PCM Global Settings"},
    "settings.tab.general":        {"it": "Generale",                  "en": "General"},
    "settings.tab.terminal":       {"it": "Terminale",                 "en": "Terminal"},
    "settings.tab.ssh":            {"it": "SSH",                       "en": "SSH"},
    "settings.tab.shortcuts":      {"it": "Scorciatoie",               "en": "Shortcuts"},
    "settings.general.home_dir":   {"it": "Home directory:",           "en": "Home directory:"},
    "settings.general.editor":     {"it": "Editor predefinito:",       "en": "Default editor:"},
    "settings.general.confirm_exit":{"it": "Conferma all'uscita",      "en": "Confirm on exit"},
    "settings.general.language_note":{"it": "Riavvia PCM per applicare la nuova lingua.",
                                       "en": "Restart PCM to apply the new language."},
    "settings.terminal.default_theme":{"it": "Tema terminale:",        "en": "Terminal theme:"},
    "settings.terminal.default_font": {"it": "Font:",                  "en": "Font:"},
    "settings.terminal.font_size":    {"it": "Dimensione font:",       "en": "Font size:"},
    "settings.terminal.scrollback":   {"it": "Righe scrollback:",      "en": "Scrollback lines:"},
    "settings.terminal.paste_right":  {"it": "Incolla con tasto destro","en": "Paste on right click"},
    "settings.terminal.confirm_close":{"it": "Conferma chiusura tab",  "en": "Confirm tab close"},
    "settings.terminal.warn_paste":   {"it": "Avvisa incolla multiriga","en": "Warn on multiline paste"},
    "settings.terminal.log_output":   {"it": "Registra output",        "en": "Log output"},
    "settings.terminal.log_dir":      {"it": "Cartella log:",          "en": "Log folder:"},
    "settings.ssh.keepalive":         {"it": "Keepalive (sec):",       "en": "Keepalive (sec):"},
    "settings.ssh.strict":            {"it": "Strict host check",      "en": "Strict host check"},
    "settings.ssh.sftp_auto":         {"it": "Apri SFTP auto (SSH)",   "en": "Auto SFTP browser (SSH)"},
    "settings.shortcuts.new_terminal":{"it": "Nuovo terminale",        "en": "New terminal"},
    "settings.shortcuts.close_tab":   {"it": "Chiudi tab",             "en": "Close tab"},
    "settings.shortcuts.prev_tab":    {"it": "Tab precedente",         "en": "Previous tab"},
    "settings.shortcuts.next_tab":    {"it": "Tab successivo",         "en": "Next tab"},
    "settings.shortcuts.new_session": {"it": "Nuova sessione",         "en": "New session"},
    "settings.shortcuts.toggle_sidebar":{"it": "Mostra/Nascondi sidebar","en": "Toggle sidebar"},
    "settings.shortcuts.find":        {"it": "Cerca",                  "en": "Find"},
    "settings.shortcuts.fullscreen":  {"it": "Schermo intero",         "en": "Fullscreen"},
    "settings.shortcuts.note":        {"it": "Formato: Ctrl+Shift+T, F11, ecc.",
                                       "en": "Format: Ctrl+Shift+T, F11, etc."},

    # SFTP browser
    "sftp.title":       {"it": "Browser SFTP",  "en": "SFTP Browser"},
    "sftp.loading":     {"it": "Caricamento…",  "en": "Loading…"},
    "sftp.upload":      {"it": "Carica",        "en": "Upload"},
    "sftp.download":    {"it": "Scarica",       "en": "Download"},
    "sftp.delete":      {"it": "Elimina",       "en": "Delete"},
    "sftp.rename":      {"it": "Rinomina",      "en": "Rename"},
    "sftp.mkdir":       {"it": "Nuova cartella","en": "New folder"},
    "sftp.refresh":     {"it": "Aggiorna",      "en": "Refresh"},
    "sftp.permissions": {"it": "Permessi",      "en": "Permissions"},

    # Tunnel
    "tunnel.title":     {"it": "Tunnel SSH",    "en": "SSH Tunnels"},
    "tunnel.add":       {"it": "Aggiungi",      "en": "Add"},
    "tunnel.edit":      {"it": "Modifica",      "en": "Edit"},
    "tunnel.delete":    {"it": "Elimina",       "en": "Delete"},
    "tunnel.start":     {"it": "Avvia",         "en": "Start"},
    "tunnel.stop":      {"it": "Ferma",         "en": "Stop"},
    "tunnel.status.running": {"it": "Attivo",   "en": "Running"},
    "tunnel.status.stopped": {"it": "Fermo",    "en": "Stopped"},

    # Errori generici
    "err.no_host":      {"it": "Host non specificato",   "en": "No host specified"},
    "err.save_failed":  {"it": "Salvataggio fallito",    "en": "Save failed"},
    "err.connect":      {"it": "Errore di connessione",  "en": "Connection error"},
}
