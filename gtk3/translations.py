"""
translations.py - Sistema i18n per PCM (versione GTK3/VTE)
Supporta: Italiano (it), English (en), Deutsch (de), Français (fr), Español (es)

Uso rapido:
    from translations import t, set_lang, get_lang
    t("chiave")           → stringa nella lingua attiva
    t("chiave", n=3)      → con sostituzione {n}
    set_lang("en")        → cambia lingua in memoria (non salva su disco)
    get_lang()            → codice lingua corrente

Note:
  - Il selettore lingua nell'UI è SEMPRE in inglese (nomi fissi).
  - Fallback: se la chiave manca nella lingua attiva → inglese → chiave grezza.
  - set_lang() non salva su disco: il salvataggio avviene in SettingsDialog.
  - Chiamare init_from_settings() una sola volta all'avvio di PCM.py.
"""

_LANG: str = "it"

# Lingue disponibili: codice ISO → etichetta SEMPRE in inglese (per il selettore UI)
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


def t(key: str, **kwargs) -> str:
    """Traduce una chiave. Fallback: inglese → chiave grezza."""
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
    """Traduce una chiave che contiene una lista di stringhe."""
    entry = _T.get(key, {})
    result = entry.get(_LANG) or entry.get("en") or []
    return result if isinstance(result, list) else [result]


def init_from_settings() -> None:
    """
    Legge la lingua salvata in pcm_settings.json e la imposta.
    Chiamare una sola volta all'avvio, dopo aver importato config_manager.
    """
    global _LANG
    try:
        import config_manager
        s = config_manager.load_settings()
        code = s.get("general", {}).get("language", "it")
        if code in AVAILABLE_LANGUAGES:
            _LANG = code
    except Exception:
        pass


# ===========================================================================
# Dizionario traduzioni
# ===========================================================================

_T: dict[str, dict[str, str]] = {

    # ── Applicazione ─────────────────────────────────────────────────────────
    "app.title": {
        "it": "PCM — Python Connection Manager",
        "en": "PCM — Python Connection Manager",
        "de": "PCM — Python Connection Manager",
        "fr": "PCM — Python Connection Manager",
        "es": "PCM — Python Connection Manager",
    },
    "app.subtitle": {
        "it": "Python Connection Manager • Gestione sessioni remote multi-protocollo",
        "en": "Python Connection Manager • Multi-protocol remote session manager",
        "de": "Python Connection Manager • Mehrprotokoll-Fernverbindungsmanager",
        "fr": "Python Connection Manager • Gestionnaire de sessions distantes multi-protocole",
        "es": "Python Connection Manager • Gestor de sesiones remotas multi-protocolo",
    },
    "app.ready": {
        "it": "PCM pronto",
        "en": "PCM ready",
        "de": "PCM bereit",
        "fr": "PCM prêt",
        "es": "PCM listo",
    },
    "app.sessions_open": {
        "it": "  Sessioni aperte: {n}  ",
        "en": "  Open sessions: {n}  ",
        "de": "  Offene Sitzungen: {n}  ",
        "fr": "  Sessions ouvertes : {n}  ",
        "es": "  Sesiones abiertas: {n}  ",
    },
    "app.about_text": {
        "it": (
            "<b>PCM — Python Connection Manager</b> (GTK3)<br><br>"
            "Sviluppato in Python/GTK3 con terminale VTE nativo.<br><br>"
            "<b>Protocolli supportati:</b> SSH, Telnet, SFTP, FTP, RDP, VNC, "
            "SSH Tunnel, Mosh, Seriale<br><br>"
            "<b>Autore:</b> Andres Zanzani - azanzani@gmail.com"
        ),
        "en": (
            "<b>PCM — Python Connection Manager</b> (GTK3)<br><br>"
            "Built with Python/GTK3 and native VTE terminal.<br><br>"
            "<b>Supported protocols:</b> SSH, Telnet, SFTP, FTP, RDP, VNC, "
            "SSH Tunnel, Mosh, Serial<br><br>"
            "<b>Author:</b> Andres Zanzani - azanzani@gmail.com"
        ),
        "de": (
            "<b>PCM — Python Connection Manager</b> (GTK3)<br><br>"
            "Entwickelt mit Python/GTK3 und nativem VTE-Terminal.<br><br>"
            "<b>Unterstützte Protokolle:</b> SSH, Telnet, SFTP, FTP, RDP, VNC, "
            "SSH-Tunnel, Mosh, Seriell<br><br>"
            "<b>Autor:</b> Andres Zanzani - azanzani@gmail.com"
        ),
        "fr": (
            "<b>PCM — Python Connection Manager</b> (GTK3)<br><br>"
            "Développé avec Python/GTK3 et terminal VTE natif.<br><br>"
            "<b>Protocoles supportés :</b> SSH, Telnet, SFTP, FTP, RDP, VNC, "
            "Tunnel SSH, Mosh, Série<br><br>"
            "<b>Auteur :</b> Andres Zanzani - azanzani@gmail.com"
        ),
        "es": (
            "<b>PCM — Python Connection Manager</b> (GTK3)<br><br>"
            "Desarrollado con Python/GTK3 y terminal VTE nativo.<br><br>"
            "<b>Protocolos soportados:</b> SSH, Telnet, SFTP, FTP, RDP, VNC, "
            "Túnel SSH, Mosh, Serie<br><br>"
            "<b>Autor:</b> Andres Zanzani - azanzani@gmail.com"
        ),
    },

    # ── Menu File ─────────────────────────────────────────────────────────────
    "menu.file": {
        "it": "File", "en": "File", "de": "Datei", "fr": "Fichier", "es": "Archivo",
    },
    "menu.file.new_session": {
        "it": "➕ Nuova sessione",
        "en": "➕ New session",
        "de": "➕ Neue Sitzung",
        "fr": "➕ Nouvelle session",
        "es": "➕ Nueva sesión",
    },
    "menu.file.local_terminal": {
        "it": "⌨ Terminale locale",
        "en": "⌨ Local terminal",
        "de": "⌨ Lokales Terminal",
        "fr": "⌨ Terminal local",
        "es": "⌨ Terminal local",
    },
    "menu.file.import_sessions": {
        "it": "📥 Importa sessioni…",
        "en": "📥 Import sessions…",
        "de": "📥 Sitzungen importieren…",
        "fr": "📥 Importer des sessions…",
        "es": "📥 Importar sesiones…",
    },
    "menu.file.export_sessions": {
        "it": "📤 Esporta sessioni…",
        "en": "📤 Export sessions…",
        "de": "📤 Sitzungen exportieren…",
        "fr": "📤 Exporter des sessions…",
        "es": "📤 Exportar sesiones…",
    },
    "menu.file.settings": {
        "it": "⚙ Impostazioni",
        "en": "⚙ Settings",
        "de": "⚙ Einstellungen",
        "fr": "⚙ Paramètres",
        "es": "⚙ Configuración",
    },
    "menu.file.quit": {
        "it": "✖ Esci",
        "en": "✖ Quit",
        "de": "✖ Beenden",
        "fr": "✖ Quitter",
        "es": "✖ Salir",
    },

    # ── Menu Visualizza ───────────────────────────────────────────────────────
    "menu.view": {
        "it": "Visualizza", "en": "View", "de": "Ansicht", "fr": "Affichage", "es": "Vista",
    },
    "menu.view.sidebar": {
        "it": "📋 Mostra/Nascondi Sidebar",
        "en": "📋 Show/Hide Sidebar",
        "de": "📋 Seitenleiste ein-/ausblenden",
        "fr": "📋 Afficher/masquer la barre latérale",
        "es": "📋 Mostrar/ocultar barra lateral",
    },
    "menu.view.split_vertical": {
        "it": "🔀 Modalità Split verticale",
        "en": "🔀 Vertical split mode",
        "de": "🔀 Vertikaler Split-Modus",
        "fr": "🔀 Mode division verticale",
        "es": "🔀 Modo división vertical",
    },
    "menu.view.split_horizontal": {
        "it": "🔀 Modalità Split orizzontale",
        "en": "🔀 Horizontal split mode",
        "de": "🔀 Horizontaler Split-Modus",
        "fr": "🔀 Mode division horizontale",
        "es": "🔀 Modo división horizontal",
    },
    "menu.view.split_single": {
        "it": "⬜ Vista singola",
        "en": "⬜ Single view",
        "de": "⬜ Einzelansicht",
        "fr": "⬜ Vue unique",
        "es": "⬜ Vista única",
    },

    # ── Menu Strumenti ────────────────────────────────────────────────────────
    "menu.tools": {
        "it": "Strumenti", "en": "Tools", "de": "Werkzeuge", "fr": "Outils", "es": "Herramientas",
    },
    "menu.tools.tunnels": {
        "it": "🔀 Gestione Tunnel SSH",
        "en": "🔀 SSH Tunnel Manager",
        "de": "🔀 SSH-Tunnel-Verwaltung",
        "fr": "🔀 Gestionnaire de tunnels SSH",
        "es": "🔀 Gestión de túneles SSH",
    },
    "menu.tools.multiexec": {
        "it": "⚡ Multi-exec…", "en": "⚡ Multi-exec…", "de": "⚡ Multi-exec…",
        "fr": "⚡ Multi-exec…", "es": "⚡ Multi-exec…",
    },
    "menu.tools.variables": {
        "it": "📦 Variabili globali…",
        "en": "📦 Global variables…",
        "de": "📦 Globale Variablen…",
        "fr": "📦 Variables globales…",
        "es": "📦 Variables globales…",
    },
    "menu.tools.ftp_server": {
        "it": "🗄  Server FTP locale…",
        "en": "🗄  Local FTP server…",
        "de": "🗄  Lokaler FTP-Server…",
        "fr": "🗄  Serveur FTP local…",
        "es": "🗄  Servidor FTP local…",
    },
    "menu.tools.import_from": {
        "it": "📥  Importa da applicazione esterna",
        "en": "📥  Import from external app",
        "de": "📥  Aus externer Anwendung importieren",
        "fr": "📥  Importer depuis une application externe",
        "es": "📥  Importar desde aplicación externa",
    },
    "menu.tools.protected_mode": {
        "it": "🔒 Modalità protetta (nascondi password)",
        "en": "🔒 Protected mode (hide passwords)",
        "de": "🔒 Geschützter Modus (Passwörter verbergen)",
        "fr": "🔒 Mode protégé (masquer les mots de passe)",
        "es": "🔒 Modo protegido (ocultar contraseñas)",
    },
    "menu.tools.check_deps": {
        "it": "📋 Verifica dipendenze",
        "en": "📋 Check dependencies",
        "de": "📋 Abhängigkeiten prüfen",
        "fr": "📋 Vérifier les dépendances",
        "es": "📋 Verificar dependencias",
    },
    "menu.tools.crypto": {
        "it": "Imposta password globale...",
        "en": "Set global password...",
        "de": "Globales Passwort festlegen...",
        "fr": "Définir le mot de passe global...",
        "es": "Establecer contraseña global...",
    },

    # ── Menu Aiuto ────────────────────────────────────────────────────────────
    "menu.help.guide": {
        "it": "📖 Guida di PCM",
        "en": "📖 PCM Guide",
        "de": "📖 PCM-Handbuch",
        "fr": "📖 Guide PCM",
        "es": "📖 Guía de PCM",
    },
    "menu.help.about": {
        "it": "ℹ  Informazioni su PCM",
        "en": "ℹ  About PCM",
        "de": "ℹ  Über PCM",
        "fr": "ℹ  À propos de PCM",
        "es": "ℹ  Acerca de PCM",
    },

    # ── Toolbar ───────────────────────────────────────────────────────────────
    "toolbar.session":          {"it": "Sessione",      "en": "Session",     "de": "Sitzung",       "fr": "Session",    "es": "Sesión"},
    "toolbar.session.tooltip":  {"it": "Nuova sessione remota", "en": "New remote session", "de": "Neue Fernsitzung", "fr": "Nouvelle session distante", "es": "Nueva sesión remota"},
    "toolbar.local":            {"it": "Locale",        "en": "Local",       "de": "Lokal",         "fr": "Local",      "es": "Local"},
    "toolbar.local.tooltip":    {"it": "Terminale locale", "en": "Local terminal", "de": "Lokales Terminal", "fr": "Terminal local", "es": "Terminal local"},
    "toolbar.tunnel.tooltip":   {"it": "Gestione tunnel SSH", "en": "SSH tunnel manager", "de": "SSH-Tunnel-Verwaltung", "fr": "Gestionnaire de tunnels SSH", "es": "Gestión de túneles SSH"},
    "toolbar.settings":         {"it": "Impostazioni",  "en": "Settings",    "de": "Einstellungen", "fr": "Paramètres", "es": "Configuración"},
    "toolbar.settings.tooltip": {"it": "Impostazioni globali", "en": "Global settings", "de": "Globale Einstellungen", "fr": "Paramètres globaux", "es": "Configuración global"},
    "toolbar.split":            {"it": "Split",         "en": "Split",       "de": "Teilen",        "fr": "Diviser",    "es": "Dividir"},
    "toolbar.split.tooltip":    {"it": "Modalità split terminale", "en": "Terminal split mode", "de": "Terminal-Split-Modus", "fr": "Mode division du terminal", "es": "Modo división del terminal"},
    "toolbar.split.single":     {"it": "Singolo",       "en": "Single",      "de": "Einzeln",       "fr": "Simple",     "es": "Simple"},
    "toolbar.split.vertical":   {"it": "Split verticale (2)", "en": "Vertical split (2)", "de": "Vertikale Teilung (2)", "fr": "Division verticale (2)", "es": "División vertical (2)"},
    "toolbar.split.horizontal": {"it": "Split orizzontale (2)", "en": "Horizontal split (2)", "de": "Horizontale Teilung (2)", "fr": "Division horizontale (2)", "es": "División horizontal (2)"},

    # ── Quick Connect ─────────────────────────────────────────────────────────
    "qc.label":       {"it": "Quick Connect:", "en": "Quick Connect:", "de": "Schnellverbindung:", "fr": "Connexion rapide :", "es": "Conexión rápida:"},
    "qc.placeholder": {"it": "utente@host:porta  oppure  host", "en": "user@host:port  or  host", "de": "benutzer@host:port  oder  host", "fr": "utilisateur@hôte:port  ou  hôte", "es": "usuario@host:puerto  o  host"},
    "qc.connect":     {"it": "▶ Connetti", "en": "▶ Connect", "de": "▶ Verbinden", "fr": "▶ Connecter", "es": "▶ Conectar"},
    "qc.bad_format":  {"it": "Quick Connect: formato non riconosciuto", "en": "Quick Connect: unrecognised format", "de": "Quick Connect: Format nicht erkannt", "fr": "Connexion rapide : format non reconnu", "es": "Conexión rápida: formato no reconocido"},

    # ── Schermata Benvenuto ───────────────────────────────────────────────────
    "welcome.btn_new_session":    {"it": "➕\n\nNuova sessione\nremota", "en": "➕\n\nNew remote\nsession", "de": "➕\n\nNeue\nFernsitzung", "fr": "➕\n\nNouvelle session\ndistante", "es": "➕\n\nNueva sesión\nremota"},
    "welcome.btn_local_terminal": {"it": "⌨\n\nTerminale\nlocale", "en": "⌨\n\nLocal\nterminal", "de": "⌨\n\nLokales\nTerminal", "fr": "⌨\n\nTerminal\nlocal", "es": "⌨\n\nTerminal\nlocal"},
    "welcome.missing_tools":      {"it": "⚠  Strumenti non trovati: {tools}", "en": "⚠  Tools not found: {tools}", "de": "⚠  Werkzeuge nicht gefunden: {tools}", "fr": "⚠  Outils non trouvés : {tools}", "es": "⚠  Herramientas no encontradas: {tools}"},
    "welcome.footer":             {"it": "Doppio clic su una sessione nella sidebar per connettersi  •  Ctrl+Alt+T = terminale locale", "en": "Double-click a session in the sidebar to connect  •  Ctrl+Alt+T = local terminal", "de": "Doppelklick auf eine Sitzung in der Seitenleiste  •  Ctrl+Alt+T = lokales Terminal", "fr": "Double-cliquez sur une session dans la barre latérale  •  Ctrl+Alt+T = terminal local", "es": "Doble clic en una sesión en la barra lateral  •  Ctrl+Alt+T = terminal local"},

    # ── Sidebar ───────────────────────────────────────────────────────────────
    "sidebar.sessions":            {"it": "  Sessioni",      "en": "  Sessions",    "de": "  Sitzungen",    "fr": "  Sessions",   "es": "  Sesiones"},
    "sidebar.search_placeholder":  {"it": "Cerca sessione…", "en": "Search session…", "de": "Sitzung suchen…", "fr": "Rechercher session…", "es": "Buscar sesión…"},
    "sidebar.new_session_tooltip": {"it": "Nuova sessione",  "en": "New session",   "de": "Neue Sitzung",   "fr": "Nouvelle session", "es": "Nueva sesión"},
    "sidebar.refresh_tooltip":     {"it": "Aggiorna lista",  "en": "Refresh list",  "de": "Liste aktualisieren", "fr": "Actualiser la liste", "es": "Actualizar lista"},
    "sidebar.expand_tooltip":      {"it": "Espandi tutto",   "en": "Expand all",    "de": "Alle aufklappen","fr": "Tout développer","es": "Expandir todo"},
    "sidebar.collapse_tooltip":    {"it": "Comprimi tutto",  "en": "Collapse all",  "de": "Alle einklappen","fr": "Tout réduire",   "es": "Contraer todo"},
    "sidebar.no_group":            {"it": "  (senza gruppo)","en": "  (no group)",  "de": "  (keine Gruppe)","fr": "  (sans groupe)","es": "  (sin grupo)"},
    "sidebar.count":               {"it": "   {sessions} sessioni  ·  {groups} gruppi", "en": "   {sessions} sessions  ·  {groups} groups", "de": "   {sessions} Sitzungen  ·  {groups} Gruppen", "fr": "   {sessions} sessions  ·  {groups} groupes", "es": "   {sessions} sesiones  ·  {groups} grupos"},

    # ── Tab ───────────────────────────────────────────────────────────────────
    "tab.welcome":           {"it": "🏠 Benvenuto",  "en": "🏠 Welcome",  "de": "🏠 Willkommen","fr": "🏠 Bienvenue",  "es": "🏠 Bienvenido"},
    "tab.guide":             {"it": "📖 Guida",      "en": "📖 Guide",    "de": "📖 Handbuch",  "fr": "📖 Guide",      "es": "📖 Guía"},
    "tab.local":             {"it": " Locale",       "en": " Local",      "de": " Lokal",       "fr": " Local",        "es": " Local"},
    "tab.move_to_other":     {"it": "⇄  Sposta nell'altro pannello", "en": "⇄  Move to other panel", "de": "⇄  In das andere Panel verschieben", "fr": "⇄  Déplacer vers l'autre panneau", "es": "⇄  Mover al otro panel"},
    "tab.export_commands":   {"it": "📄  Esporta comandi.sh…", "en": "📄  Export commands.sh…", "de": "📄  Befehle.sh exportieren…", "fr": "📄  Exporter commandes.sh…", "es": "📄  Exportar comandos.sh…"},
    "tab.close":             {"it": "✖  Chiudi tab", "en": "✖  Close tab", "de": "✖  Tab schließen", "fr": "✖  Fermer l'onglet", "es": "✖  Cerrar pestaña"},
    "tab.close_confirm_title": {"it": "Chiudi tab",  "en": "Close tab",   "de": "Tab schließen","fr": "Fermer l'onglet","es": "Cerrar pestaña"},
    "tab.close_confirm_msg":   {"it": "Chiudere la sessione '{name}'?", "en": "Close session '{name}'?", "de": "Sitzung '{name}' schließen?", "fr": "Fermer la session '{name}' ?", "es": "¿Cerrar la sesión '{name}'?"},
    "tab.open_ft_here":        {"it": "📂  Apri SFTP/FTP qui…", "en": "📂  Open SFTP/FTP here…", "de": "📂  SFTP/FTP hier öffnen…", "fr": "📂  Ouvrir SFTP/FTP ici…", "es": "📂  Abrir SFTP/FTP aquí…"},

    # ── Pannello sessioni (menu contestuale) ──────────────────────────────────
    "panel.connect":        {"it": "▶  Connetti",   "en": "▶  Connect",    "de": "▶  Verbinden",    "fr": "▶  Connecter",  "es": "▶  Conectar"},
    "panel.edit":           {"it": "✏  Modifica",   "en": "✏  Edit",       "de": "✏  Bearbeiten",   "fr": "✏  Modifier",   "es": "✏  Editar"},
    "panel.duplicate":      {"it": "📋  Duplica",   "en": "📋  Duplicate", "de": "📋  Duplizieren", "fr": "📋  Dupliquer",  "es": "📋  Duplicar"},
    "panel.copy_command":   {"it": "📋  Copia comando", "en": "📋  Copy command", "de": "📋  Befehl kopieren", "fr": "📋  Copier la commande", "es": "📋  Copiar comando"},
    "panel.export_sh":      {"it": "📄  Esporta apri-connessione.sh…", "en": "📄  Export open-connection.sh…", "de": "📄  Verbindung.sh exportieren…", "fr": "📄  Exporter ouvrir-connexion.sh…", "es": "📄  Exportar abrir-conexión.sh…"},
    "panel.check_reach":    {"it": "🌐  Verifica raggiungibilità…", "en": "🌐  Check reachability…", "de": "🌐  Erreichbarkeit prüfen…", "fr": "🌐  Vérifier la disponibilité…", "es": "🌐  Verificar accesibilidad…"},
    "panel.delete":         {"it": "🗑  Elimina",   "en": "🗑  Delete",    "de": "🗑  Löschen",     "fr": "🗑  Supprimer",  "es": "🗑  Eliminar"},
    "panel.macros":         {"it": "⚡  Macro",     "en": "⚡  Macros",    "de": "⚡  Makros",      "fr": "⚡  Macros",     "es": "⚡  Macros"},
    "panel.delete_confirm": {"it": "Eliminare la sessione «{name}»?", "en": "Delete session «{name}»?", "de": "Sitzung «{name}» löschen?", "fr": "Supprimer la session «{name}» ?", "es": "¿Eliminar la sesión «{name}»?"},
    "panel.open_ft_here":   {"it": "📂  Apri SFTP/FTP qui…", "en": "📂  Open SFTP/FTP here…", "de": "📂  SFTP/FTP hier öffnen…", "fr": "📂  Ouvrir SFTP/FTP ici…", "es": "📂  Abrir SFTP/FTP aquí…"},

    # ── Dialog Apri SFTP/FTP da sessione esistente ────────────────────────────
    "dlg_ft.title":    {"it": "Apri connessione file", "en": "Open file connection", "de": "Dateiverbindung öffnen", "fr": "Ouvrir connexion fichier", "es": "Abrir conexión de archivos"},
    "dlg_ft.protocol": {"it": "Protocollo", "en": "Protocol", "de": "Protokoll", "fr": "Protocole", "es": "Protocolo"},
    "dlg_ft.host":     {"it": "Host", "en": "Host", "de": "Host", "fr": "Hôte", "es": "Host"},
    "dlg_ft.port":     {"it": "Porta", "en": "Port", "de": "Port", "fr": "Port", "es": "Puerto"},
    "dlg_ft.user":     {"it": "Utente", "en": "User", "de": "Benutzer", "fr": "Utilisateur", "es": "Usuario"},
    "dlg_ft.password": {"it": "Password", "en": "Password", "de": "Passwort", "fr": "Mot de passe", "es": "Contraseña"},
    "dlg_ft.pkey":     {"it": "Chiave privata", "en": "Private key", "de": "Privater Schlüssel", "fr": "Clé privée", "es": "Clave privada"},
    "dlg_ft.pkey_browse": {"it": "Sfoglia…", "en": "Browse…", "de": "Durchsuchen…", "fr": "Parcourir…", "es": "Examinar…"},

    # ── Terminale (VTE) ───────────────────────────────────────────────────────
    "terminal.session_ended":      {"it": "  ✖  Sessione terminata — clicca 'Riconnetti' o chiudi il tab", "en": "  ✖  Session ended — click 'Reconnect' or close the tab", "de": "  ✖  Sitzung beendet — 'Neu verbinden' klicken oder Tab schließen", "fr": "  ✖  Session terminée — cliquez sur 'Reconnecter' ou fermez l'onglet", "es": "  ✖  Sesión terminada — haz clic en 'Reconectar' o cierra la pestaña"},
    "terminal.reconnect":          {"it": "🔄  Riconnetti", "en": "🔄  Reconnect", "de": "🔄  Neu verbinden", "fr": "🔄  Reconnecter", "es": "🔄  Reconectar"},
    "terminal.vte_missing":        {"it": "VTE non trovato. Installa gir1.2-vte-2.91", "en": "VTE not found. Install gir1.2-vte-2.91", "de": "VTE nicht gefunden. Installiere gir1.2-vte-2.91", "fr": "VTE introuvable. Installez gir1.2-vte-2.91", "es": "VTE no encontrado. Instala gir1.2-vte-2.91"},
    "terminal.deps_missing":       {"it": "Dipendenze mancanti", "en": "Missing dependencies", "de": "Fehlende Abhängigkeiten", "fr": "Dépendances manquantes", "es": "Dependencias faltantes"},
    "terminal.clipboard_unavail":  {"it": "Clipboard non disponibile", "en": "Clipboard unavailable", "de": "Zwischenablage nicht verfügbar", "fr": "Presse-papiers indisponible", "es": "Portapapeles no disponible"},

    # ── Impostazioni ──────────────────────────────────────────────────────────
    "settings.title":   {"it": "Impostazioni PCM", "en": "PCM Settings", "de": "PCM-Einstellungen", "fr": "Paramètres PCM", "es": "Configuración PCM"},
    "settings.header":  {"it": "  ⚙  Impostazioni Globali", "en": "  ⚙  Global Settings", "de": "  ⚙  Globale Einstellungen", "fr": "  ⚙  Paramètres globaux", "es": "  ⚙  Configuración global"},
    "settings.tab.general":   {"it": "🏠 Generale",    "en": "🏠 General",    "de": "🏠 Allgemein",  "fr": "🏠 Général",    "es": "🏠 General"},
    "settings.tab.terminal":  {"it": "⌨ Terminale",    "en": "⌨ Terminal",    "de": "⌨ Terminal",    "fr": "⌨ Terminal",    "es": "⌨ Terminal"},
    "settings.tab.ssh":       {"it": "🔐 SSH",          "en": "🔐 SSH",         "de": "🔐 SSH",         "fr": "🔐 SSH",         "es": "🔐 SSH"},
    "settings.tab.shortcuts": {"it": "⌨ Scorciatoie", "en": "⌨ Shortcuts",   "de": "⌨ Tastenkürzel","fr": "⌨ Raccourcis",  "es": "⌨ Atajos"},
    "settings.tab.tools":     {"it": "🔧 Strumenti",   "en": "🔧 Tools",       "de": "🔧 Werkzeuge",   "fr": "🔧 Outils",      "es": "🔧 Herramientas"},

    # ─ Strumenti (VNC/RDP custom tools) ─
    "settings.tools.vnc_group":    {"it": "Strumenti VNC personalizzati",  "en": "Custom VNC tools",  "de": "Benutzerdefinierte VNC-Tools",  "fr": "Outils VNC personnalisés",  "es": "Herramientas VNC personalizadas"},
    "settings.tools.rdp_group":    {"it": "Strumenti RDP personalizzati",  "en": "Custom RDP tools",  "de": "Benutzerdefinierte RDP-Tools",  "fr": "Outils RDP personnalisés",  "es": "Herramientas RDP personalizadas"},
    "settings.tools.col_label":    {"it": "Etichetta",   "en": "Label",    "de": "Bezeichnung", "fr": "Étiquette",  "es": "Etiqueta"},
    "settings.tools.col_path":     {"it": "Percorso",    "en": "Path",     "de": "Pfad",        "fr": "Chemin",     "es": "Ruta"},
    "settings.tools.col_syntax":   {"it": "Sintassi",    "en": "Syntax",   "de": "Syntax",      "fr": "Syntaxe",    "es": "Sintaxis"},
    "settings.tools.add":          {"it": "➕ Aggiungi", "en": "➕ Add",    "de": "➕ Hinzufügen","fr": "➕ Ajouter",  "es": "➕ Añadir"},
    "settings.tools.remove":       {"it": "🗑 Rimuovi",  "en": "🗑 Remove", "de": "🗑 Entfernen", "fr": "🗑 Supprimer","es": "🗑 Eliminar"},
    "settings.tools.note":         {"it": "Nota: usa {host}, {port}, {user} come segnaposto nel campo Sintassi.", "en": "Note: use {host}, {port}, {user} as placeholders in the Syntax field.", "de": "Hinweis: Verwende {host}, {port}, {user} als Platzhalter im Feld Syntax.", "fr": "Remarque : utilisez {host}, {port}, {user} comme espaces réservés dans le champ Syntaxe.", "es": "Nota: usa {host}, {port}, {user} como marcadores en el campo Sintaxis."},
    "settings.tools.dlg_title_vnc":{"it": "Aggiungi strumento VNC",  "en": "Add VNC tool",  "de": "VNC-Tool hinzufügen",  "fr": "Ajouter un outil VNC",  "es": "Añadir herramienta VNC"},
    "settings.tools.dlg_title_rdp":{"it": "Aggiungi strumento RDP",  "en": "Add RDP tool",  "de": "RDP-Tool hinzufügen",  "fr": "Ajouter un outil RDP",  "es": "Añadir herramienta RDP"},
    "settings.tools.lbl_label":    {"it": "Etichetta:",  "en": "Label:",   "de": "Bezeichnung:", "fr": "Étiquette :", "es": "Etiqueta:"},
    "settings.tools.lbl_path":     {"it": "Percorso:",   "en": "Path:",    "de": "Pfad:",        "fr": "Chemin :",    "es": "Ruta:"},
    "settings.tools.lbl_syntax":   {"it": "Sintassi:",   "en": "Syntax:",  "de": "Syntax:",      "fr": "Syntaxe :",   "es": "Sintaxis:"},
    "settings.tools.browse":       {"it": "Sfoglia…",    "en": "Browse…",  "de": "Durchsuchen…", "fr": "Parcourir…",  "es": "Explorar…"},

    # ─ Generale ─
    "settings.general.home_dir":      {"it": "Home directory:", "en": "Home directory:", "de": "Home-Verzeichnis:", "fr": "Répertoire personnel :", "es": "Directorio home:"},
    "settings.general.editor":        {"it": "Editor di testo:", "en": "Text editor:", "de": "Texteditor:", "fr": "Éditeur de texte :", "es": "Editor de texto:"},
    "settings.general.confirm_exit":  {"it": "Chiedi conferma alla chiusura", "en": "Ask for confirmation on exit", "de": "Beim Beenden bestätigen", "fr": "Demander confirmation à la fermeture", "es": "Pedir confirmación al salir"},
    "settings.general.language":      {"it": "Language / Lingua:", "en": "Language / Lingua:", "de": "Language / Lingua:", "fr": "Language / Lingua:", "es": "Language / Lingua:"},
    "settings.general.language_note": {"it": "Riavvia PCM per applicare la lingua.", "en": "Restart PCM to apply the language.", "de": "PCM neu starten, um die Sprache zu übernehmen.", "fr": "Redémarrez PCM pour appliquer la langue.", "es": "Reinicia PCM para aplicar el idioma."},

    # ─ Terminale ─
    "settings.terminal.default_theme": {"it": "Tema predefinito:", "en": "Default theme:", "de": "Standarddesign:", "fr": "Thème par défaut :", "es": "Tema predeterminado:"},
    "settings.terminal.default_font":  {"it": "Font predefinito:", "en": "Default font:", "de": "Standardschrift:", "fr": "Police par défaut :", "es": "Fuente predeterminada:"},
    "settings.terminal.font_size":     {"it": "Dimensione font:", "en": "Font size:", "de": "Schriftgröße:", "fr": "Taille de police :", "es": "Tamaño de fuente:"},
    "settings.terminal.scrollback":           {"it": "Righe scrollback:", "en": "Scrollback lines:", "de": "Rückblatt-Zeilen:", "fr": "Lignes de défilement :", "es": "Líneas de desplazamiento:"},
    "settings.terminal.infinite_scrollback":  {"it": "Scrollback illimitato", "en": "Unlimited scrollback", "de": "Unbegrenztes Scrollback", "fr": "Défilement illimité", "es": "Desplazamiento ilimitado"},
    "settings.terminal.paste_right":   {"it": "Incolla con tasto destro", "en": "Paste with right-click", "de": "Mit Rechtsklick einfügen", "fr": "Coller avec clic droit", "es": "Pegar con clic derecho"},
    "settings.terminal.confirm_close": {"it": "Conferma chiusura tab con processo attivo", "en": "Confirm tab close with active process", "de": "Tab-Schließen mit aktivem Prozess bestätigen", "fr": "Confirmer la fermeture d'un onglet avec un processus actif", "es": "Confirmar cierre de pestaña con proceso activo"},
    "settings.terminal.warn_paste":    {"it": "Avverti prima di incollare più righe", "en": "Warn before pasting multiple lines", "de": "Vor dem Einfügen mehrerer Zeilen warnen", "fr": "Avertir avant de coller plusieurs lignes", "es": "Advertir antes de pegar varias líneas"},
    "settings.terminal.log_output":    {"it": "Registra output terminale su file", "en": "Log terminal output to file", "de": "Terminal-Ausgabe in Datei protokollieren", "fr": "Enregistrer la sortie du terminal dans un fichier", "es": "Registrar salida del terminal en archivo"},
    "settings.terminal.log_dir":       {"it": "Cartella log:", "en": "Log folder:", "de": "Log-Ordner:", "fr": "Dossier de logs :", "es": "Carpeta de logs:"},

    # ─ SSH ─
    "settings.ssh.keepalive": {"it": "Keepalive interval:", "en": "Keepalive interval:", "de": "Keepalive-Intervall:", "fr": "Intervalle keepalive :", "es": "Intervalo keepalive:"},
    "settings.ssh.strict":    {"it": "StrictHostKeyChecking (consigliato: disabilitato per lab)", "en": "StrictHostKeyChecking (recommended: disabled for lab)", "de": "StrictHostKeyChecking (empfohlen: für Labor deaktiviert)", "fr": "StrictHostKeyChecking (recommandé : désactivé pour lab)", "es": "StrictHostKeyChecking (recomendado: deshabilitado para lab)"},
    "settings.ssh.sftp_auto": {"it": "Apri browser SFTP automaticamente per sessioni SSH", "en": "Automatically open SFTP browser for SSH sessions", "de": "SFTP-Browser für SSH-Sitzungen automatisch öffnen", "fr": "Ouvrir automatiquement le navigateur SFTP pour les sessions SSH", "es": "Abrir automáticamente el navegador SFTP para sesiones SSH"},

    # ─ Scorciatoie ─
    "settings.shortcuts.new_terminal":    {"it": "Nuovo terminale locale", "en": "New local terminal", "de": "Neues lokales Terminal", "fr": "Nouveau terminal local", "es": "Nuevo terminal local"},
    "settings.shortcuts.close_tab":       {"it": "Chiudi tab", "en": "Close tab", "de": "Tab schließen", "fr": "Fermer l'onglet", "es": "Cerrar pestaña"},
    "settings.shortcuts.prev_tab":        {"it": "Tab precedente", "en": "Previous tab", "de": "Vorheriger Tab", "fr": "Onglet précédent", "es": "Pestaña anterior"},
    "settings.shortcuts.next_tab":        {"it": "Tab successivo", "en": "Next tab", "de": "Nächster Tab", "fr": "Onglet suivant", "es": "Pestaña siguiente"},
    "settings.shortcuts.new_session":     {"it": "Nuova sessione remota", "en": "New remote session", "de": "Neue Fernsitzung", "fr": "Nouvelle session distante", "es": "Nueva sesión remota"},
    "settings.shortcuts.toggle_sidebar":  {"it": "Mostra/nascondi sidebar", "en": "Show/hide sidebar", "de": "Seitenleiste ein-/ausblenden", "fr": "Afficher/masquer la barre latérale", "es": "Mostrar/ocultar barra lateral"},
    "settings.shortcuts.find":            {"it": "Cerca nel terminale", "en": "Find in terminal", "de": "Im Terminal suchen", "fr": "Rechercher dans le terminal", "es": "Buscar en el terminal"},
    "settings.shortcuts.fullscreen":      {"it": "Schermo intero", "en": "Fullscreen", "de": "Vollbild", "fr": "Plein écran", "es": "Pantalla completa"},
    "settings.shortcuts.note":            {"it": "Nota: le scorciatoie sono applicate al riavvio dell'applicazione.", "en": "Note: shortcuts are applied on application restart.", "de": "Hinweis: Tastenkürzel werden beim Neustart der Anwendung übernommen.", "fr": "Remarque : les raccourcis sont appliqués au redémarrage de l'application.", "es": "Nota: los atajos se aplican al reiniciar la aplicación."},
    "settings.saved": {"it": "Impostazioni salvate", "en": "Settings saved", "de": "Einstellungen gespeichert", "fr": "Paramètres enregistrés", "es": "Configuración guardada"},

    # ── Chiusura app ──────────────────────────────────────────────────────────
    "close.title":           {"it": "Chiudi PCM",    "en": "Close PCM",    "de": "PCM schließen",  "fr": "Fermer PCM",   "es": "Cerrar PCM"},
    "close.active_sessions": {"it": "Ci sono <b>{n}</b> sessione/i attive.", "en": "There are <b>{n}</b> active session(s).", "de": "Es gibt <b>{n}</b> aktive Sitzung(en).", "fr": "Il y a <b>{n}</b> session(s) active(s).", "es": "Hay <b>{n}</b> sesión/sesiones activa(s)."},
    "close.what_to_do":      {"it": "Cosa vuoi fare?", "en": "What do you want to do?", "de": "Was möchten Sie tun?", "fr": "Que voulez-vous faire ?", "es": "¿Qué deseas hacer?"},
    "close.minimize_tray":   {"it": "🔽  Minimizza nel tray", "en": "🔽  Minimize to tray", "de": "🔽  In Taskleiste minimieren", "fr": "🔽  Réduire dans la barre des tâches", "es": "🔽  Minimizar en la bandeja"},
    "close.close_all_btn":   {"it": "✖  Chiudi e termina tutto", "en": "✖  Close and terminate all", "de": "✖  Schließen und alles beenden", "fr": "✖  Fermer et tout terminer", "es": "✖  Cerrar y terminar todo"},
    "close.cancel":          {"it": "Annulla", "en": "Cancel", "de": "Abbrechen", "fr": "Annuler", "es": "Cancelar"},
    "close.dialog":          {"it": "Chiudi",  "en": "Close",  "de": "Schließen", "fr": "Fermer",  "es": "Cerrar"},
    "close.confirm_msg":     {"it": "Vuoi chiudere tutto e terminare PCM?", "en": "Do you want to close everything and quit PCM?", "de": "Möchten Sie alles schließen und PCM beenden?", "fr": "Voulez-vous tout fermer et quitter PCM ?", "es": "¿Deseas cerrar todo y salir de PCM?"},
    "close.close_btn":       {"it": "✖  Chiudi tutto", "en": "✖  Close all", "de": "✖  Alles schließen", "fr": "✖  Tout fermer", "es": "✖  Cerrar todo"},
    "tray.running_msg":      {"it": "PCM continua in background. Doppio clic sull'icona per riaprire.", "en": "PCM continues in background. Double-click the icon to reopen.", "de": "PCM läuft im Hintergrund. Doppelklicken Sie auf das Symbol.", "fr": "PCM continue en arrière-plan. Double-cliquez sur l'icône pour rouvrir.", "es": "PCM continúa en segundo plano. Doble clic en el icono para abrir de nuevo."},

    # ── Tray ──────────────────────────────────────────────────────────────────
    "tray.show":                {"it": "🖥  Mostra PCM",     "en": "🖥  Show PCM",       "de": "🖥  PCM anzeigen",      "fr": "🖥  Afficher PCM",       "es": "🖥  Mostrar PCM"},
    "tray.connect_to":          {"it": "⚡  Connetti a…",   "en": "⚡  Connect to…",    "de": "⚡  Verbinden mit…",    "fr": "⚡  Se connecter à…",    "es": "⚡  Conectar a…"},
    "tray.new_session":         {"it": "➕  Nuova sessione", "en": "➕  New session",     "de": "➕  Neue Sitzung",      "fr": "➕  Nouvelle session",    "es": "➕  Nueva sesión"},
    "tray.local_terminal":      {"it": "⌨  Terminale locale","en": "⌨  Local terminal",  "de": "⌨  Lokales Terminal",  "fr": "⌨  Terminal local",      "es": "⌨  Terminal local"},
    "tray.quit":                {"it": "✖  Esci",            "en": "✖  Quit",             "de": "✖  Beenden",           "fr": "✖  Quitter",              "es": "✖  Salir"},
    "tray.no_sessions":         {"it": "(nessuna sessione)", "en": "(no sessions)",        "de": "(keine Sitzungen)",    "fr": "(aucune session)",         "es": "(sin sesiones)"},
    "tray.more_sessions":       {"it": "... e altre {n} sessioni (apri PCM)", "en": "... and {n} more sessions (open PCM)", "de": "... und {n} weitere Sitzungen (PCM öffnen)", "fr": "... et {n} autres sessions (ouvrir PCM)", "es": "... y {n} sesiones más (abrir PCM)"},
    "tray.session_ended_title": {"it": "PCM — Sessione terminata", "en": "PCM — Session ended", "de": "PCM — Sitzung beendet", "fr": "PCM — Session terminée", "es": "PCM — Sesión terminada"},
    "tray.session_ended_msg":   {"it": "La sessione '{name}' si è disconnessa.", "en": "Session '{name}' has disconnected.", "de": "Sitzung '{name}' wurde getrennt.", "fr": "La session '{name}' s'est déconnectée.", "es": "La sesión '{name}' se ha desconectado."},

    # ── Multi-exec ────────────────────────────────────────────────────────────
    "multiexec.title":           {"it": "⚡ Multi-exec — Invia comando a più sessioni", "en": "⚡ Multi-exec — Send command to multiple sessions", "de": "⚡ Multi-exec — Befehl an mehrere Sitzungen senden", "fr": "⚡ Multi-exec — Envoyer une commande à plusieurs sessions", "es": "⚡ Multi-exec — Enviar comando a varias sesiones"},
    "multiexec.select_sessions": {"it": "Seleziona le sessioni destinatarie:", "en": "Select target sessions:", "de": "Zielsitzungen auswählen:", "fr": "Sélectionnez les sessions cibles :", "es": "Selecciona las sesiones destino:"},
    "multiexec.command":         {"it": "Comando da inviare:", "en": "Command to send:", "de": "Zu sendender Befehl:", "fr": "Commande à envoyer :", "es": "Comando a enviar:"},
    "multiexec.auto_enter":      {"it": "Invia Enter automaticamente dopo il comando", "en": "Automatically send Enter after the command", "de": "Enter nach dem Befehl automatisch senden", "fr": "Envoyer automatiquement Entrée après la commande", "es": "Enviar Enter automáticamente después del comando"},
    "multiexec.send_btn":        {"it": "⚡ Invia", "en": "⚡ Send", "de": "⚡ Senden", "fr": "⚡ Envoyer", "es": "⚡ Enviar"},
    "multiexec.no_sessions":     {"it": "Nessuna sessione attiva.", "en": "No active sessions.", "de": "Keine aktiven Sitzungen.", "fr": "Aucune session active.", "es": "Ninguna sesión activa."},
    "multiexec.sent":            {"it": "Multi-exec: comando inviato a {n} sessioni", "en": "Multi-exec: command sent to {n} sessions", "de": "Multi-exec: Befehl an {n} Sitzungen gesendet", "fr": "Multi-exec : commande envoyée à {n} sessions", "es": "Multi-exec: comando enviado a {n} sesiones"},

    # ── Variabili globali ─────────────────────────────────────────────────────
    "variables.title":     {"it": "📦 Variabili globali PCM", "en": "📦 PCM global variables", "de": "📦 Globale PCM-Variablen", "fr": "📦 Variables globales PCM", "es": "📦 Variables globales PCM"},
    "variables.col_name":  {"it": "Nome variabile", "en": "Variable name", "de": "Variablenname", "fr": "Nom de variable", "es": "Nombre de variable"},
    "variables.col_value": {"it": "Valore", "en": "Value", "de": "Wert", "fr": "Valeur", "es": "Valor"},
    "variables.add":       {"it": "➕ Aggiungi", "en": "➕ Add", "de": "➕ Hinzufügen", "fr": "➕ Ajouter", "es": "➕ Agregar"},
    "variables.delete":    {"it": "🗑 Elimina",  "en": "🗑 Delete", "de": "🗑 Löschen", "fr": "🗑 Supprimer", "es": "🗑 Eliminar"},
    "variables.saved":     {"it": "Variabili globali salvate ({n})", "en": "Global variables saved ({n})", "de": "Globale Variablen gespeichert ({n})", "fr": "Variables globales enregistrées ({n})", "es": "Variables globales guardadas ({n})"},

    # ── Errori generici ───────────────────────────────────────────────────────
    "error.title":            {"it": "Errore",   "en": "Error",   "de": "Fehler",   "fr": "Erreur",   "es": "Error"},
    "error.cannot_build_cmd": {"it": "Impossibile costruire il comando per questa sessione.", "en": "Cannot build the command for this session.", "de": "Befehl für diese Sitzung kann nicht erstellt werden.", "fr": "Impossible de construire la commande pour cette session.", "es": "No se puede construir el comando para esta sesión."},
    "error.tunnel":           {"it": "Errore tunnel", "en": "Tunnel error", "de": "Tunnel-Fehler", "fr": "Erreur tunnel", "es": "Error de túnel"},
    "error.import":           {"it": "Errore importazione", "en": "Import error", "de": "Importfehler", "fr": "Erreur d'importation", "es": "Error de importación"},
    "error.export":           {"it": "Errore esportazione", "en": "Export error", "de": "Exportfehler", "fr": "Erreur d'exportation", "es": "Error de exportación"},

    # ── Macro ─────────────────────────────────────────────────────────────────
    "macro.no_active_session": {"it": "Nessuna sessione attiva per '{host}'.\nComando: {cmd}", "en": "No active session for '{host}'.\nCommand: {cmd}", "de": "Keine aktive Sitzung für '{host}'.\nBefehl: {cmd}", "fr": "Aucune session active pour '{host}'.\nCommande : {cmd}", "es": "No hay sesión activa para '{host}'.\nComando: {cmd}"},
    "macro.sent":              {"it": "Macro inviata: {cmd}", "en": "Macro sent: {cmd}", "de": "Makro gesendet: {cmd}", "fr": "Macro envoyée : {cmd}", "es": "Macro enviada: {cmd}"},

    # ── Modalità protetta ─────────────────────────────────────────────────────
    "protected.active":    {"it": "🔒 ATTIVA",       "en": "🔒 ACTIVE",    "de": "🔒 AKTIV",       "fr": "🔒 ACTIVE",    "es": "🔒 ACTIVO"},
    "protected.inactive":  {"it": "🔓 disattivata",  "en": "🔓 disabled",  "de": "🔓 deaktiviert", "fr": "🔓 désactivée","es": "🔓 desactivado"},
    "protected.status":    {"it": "Modalità protetta {state}", "en": "Protected mode {state}", "de": "Geschützter Modus {state}", "fr": "Mode protégé {state}", "es": "Modo protegido {state}"},
    "protected.indicator": {"it": "  🔒 Modalità protetta  ", "en": "  🔒 Protected mode  ", "de": "  🔒 Geschützter Modus  ", "fr": "  🔒 Mode protégé  ", "es": "  🔒 Modo protegido  "},

    # ── Import / Export ───────────────────────────────────────────────────────
    "import.done":             {"it": "Importate {n} sessioni", "en": "{n} sessions imported", "de": "{n} Sitzungen importiert", "fr": "{n} sessions importées", "es": "{n} sesiones importadas"},
    "import.conflicts_title":  {"it": "Conflitti trovati", "en": "Conflicts found", "de": "Konflikte gefunden", "fr": "Conflits trouvés", "es": "Conflictos encontrados"},
    "import.conflicts_msg":    {"it": "Le seguenti sessioni esistono già:\n\n{names}\n\nSovrascrivi?", "en": "The following sessions already exist:\n\n{names}\n\nOverwrite?", "de": "Die folgenden Sitzungen sind bereits vorhanden:\n\n{names}\n\nÜberschreiben?", "fr": "Les sessions suivantes existent déjà :\n\n{names}\n\nÉcraser ?", "es": "Las siguientes sesiones ya existen:\n\n{names}\n\n¿Sobrescribir?"},
    "export.done_title":       {"it": "Esportazione completata", "en": "Export complete", "de": "Export abgeschlossen", "fr": "Exportation terminée", "es": "Exportación completada"},
    "export.done_msg":         {"it": "Esportate {n} sessioni in:\n{path}", "en": "Exported {n} sessions to:\n{path}", "de": "{n} Sitzungen exportiert nach:\n{path}", "fr": "{n} sessions exportées dans :\n{path}", "es": "{n} sesiones exportadas en:\n{path}"},
    "export.done_status":      {"it": "Sessioni esportate: {path}", "en": "Sessions exported: {path}", "de": "Sitzungen exportiert: {path}", "fr": "Sessions exportées : {path}", "es": "Sesiones exportadas: {path}"},

    # ── Import da app esterna ─────────────────────────────────────────────────
    "import.app.no_connections": {"it": "Nessuna connessione trovata.", "en": "No connections found.", "de": "Keine Verbindungen gefunden.", "fr": "Aucune connexion trouvée.", "es": "No se encontraron conexiones."},
    "import.app.confirm_msg":    {"it": "Importare e unire a PCM?", "en": "Import and merge into PCM?", "de": "In PCM importieren und zusammenführen?", "fr": "Importer et fusionner dans PCM ?", "es": "¿Importar y combinar en PCM?"},
    "import.app.added":          {"it": "Aggiunte <b>{n}</b> connessioni al pannello sessioni.", "en": "Added <b>{n}</b> connections to the session panel.", "de": "<b>{n}</b> Verbindungen zum Sitzungspanel hinzugefügt.", "fr": "<b>{n}</b> connexions ajoutées au panneau de sessions.", "es": "<b>{n}</b> conexiones añadidas al panel de sesiones."},
    "import.app.module_missing": {"it": "Modulo importer.py non trovato.\nAssicurati che importer.py sia nella stessa cartella di PCM.py.", "en": "Module importer.py not found.\nMake sure importer.py is in the same folder as PCM.py.", "de": "Modul importer.py nicht gefunden.\nStelle sicher, dass importer.py im selben Ordner wie PCM.py ist.", "fr": "Module importer.py introuvable.\nAssurez-vous qu'importer.py se trouve dans le même dossier que PCM.py.", "es": "Módulo importer.py no encontrado.\nAsegúrate de que importer.py esté en la misma carpeta que PCM.py."},
    "import.app.title_done":     {"it": "Importazione completata", "en": "Import complete", "de": "Import abgeschlossen", "fr": "Importation terminée", "es": "Importación completada"},

    # ── Dipendenze ────────────────────────────────────────────────────────────
    "deps.title":        {"it": "Dipendenze PCM", "en": "PCM Dependencies", "de": "PCM-Abhängigkeiten", "fr": "Dépendances PCM", "es": "Dependencias PCM"},
    "deps.install_hint": {"it": "\n\nInstalla i mancanti con il gestore pacchetti della tua distribuzione.", "en": "\n\nInstall missing ones with your distribution's package manager.", "de": "\n\nInstalliere fehlende mit dem Paketmanager deiner Distribution.", "fr": "\n\nInstallez les manquants avec le gestionnaire de paquets de votre distribution.", "es": "\n\nInstala los faltantes con el gestor de paquetes de tu distribución."},

    # ── Connessione sessione ──────────────────────────────────────────────────
    "session.connected":               {"it": "Connesso: {name}", "en": "Connected: {name}", "de": "Verbunden: {name}", "fr": "Connecté : {name}", "es": "Conectado: {name}"},
    "session.connection_failed_sftp":  {"it": "Connessione SFTP fallita", "en": "SFTP connection failed", "de": "SFTP-Verbindung fehlgeschlagen", "fr": "Échec de la connexion SFTP", "es": "Error de conexión SFTP"},
    "session.connection_failed_ftp":   {"it": "Connessione FTP fallita", "en": "FTP connection failed", "de": "FTP-Verbindung fehlgeschlagen", "fr": "Échec de la connexion FTP", "es": "Error de conexión FTP"},
    "session.status.started":          {"it": "Avviato: {name} ({proto})", "en": "Started: {name} ({proto})", "de": "Gestartet: {name} ({proto})", "fr": "Démarré : {name} ({proto})", "es": "Iniciado: {name} ({proto})"},
    "session.status.vnc_starting":     {"it": "Avvio VNC integrato: {name}...", "en": "Starting embedded VNC: {name}...", "de": "Eingebettetes VNC wird gestartet: {name}...", "fr": "Démarrage VNC intégré : {name}...", "es": "Iniciando VNC integrado: {name}..."},
    "session.status.opened_fm_ftp":    {"it": "Aperto file manager FTP: {name}", "en": "Opened FTP file manager: {name}", "de": "FTP-Dateimanager geöffnet: {name}", "fr": "Gestionnaire de fichiers FTP ouvert : {name}", "es": "Gestor de archivos FTP abierto: {name}"},
    "session.status.opened_ftp_ext":   {"it": "Aperto terminale FTP esterno: {name}", "en": "Opened external FTP terminal: {name}", "de": "Externes FTP-Terminal geöffnet: {name}", "fr": "Terminal FTP externe ouvert : {name}", "es": "Terminal FTP externo abierto: {name}"},
    "session.status.opened_ext":       {"it": "Aperto terminale esterno: {name}", "en": "Opened external terminal: {name}", "de": "Externes Terminal geöffnet: {name}", "fr": "Terminal externe ouvert : {name}", "es": "Terminal externo abierto: {name}"},
    "session.status.opened_fm_sftp":   {"it": "Aperto file manager SFTP: {name}", "en": "Opened SFTP file manager: {name}", "de": "SFTP-Dateimanager geöffnet: {name}", "fr": "Gestionnaire de fichiers SFTP ouvert : {name}", "es": "Gestor de archivos SFTP abierto: {name}"},
    "session.status.opened_sftp_ext":  {"it": "Aperto terminale SFTP esterno: {name}", "en": "Opened external SFTP terminal: {name}", "de": "Externes SFTP-Terminal geöffnet: {name}", "fr": "Terminal SFTP externe ouvert : {name}", "es": "Terminal SFTP externo abierto: {name}"},

    # ── Tunnel ────────────────────────────────────────────────────────────────
    "tunnel.started":      {"it": "Tunnel '{name}' avviato in background.\n\nComando:\n{cmd}\n\nPID: {pid}", "en": "Tunnel '{name}' started in background.\n\nCommand:\n{cmd}\n\nPID: {pid}", "de": "Tunnel '{name}' im Hintergrund gestartet.\n\nBefehl:\n{cmd}\n\nPID: {pid}", "fr": "Tunnel '{name}' démarré en arrière-plan.\n\nCommande :\n{cmd}\n\nPID : {pid}", "es": "Túnel '{name}' iniciado en segundo plano.\n\nComando:\n{cmd}\n\nPID: {pid}"},
    "tunnel.active_status":{"it": "Tunnel attivo: {name} (PID {pid})", "en": "Tunnel active: {name} (PID {pid})", "de": "Tunnel aktiv: {name} (PID {pid})", "fr": "Tunnel actif : {name} (PID {pid})", "es": "Túnel activo: {name} (PID {pid})"},

    # ── Guida ─────────────────────────────────────────────────────────────────
    "guide.file_missing": {"it": "File pcm_help.html non trovato nella cartella di PCM.", "en": "File pcm_help.html not found in the PCM folder.", "de": "Datei pcm_help.html nicht im PCM-Ordner gefunden.", "fr": "Fichier pcm_help.html introuvable dans le dossier PCM.", "es": "Archivo pcm_help.html no encontrado en la carpeta de PCM."},

    # ── Esporta comandi.sh ────────────────────────────────────────────────────
    "export_cmd.not_terminal":   {"it": "Il tab selezionato non è una sessione terminale.", "en": "The selected tab is not a terminal session.", "de": "Der ausgewählte Tab ist keine Terminal-Sitzung.", "fr": "L'onglet sélectionné n'est pas une session terminal.", "es": "La pestaña seleccionada no es una sesión de terminal."},
    "export_cmd.no_log_title":   {"it": "Esporta comandi.sh — Log non abilitato", "en": "Export commands.sh — Log not enabled", "de": "Befehle.sh exportieren — Log nicht aktiviert", "fr": "Exporter commandes.sh — Journal non activé", "es": "Exportar comandos.sh — Log no habilitado"},
    "export_cmd.no_log_text":    {"it": "<b>Il log della sessione non è abilitato.</b><br><br>Per poter esportare tutti i comandi digitati in console, abilita il log nel profilo della sessione:", "en": "<b>Session logging is not enabled.</b><br><br>To export all commands typed in the console, enable logging in the session profile:", "de": "<b>Die Sitzungsprotokollierung ist nicht aktiviert.</b><br><br>Um alle in der Konsole eingegebenen Befehle zu exportieren, aktiviere die Protokollierung im Sitzungsprofil:", "fr": "<b>La journalisation de la session n'est pas activée.</b><br><br>Pour exporter toutes les commandes saisies dans la console, activez la journalisation dans le profil de session :", "es": "<b>El registro de sesión no está habilitado.</b><br><br>Para exportar todos los comandos escritos en la consola, habilita el registro en el perfil de sesión:"},
    "export_cmd.no_log_info":    {"it": "1. Tasto destro sulla sessione nel pannello → Modifica\n2. Tab Terminale\n3. Spunta 'Registra output su file'\n4. Imposta la cartella log\n5. Riconnetti la sessione\n\nSenza log, sono disponibili solo i comandi inviati tramite macro e multi-exec.", "en": "1. Right-click the session in the panel → Edit\n2. Terminal tab\n3. Check 'Log output to file'\n4. Set the log folder\n5. Reconnect the session\n\nWithout log, only commands sent via macro and multi-exec are available.", "de": "1. Rechtsklick auf die Sitzung im Panel → Bearbeiten\n2. Terminal-Tab\n3. 'Ausgabe in Datei protokollieren' aktivieren\n4. Log-Ordner festlegen\n5. Sitzung neu verbinden\n\nOhne Log sind nur Befehle verfügbar, die über Makros und Multi-exec gesendet wurden.", "fr": "1. Clic droit sur la session dans le panneau → Modifier\n2. Onglet Terminal\n3. Cocher 'Enregistrer la sortie dans un fichier'\n4. Définir le dossier de logs\n5. Reconnecter la session\n\nSans journal, seules les commandes envoyées via macro et multi-exec sont disponibles.", "es": "1. Clic derecho en la sesión del panel → Editar\n2. Pestaña Terminal\n3. Marcar 'Registrar salida en archivo'\n4. Establecer la carpeta de logs\n5. Reconectar la sesión\n\nSin log, solo están disponibles los comandos enviados mediante macro y multi-exec."},
    "export_cmd.only_pcm":       {"it": "Esporta solo comandi PCM", "en": "Export PCM commands only", "de": "Nur PCM-Befehle exportieren", "fr": "Exporter uniquement les commandes PCM", "es": "Exportar solo comandos PCM"},
    "export_cmd.cancel":         {"it": "Annulla", "en": "Cancel", "de": "Abbrechen", "fr": "Annuler", "es": "Cancelar"},
    "export_cmd.title":          {"it": "Esporta comandi.sh — {name}", "en": "Export commands.sh — {name}", "de": "Befehle.sh exportieren — {name}", "fr": "Exporter commandes.sh — {name}", "es": "Exportar comandos.sh — {name}"},
    "export_cmd.no_log_found":   {"it": "Log abilitato ma nessun file trovato in:\n{dir}\n\nIl file viene creato alla connessione. Assicurati che la sessione sia stata avviata dopo aver abilitato il log.", "en": "Logging enabled but no file found in:\n{dir}\n\nThe file is created on connection. Make sure the session was started after enabling logging.", "de": "Protokollierung aktiviert, aber keine Datei gefunden in:\n{dir}\n\nDie Datei wird bei der Verbindung erstellt. Stelle sicher, dass die Sitzung nach der Aktivierung der Protokollierung gestartet wurde.", "fr": "Journalisation activée mais aucun fichier trouvé dans :\n{dir}\n\nLe fichier est créé à la connexion. Assurez-vous que la session a été démarrée après l'activation de la journalisation.", "es": "Registro habilitado pero no se encontró ningún archivo en:\n{dir}\n\nEl archivo se crea al conectar. Asegúrate de que la sesión se inició después de habilitar el registro."},

    # ── Pulsanti generici ─────────────────────────────────────────────────────
    "btn.close":       {"it": "Chiudi",   "en": "Close",  "de": "Schließen", "fr": "Fermer",   "es": "Cerrar"},
    "btn.save":        {"it": "💾  Salva comandi.sh…", "en": "💾  Save commands.sh…", "de": "💾  Befehle.sh speichern…", "fr": "💾  Enregistrer commandes.sh…", "es": "💾  Guardar comandos.sh…"},
    "btn.copy_script": {"it": "📋  Copia script", "en": "📋  Copy script", "de": "📋  Skript kopieren", "fr": "📋  Copier le script", "es": "📋  Copiar script"},
    "btn.copied":      {"it": "✅  Copiato!", "en": "✅  Copied!", "de": "✅  Kopiert!", "fr": "✅  Copié !", "es": "✅  ¡Copiado!"},
    "btn.saved":       {"it": "Script salvato:\n{path}", "en": "Script saved:\n{path}", "de": "Skript gespeichert:\n{path}", "fr": "Script enregistré :\n{path}", "es": "Script guardado:\n{path}"},
    "btn.remove_row":  {"it": "🗑  Rimuovi riga", "en": "🗑  Remove row", "de": "🗑  Zeile entfernen", "fr": "🗑  Supprimer la ligne", "es": "🗑  Eliminar fila"},
    "btn.save_sh":     {"it": "💾  Salva .sh…",  "en": "💾  Save .sh…",  "de": "💾  .sh speichern…", "fr": "💾  Enregistrer .sh…", "es": "💾  Guardar .sh…"},
    "btn.copy_cb":     {"it": "📋  Copia negli appunti", "en": "📋  Copy to clipboard", "de": "📋  In die Zwischenablage kopieren", "fr": "📋  Copier dans le presse-papiers", "es": "📋  Copiar al portapapeles"},
    "btn.saved_exec":  {"it": "Script salvato e reso eseguibile:\n{path}", "en": "Script saved and made executable:\n{path}", "de": "Skript gespeichert und ausführbar gemacht:\n{path}", "fr": "Script enregistré et rendu exécutable :\n{path}", "es": "Script guardado y hecho ejecutable:\n{path}"},

    # ── Dialog verifica raggiungibilità ───────────────────────────────────────
    "reach.title": {"it": "Verifica raggiungibilita — {name}", "en": "Reachability check — {name}", "de": "Erreichbarkeit prüfen — {name}", "fr": "Vérification de disponibilité — {name}", "es": "Verificación de accesibilidad — {name}"},

    # ── Dialog esporta apri-connessione.sh ────────────────────────────────────
    "export_conn.title":    {"it": "📄  Esporta apri-connessione.sh — {name}", "en": "📄  Export open-connection.sh — {name}", "de": "📄  Verbindung.sh exportieren — {name}", "fr": "📄  Exporter ouvrir-connexion.sh — {name}", "es": "📄  Exportar abrir-conexión.sh — {name}"},
    "export_conn.subtitle": {"it": "Script <b>apri-connessione.sh</b> per {name} ({proto} {host}).<br><small>Per esportare i comandi digitati: tasto destro sul <b>tab</b> della sessione → 'Esporta comandi.sh'</small>", "en": "Script <b>open-connection.sh</b> for {name} ({proto} {host}).<br><small>To export typed commands: right-click the session <b>tab</b> → 'Export commands.sh'</small>", "de": "Skript <b>Verbindung.sh</b> für {name} ({proto} {host}).<br><small>Um eingegebene Befehle zu exportieren: Rechtsklick auf den Sitzungs-<b>Tab</b> → 'Befehle.sh exportieren'</small>", "fr": "Script <b>ouvrir-connexion.sh</b> pour {name} ({proto} {host}).<br><small>Pour exporter les commandes saisies : clic droit sur l'<b>onglet</b> de session → 'Exporter commandes.sh'</small>", "es": "Script <b>abrir-conexión.sh</b> para {name} ({proto} {host}).<br><small>Para exportar los comandos escritos: clic derecho en la <b>pestaña</b> de sesión → 'Exportar comandos.sh'</small>"},

    # ── Dialog genera comandi ─────────────────────────────────────────────────
    "cmd_dialog.headers": {"it": ["Timestamp", "Sorgente", "Comando"], "en": ["Timestamp", "Source", "Command"], "de": ["Zeitstempel", "Quelle", "Befehl"], "fr": ["Horodatage", "Source", "Commande"], "es": ["Marca de tiempo", "Origen", "Comando"]},
    "cmd_dialog.no_cmds": {"it": "\n  Nessun comando trovato.\n  Invia comandi tramite macro/multi-exec oppure\n  abilita il log e riconnetti la sessione.\n", "en": "\n  No commands found.\n  Send commands via macro/multi-exec or\n  enable logging and reconnect the session.\n", "de": "\n  Keine Befehle gefunden.\n  Sende Befehle über Makros/Multi-exec oder\n  aktiviere die Protokollierung und verbinde die Sitzung erneut.\n", "fr": "\n  Aucune commande trouvée.\n  Envoyez des commandes via macro/multi-exec ou\n  activez la journalisation et reconnectez la session.\n", "es": "\n  No se encontraron comandos.\n  Envía comandos mediante macro/multi-exec o\n  habilita el registro y reconecta la sesión.\n"},

    # ── Session dialog ────────────────────────────────────────────────────────
    "sd.new_title":       {"it": "Nuova sessione",     "en": "New session",          "de": "Neue Sitzung",        "fr": "Nouvelle session",    "es": "Nueva sesión"},
    "sd.edit_title":      {"it": "Modifica: {name}",   "en": "Edit: {name}",         "de": "Bearbeiten: {name}", "fr": "Modifier : {name}",   "es": "Editar: {name}"},
    "sd.session_name":    {"it": "Nome sessione:",     "en": "Session name:",        "de": "Sitzungsname:",      "fr": "Nom de session :",    "es": "Nombre de sesión:"},
    "sd.session_name_ph": {"it": "es. Server produzione", "en": "e.g. Production server", "de": "z.B. Produktionsserver", "fr": "ex. Serveur de production", "es": "ej. Servidor producción"},
    "sd.group":           {"it": "Gruppo:",            "en": "Group:",               "de": "Gruppe:",            "fr": "Groupe :",            "es": "Grupo:"},
    "sd.group_ph":        {"it": "es. Lavoro, Casa (vuoto = radice)", "en": "e.g. Work, Home (empty = root)", "de": "z.B. Arbeit, Zuhause (leer = Wurzel)", "fr": "ex. Travail, Maison (vide = racine)", "es": "ej. Trabajo, Casa (vacío = raíz)"},
    "sd.protocol":        {"it": "Protocollo:",        "en": "Protocol:",            "de": "Protokoll:",         "fr": "Protocole :",         "es": "Protocolo:"},
    "sd.host":            {"it": "Host:",              "en": "Host:",                "de": "Host:",              "fr": "Hôte :",              "es": "Host:"},
    "sd.host_ph":         {"it": "hostname o IP",     "en": "hostname or IP",       "de": "Hostname oder IP",   "fr": "nom d'hôte ou IP",    "es": "hostname o IP"},
    "sd.port":            {"it": "Porta:",             "en": "Port:",                "de": "Port:",              "fr": "Port :",              "es": "Puerto:"},
    "sd.user":            {"it": "Utente:",            "en": "User:",                "de": "Benutzer:",          "fr": "Utilisateur :",       "es": "Usuario:"},
    "sd.user_ph":         {"it": "nome utente",       "en": "username",             "de": "Benutzername",       "fr": "nom d'utilisateur",   "es": "nombre de usuario"},

    # ─ Tab ─
    "sd.tab.connection": {"it": "Connessione",     "en": "Connection",     "de": "Verbindung",        "fr": "Connexion",        "es": "Conexión"},
    "sd.tab.auth":       {"it": "Autenticazione",  "en": "Authentication", "de": "Authentifizierung", "fr": "Authentification", "es": "Autenticación"},
    "sd.tab.terminal":   {"it": "Terminale",        "en": "Terminal",       "de": "Terminal",          "fr": "Terminal",         "es": "Terminal"},
    "sd.tab.advanced":   {"it": "⚙ Avanzate",       "en": "⚙ Advanced",     "de": "⚙ Erweitert",       "fr": "⚙ Avancé",         "es": "⚙ Avanzado"},
    "sd.tab.notes":      {"it": "📝 Note",           "en": "📝 Notes",        "de": "📝 Notizen",         "fr": "📝 Notes",          "es": "📝 Notas"},
    "sd.tab.macros":     {"it": "⚡ Macro",          "en": "⚡ Macros",       "de": "⚡ Makros",          "fr": "⚡ Macros",         "es": "⚡ Macros"},

    # ─ Gruppi protocollo ─
    "sd.grp.rdp":        {"it": "Opzioni RDP",          "en": "RDP options",         "de": "RDP-Optionen",          "fr": "Options RDP",          "es": "Opciones RDP"},
    "sd.rdp.client":     {"it": "Client RDP:",          "en": "RDP client:",         "de": "RDP-Client:",           "fr": "Client RDP :",         "es": "Cliente RDP:"},
    "sd.rdp.fullscreen": {"it": "Schermo intero",       "en": "Fullscreen",          "de": "Vollbild",              "fr": "Plein écran",          "es": "Pantalla completa"},
    "sd.rdp.clipboard":  {"it": "Condividi clipboard",  "en": "Share clipboard",     "de": "Zwischenablage teilen", "fr": "Partager le presse-papiers", "es": "Compartir portapapeles"},
    "sd.rdp.drives":     {"it": "Condividi cartelle locali", "en": "Share local folders", "de": "Lokale Ordner teilen", "fr": "Partager les dossiers locaux", "es": "Compartir carpetas locales"},
    "sd.rdp.domain":     {"it": "Dominio:", "en": "Domain:", "de": "Domäne:", "fr": "Domaine :", "es": "Dominio:"},
    "sd.rdp.domain_ph":  {"it": "es. MAGGIOLI", "en": "e.g. CORP", "de": "z.B. FIRMA", "fr": "ex. SOCIETE", "es": "ej. EMPRESA"},
    "sd.rdp.auth":       {"it": "Autenticazione:", "en": "Authentication:", "de": "Authentifizierung:", "fr": "Authentification :", "es": "Autenticación:"},
    "sd.rdp.auth_ntlm":  {"it": "NTLM (veloce, senza Kerberos)", "en": "NTLM (fast, no Kerberos)", "de": "NTLM (schnell, kein Kerberos)", "fr": "NTLM (rapide, sans Kerberos)", "es": "NTLM (rápido, sin Kerberos)"},
    "sd.rdp.auth_kerberos": {"it": "Kerberos + NTLM (standard Active Directory)", "en": "Kerberos + NTLM (standard Active Directory)", "de": "Kerberos + NTLM (Standard Active Directory)", "fr": "Kerberos + NTLM (Active Directory standard)", "es": "Kerberos + NTLM (Active Directory estándar)"},
    "sd.rdp.auth_tooltip":  {"it": "NTLM: connessione rapida se il server Kerberos non è raggiungibile dalla rete Linux. Kerberos+NTLM: autenticazione AD standard, può impiegare 60+ secondi se il KDC non risponde.", "en": "NTLM: fast connection when the Kerberos server (KDC) is not reachable from Linux. Kerberos+NTLM: standard AD authentication, may take 60+ seconds if KDC does not respond.", "de": "NTLM: Schnelle Verbindung wenn Kerberos-Server (KDC) von Linux nicht erreichbar. Kerberos+NTLM: Standard-AD-Authentifizierung, kann 60+ Sekunden dauern.", "fr": "NTLM: connexion rapide si le serveur Kerberos n'est pas accessible depuis Linux. Kerberos+NTLM: authentification AD standard, peut prendre 60+ secondes.", "es": "NTLM: conexión rápida si el servidor Kerberos no es accesible desde Linux. Kerberos+NTLM: autenticación AD estándar, puede tardar 60+ segundos."},
    "sd.grp.rdp_open":   {"it": "Modalità apertura RDP", "en": "RDP open mode", "de": "RDP-Öffnungsmodus", "fr": "Mode ouverture RDP", "es": "Modo apertura RDP"},
    "sd.rdp.open_mode":  {"it": "Modalità:", "en": "Mode:", "de": "Modus:", "fr": "Mode :", "es": "Modo:"},
    "sd.rdp.open_ext":   {"it": "Finestra esterna", "en": "External window", "de": "Externes Fenster", "fr": "Fenêtre externe", "es": "Ventana externa"},
    "sd.rdp.open_int":   {"it": "Pannello interno",  "en": "Internal panel",  "de": "Internes Panel",   "fr": "Panneau interne",  "es": "Panel interno"},
    "sd.rdp.embed_v2_warn":      {"it": "Il pannello interno richiede xfreerdp3 (FreeRDP 3.x). Con xfreerdp v2 usa la finestra esterna.", "en": "Internal panel requires xfreerdp3 (FreeRDP 3.x). With xfreerdp v2 use external window.", "de": "Internes Panel erfordert xfreerdp3 (FreeRDP 3.x). Mit xfreerdp v2 externes Fenster verwenden.", "fr": "Le panneau interne nécessite xfreerdp3 (FreeRDP 3.x). Avec xfreerdp v2 utilisez la fenêtre externe.", "es": "El panel interno requiere xfreerdp3 (FreeRDP 3.x). Con xfreerdp v2 usa la ventana externa."},
    "sd.rdp.embed_rdesktop_warn": {"it": "rdesktop non supporta il pannello interno. Usa xfreerdp3.", "en": "rdesktop does not support internal panel. Use xfreerdp3.", "de": "rdesktop unterstützt kein internes Panel. Verwende xfreerdp3.", "fr": "rdesktop ne supporte pas le panneau interne. Utilisez xfreerdp3.", "es": "rdesktop no soporta el panel interno. Usa xfreerdp3."},

    "sd.grp.vnc":         {"it": "Opzioni VNC",          "en": "VNC options",          "de": "VNC-Optionen",          "fr": "Options VNC",           "es": "Opciones VNC"},
    "sd.vnc.integrated":  {"it": "Integra VNC in una scheda di PCM", "en": "Embed VNC in a PCM tab", "de": "VNC in einen PCM-Tab integrieren", "fr": "Intégrer VNC dans un onglet PCM", "es": "Integrar VNC en una pestaña de PCM"},
    "sd.vnc.client":      {"it": "Client VNC esterno:",  "en": "External VNC client:", "de": "Externer VNC-Client:",  "fr": "Client VNC externe :",  "es": "Cliente VNC externo:"},
    "sd.vnc.color":       {"it": "Profondità colore:",   "en": "Color depth:",         "de": "Farbtiefe:",            "fr": "Profondeur de couleur :","es": "Profundidad de color:"},
    "sd.vnc.quality":     {"it": "Qualità:",             "en": "Quality:",             "de": "Qualität:",             "fr": "Qualité :",             "es": "Calidad:"},

    "sd.grp.ftp":    {"it": "Opzioni FTP / FTPS",  "en": "FTP / FTPS options",  "de": "FTP / FTPS-Optionen",  "fr": "Options FTP / FTPS",   "es": "Opciones FTP / FTPS"},
    "sd.ftp.tls":    {"it": "Usa FTPS (TLS esplicito — porta 21, AUTH TLS)", "en": "Use FTPS (explicit TLS — port 21, AUTH TLS)", "de": "FTPS verwenden (explizites TLS — Port 21, AUTH TLS)", "fr": "Utiliser FTPS (TLS explicite — port 21, AUTH TLS)", "es": "Usar FTPS (TLS explícito — puerto 21, AUTH TLS)"},
    "sd.ftp.passive":{"it": "Modalità passiva (PASV) — consigliata dietro NAT/firewall", "en": "Passive mode (PASV) — recommended behind NAT/firewall", "de": "Passivmodus (PASV) — empfohlen hinter NAT/Firewall", "fr": "Mode passif (PASV) — recommandé derrière NAT/pare-feu", "es": "Modo pasivo (PASV) — recomendado detrás de NAT/firewall"},
    "sd.ftp.note":   {"it": "<b>FTP plain</b>: porta 21, nessuna cifratura.<br><b>FTPS</b>: TLS esplicito sulla porta 21 — diverso da SFTP (che usa SSH).<br>La modalità di apertura si configura nel tab <b>Avanzate</b>.", "en": "<b>FTP plain</b>: port 21, no encryption.<br><b>FTPS</b>: explicit TLS on port 21 — different from SFTP (which uses SSH).<br>Open mode is configured in the <b>Advanced</b> tab.", "de": "<b>FTP plain</b>: Port 21, keine Verschlüsselung.<br><b>FTPS</b>: explizites TLS auf Port 21 — anders als SFTP (das SSH verwendet).<br>Der Öffnungsmodus wird im Tab <b>Erweitert</b> konfiguriert.", "fr": "<b>FTP plain</b> : port 21, aucun chiffrement.<br><b>FTPS</b> : TLS explicite sur le port 21 — différent de SFTP (qui utilise SSH).<br>Le mode d'ouverture se configure dans l'onglet <b>Avancé</b>.", "es": "<b>FTP plain</b>: puerto 21, sin cifrado.<br><b>FTPS</b>: TLS explícito en el puerto 21 — diferente de SFTP (que usa SSH).<br>El modo de apertura se configura en la pestaña <b>Avanzado</b>."},

    "sd.grp.tunnel":    {"it": "Configurazione Tunnel SSH", "en": "SSH Tunnel configuration", "de": "SSH-Tunnel-Konfiguration", "fr": "Configuration tunnel SSH", "es": "Configuración túnel SSH"},
    "sd.tunnel.type":   {"it": "Tipo:",          "en": "Type:",       "de": "Typ:",        "fr": "Type :",      "es": "Tipo:"},
    "sd.tunnel.lport":  {"it": "Porta locale:",  "en": "Local port:", "de": "Lokaler Port:", "fr": "Port local :", "es": "Puerto local:"},
    "sd.tunnel.rhost":  {"it": "Host remoto:",   "en": "Remote host:", "de": "Remote-Host:", "fr": "Hôte distant :", "es": "Host remoto:"},
    "sd.tunnel.rhost_ph": {"it": "host destinazione (per -L/-R)", "en": "destination host (for -L/-R)", "de": "Ziel-Host (für -L/-R)", "fr": "hôte destination (pour -L/-R)", "es": "host destino (para -L/-R)"},
    "sd.tunnel.rport":  {"it": "Porta remota:",  "en": "Remote port:", "de": "Remote-Port:", "fr": "Port distant :", "es": "Puerto remoto:"},
    "sd.tunnel.rport_ph": {"it": "porta dest.", "en": "dest. port", "de": "Ziel-Port", "fr": "port dest.", "es": "puerto dest."},

    "sd.grp.serial":      {"it": "Configurazione Seriale", "en": "Serial configuration", "de": "Serielle Konfiguration", "fr": "Configuration série", "es": "Configuración serie"},
    "sd.serial.device":   {"it": "Dispositivo:",  "en": "Device:",    "de": "Gerät:",    "fr": "Périphérique :", "es": "Dispositivo:"},
    "sd.serial.baud":     {"it": "Baud rate:",    "en": "Baud rate:", "de": "Baudrate:", "fr": "Débit :",        "es": "Velocidad en baudios:"},
    "sd.serial.databits": {"it": "Data bits:",    "en": "Data bits:", "de": "Datenbits:", "fr": "Bits de données :", "es": "Bits de datos:"},
    "sd.serial.parity":   {"it": "Parità:",       "en": "Parity:",    "de": "Parität:",   "fr": "Parité :",      "es": "Paridad:"},
    "sd.serial.stopbits": {"it": "Stop bits:",    "en": "Stop bits:", "de": "Stoppbits:", "fr": "Bits d'arrêt :", "es": "Bits de parada:"},

    "sd.grp.wol":       {"it": "Wake-on-LAN",    "en": "Wake-on-LAN", "de": "Wake-on-LAN", "fr": "Wake-on-LAN", "es": "Wake-on-LAN"},
    "sd.wol.enable":    {"it": "Invia magic packet prima di connettersi", "en": "Send magic packet before connecting", "de": "Magic Packet vor dem Verbinden senden", "fr": "Envoyer un magic packet avant de se connecter", "es": "Enviar magic packet antes de conectar"},
    "sd.wol.enable_tip":{"it": "Invia un magic packet UDP (porta 9) all'indirizzo MAC indicato\ne attende che l'host risponda al ping prima di aprire la sessione.", "en": "Sends a UDP magic packet (port 9) to the MAC address\nand waits for the host to respond to ping before opening the session.", "de": "Sendet ein UDP-Magic-Packet (Port 9) an die MAC-Adresse\nund wartet, bis der Host auf Ping antwortet, bevor die Sitzung geöffnet wird.", "fr": "Envoie un magic packet UDP (port 9) à l'adresse MAC\net attend que l'hôte réponde au ping avant d'ouvrir la session.", "es": "Envía un magic packet UDP (puerto 9) a la dirección MAC\ny espera que el host responda al ping antes de abrir la sesión."},
    "sd.wol.mac":       {"it": "Indirizzo MAC:", "en": "MAC address:", "de": "MAC-Adresse:", "fr": "Adresse MAC :", "es": "Dirección MAC:"},
    "sd.wol.wait":      {"it": "Attesa risposta:", "en": "Response wait:", "de": "Antwortwartezeit:", "fr": "Attente réponse :", "es": "Espera respuesta:"},
    "sd.wol.wait_tip":  {"it": "Secondi massimi di attesa che l'host risponda al ping dopo il WoL.", "en": "Maximum seconds to wait for the host to respond to ping after WoL.", "de": "Maximale Sekunden auf Ping-Antwort des Hosts nach WoL warten.", "fr": "Secondes maximales d'attente de réponse ping de l'hôte après WoL.", "es": "Segundos máximos de espera para que el host responda al ping tras WoL."},

    # ─ Tab Autenticazione ─
    "sd.pwd":           {"it": "Password:",       "en": "Password:",      "de": "Passwort:",      "fr": "Mot de passe :",   "es": "Contraseña:"},
    "sd.pwd_ph":        {"it": "lascia vuoto per chiave privata o prompt", "en": "leave empty for private key or prompt", "de": "leer für privaten Schlüssel oder Eingabeaufforderung", "fr": "laisser vide pour clé privée ou invite", "es": "dejar vacío para clave privada o prompt"},
    "sd.pwd_show_tip":  {"it": "Mostra/Nascondi password", "en": "Show/Hide password", "de": "Passwort anzeigen/verbergen", "fr": "Afficher/masquer le mot de passe", "es": "Mostrar/ocultar contraseña"},
    "sd.pkey":          {"it": "Chiave privata:", "en": "Private key:",   "de": "Privater Schlüssel:", "fr": "Clé privée :", "es": "Clave privada:"},
    "sd.pkey_ph":       {"it": "percorso chiave privata (es. ~/.ssh/id_ed25519)", "en": "private key path (e.g. ~/.ssh/id_ed25519)", "de": "Pfad zum privaten Schlüssel (z.B. ~/.ssh/id_ed25519)", "fr": "chemin de la clé privée (ex. ~/.ssh/id_ed25519)", "es": "ruta de clave privada (ej. ~/.ssh/id_ed25519)"},

    "sd.grp.keys":        {"it": "🔑  Gestione chiavi SSH",   "en": "🔑  SSH Key Management",    "de": "🔑  SSH-Schlüsselverwaltung",  "fr": "🔑  Gestion des clés SSH",     "es": "🔑  Gestión de claves SSH"},
    "sd.keys.existing":   {"it": "Chiavi in ~/.ssh:",         "en": "Keys in ~/.ssh:",             "de": "Schlüssel in ~/.ssh:",         "fr": "Clés dans ~/.ssh :",           "es": "Claves en ~/.ssh:"},
    "sd.keys.reload_tip": {"it": "Ricarica lista chiavi",     "en": "Reload key list",             "de": "Schlüsselliste neu laden",     "fr": "Recharger la liste des clés",  "es": "Recargar lista de claves"},
    "sd.keys.none":       {"it": "(nessuna — usa password)",  "en": "(none — use password)",       "de": "(keine — Passwort verwenden)", "fr": "(aucune — utiliser le mot de passe)", "es": "(ninguna — usar contraseña)"},
    "sd.keys.generate":   {"it": "Genera nuova:",             "en": "Generate new:",               "de": "Neu generieren:",              "fr": "Générer nouveau :",            "es": "Generar nueva:"},
    "sd.keys.gen_btn":    {"it": "⚙  Genera",                "en": "⚙  Generate",                "de": "⚙  Generieren",                "fr": "⚙  Générer",                  "es": "⚙  Generar"},
    "sd.keys.gen_tip":    {"it": "Genera una nuova coppia di chiavi SSH", "en": "Generate a new SSH key pair", "de": "Neues SSH-Schlüsselpaar generieren", "fr": "Générer une nouvelle paire de clés SSH", "es": "Generar un nuevo par de claves SSH"},
    "sd.keys.copy_server":{"it": "📤  Copia chiave pubblica sul server", "en": "📤  Copy public key to server", "de": "📤  Öffentlichen Schlüssel auf Server kopieren", "fr": "📤  Copier la clé publique sur le serveur", "es": "📤  Copiar clave pública al servidor"},
    "sd.keys.copy_tip":   {"it": "Esegue ssh-copy-id per copiare la chiave pubblica sul server remoto\nRichiede la password del server (una sola volta)", "en": "Runs ssh-copy-id to copy the public key to the remote server\nRequires the server password (once only)", "de": "Führt ssh-copy-id aus, um den öffentlichen Schlüssel auf den Remote-Server zu kopieren\nErfordert das Server-Passwort (einmalig)", "fr": "Exécute ssh-copy-id pour copier la clé publique sur le serveur distant\nNécessite le mot de passe du serveur (une seule fois)", "es": "Ejecuta ssh-copy-id para copiar la clave pública al servidor remoto\nRequiere la contraseña del servidor (solo una vez)"},
    "sd.keys.show_pub":   {"it": "👁  Mostra pubblica",       "en": "👁  Show public",             "de": "👁  Öffentliche anzeigen",      "fr": "👁  Afficher publique",         "es": "👁  Mostrar pública"},
    "sd.keys.show_pub_tip":{"it": "Mostra il contenuto della chiave pubblica (da copiare manualmente)", "en": "Show the public key content (to copy manually)", "de": "Inhalt des öffentlichen Schlüssels anzeigen (zum manuellen Kopieren)", "fr": "Afficher le contenu de la clé publique (à copier manuellement)", "es": "Mostrar el contenido de la clave pública (para copiar manualmente)"},

    "sd.grp.jump":    {"it": "Jump Host (Bastion)", "en": "Jump Host (Bastion)", "de": "Jump-Host (Bastion)", "fr": "Jump Host (Bastion)", "es": "Jump Host (Bastion)"},
    "sd.jump.info":   {"it": "<b>A cosa serve:</b> un Jump Host è un server intermedio che fa da ponte verso macchine non raggiungibili direttamente.<br>Es: <tt>PC → gateway.azienda.it → server-interno</tt><br><br><b>Come funziona:</b> PCM si connette prima al Jump Host, poi apre automaticamente la connessione al server finale. Equivale a <tt>ssh -J gateway host</tt>.", "en": "<b>Purpose:</b> a Jump Host is an intermediate server that bridges to machines not directly reachable.<br>E.g.: <tt>PC → gateway.company.com → internal-server</tt><br><br><b>How it works:</b> PCM connects first to the Jump Host, then automatically opens the connection to the final server. Equivalent to <tt>ssh -J gateway host</tt>.", "de": "<b>Zweck:</b> Ein Jump-Host ist ein Zwischenserver, der als Brücke zu Maschinen dient, die nicht direkt erreichbar sind.<br>Z.B.: <tt>PC → gateway.firma.de → interner-server</tt><br><br><b>Funktionsweise:</b> PCM verbindet sich zuerst mit dem Jump-Host und öffnet dann automatisch die Verbindung zum Zielserver. Entspricht <tt>ssh -J gateway host</tt>.", "fr": "<b>À quoi ça sert :</b> un Jump Host est un serveur intermédiaire qui fait pont vers des machines non directement accessibles.<br>Ex. : <tt>PC → passerelle.entreprise.fr → serveur-interne</tt><br><br><b>Comment ça marche :</b> PCM se connecte d'abord au Jump Host, puis ouvre automatiquement la connexion au serveur final. Équivaut à <tt>ssh -J passerelle hôte</tt>.", "es": "<b>Para qué sirve:</b> un Jump Host es un servidor intermedio que hace de puente hacia máquinas no accesibles directamente.<br>Ej.: <tt>PC → gateway.empresa.com → servidor-interno</tt><br><br><b>Cómo funciona:</b> PCM se conecta primero al Jump Host y luego abre automáticamente la conexión al servidor final. Equivale a <tt>ssh -J gateway host</tt>."},
    "sd.jump.host":     {"it": "Jump host:",     "en": "Jump host:",     "de": "Jump-Host:",     "fr": "Jump host :",     "es": "Jump host:"},
    "sd.jump.host_ph":  {"it": "gateway.esempio.it", "en": "gateway.example.com", "de": "gateway.beispiel.de", "fr": "passerelle.exemple.fr", "es": "gateway.ejemplo.com"},
    "sd.jump.user":     {"it": "Utente jump:",   "en": "Jump user:",     "de": "Jump-Benutzer:", "fr": "Utilisateur jump :", "es": "Usuario jump:"},
    "sd.jump.user_ph":  {"it": "utente sul gateway (vuoto = stesso utente)", "en": "gateway user (empty = same user)", "de": "Gateway-Benutzer (leer = gleicher Benutzer)", "fr": "utilisateur sur la passerelle (vide = même utilisateur)", "es": "usuario en el gateway (vacío = mismo usuario)"},
    "sd.jump.port":     {"it": "Porta jump:",    "en": "Jump port:",     "de": "Jump-Port:",     "fr": "Port jump :",     "es": "Puerto jump:"},

    # ─ Tab Terminale ─
    "sd.term.theme":        {"it": "Tema:",                "en": "Theme:",              "de": "Design:",             "fr": "Thème :",               "es": "Tema:"},
    "sd.term.font":         {"it": "Font:",                "en": "Font:",               "de": "Schrift:",            "fr": "Police :",              "es": "Fuente:"},
    "sd.term.font_size":    {"it": "Dimensione font:",     "en": "Font size:",          "de": "Schriftgröße:",       "fr": "Taille de police :",    "es": "Tamaño de fuente:"},
    "sd.term.startup_cmd":  {"it": "Comando avvio:",       "en": "Startup command:",    "de": "Startbefehl:",        "fr": "Commande de démarrage :","es": "Comando de inicio:"},
    "sd.term.startup_ph":   {"it": "es. cd /var/log && tail -f syslog", "en": "e.g. cd /var/log && tail -f syslog", "de": "z.B. cd /var/log && tail -f syslog", "fr": "ex. cd /var/log && tail -f syslog", "es": "ej. cd /var/log && tail -f syslog"},
    "sd.term.pre_cmd":      {"it": "Cmd locale pre-connessione:", "en": "Local pre-connection cmd:", "de": "Lokaler Vor-Verbindungs-Befehl:", "fr": "Cmd local pré-connexion :", "es": "Cmd local pre-conexión:"},
    "sd.term.pre_cmd_ph":   {"it": "es. wg-quick up vpn0  oppure  openfortivpn --config=/etc/vpn.conf", "en": "e.g. wg-quick up vpn0  or  openfortivpn --config=/etc/vpn.conf", "de": "z.B. wg-quick up vpn0  oder  openfortivpn --config=/etc/vpn.conf", "fr": "ex. wg-quick up vpn0  ou  openfortivpn --config=/etc/vpn.conf", "es": "ej. wg-quick up vpn0  o  openfortivpn --config=/etc/vpn.conf"},
    "sd.term.pre_cmd_tip":  {"it": "Comando shell locale eseguito PRIMA di aprire la connessione remota.\nUtile per attivare una VPN, montare un volume, ecc.\nLa connessione parte solo se il comando esce con codice 0.", "en": "Local shell command executed BEFORE opening the remote connection.\nUseful to activate a VPN, mount a volume, etc.\nThe connection starts only if the command exits with code 0.", "de": "Lokaler Shell-Befehl, der VOR dem Öffnen der Remote-Verbindung ausgeführt wird.\nNützlich zum Aktivieren eines VPN, Einhängen eines Volumes usw.\nDie Verbindung startet nur, wenn der Befehl mit Code 0 endet.", "fr": "Commande shell locale exécutée AVANT d'ouvrir la connexion distante.\nUtile pour activer un VPN, monter un volume, etc.\nLa connexion démarre uniquement si la commande se termine avec le code 0.", "es": "Comando shell local ejecutado ANTES de abrir la conexión remota.\nÚtil para activar una VPN, montar un volumen, etc.\nLa conexión inicia solo si el comando termina con código 0."},
    "sd.term.timeout":      {"it": "Timeout pre-cmd:",    "en": "Pre-cmd timeout:",    "de": "Vor-Befehl-Timeout:", "fr": "Délai pre-cmd :",       "es": "Timeout pre-cmd:"},
    "sd.term.timeout_sfx":  {"it": " s  (0 = nessun timeout)", "en": " s  (0 = no timeout)", "de": " s  (0 = kein Timeout)", "fr": " s  (0 = aucun délai)", "es": " s  (0 = sin timeout)"},
    "sd.term.timeout_tip":  {"it": "Secondi di attesa massima per il completamento del comando locale.\nSe scade, la connessione viene annullata.", "en": "Maximum seconds to wait for the local command to complete.\nIf it expires, the connection is cancelled.", "de": "Maximale Sekunden auf den Abschluss des lokalen Befehls warten.\nBei Ablauf wird die Verbindung abgebrochen.", "fr": "Secondes d'attente maximale pour l'exécution de la commande locale.\nSi délai dépassé, la connexion est annulée.", "es": "Segundos máximos de espera para que el comando local termine.\nSi expira, la conexión se cancela."},
    "sd.term.sftp_auto":    {"it": "Apri browser SFTP laterale dopo la connessione SSH", "en": "Open side SFTP browser after SSH connection", "de": "Seitliches SFTP-Browser nach SSH-Verbindung öffnen", "fr": "Ouvrir le navigateur SFTP latéral après la connexion SSH", "es": "Abrir navegador SFTP lateral tras la conexión SSH"},
    "sd.term.log":          {"it": "Registra output su file", "en": "Log output to file", "de": "Ausgabe in Datei protokollieren", "fr": "Enregistrer la sortie dans un fichier", "es": "Registrar salida en archivo"},
    "sd.term.log_dir":      {"it": "Cartella log:",       "en": "Log folder:",         "de": "Log-Ordner:",         "fr": "Dossier de logs :",     "es": "Carpeta de logs:"},
    "sd.term.paste_right":  {"it": "Incolla con tasto destro", "en": "Paste with right-click", "de": "Mit Rechtsklick einfügen", "fr": "Coller avec clic droit", "es": "Pegar con clic derecho"},

    # ─ Tab Avanzate ─
    "sd.grp.ssh_adv":     {"it": "Opzioni SSH",           "en": "SSH options",          "de": "SSH-Optionen",           "fr": "Options SSH",           "es": "Opciones SSH"},
    "sd.ssh.x11":         {"it": "X11 Forwarding (-X)",   "en": "X11 Forwarding (-X)",  "de": "X11-Weiterleitung (-X)", "fr": "X11 Forwarding (-X)",   "es": "X11 Forwarding (-X)"},
    "sd.ssh.compression": {"it": "Compressione (-C)",     "en": "Compression (-C)",     "de": "Komprimierung (-C)",     "fr": "Compression (-C)",      "es": "Compresión (-C)"},
    "sd.ssh.keepalive":   {"it": "Keepalive (ServerAliveInterval=60)", "en": "Keepalive (ServerAliveInterval=60)", "de": "Keepalive (ServerAliveInterval=60)", "fr": "Keepalive (ServerAliveInterval=60)", "es": "Keepalive (ServerAliveInterval=60)"},
    "sd.ssh.strict":      {"it": "Strict Host Key Checking", "en": "Strict Host Key Checking", "de": "Strenge Host-Key-Prüfung", "fr": "Vérification stricte de la clé hôte", "es": "Verificación estricta de clave host"},
    "sd.grp.ssh_open":    {"it": "Modalità apertura SSH",  "en": "SSH open mode",        "de": "SSH-Öffnungsmodus",      "fr": "Mode d'ouverture SSH",  "es": "Modo apertura SSH"},
    "sd.grp.sftp_open":   {"it": "Modalità apertura SFTP", "en": "SFTP open mode",       "de": "SFTP-Öffnungsmodus",     "fr": "Mode d'ouverture SFTP", "es": "Modo apertura SFTP"},
    "sd.grp.ftp_open":    {"it": "Modalità apertura FTP",  "en": "FTP open mode",        "de": "FTP-Öffnungsmodus",      "fr": "Mode d'ouverture FTP",  "es": "Modo apertura FTP"},
    "sd.open_with":       {"it": "Apri con:",              "en": "Open with:",           "de": "Öffnen mit:",            "fr": "Ouvrir avec :",         "es": "Abrir con:"},
    "sd.grp.terminal":    {"it": "Terminale",              "en": "Terminal",             "de": "Terminal",               "fr": "Terminal",              "es": "Terminal"},
    "sd.terminal_lbl":    {"it": "Terminale:",             "en": "Terminal:",            "de": "Terminal:",              "fr": "Terminal :",            "es": "Terminal:"},

    # ─ Tab Note e Macro ─
    "sd.notes_ph":     {"it": "Note libere su questa sessione…", "en": "Free notes about this session…", "de": "Freie Notizen zu dieser Sitzung…", "fr": "Notes libres sur cette session…", "es": "Notas libres sobre esta sesión…"},
    "sd.macro.info":   {"it": "Le macro sono comandi inviati al terminale con un clic dal pannello sessioni.<br>Ogni macro ha un <b>nome</b> (etichetta nel menu) e un <b>comando</b> da eseguire.", "en": "Macros are commands sent to the terminal with one click from the session panel.<br>Each macro has a <b>name</b> (menu label) and a <b>command</b> to execute.", "de": "Makros sind Befehle, die mit einem Klick aus dem Sitzungspanel an das Terminal gesendet werden.<br>Jedes Makro hat einen <b>Namen</b> (Menübezeichnung) und einen auszuführenden <b>Befehl</b>.", "fr": "Les macros sont des commandes envoyées au terminal en un clic depuis le panneau de sessions.<br>Chaque macro a un <b>nom</b> (étiquette du menu) et une <b>commande</b> à exécuter.", "es": "Las macros son comandos enviados al terminal con un clic desde el panel de sesiones.<br>Cada macro tiene un <b>nombre</b> (etiqueta del menú) y un <b>comando</b> a ejecutar."},
    "sd.macro.name":   {"it": "Nome:",    "en": "Name:",    "de": "Name:",    "fr": "Nom :",    "es": "Nombre:"},
    "sd.macro.name_ph":{"it": "es. Stato servizi", "en": "e.g. Service status", "de": "z.B. Dienststatus", "fr": "ex. État des services", "es": "ej. Estado servicios"},
    "sd.macro.cmd":    {"it": "Comando:", "en": "Command:", "de": "Befehl:",  "fr": "Commande :", "es": "Comando:"},
    "sd.macro.cmd_ph": {"it": "es. systemctl status nginx", "en": "e.g. systemctl status nginx", "de": "z.B. systemctl status nginx", "fr": "ex. systemctl status nginx", "es": "ej. systemctl status nginx"},
    "sd.macro.add":    {"it": "➕  Aggiungi", "en": "➕  Add",    "de": "➕  Hinzufügen",  "fr": "➕  Ajouter",    "es": "➕  Agregar"},
    "sd.macro.update": {"it": "✏  Aggiorna", "en": "✏  Update",  "de": "✏  Aktualisieren","fr": "✏  Mettre à jour","es": "✏  Actualizar"},
    "sd.macro.delete": {"it": "🗑  Elimina",  "en": "🗑  Delete",  "de": "🗑  Löschen",    "fr": "🗑  Supprimer",  "es": "🗑  Eliminar"},
    "sd.macro.warn":   {"it": "Inserisci nome e comando.", "en": "Enter name and command.", "de": "Name und Befehl eingeben.", "fr": "Entrez un nom et une commande.", "es": "Introduce nombre y comando."},

    # ── Dialogs chiavi SSH ────────────────────────────────────────────────────
    "sd.keygen.title":            {"it": "Nome file chiave", "en": "Key file name", "de": "Schlüsseldateiname", "fr": "Nom du fichier de clé", "es": "Nombre de archivo de clave"},
    "sd.keygen.label":            {"it": "Nome del file chiave (in ~/.ssh/):", "en": "Key file name (in ~/.ssh/):", "de": "Schlüsseldateiname (in ~/.ssh/):", "fr": "Nom du fichier de clé (dans ~/.ssh/) :", "es": "Nombre del archivo de clave (en ~/.ssh/):"},
    "sd.keygen.overwrite":        {"it": "Il file '{path}' esiste già. Sovrascrivere?", "en": "File '{path}' already exists. Overwrite?", "de": "Datei '{path}' existiert bereits. Überschreiben?", "fr": "Le fichier '{path}' existe déjà. Écraser ?", "es": "El archivo '{path}' ya existe. ¿Sobrescribir?"},
    "sd.keygen.passphrase_title": {"it": "Passphrase (opzionale)", "en": "Passphrase (optional)", "de": "Passphrase (optional)", "fr": "Phrase secrète (optionnelle)", "es": "Frase de contraseña (opcional)"},
    "sd.keygen.passphrase_label": {"it": "Passphrase per la chiave (lascia vuoto per nessuna):", "en": "Key passphrase (leave empty for none):", "de": "Schlüssel-Passphrase (leer lassen für keine):", "fr": "Phrase secrète pour la clé (laisser vide pour aucune) :", "es": "Frase de contraseña de la clave (dejar vacío para ninguna):"},
    "sd.keygen.done":             {"it": "Chiave generata", "en": "Key generated", "de": "Schlüssel generiert", "fr": "Clé générée", "es": "Clave generada"},
    "sd.keygen.done_msg":         {"it": "✅ Coppia di chiavi creata:\n\n  Privata: {priv}\n  Pubblica: {pub}\n\nUsa 'Copia chiave pubblica sul server' per installarla sul server remoto.", "en": "✅ Key pair created:\n\n  Private: {priv}\n  Public: {pub}\n\nUse 'Copy public key to server' to install it on the remote server.", "de": "✅ Schlüsselpaar erstellt:\n\n  Privat: {priv}\n  Öffentlich: {pub}\n\nVerwende 'Öffentlichen Schlüssel auf Server kopieren', um ihn auf dem Remote-Server zu installieren.", "fr": "✅ Paire de clés créée :\n\n  Privée : {priv}\n  Publique : {pub}\n\nUtilisez 'Copier la clé publique sur le serveur' pour l'installer sur le serveur distant.", "es": "✅ Par de claves creado:\n\n  Privada: {priv}\n  Pública: {pub}\n\nUsa 'Copiar clave pública al servidor' para instalarla en el servidor remoto."},
    "sd.keygen.missing":          {"it": "ssh-keygen non trovato nel PATH.", "en": "ssh-keygen not found in PATH.", "de": "ssh-keygen nicht im PATH gefunden.", "fr": "ssh-keygen introuvable dans le PATH.", "es": "ssh-keygen no encontrado en el PATH."},
    "sd.keygen.timeout":          {"it": "ssh-keygen ha impiegato troppo. Riprova.", "en": "ssh-keygen took too long. Try again.", "de": "ssh-keygen hat zu lange gedauert. Erneut versuchen.", "fr": "ssh-keygen a pris trop de temps. Réessayez.", "es": "ssh-keygen tardó demasiado. Inténtalo de nuevo."},

    "sd.copykey.title":               {"it": "📤 Copia chiave pubblica sul server", "en": "📤 Copy public key to server", "de": "📤 Öffentlichen Schlüssel auf Server kopieren", "fr": "📤 Copier la clé publique sur le serveur", "es": "📤 Copiar clave pública al servidor"},
    "sd.copykey.content_lbl":         {"it": "Contenuto chiave pubblica (authorized_keys):", "en": "Public key content (authorized_keys):", "de": "Inhalt des öffentlichen Schlüssels (authorized_keys):", "fr": "Contenu de la clé publique (authorized_keys) :", "es": "Contenido de la clave pública (authorized_keys):"},
    "sd.copykey.run":                 {"it": "▶  Esegui ssh-copy-id", "en": "▶  Run ssh-copy-id", "de": "▶  ssh-copy-id ausführen", "fr": "▶  Exécuter ssh-copy-id", "es": "▶  Ejecutar ssh-copy-id"},
    "sd.copykey.manual":              {"it": "📋  Copia testo pubblica", "en": "📋  Copy public key text", "de": "📋  Öffentlichen Schlüsseltext kopieren", "fr": "📋  Copier le texte de la clé publique", "es": "📋  Copiar texto de clave pública"},
    "sd.copykey.copied":              {"it": "Chiave pubblica copiata negli appunti.\n\nIncollala nel file ~/.ssh/authorized_keys del server remoto.", "en": "Public key copied to clipboard.\n\nPaste it into the ~/.ssh/authorized_keys file on the remote server.", "de": "Öffentlicher Schlüssel in die Zwischenablage kopiert.\n\nEinfügen in die Datei ~/.ssh/authorized_keys auf dem Remote-Server.", "fr": "Clé publique copiée dans le presse-papiers.\n\nCollez-la dans le fichier ~/.ssh/authorized_keys du serveur distant.", "es": "Clave pública copiada al portapapeles.\n\nPégala en el archivo ~/.ssh/authorized_keys del servidor remoto."},
    "sd.copykey.missing_sshcopyid":   {"it": "ssh-copy-id non trovato nel PATH.", "en": "ssh-copy-id not found in PATH.", "de": "ssh-copy-id nicht im PATH gefunden.", "fr": "ssh-copy-id introuvable dans le PATH.", "es": "ssh-copy-id no encontrado en el PATH."},
    "sd.copykey.no_key":              {"it": "Seleziona o genera prima una chiave privata.", "en": "Select or generate a private key first.", "de": "Zuerst einen privaten Schlüssel auswählen oder generieren.", "fr": "Sélectionnez ou générez d'abord une clé privée.", "es": "Selecciona o genera primero una clave privada."},
    "sd.copykey.no_pub":              {"it": "Non trovato il file:\n{path}\n\nGenera prima la coppia di chiavi.", "en": "File not found:\n{path}\n\nGenerate the key pair first.", "de": "Datei nicht gefunden:\n{path}\n\nErstelle zuerst das Schlüsselpaar.", "fr": "Fichier introuvable :\n{path}\n\nGénérez d'abord la paire de clés.", "es": "Archivo no encontrado:\n{path}\n\nGenera primero el par de claves."},
    "sd.copykey.no_host":             {"it": "Inserisci l'indirizzo del server nel campo Host.", "en": "Enter the server address in the Host field.", "de": "Serveradresse im Host-Feld eingeben.", "fr": "Entrez l'adresse du serveur dans le champ Hôte.", "es": "Introduce la dirección del servidor en el campo Host."},

    "sd.showpub.title":   {"it": "Chiave pubblica — {name}", "en": "Public key — {name}", "de": "Öffentlicher Schlüssel — {name}", "fr": "Clé publique — {name}", "es": "Clave pública — {name}"},
    "sd.showpub.no_key":  {"it": "Seleziona prima una chiave privata.", "en": "Select a private key first.", "de": "Zuerst einen privaten Schlüssel auswählen.", "fr": "Sélectionnez d'abord une clé privée.", "es": "Selecciona primero una clave privada."},
    "sd.showpub.no_file": {"it": "File non trovato:\n{path}", "en": "File not found:\n{path}", "de": "Datei nicht gefunden:\n{path}", "fr": "Fichier introuvable :\n{path}", "es": "Archivo no encontrado:\n{path}"},
    "sd.showpub.read_err":{"it": "Errore lettura", "en": "Read error", "de": "Lesefehler", "fr": "Erreur de lecture", "es": "Error de lectura"},

    "sd.browse_key": {"it": "Seleziona chiave privata", "en": "Select private key", "de": "Privaten Schlüssel auswählen", "fr": "Sélectionner une clé privée", "es": "Seleccionar clave privada"},
    "sd.browse_log": {"it": "Cartella log", "en": "Log folder", "de": "Log-Ordner", "fr": "Dossier de logs", "es": "Carpeta de logs"},
    "sd.ok":          {"it": "OK",      "en": "OK",     "de": "OK",        "fr": "OK",      "es": "OK"},
    "sd.cancel":      {"it": "Annulla", "en": "Cancel", "de": "Abbrechen", "fr": "Annuler", "es": "Cancelar"},
    "sd.password":     {"it": "Password:",       "en": "Password:",      "de": "Passwort:",      "fr": "Mot de passe :",   "es": "Contraseña:"},
    "sd.private_key":  {"it": "Chiave privata:", "en": "Private key:",   "de": "Privater Schlüssel:", "fr": "Clé privée :", "es": "Clave privada:"},
    "sd.tab.tunnel":   {"it": "Tunnel",          "en": "Tunnel",         "de": "Tunnel",         "fr": "Tunnel",           "es": "Túnel"},
    "sd.grp.ssh_open": {"it": "Apertura SSH:",   "en": "SSH open mode:", "de": "SSH-Öffnung:",   "fr": "Ouverture SSH :",  "es": "Apertura SSH:"},
    "sd.grp.sftp_open":{"it": "Apertura SFTP:",  "en": "SFTP open mode:","de": "SFTP-Öffnung:",  "fr": "Ouverture SFTP :", "es": "Apertura SFTP:"},
    "sd.grp.ftp_open": {"it": "Apertura FTP:",   "en": "FTP open mode:", "de": "FTP-Öffnung:",   "fr": "Ouverture FTP :",  "es": "Apertura FTP:"},
    # Valori combo modalità apertura (indice-based, usati come display)
    "sd.rdp.open_ext":   {"it": "Finestra esterna",   "en": "External window",   "de": "Externes Fenster",   "fr": "Fenêtre externe",   "es": "Ventana externa"},
    "sd.rdp.open_int":   {"it": "Pannello interno",   "en": "Internal panel",    "de": "Internes Panel",     "fr": "Panneau interne",    "es": "Panel interno"},
    "sd.open_int":       {"it": "Browser interno",    "en": "Internal browser",  "de": "Interner Browser",   "fr": "Navigateur interne", "es": "Navegador interno"},
    "sd.open_ext":       {"it": "Terminale esterno",  "en": "External terminal", "de": "Externes Terminal",  "fr": "Terminal externe",   "es": "Terminal externo"},
    "sd.open_int_terminal": {"it": "Terminale interno", "en": "Internal terminal", "de": "Internes Terminal", "fr": "Terminal interne", "es": "Terminal interno"},
    "sd.open_ext_client":   {"it": "Client esterno",          "en": "External client",                       "de": "Externer Client",                  "fr": "Client externe",                        "es": "Cliente externo"},
    "sd.open_browser_ext":  {"it": "Browser esterno (Nemo / Thunar / Dolphin)", "en": "External browser (Nemo / Thunar / Dolphin)", "de": "Externer Dateimanager (Nemo / Thunar / Dolphin)", "fr": "Gestionnaire externe (Nemo / Thunar / Dolphin)", "es": "Gestor externo (Nemo / Thunar / Dolphin)"},
    "sd.sftp.open_term_int":{"it": "Terminale interno (sftp)",  "en": "Internal terminal (sftp)",   "de": "Internes Terminal (sftp)",  "fr": "Terminal interne (sftp)",  "es": "Terminal interno (sftp)"},
    "sd.sftp.open_term_ext":{"it": "Terminale esterno (sftp)",  "en": "External terminal (sftp)",   "de": "Externes Terminal (sftp)",  "fr": "Terminal externe (sftp)",  "es": "Terminal externo (sftp)"},
    "sd.ftp.open_term_int": {"it": "Terminale interno (lftp)",  "en": "Internal terminal (lftp)",   "de": "Internes Terminal (lftp)",  "fr": "Terminal interne (lftp)",  "es": "Terminal interno (lftp)"},
    "sd.ftp.open_term_ext": {"it": "Terminale esterno (lftp)",  "en": "External terminal (lftp)",   "de": "Externes Terminal (lftp)",  "fr": "Terminal externe (lftp)",  "es": "Terminal externo (lftp)"},
    # VNC mode
    "sd.vnc.ext":        {"it": "Client esterno",             "en": "External client",          "de": "Externer Client",          "fr": "Client externe",           "es": "Cliente externo"},
    "sd.vnc.novnc":      {"it": "gtk-vnc integrato",          "en": "Embedded (gtk-vnc)",       "de": "Eingebettet (gtk-vnc)",    "fr": "Intégré (gtk-vnc)",        "es": "Integrado (gtk-vnc)"},
    # VNC color depth
    "sd.vnc.color_32":   {"it": "Truecolor (32 bpp)", "en": "Truecolor (32 bpp)", "de": "Truecolor (32 bpp)", "fr": "Truecolor (32 bpp)", "es": "Truecolor (32 bpp)"},
    "sd.vnc.color_16":   {"it": "High (16 bpp)",      "en": "High (16 bpp)",      "de": "High (16 bpp)",      "fr": "High (16 bpp)",      "es": "High (16 bpp)"},
    "sd.vnc.color_8":    {"it": "Low (8 bpp)",         "en": "Low (8 bpp)",        "de": "Low (8 bpp)",        "fr": "Low (8 bpp)",        "es": "Low (8 bpp)"},
    # VNC quality
    "sd.vnc.q_best":     {"it": "Migliore", "en": "Best",   "de": "Beste",    "fr": "Meilleure", "es": "Mejor"},
    "sd.vnc.q_good":     {"it": "Buona",    "en": "Good",   "de": "Gut",      "fr": "Bonne",     "es": "Buena"},
    "sd.vnc.q_fast":     {"it": "Veloce",   "en": "Fast",   "de": "Schnell",  "fr": "Rapide",    "es": "Rápida"},
    "tab.close_session_tooltip": {"it": "Chiudi la sessione attiva", "en": "Close active session", "de": "Aktive Sitzung schließen", "fr": "Fermer la session active", "es": "Cerrar sesión activa"},
    "crypto.unlock.wrong_master": {"it": "Password master errata.\nLe credenziali resteranno cifrate.", "en": "Wrong master password.\nCredentials will remain encrypted.", "de": "Falsches Masterpasswort.\nAnmeldedaten bleiben verschlüsselt.", "fr": "Mot de passe maître incorrect.\nLes identifiants resteront chiffrés.", "es": "Contraseña maestra incorrecta.\nLas credenciales permanecerán cifradas."},
    "sd.save":        {"it": "Salva",   "en": "Save",   "de": "Speichern","fr": "Enregistrer", "es": "Guardar"},

    # ─ Placeholder password per protocollo ─
    "sd.pwd_ph.ssh":     {"it": "lascia vuoto per chiave privata o prompt interattivo", "en": "leave empty for private key or interactive prompt", "de": "leer für privaten Schlüssel oder interaktive Eingabe", "fr": "laisser vide pour clé privée ou invite interactive", "es": "dejar vacío para clave privada o prompt interactivo"},
    "sd.pwd_ph.ftp":     {"it": "password FTP (lascia vuoto per anonymous)", "en": "FTP password (leave empty for anonymous)", "de": "FTP-Passwort (leer für anonym)", "fr": "mot de passe FTP (vide pour anonyme)", "es": "contraseña FTP (dejar vacío para anónimo)"},
    "sd.pwd_ph.telnet":  {"it": "lascia vuoto per prompt interattivo", "en": "leave empty for interactive prompt", "de": "leer für interaktive Eingabe", "fr": "laisser vide pour invite interactive", "es": "dejar vacío para prompt interactivo"},
    "sd.pwd_ph.rdp":     {"it": "password Windows", "en": "Windows password", "de": "Windows-Passwort", "fr": "mot de passe Windows", "es": "contraseña Windows"},
    "sd.pwd_ph.vnc":     {"it": "password VNC", "en": "VNC password", "de": "VNC-Passwort", "fr": "mot de passe VNC", "es": "contraseña VNC"},
    "sd.pwd_ph.tunnel":  {"it": "lascia vuoto per chiave privata", "en": "leave empty for private key", "de": "leer für privaten Schlüssel", "fr": "laisser vide pour clé privée", "es": "dejar vacío para clave privada"},
    "sd.pwd_ph.default": {"it": "password", "en": "password", "de": "Passwort", "fr": "mot de passe", "es": "contraseña"},

    # ── Cifratura credenziali ─────────────────────────────────────────────────
    "crypto.first_run.title":           {"it": "Primo avvio - Protezione credenziali", "en": "First run - Credential protection", "de": "Erster Start - Anmeldedatenschutz", "fr": "Premier démarrage - Protection des identifiants", "es": "Primer inicio - Protección de credenciales"},
    "crypto.first_run.heading":         {"it": "Vuoi proteggere le tue credenziali?", "en": "Do you want to protect your credentials?", "de": "Möchtest du deine Anmeldedaten schützen?", "fr": "Voulez-vous protéger vos identifiants ?", "es": "¿Deseas proteger tus credenciales?"},
    "crypto.first_run.description":     {"it": "PCM può cifrare utenti e password in connections.json con AES-256. Ad ogni avvio viene chiesta la password master per sbloccare.\n\nSenza cifratura le credenziali restano in chiaro nel JSON.", "en": "PCM can encrypt saved credentials in connections.json using AES-256. At startup the master password will be requested.\n\nWithout encryption, credentials remain in plain text.", "de": "PCM kann Anmeldedaten in connections.json mit AES-256 verschlüsseln. Beim Start wird das Masterpasswort abgefragt.\n\nOhne Verschlüsselung bleiben Daten im Klartext.", "fr": "PCM peut chiffrer les identifiants dans connections.json avec AES-256. Au démarrage le mot de passe maître sera demandé.\n\nSans chiffrement, les identifiants restent en clair.", "es": "PCM puede cifrar credenciales en connections.json con AES-256. Al inicio se pedirá la contraseña maestra.\n\nSin cifrado quedan en texto plano."},
    "crypto.first_run.enable_checkbox": {"it": "Sì, voglio cifrare le credenziali", "en": "Yes, I want to encrypt credentials", "de": "Ja, ich möchte Anmeldedaten verschlüsseln", "fr": "Oui, je veux chiffrer les identifiants", "es": "Sí, quiero cifrar las credenciales"},
    "crypto.first_run.btn_skip":        {"it": "No, lascia in chiaro", "en": "No, keep plain text", "de": "Nein, Klartext behalten", "fr": "Non, garder en clair", "es": "No, mantener en texto plano"},
    "crypto.first_run.btn_ok":          {"it": "Abilita cifratura", "en": "Enable encryption", "de": "Verschlüsselung aktivieren", "fr": "Activer le chiffrement", "es": "Activar cifrado"},
    "crypto.unlock.title":              {"it": "PCM - Sblocco credenziali", "en": "PCM - Unlock credentials", "de": "PCM - Anmeldedaten entsperren", "fr": "PCM - Déverrouillage des identifiants", "es": "PCM - Desbloqueo de credenciales"},
    "crypto.unlock.prompt":             {"it": "Inserisci la password master per sbloccare le credenziali salvate.", "en": "Enter the master password to unlock saved credentials.", "de": "Gib das Masterpasswort ein, um gespeicherte Anmeldedaten zu entsperren.", "fr": "Entrez le mot de passe maître pour déverrouiller les identifiants.", "es": "Introduce la contraseña maestra para desbloquear las credenciales."},
    "crypto.unlock.btn_ok":             {"it": "Sblocca", "en": "Unlock", "de": "Entsperren", "fr": "Déverrouiller", "es": "Desbloquear"},
    "crypto.unlock.btn_exit":           {"it": "Esci", "en": "Exit", "de": "Beenden", "fr": "Quitter", "es": "Salir"},
    "crypto.unlock.wrong_password":     {"it": "Password errata. Tentativi rimanenti: {n}", "en": "Wrong password. Remaining attempts: {n}", "de": "Falsches Passwort. Verbleibende Versuche: {n}", "fr": "Mot de passe incorrect. Tentatives restantes : {n}", "es": "Contraseña incorrecta. Intentos restantes: {n}"},
    "crypto.unlock.too_many_attempts":  {"it": "Troppi tentativi falliti. Riavvia PCM.", "en": "Too many failed attempts. Restart PCM.", "de": "Zu viele fehlgeschlagene Versuche. Starte PCM neu.", "fr": "Trop de tentatives échouées. Redémarrez PCM.", "es": "Demasiados intentos fallidos. Reinicia PCM."},
    "crypto.password_label":            {"it": "Password master:", "en": "Master password:", "de": "Masterpasswort:", "fr": "Mot de passe maître :", "es": "Contraseña maestra:"},
    "crypto.password_ph":               {"it": "minimo 6 caratteri", "en": "minimum 6 characters", "de": "mindestens 6 Zeichen", "fr": "minimum 6 caractères", "es": "mínimo 6 caracteres"},
    "crypto.password_confirm_label":    {"it": "Conferma password:", "en": "Confirm password:", "de": "Passwort bestätigen:", "fr": "Confirmer le mot de passe :", "es": "Confirmar contraseña:"},
    "crypto.password_confirm_ph":       {"it": "ripeti la password", "en": "repeat the password", "de": "Passwort wiederholen", "fr": "répétez le mot de passe", "es": "repite la contraseña"},
    "crypto.err_too_short":             {"it": "La password deve essere di almeno 6 caratteri.", "en": "Password must be at least 6 characters.", "de": "Das Passwort muss mindestens 6 Zeichen haben.", "fr": "Le mot de passe doit comporter au moins 6 caractères.", "es": "La contraseña debe tener al menos 6 caracteres."},
    "crypto.err_mismatch":              {"it": "Le password non corrispondono.", "en": "Passwords do not match.", "de": "Passwörter stimmen nicht überein.", "fr": "Les mots de passe ne correspondent pas.", "es": "Las contraseñas no coinciden."},
    "crypto.err_wrong_old":             {"it": "Password attuale errata.", "en": "Current password is incorrect.", "de": "Aktuelles Passwort falsch.", "fr": "Mot de passe actuel incorrect.", "es": "Contraseña actual incorrecta."},
    "crypto.manage.title":              {"it": "Gestione password globale", "en": "Global password management", "de": "Globale Passwortverwaltung", "fr": "Gestion du mot de passe global", "es": "Gestión de contraseña global"},
    "crypto.manage.status_label":       {"it": "Stato cifratura", "en": "Encryption status", "de": "Verschlüsselungsstatus", "fr": "État du chiffrement", "es": "Estado del cifrado"},
    "crypto.manage.status_on":          {"it": "Attiva",    "en": "Active",   "de": "Aktiv",   "fr": "Active",   "es": "Activa"},
    "crypto.manage.status_off":         {"it": "Non attiva","en": "Inactive", "de": "Inaktiv", "fr": "Inactive", "es": "Inactiva"},
    "crypto.manage.tab_enable":         {"it": "Abilita cifratura",  "en": "Enable encryption",  "de": "Verschlüsselung aktivieren",   "fr": "Activer le chiffrement",  "es": "Activar cifrado"},
    "crypto.manage.tab_change":         {"it": "Cambia password",    "en": "Change password",    "de": "Passwort ändern",              "fr": "Changer le mot de passe", "es": "Cambiar contraseña"},
    "crypto.manage.tab_disable":        {"it": "Disabilita cifratura","en": "Disable encryption","de": "Verschlüsselung deaktivieren", "fr": "Désactiver le chiffrement","es": "Desactivar cifrado"},
    "crypto.manage.old_password":       {"it": "Password attuale:", "en": "Current password:", "de": "Aktuelles Passwort:", "fr": "Mot de passe actuel :", "es": "Contraseña actual:"},
    "crypto.manage.change_hint":        {"it": "Tutti i profili verranno ricifrati con la nuova password.", "en": "All profiles will be re-encrypted with the new password.", "de": "Alle Profile werden mit dem neuen Passwort neu verschlüsselt.", "fr": "Tous les profils seront rechiffrés avec le nouveau mot de passe.", "es": "Todos los perfiles se recifran con la nueva contraseña."},
    "crypto.manage.disable_warning":    {"it": "Attenzione: le credenziali verranno salvate in chiaro nel file JSON.", "en": "Warning: credentials will be saved in plain text in the JSON file.", "de": "Achtung: Anmeldedaten werden im Klartext in der JSON-Datei gespeichert.", "fr": "Attention : les identifiants seront enregistrés en clair dans le JSON.", "es": "Atención: las credenciales se guardarán en texto plano en el JSON."},
    "crypto.manage.btn_enable":         {"it": "Abilita e cifra",    "en": "Enable and encrypt",  "de": "Aktivieren und verschlüsseln",  "fr": "Activer et chiffrer",    "es": "Activar y cifrar"},
    "crypto.manage.btn_change":         {"it": "Cambia password",    "en": "Change password",     "de": "Passwort ändern",               "fr": "Changer le mot de passe","es": "Cambiar contraseña"},
    "crypto.manage.btn_disable":        {"it": "Disabilita e decifra","en": "Disable and decrypt","de": "Deaktivieren und entschlüsseln","fr": "Désactiver et déchiffrer","es": "Desactivar y descifrar"},
    "crypto.manage.success_enable":     {"it": "Cifratura abilitata. Credenziali protette.", "en": "Encryption enabled. Credentials protected.", "de": "Verschlüsselung aktiviert. Anmeldedaten geschützt.", "fr": "Chiffrement activé. Identifiants protégés.", "es": "Cifrado activado. Credenciales protegidas."},
    "crypto.manage.success_change":     {"it": "Password cambiata. Profili ricifrati.", "en": "Password changed. Profiles re-encrypted.", "de": "Passwort geändert. Profile neu verschlüsselt.", "fr": "Mot de passe changé. Profils rechiffrés.", "es": "Contraseña cambiada. Perfiles recifrados."},
    "crypto.manage.success_disable":    {"it": "Cifratura disabilitata. Credenziali salvate in chiaro.", "en": "Encryption disabled. Credentials saved in plain text.", "de": "Verschlüsselung deaktiviert. Anmeldedaten im Klartext.", "fr": "Chiffrement désactivé. Identifiants enregistrés en clair.", "es": "Cifrado desactivado. Credenciales en texto plano."},

    # ── RDP embedded (messaggi runtime) ──────────────────────────────────────
    "rdp.embed.waiting":               {"it": "Connessione RDP in corso...", "en": "Connecting RDP...", "de": "RDP-Verbindung wird aufgebaut...", "fr": "Connexion RDP en cours...", "es": "Conectando RDP..."},
    "rdp.embed.client_missing":        {"it": "Client RDP '{client}' non trovato nel PATH.", "en": "RDP client '{client}' not found in PATH.", "de": "RDP-Client '{client}' nicht im PATH gefunden.", "fr": "Client RDP '{client}' introuvable dans le PATH.", "es": "Cliente RDP '{client}' no encontrado en el PATH."},
    "rdp.embed.reparent_failed":       {"it": "Impossibile agganciare la finestra RDP al pannello. Controlla che xdotool sia installato.", "en": "Could not attach RDP window to panel. Check that xdotool is installed.", "de": "RDP-Fenster konnte nicht am Panel befestigt werden. Prüfen ob xdotool installiert ist.", "fr": "Impossible d'attacher la fenêtre RDP au panneau. Vérifiez que xdotool est installé.", "es": "No se pudo adjuntar la ventana RDP al panel. Comprueba que xdotool esté instalado."},
    "rdp.embed.wayland_no_xwayland":   {"it": "Wayland rilevato senza XWayland (DISPLAY non impostato). Usa Finestra esterna per RDP.", "en": "Wayland detected without XWayland (DISPLAY not set). Use External window for RDP.", "de": "Wayland ohne XWayland erkannt (DISPLAY nicht gesetzt). Verwende Externes Fenster.", "fr": "Wayland détecté sans XWayland (DISPLAY non défini). Utilisez Fenêtre externe.", "es": "Wayland detectado sin XWayland (DISPLAY no definido). Usa Ventana externa."},
    "rdp.embed.wid_error":             {"it": "Impossibile ottenere il WID X11 del container. Usa Finestra esterna.", "en": "Cannot obtain X11 WID for container. Use External window.", "de": "X11-WID des Containers nicht ermittelbar. Verwende Externes Fenster.", "fr": "Impossible d'obtenir le WID X11 du conteneur. Utilisez Fenêtre externe.", "es": "No se puede obtener el WID X11 del contenedor. Usa Ventana externa."},
    "rdp.embed.rdesktop_no_embed":     {"it": "rdesktop non supporta il pannello interno. Cambia client in xfreerdp o xfreerdp3.", "en": "rdesktop does not support embedded panel. Switch client to xfreerdp or xfreerdp3.", "de": "rdesktop unterstützt kein eingebettetes Panel. Wechsle zu xfreerdp oder xfreerdp3.", "fr": "rdesktop ne supporte pas le panneau intégré. Changez de client vers xfreerdp.", "es": "rdesktop no soporta panel interno. Cambia el cliente a xfreerdp o xfreerdp3."},
    "rdp.embed.failed_suggest":        {"it": "{client} non si è connesso. Prova a cambiare client in '{alt}' nelle impostazioni della sessione.", "en": "{client} failed to connect. Try switching client to '{alt}' in session settings.", "de": "{client} konnte keine Verbindung herstellen. Versuche den Client in den Sitzungseinstellungen auf '{alt}' zu wechseln.", "fr": "{client} n'a pas pu se connecter. Essayez de changer le client en '{alt}' dans les paramètres de session.", "es": "{client} no pudo conectarse. Prueba a cambiar el cliente a '{alt}' en la configuración de sesión."},
    "rdp.embed.failed_noalt":          {"it": "{client} non si è connesso. Verifica credenziali, host e porta.", "en": "{client} failed to connect. Check credentials, host and port.", "de": "{client} konnte keine Verbindung herstellen. Anmeldedaten, Host und Port prüfen.", "fr": "{client} n'a pas pu se connecter. Vérifiez les identifiants, l'hôte et le port.", "es": "{client} no pudo conectarse. Verifica credenciales, host y puerto."},
# ── Gestione Cifratura (Dialog) ──────────────────────────────
    "crypto.custom.title":          {"it": "Gestione Cifratura", "en": "Encryption Management", "de": "Verschlüsselungsverwaltung", "fr": "Gestion du Chiffrement", "es": "Gestión de Cifrado"},
    "crypto.custom.disabled_title": {"it": "Cifratura Disabilitata", "en": "Encryption Disabled", "de": "Verschlüsselung Deaktiviert", "fr": "Chiffrement Désactivé", "es": "Cifrado Desactivado"},
    "crypto.custom.disabled_desc":  {"it": "Inserisci una password per proteggere le tue connessioni.", "en": "Enter a password to protect your connections.", "de": "Geben Sie ein Passwort ein, um Ihre Verbindungen zu schützen.", "fr": "Entrez un mot de passe pour protéger vos connexions.", "es": "Introduce una contraseña para proteger tus conexiones."},
    "crypto.custom.new_pwd_ph":     {"it": "Nuova Password Master", "en": "New Master Password", "de": "Neues Masterpasswort", "fr": "Nouveau mot de passe maître", "es": "Nueva Contraseña Maestra"},
    "crypto.custom.active_title":   {"it": "Cifratura Attiva", "en": "Encryption Active", "de": "Verschlüsselung Aktiv", "fr": "Chiffrement Actif", "es": "Cifrado Activo"},
    "crypto.custom.active_desc":    {"it": "Inserisci la vecchia password per disabilitarla, o compila anche la nuova per cambiarla.", "en": "Enter the old password to disable it, or also fill in the new one to change it.", "de": "Geben Sie das alte Passwort ein, um es zu deaktivieren, oder füllen Sie auch das neue aus, um es zu ändern.", "fr": "Entrez l'ancien mot de passe pour le désactiver, ou remplissez également le nouveau pour le modifier.", "es": "Introduce la contraseña antigua para desactivarla, o completa también la nueva para cambiarla."},
    "crypto.custom.old_pwd_ph":     {"it": "Vecchia Password Master", "en": "Old Master Password", "de": "Altes Masterpasswort", "fr": "Ancien mot de passe maître", "es": "Antigua Contraseña Maestra"},
    "crypto.custom.new_pwd_opt_ph": {"it": "Nuova Password (lascia vuoto per rimuovere)", "en": "New Password (leave empty to remove)", "de": "Neues Passwort (leer lassen zum Entfernen)", "fr": "Nouveau mot de passe (laisser vide pour supprimer)", "es": "Nueva Contraseña (dejar vacío para eliminar)"},
    "crypto.custom.btn_apply":      {"it": "Applica", "en": "Apply", "de": "Anwenden", "fr": "Appliquer", "es": "Aplicar"},
    "crypto.custom.success":        {"it": "Successo", "en": "Success", "de": "Erfolg", "fr": "Succès", "es": "Éxito"},
    "crypto.custom.error":          {"it": "Errore", "en": "Error", "de": "Fehler", "fr": "Erreur", "es": "Error"},
    "crypto.custom.msg_enabled":    {"it": "Cifratura attivata con successo!", "en": "Encryption successfully enabled!", "de": "Verschlüsselung erfolgreich aktiviert!", "fr": "Chiffrement activé avec succès !", "es": "¡Cifrado activado con éxito!"},
    "crypto.custom.msg_changed":    {"it": "Password cambiata con successo!", "en": "Password successfully changed!", "de": "Passwort erfolgreich geändert!", "fr": "Mot de passe modifié avec succès !", "es": "¡Contraseña cambiada con éxito!"},
    "crypto.custom.msg_wrong_old":  {"it": "La vecchia password è errata!", "en": "The old password is incorrect!", "de": "Das alte Passwort ist falsch!", "fr": "L'ancien mot de passe est incorrect !", "es": "¡La contraseña antigua es incorrecta!"},
    "crypto.custom.msg_disabled":   {"it": "Cifratura disabilitata. Dati in chiaro.", "en": "Encryption disabled. Plaintext data.", "de": "Verschlüsselung deaktiviert. Klartextdaten.", "fr": "Chiffrement désactivé. Données en clair.", "es": "Cifrado desactivado. Datos en texto plano."},
    "crypto.custom.msg_wrong":      {"it": "Password errata!", "en": "Incorrect password!", "de": "Falsches Passwort!", "fr": "Mot de passe incorrect !", "es": "¡Contraseña incorrecta!"},

    # ── deps_dialog ──────────────────────────────────────────────────────────
    "deps.title":           {"it": "Configurazione Dipendenze",          "en": "Dependencies Configuration",      "de": "Abhängigkeitskonfiguration",     "fr": "Configuration des dépendances",    "es": "Configuración de dependencias"},
    "deps.col_status":      {"it": "Status",                             "en": "Status",                          "de": "Status",                          "fr": "Statut",                           "es": "Estado"},
    "deps.col_component":   {"it": "Componente",                         "en": "Component",                       "de": "Komponente",                      "fr": "Composant",                        "es": "Componente"},
    "deps.col_default":     {"it": "Comando Default",                    "en": "Default Command",                 "de": "Standardbefehl",                  "fr": "Commande par défaut",              "es": "Comando predeterminado"},
    "deps.col_custom":      {"it": "Percorso Personalizzato (doppio clic)","en": "Custom Path (double-click)",    "de": "Benutzerdefinierter Pfad (Doppelklick)","fr": "Chemin personnalisé (double-clic)","es": "Ruta personalizada (doble clic)"},
    "deps.col_custom_qt":   {"it": "Percorso Personalizzato",            "en": "Custom Path",                     "de": "Benutzerdefinierter Pfad",        "fr": "Chemin personnalisé",              "es": "Ruta personalizada"},
    "deps.btn_browse":      {"it": "📁 Sfoglia...",                      "en": "📁 Browse...",                    "de": "📁 Durchsuchen...",               "fr": "📁 Parcourir...",                  "es": "📁 Explorar..."},
    "deps.btn_reset":       {"it": "🔄 Reset",                           "en": "🔄 Reset",                        "de": "🔄 Zurücksetzen",                 "fr": "🔄 Réinitialiser",                 "es": "🔄 Restablecer"},
    "deps.not_found":       {"it": "Non trovato",                        "en": "Not found",                       "de": "Nicht gefunden",                  "fr": "Introuvable",                      "es": "No encontrado"},
    "deps.browse_title":    {"it": "Seleziona percorso per {tool}",      "en": "Select path for {tool}",          "de": "Pfad für {tool} auswählen",       "fr": "Sélectionnez le chemin pour {tool}","es": "Seleccionar ruta para {tool}"},

    # ── ftp_server_dialog ─────────────────────────────────────────────────────
    "ftp.title":            {"it": "Server FTP locale",                  "en": "Local FTP Server",                "de": "Lokaler FTP-Server",              "fr": "Serveur FTP local",                "es": "Servidor FTP local"},
    "ftp.title_full":       {"it": "Server FTP locale — PCM",            "en": "Local FTP Server — PCM",          "de": "Lokaler FTP-Server — PCM",        "fr": "Serveur FTP local — PCM",          "es": "Servidor FTP local — PCM"},
    "ftp.tab_server":       {"it": "Server",                             "en": "Server",                          "de": "Server",                          "fr": "Serveur",                          "es": "Servidor"},
    "ftp.tab_users":        {"it": "Utenti",                             "en": "Users",                           "de": "Benutzer",                        "fr": "Utilisateurs",                     "es": "Usuarios"},
    "ftp.tab_log":          {"it": "Log",                                "en": "Log",                             "de": "Log",                             "fr": "Journal",                          "es": "Registro"},
    "ftp.btn_start":        {"it": "▶  Avvia server",                    "en": "▶  Start server",                 "de": "▶  Server starten",               "fr": "▶  Démarrer le serveur",           "es": "▶  Iniciar servidor"},
    "ftp.btn_stop":         {"it": "■  Ferma server",                    "en": "■  Stop server",                  "de": "■  Server stoppen",               "fr": "■  Arrêter le serveur",            "es": "■  Detener servidor"},
    "ftp.btn_close":        {"it": "Chiudi",                             "en": "Close",                           "de": "Schließen",                       "fr": "Fermer",                           "es": "Cerrar"},
    "ftp.btn_add_user":     {"it": "Aggiungi",                           "en": "Add",                             "de": "Hinzufügen",                      "fr": "Ajouter",                          "es": "Agregar"},
    "ftp.btn_edit_user":    {"it": "Modifica",                           "en": "Edit",                            "de": "Bearbeiten",                      "fr": "Modifier",                         "es": "Editar"},
    "ftp.btn_remove_user":  {"it": "Rimuovi",                            "en": "Remove",                          "de": "Entfernen",                       "fr": "Supprimer",                        "es": "Eliminar"},
    "ftp.btn_remove_sel":   {"it": "Rimuovi selezionato",                "en": "Remove selected",                 "de": "Ausgewählten entfernen",          "fr": "Supprimer la sélection",           "es": "Eliminar seleccionado"},
    "ftp.btn_add_save":     {"it": "Aggiungi / Salva modifiche utente",  "en": "Add / Save user changes",         "de": "Hinzufügen / Änderungen speichern","fr": "Ajouter / Enregistrer les modifications","es": "Agregar / Guardar cambios"},
    "ftp.btn_clear_log":    {"it": "Pulisci log",                        "en": "Clear log",                       "de": "Log leeren",                      "fr": "Effacer le journal",               "es": "Limpiar registro"},
    "ftp.status_idle":      {"it": "● Server fermo",                     "en": "● Server stopped",                "de": "● Server angehalten",             "fr": "● Serveur arrêté",                 "es": "● Servidor detenido"},
    "ftp.status_starting":  {"it": "⏳ Avvio in corso…",                 "en": "⏳ Starting…",                    "de": "⏳ Wird gestartet…",               "fr": "⏳ Démarrage en cours…",            "es": "⏳ Iniciando…"},
    "ftp.status_active":    {"it": "● Server attivo",                    "en": "● Server active",                 "de": "● Server aktiv",                  "fr": "● Serveur actif",                  "es": "● Servidor activo"},
    "ftp.status_error":     {"it": "✖ Errore",                           "en": "✖ Error",                         "de": "✖ Fehler",                        "fr": "✖ Erreur",                         "es": "✖ Error"},
    "ftp.status_stopped":   {"it": "Server fermato.",                    "en": "Server stopped.",                 "de": "Server angehalten.",              "fr": "Serveur arrêté.",                  "es": "Servidor detenido."},
    "ftp.label_port":       {"it": "Porta:",                             "en": "Port:",                           "de": "Port:",                           "fr": "Port :",                           "es": "Puerto:"},
    "ftp.label_bind":       {"it": "Bind IP:",                           "en": "Bind IP:",                        "de": "Bind-IP:",                        "fr": "IP de liaison :",                  "es": "IP de enlace:"},
    "ftp.label_pasv_min":   {"it": "Passive ports min:",                 "en": "Passive ports min:",              "de": "Passive Ports Min:",              "fr": "Ports passifs min :",               "es": "Puertos pasivos mín.:"},
    "ftp.label_pasv_max":   {"it": "Passive ports max:",                 "en": "Passive ports max:",              "de": "Passive Ports Max:",              "fr": "Ports passifs max :",               "es": "Puertos pasivos máx.:"},
    "ftp.chk_tls":          {"it": "Abilita TLS (FTPS — richiede certificato)", "en": "Enable TLS (FTPS — requires certificate)", "de": "TLS aktivieren (FTPS — Zertifikat erforderlich)", "fr": "Activer TLS (FTPS — certificat requis)", "es": "Habilitar TLS (FTPS — requiere certificado)"},
    "ftp.col_type":         {"it": "Tipo",                               "en": "Type",                            "de": "Typ",                             "fr": "Type",                             "es": "Tipo"},
    "ftp.col_name":         {"it": "Nome/Utente",                        "en": "Name/User",                       "de": "Name/Benutzer",                   "fr": "Nom/Utilisateur",                  "es": "Nombre/Usuario"},
    "ftp.col_folder":       {"it": "Cartella",                           "en": "Folder",                          "de": "Ordner",                          "fr": "Dossier",                          "es": "Carpeta"},
    "ftp.col_perms":        {"it": "Permessi",                           "en": "Permissions",                     "de": "Berechtigungen",                  "fr": "Permissions",                      "es": "Permisos"},
    "ftp.user_dialog_title":{"it": "Utente FTP",                         "en": "FTP User",                        "de": "FTP-Benutzer",                    "fr": "Utilisateur FTP",                  "es": "Usuario FTP"},
    "ftp.user_type":        {"it": "Tipo:",                              "en": "Type:",                           "de": "Typ:",                            "fr": "Type :",                           "es": "Tipo:"},
    "ftp.user_name":        {"it": "Nome utente:",                       "en": "Username:",                       "de": "Benutzername:",                   "fr": "Nom d'utilisateur :",              "es": "Nombre de usuario:"},
    "ftp.user_name_lbl":    {"it": "Nome utente:",                       "en": "Username:",                       "de": "Benutzername:",                   "fr": "Nom d'utilisateur :",              "es": "Nombre de usuario:"},
    "ftp.user_password":    {"it": "Password:",                          "en": "Password:",                       "de": "Passwort:",                       "fr": "Mot de passe :",                   "es": "Contraseña:"},
    "ftp.user_folder":      {"it": "Cartella:",                          "en": "Folder:",                         "de": "Ordner:",                         "fr": "Dossier :",                        "es": "Carpeta:"},
    "ftp.user_perms":       {"it": "Permessi:",                          "en": "Permissions:",                    "de": "Berechtigungen:",                 "fr": "Permissions :",                    "es": "Permisos:"},
    "ftp.perm_read":        {"it": "Lettura",                            "en": "Read",                            "de": "Lesen",                           "fr": "Lecture",                          "es": "Lectura"},
    "ftp.perm_write":       {"it": "Scrittura",                          "en": "Write",                           "de": "Schreiben",                       "fr": "Écriture",                         "es": "Escritura"},
    "ftp.perm_delete":      {"it": "Eliminazione",                       "en": "Delete",                          "de": "Löschen",                         "fr": "Suppression",                      "es": "Eliminación"},
    "ftp.perm_rename":      {"it": "Rinomina",                           "en": "Rename",                          "de": "Umbenennen",                      "fr": "Renommer",                         "es": "Cambiar nombre"},
    "ftp.perm_mkdir":       {"it": "Crea cartelle",                      "en": "Create folders",                  "de": "Ordner erstellen",                "fr": "Créer des dossiers",               "es": "Crear carpetas"},
    "ftp.browse_folder":    {"it": "Cartella radice FTP",                "en": "FTP root folder",                 "de": "FTP-Stammordner",                 "fr": "Dossier racine FTP",               "es": "Carpeta raíz FTP"},
    "ftp.btn_save":         {"it": "Salva",                              "en": "Save",                            "de": "Speichern",                       "fr": "Enregistrer",                      "es": "Guardar"},
    "ftp.users_configured": {"it": "Utenti configurati:",                "en": "Configured users:",               "de": "Konfigurierte Benutzer:",         "fr": "Utilisateurs configurés :",        "es": "Usuarios configurados:"},
    "ftp.presets":          {"it": "Preset rapidi:",                     "en": "Quick presets:",                  "de": "Schnellvorlagen:",                "fr": "Préréglages rapides :",             "es": "Ajustes rápidos:"},
    "ftp.anon_user":        {"it": "Utente anonimo (anonymous)",         "en": "Anonymous user",                  "de": "Anonymer Benutzer",               "fr": "Utilisateur anonyme",              "es": "Usuario anónimo"},
    "ftp.server_started":   {"it": "Server avviato: {url}",              "en": "Server started: {url}",           "de": "Server gestartet: {url}",         "fr": "Serveur démarré : {url}",          "es": "Servidor iniciado: {url}"},

    # ── tunnel_manager ────────────────────────────────────────────────────────
    "tunnel.edit_title":    {"it": "Configura Tunnel SSH",               "en": "Configure SSH Tunnel",            "de": "SSH-Tunnel konfigurieren",        "fr": "Configurer le tunnel SSH",         "es": "Configurar túnel SSH"},
    "tunnel.main_title":    {"it": "Tunnel SSH",                         "en": "SSH Tunnels",                     "de": "SSH-Tunnel",                      "fr": "Tunnels SSH",                      "es": "Túneles SSH"},
    "tunnel.main_title_full":{"it":"Gestione Tunnel SSH",                "en": "SSH Tunnel Manager",              "de": "SSH-Tunnel-Verwaltung",           "fr": "Gestionnaire de tunnels SSH",      "es": "Gestión de túneles SSH"},
    "tunnel.toolbar_title": {"it": "🔀  Gestore Tunnel SSH (Port Forwarding)", "en": "🔀  SSH Tunnel Manager (Port Forwarding)", "de": "🔀  SSH-Tunnel-Manager (Port-Weiterleitung)", "fr": "🔀  Gestionnaire de tunnels SSH (transfert de port)", "es": "🔀  Gestor de túneles SSH (reenvío de puertos)"},
    "tunnel.btn_add":       {"it": "➕ Aggiungi",                        "en": "➕ Add",                          "de": "➕ Hinzufügen",                    "fr": "➕ Ajouter",                        "es": "➕ Agregar"},
    "tunnel.btn_edit":      {"it": "✏ Modifica",                         "en": "✏ Edit",                          "de": "✏ Bearbeiten",                    "fr": "✏ Modifier",                       "es": "✏ Editar"},
    "tunnel.btn_delete":    {"it": "🗑 Elimina",                          "en": "🗑 Delete",                       "de": "🗑 Löschen",                       "fr": "🗑 Supprimer",                      "es": "🗑 Eliminar"},
    "tunnel.btn_start":     {"it": "▶ Avvia",                            "en": "▶ Start",                         "de": "▶ Starten",                       "fr": "▶ Démarrer",                       "es": "▶ Iniciar"},
    "tunnel.btn_stop":      {"it": "■ Ferma",                            "en": "■ Stop",                          "de": "■ Stoppen",                       "fr": "■ Arrêter",                        "es": "■ Detener"},
    "tunnel.btn_start_all": {"it": "▶▶ Avvia tutti",                     "en": "▶▶ Start all",                    "de": "▶▶ Alle starten",                  "fr": "▶▶ Démarrer tout",                 "es": "▶▶ Iniciar todos"},
    "tunnel.btn_stop_all":  {"it": "■■ Ferma tutti",                     "en": "■■ Stop all",                     "de": "■■ Alle stoppen",                  "fr": "■■ Arrêter tout",                  "es": "■■ Detener todos"},
    "tunnel.btn_close":     {"it": "Chiudi",                             "en": "Close",                           "de": "Schließen",                       "fr": "Fermer",                           "es": "Cerrar"},
    "tunnel.btn_cancel":    {"it": "Annulla",                            "en": "Cancel",                          "de": "Abbrechen",                       "fr": "Annuler",                          "es": "Cancelar"},
    "tunnel.btn_save":      {"it": "Salva",                              "en": "Save",                            "de": "Speichern",                       "fr": "Enregistrer",                      "es": "Guardar"},
    "tunnel.field_name":    {"it": "Nome:",                              "en": "Name:",                           "de": "Name:",                           "fr": "Nom :",                            "es": "Nombre:"},
    "tunnel.field_type":    {"it": "Tipo:",                              "en": "Type:",                           "de": "Typ:",                            "fr": "Type :",                           "es": "Tipo:"},
    "tunnel.field_user":    {"it": "Utente:",                            "en": "User:",                           "de": "Benutzer:",                       "fr": "Utilisateur :",                    "es": "Usuario:"},
    "tunnel.field_host":    {"it": "SSH host:",                          "en": "SSH host:",                       "de": "SSH-Host:",                       "fr": "Hôte SSH :",                       "es": "Host SSH:"},
    "tunnel.field_ssh_port":{"it": "SSH porta:",                         "en": "SSH port:",                       "de": "SSH-Port:",                       "fr": "Port SSH :",                       "es": "Puerto SSH:"},
    "tunnel.field_password":{"it": "Password:",                          "en": "Password:",                       "de": "Passwort:",                       "fr": "Mot de passe :",                   "es": "Contraseña:"},
    "tunnel.field_lport":   {"it": "Porta locale:",                      "en": "Local port:",                     "de": "Lokaler Port:",                   "fr": "Port local :",                     "es": "Puerto local:"},
    "tunnel.field_rhost":   {"it": "Host remoto:",                       "en": "Remote host:",                    "de": "Remote-Host:",                    "fr": "Hôte distant :",                   "es": "Host remoto:"},
    "tunnel.field_rport":   {"it": "Porta remota:",                      "en": "Remote port:",                    "de": "Remote-Port:",                    "fr": "Port distant :",                   "es": "Puerto remoto:"},
    "tunnel.chk_autostart": {"it": "Avvia automaticamente",              "en": "Start automatically",             "de": "Automatisch starten",             "fr": "Démarrage automatique",            "es": "Iniciar automáticamente"},
    "tunnel.col_name":      {"it": "Nome",                               "en": "Name",                            "de": "Name",                            "fr": "Nom",                              "es": "Nombre"},
    "tunnel.col_type":      {"it": "Tipo",                               "en": "Type",                            "de": "Typ",                             "fr": "Type",                             "es": "Tipo"},
    "tunnel.col_host":      {"it": "Host",                               "en": "Host",                            "de": "Host",                            "fr": "Hôte",                             "es": "Host"},
    "tunnel.col_lport":     {"it": "Porta locale",                       "en": "Local port",                      "de": "Lokaler Port",                    "fr": "Port local",                       "es": "Puerto local"},
    "tunnel.col_rhost":     {"it": "Host remoto",                        "en": "Remote host",                     "de": "Remote-Host",                     "fr": "Hôte distant",                     "es": "Host remoto"},
    "tunnel.col_rport":     {"it": "Porta remota",                       "en": "Remote port",                     "de": "Remote-Port",                     "fr": "Port distant",                     "es": "Puerto remoto"},
    "tunnel.col_status":    {"it": "Stato",                              "en": "Status",                          "de": "Status",                          "fr": "État",                             "es": "Estado"},
    "tunnel.status_active": {"it": "Attivo",                             "en": "Active",                          "de": "Aktiv",                           "fr": "Actif",                            "es": "Activo"},
    "tunnel.status_idle":   {"it": "Fermo",                              "en": "Stopped",                         "de": "Gestoppt",                        "fr": "Arrêté",                           "es": "Detenido"},
    "tunnel.ph_password":   {"it": "Vuoto = Chiavi SSH",                 "en": "Empty = SSH Keys",                "de": "Leer = SSH-Schlüssel",            "fr": "Vide = Clés SSH",                  "es": "Vacío = Claves SSH"},
    "tunnel.ph_name":       {"it": "es. SOCKS proxy casa",               "en": "e.g. SOCKS proxy home",           "de": "z.B. SOCKS-Proxy Zuhause",        "fr": "ex. proxy SOCKS maison",           "es": "ej. proxy SOCKS casa"},
    "tunnel.ph_rhost":      {"it": "host.interno (per -L/-R)",           "en": "internal.host (for -L/-R)",       "de": "interner.host (für -L/-R)",       "fr": "hôte.interne (pour -L/-R)",        "es": "host.interno (para -L/-R)"},

    # ── winscp_widget ────────────────────────────────────────────────────────
    "winscp.queue_title":   {"it": "📋  Coda trasferimenti",             "en": "📋  Transfer queue",              "de": "📋  Übertragungswarteschlange",   "fr": "📋  File d'attente des transferts", "es": "📋  Cola de transferencias"},
    "winscp.btn_pause":     {"it": "⏸ Pausa",                            "en": "⏸ Pause",                         "de": "⏸ Pause",                         "fr": "⏸ Pause",                          "es": "⏸ Pausa"},
    "winscp.btn_cancel":    {"it": "✖ Annulla",                          "en": "✖ Cancel",                        "de": "✖ Abbrechen",                     "fr": "✖ Annuler",                        "es": "✖ Cancelar"},
    "winscp.btn_clear":     {"it": "🧹 Pulisci",                         "en": "🧹 Clear",                        "de": "🧹 Bereinigen",                    "fr": "🧹 Nettoyer",                      "es": "🧹 Limpiar"},
    "winscp.btn_resume":    {"it": "▶ Riprendi",                         "en": "▶ Resume",                        "de": "▶ Fortsetzen",                    "fr": "▶ Reprendre",                      "es": "▶ Reanudar"},
    "winscp.btn_start_all": {"it": "Avvia tutti i trasferimenti in coda","en": "Start all queued transfers",      "de": "Alle Übertragungen starten",      "fr": "Démarrer tous les transferts en file","es": "Iniciar todas las transferencias en cola"},
    "winscp.col_name":      {"it": "Nome",                               "en": "Name",                            "de": "Name",                            "fr": "Nom",                              "es": "Nombre"},
    "winscp.col_size":      {"it": "Dim.",                               "en": "Size",                            "de": "Größe",                           "fr": "Taille",                           "es": "Tamaño"},
    "winscp.col_perms":     {"it": "Perm.",                              "en": "Perms",                           "de": "Rechte",                          "fr": "Droits",                           "es": "Perm."},
    "winscp.col_op":        {"it": "Op",                                 "en": "Op",                              "de": "Op",                              "fr": "Op",                               "es": "Op"},
    "winscp.col_src":       {"it": "Sorgente",                           "en": "Source",                          "de": "Quelle",                          "fr": "Source",                           "es": "Origen"},
    "winscp.col_dst":       {"it": "Destinazione",                       "en": "Destination",                     "de": "Ziel",                            "fr": "Destination",                      "es": "Destino"},
    "winscp.col_pct":       {"it": "%",                                  "en": "%",                               "de": "%",                               "fr": "%",                                "es": "%"},
    "winscp.col_speed":     {"it": "Velocità",                           "en": "Speed",                           "de": "Geschwindigkeit",                 "fr": "Vitesse",                          "es": "Velocidad"},
    "winscp.status_done":   {"it": "Completato",                         "en": "Done",                            "de": "Fertig",                          "fr": "Terminé",                          "es": "Completado"},
    "winscp.status_err":    {"it": "Errore",                             "en": "Error",                           "de": "Fehler",                          "fr": "Erreur",                           "es": "Error"},
    "winscp.local_panel":   {"it": "locale",                             "en": "local",                           "de": "lokal",                           "fr": "local",                            "es": "local"},
    "winscp.connecting":    {"it": "Connessione in corso…",              "en": "Connecting…",                     "de": "Verbindung wird hergestellt…",    "fr": "Connexion en cours…",              "es": "Conectando…"},
    "winscp.ftp_browser":   {"it": "📂 Browser FTP",                     "en": "📂 FTP Browser",                  "de": "📂 FTP-Browser",                  "fr": "📂 Navigateur FTP",                "es": "📂 Navegador FTP"},
    "winscp.sftp_browser":  {"it": "📂 Browser SFTP",                    "en": "📂 SFTP Browser",                 "de": "📂 SFTP-Browser",                 "fr": "📂 Navigateur SFTP",               "es": "📂 Navegador SFTP"},
    "winscp.new_folder":    {"it": "Nuova cartella",                     "en": "New folder",                      "de": "Neuer Ordner",                    "fr": "Nouveau dossier",                  "es": "Nueva carpeta"},
    "winscp.new_folder_remote":{"it":"Nuova cartella remota",            "en": "New remote folder",               "de": "Neuer Remote-Ordner",             "fr": "Nouveau dossier distant",          "es": "Nueva carpeta remota"},
    "winscp.rename":        {"it": "Rinomina",                           "en": "Rename",                          "de": "Umbenennen",                      "fr": "Renommer",                         "es": "Renombrar"},
    "winscp.parent_folder": {"it": "Cartella superiore",                 "en": "Parent folder",                   "de": "Übergeordneter Ordner",           "fr": "Dossier parent",                   "es": "Carpeta padre"},
    "winscp.drop_local":    {"it": "Drop sul pannello locale = download dal remoto.", "en": "Drop on local panel = download from remote.", "de": "Drop auf lokalem Panel = Herunterladen.", "fr": "Déposer sur le panneau local = téléchargement.", "es": "Soltar en panel local = descargar del remoto."},
    "winscp.drop_remote":   {"it": "Drop sul pannello remoto = upload dal locale.", "en": "Drop on remote panel = upload from local.", "de": "Drop auf Remote-Panel = Hochladen.", "fr": "Déposer sur le panneau distant = téléversement.", "es": "Soltar en panel remoto = subir desde local."},
    "winscp.err_nav":       {"it": "✖ Errore navigazione: {e}",          "en": "✖ Navigation error: {e}",         "de": "✖ Navigationsfehler: {e}",        "fr": "✖ Erreur de navigation : {e}",     "es": "✖ Error de navegación: {e}"},
    "winscp.err_generic":   {"it": "Errore",                             "en": "Error",                           "de": "Fehler",                          "fr": "Erreur",                           "es": "Error"},
    "winscp.field_name":    {"it": "Nome:",                              "en": "Name:",                           "de": "Name:",                           "fr": "Nom :",                            "es": "Nombre:"},

    # ── vnc_widget ────────────────────────────────────────────────────────────
    "vnc.password_dialog":  {"it": "Password VNC",                       "en": "VNC Password",                    "de": "VNC-Passwort",                    "fr": "Mot de passe VNC",                 "es": "Contraseña VNC"},
    "vnc.pwd_prompt":       {"it": "Password per {host}:{port}",         "en": "Password for {host}:{port}",      "de": "Passwort für {host}:{port}",      "fr": "Mot de passe pour {host}:{port}",  "es": "Contraseña para {host}:{port}"},
    "vnc.save_password":    {"it": "Salva password nel profilo",         "en": "Save password in profile",        "de": "Passwort im Profil speichern",    "fr": "Enregistrer le mot de passe dans le profil", "es": "Guardar contraseña en el perfil"},
    "vnc.btn_cancel":       {"it": "_Annulla",                           "en": "_Cancel",                         "de": "_Abbrechen",                      "fr": "_Annuler",                         "es": "_Cancelar"},
    "vnc.btn_connect":      {"it": "_Connetti",                          "en": "_Connect",                        "de": "_Verbinden",                      "fr": "_Connecter",                       "es": "_Conectar"},
    "vnc.tt_fit_screen":    {"it": "Adatta schermo alla finestra",       "en": "Fit screen to window",            "de": "Bildschirm an Fenster anpassen",  "fr": "Adapter l'écran à la fenêtre",     "es": "Ajustar pantalla a la ventana"},
    "vnc.tt_pointer":       {"it": "Puntatore: locale / remoto",         "en": "Pointer: local / remote",         "de": "Zeiger: lokal / remote",          "fr": "Pointeur : local / distant",       "es": "Puntero: local / remoto"},
    "vnc.tt_keyboard":      {"it": "Cattura tastiera (intercetta scorciatoie di sistema)", "en": "Capture keyboard (intercepts system shortcuts)", "de": "Tastatur erfassen (Systemkürzel abfangen)", "fr": "Capturer le clavier (intercepte les raccourcis système)", "es": "Capturar teclado (intercepta atajos del sistema)"},
    "vnc.tt_readonly":      {"it": "Sola lettura (nessun input al server)", "en": "Read-only (no input to server)", "de": "Nur Lesen (keine Eingabe an Server)", "fr": "Lecture seule (aucune entrée vers le serveur)", "es": "Solo lectura (sin entrada al servidor)"},
    "vnc.tt_cad":           {"it": "Invia Ctrl+Alt+Canc",                "en": "Send Ctrl+Alt+Del",               "de": "Strg+Alt+Entf senden",            "fr": "Envoyer Ctrl+Alt+Suppr",           "es": "Enviar Ctrl+Alt+Supr"},
    "vnc.tt_vt":            {"it": "Invia Ctrl+Alt+Fn (cambio terminale virtuale)", "en": "Send Ctrl+Alt+Fn (change virtual terminal)", "de": "Strg+Alt+Fn senden (virtuelles Terminal wechseln)", "fr": "Envoyer Ctrl+Alt+Fn (changer le terminal virtuel)", "es": "Enviar Ctrl+Alt+Fn (cambiar terminal virtual)"},
    "vnc.tt_screenshot":    {"it": "Cattura screenshot del desktop remoto","en": "Capture screenshot of remote desktop", "de": "Screenshot des Remote-Desktops aufnehmen", "fr": "Capturer une capture d'écran du bureau distant", "es": "Capturar pantalla del escritorio remoto"},
    "vnc.tt_reconnect":     {"it": "Riconnetti al server VNC",           "en": "Reconnect to VNC server",         "de": "Mit VNC-Server neu verbinden",    "fr": "Se reconnecter au serveur VNC",    "es": "Reconectar al servidor VNC"},
    "vnc.no_client":        {"it": "Nessun client VNC trovato nel PATH.\n", "en": "No VNC client found in PATH.\n", "de": "Kein VNC-Client im PATH gefunden.\n", "fr": "Aucun client VNC trouvé dans le PATH.\n", "es": "No se encontró cliente VNC en el PATH.\n"},
    "vnc.install_hint":     {"it": "Installa: sudo apt install tigervnc-viewer\n", "en": "Install: sudo apt install tigervnc-viewer\n", "de": "Installiere: sudo apt install tigervnc-viewer\n", "fr": "Installez : sudo apt install tigervnc-viewer\n", "es": "Instala: sudo apt install tigervnc-viewer\n"},
    "vnc.install_gtklib":   {"it": "o:   sudo apt install gir1.2-gtk-vnc-2.0", "en": "or:  sudo apt install gir1.2-gtk-vnc-2.0", "de": "oder: sudo apt install gir1.2-gtk-vnc-2.0", "fr": "ou :  sudo apt install gir1.2-gtk-vnc-2.0", "es": "o:   sudo apt install gir1.2-gtk-vnc-2.0"},
    "vnc.embedded_unavail": {"it": "<b>VNC integrato non disponibile</b>\n\n", "en": "<b>Embedded VNC unavailable</b>\n\n", "de": "<b>Eingebettetes VNC nicht verfügbar</b>\n\n", "fr": "<b>VNC intégré non disponible</b>\n\n", "es": "<b>VNC integrado no disponible</b>\n\n"},
    "vnc.install_pkgs":     {"it": "Installa uno dei seguenti pacchetti:\n\n", "en": "Install one of the following packages:\n\n", "de": "Installiere eines der folgenden Pakete:\n\n", "fr": "Installez l'un des paquets suivants :\n\n", "es": "Instala uno de los siguientes paquetes:\n\n"},
    "vnc.pkg_recommended":  {"it": "<tt>sudo apt install gir1.2-gtk-vnc-2.0</tt>   (raccomandato)\n", "en": "<tt>sudo apt install gir1.2-gtk-vnc-2.0</tt>   (recommended)\n", "de": "<tt>sudo apt install gir1.2-gtk-vnc-2.0</tt>   (empfohlen)\n", "fr": "<tt>sudo apt install gir1.2-gtk-vnc-2.0</tt>   (recommandé)\n", "es": "<tt>sudo apt install gir1.2-gtk-vnc-2.0</tt>   (recomendado)\n"},
    "vnc.pkg_alternative":  {"it": "<tt>sudo apt install tigervnc-viewer</tt>       (alternativa)", "en": "<tt>sudo apt install tigervnc-viewer</tt>       (alternative)", "de": "<tt>sudo apt install tigervnc-viewer</tt>       (Alternative)", "fr": "<tt>sudo apt install tigervnc-viewer</tt>       (alternative)", "es": "<tt>sudo apt install tigervnc-viewer</tt>       (alternativa)"},
    "vnc.screenshot_saved": {"it": "Screenshot salvato:\n{path}",        "en": "Screenshot saved:\n{path}",       "de": "Screenshot gespeichert:\n{path}", "fr": "Capture d'écran enregistrée :\n{path}", "es": "Captura guardada:\n{path}"},
    "vnc.screenshot_err":   {"it": "Screenshot errore: {e}",             "en": "Screenshot error: {e}",           "de": "Screenshot-Fehler: {e}",          "fr": "Erreur de capture d'écran : {e}", "es": "Error de captura: {e}"},

    # ── sftp_browser ─────────────────────────────────────────────────────────
    "sftp.browser_title":   {"it": "🗂 Browser SFTP",                    "en": "🗂 SFTP Browser",                 "de": "🗂 SFTP-Browser",                 "fr": "🗂 Navigateur SFTP",               "es": "🗂 Navegador SFTP"},
    "sftp.ftp_browser_title":{"it":"🗂 Browser FTP",                     "en": "🗂 FTP Browser",                  "de": "🗂 FTP-Browser",                  "fr": "🗂 Navigateur FTP",                "es": "🗂 Navegador FTP"},
    "sftp.not_connected":   {"it": "Non connesso",                       "en": "Not connected",                   "de": "Nicht verbunden",                 "fr": "Non connecté",                     "es": "No conectado"},
    "sftp.col_name":        {"it": "Nome",                               "en": "Name",                            "de": "Name",                            "fr": "Nom",                              "es": "Nombre"},
    "sftp.col_size":        {"it": "Dim.",                               "en": "Size",                            "de": "Größe",                           "fr": "Taille",                           "es": "Tamaño"},
    "sftp.col_perms":       {"it": "Perm.",                              "en": "Perms",                           "de": "Rechte",                          "fr": "Droits",                           "es": "Perm."},
    "sftp.upload_title":    {"it": "Carica file",                        "en": "Upload file",                     "de": "Datei hochladen",                 "fr": "Téléverser un fichier",            "es": "Subir archivo"},
    "sftp.download_title":  {"it": "Salva come",                         "en": "Save as",                         "de": "Speichern als",                   "fr": "Enregistrer sous",                 "es": "Guardar como"},
    "sftp.mkdir_title":     {"it": "Nuova cartella",                     "en": "New folder",                      "de": "Neuer Ordner",                    "fr": "Nouveau dossier",                  "es": "Nueva carpeta"},
    "sftp.rename_title":    {"it": "Rinomina",                           "en": "Rename",                          "de": "Umbenennen",                      "fr": "Renommer",                         "es": "Renombrar"},
    "sftp.mkdir_ph":        {"it": "Nome cartella",                      "en": "Folder name",                     "de": "Ordnername",                      "fr": "Nom du dossier",                   "es": "Nombre de carpeta"},
    "sftp.btn_create":      {"it": "Crea",                               "en": "Create",                          "de": "Erstellen",                       "fr": "Créer",                            "es": "Crear"},
    "sftp.btn_rename":      {"it": "Rinomina",                           "en": "Rename",                          "de": "Umbenennen",                      "fr": "Renommer",                         "es": "Renombrar"},
    "sftp.btn_cancel":      {"it": "Annulla",                            "en": "Cancel",                          "de": "Abbrechen",                       "fr": "Annuler",                          "es": "Cancelar"},
    "sftp.btn_upload":      {"it": "_Carica",                            "en": "_Upload",                         "de": "_Hochladen",                      "fr": "_Téléverser",                      "es": "_Subir"},
    "sftp.btn_save":        {"it": "_Salva",                             "en": "_Save",                           "de": "_Speichern",                      "fr": "_Enregistrer",                     "es": "_Guardar"},
    "sftp.connecting":      {"it": "⏳ Connessione in corso…",           "en": "⏳ Connecting…",                  "de": "⏳ Verbindung wird hergestellt…", "fr": "⏳ Connexion en cours…",            "es": "⏳ Conectando…"},
    "sftp.upload_err":      {"it": "Errore upload",                      "en": "Upload error",                    "de": "Hochladefehler",                  "fr": "Erreur de téléversement",          "es": "Error de subida"},
    "sftp.err_prefix":      {"it": "✖ Errore: {msg}",                   "en": "✖ Error: {msg}",                  "de": "✖ Fehler: {msg}",                 "fr": "✖ Erreur : {msg}",                 "es": "✖ Error: {msg}"},
    "sftp.download_done":   {"it": "Download completato",                "en": "Download complete",               "de": "Download abgeschlossen",          "fr": "Téléchargement terminé",           "es": "Descarga completada"},
    "sftp.delete_confirm":  {"it": "Eliminare '{name}'?",                "en": "Delete '{name}'?",                "de": "'{name}' löschen?",               "fr": "Supprimer « {name} » ?",           "es": "¿Eliminar '{name}'?"},
    "sftp.err_delete":      {"it": "Errore eliminazione: {e}",           "en": "Delete error: {e}",               "de": "Löschfehler: {e}",                "fr": "Erreur de suppression : {e}",      "es": "Error al eliminar: {e}"},
    "sftp.err_rename":      {"it": "Errore rinomina: {e}",               "en": "Rename error: {e}",               "de": "Umbenennungsfehler: {e}",         "fr": "Erreur de renommage : {e}",        "es": "Error al renombrar: {e}"},
    "sftp.err_connect":     {"it": "Errore: {e}",                        "en": "Error: {e}",                      "de": "Fehler: {e}",                     "fr": "Erreur : {e}",                     "es": "Error: {e}"},
    "sftp.select_upload":   {"it": "Seleziona file da caricare",         "en": "Select file to upload",           "de": "Datei zum Hochladen auswählen",   "fr": "Sélectionner le fichier à téléverser", "es": "Seleccionar archivo para subir"},
    "sftp.parent_folder":   {"it": "Cartella superiore",                 "en": "Parent folder",                   "de": "Übergeordneter Ordner",           "fr": "Dossier parent",                   "es": "Carpeta padre"},
    "sftp.n_items":         {"it": "{n} elementi",                       "en": "{n} items",                       "de": "{n} Elemente",                    "fr": "{n} éléments",                     "es": "{n} elementos"},

    # ── variables_dialog (PyQt6) ──────────────────────────────────────────────
    "variables.btn_add":    {"it": "➕ Aggiungi",                        "en": "➕ Add",                          "de": "➕ Hinzufügen",                    "fr": "➕ Ajouter",                        "es": "➕ Agregar"},
    "variables.btn_remove": {"it": "➖ Rimuovi",                         "en": "➖ Remove",                       "de": "➖ Entfernen",                     "fr": "➖ Supprimer",                      "es": "➖ Eliminar"},
    "variables.btn_cancel": {"it": "Annulla",                            "en": "Cancel",                          "de": "Abbrechen",                       "fr": "Annuler",                          "es": "Cancelar"},
    "variables.confirm_delete_title": {"it": "Conferma eliminazione",    "en": "Confirm deletion",                "de": "Löschen bestätigen",              "fr": "Confirmer la suppression",         "es": "Confirmar eliminación"},
    "variables.confirm_delete_msg":   {"it": "Eliminare la variabile '{name}'?", "en": "Delete variable '{name}'?", "de": "Variable '{name}' löschen?",  "fr": "Supprimer la variable « {name} » ?", "es": "¿Eliminar la variable '{name}'?"},

    # ── ftp_server_dialog — chiavi aggiuntive ─────────────────────────────────
    "ftp.tab_settings":     {"it": "Impostazioni",                       "en": "Settings",                        "de": "Einstellungen",                   "fr": "Paramètres",                       "es": "Configuración"},
    "ftp.grp_identity":     {"it": "Identità",                           "en": "Identity",                        "de": "Identität",                       "fr": "Identité",                         "es": "Identidad"},
    "ftp.preset_ro":        {"it": "Sola lettura",                       "en": "Read only",                       "de": "Nur lesen",                       "fr": "Lecture seule",                    "es": "Solo lectura"},
    "ftp.preset_all":       {"it": "Tutto",                              "en": "Full access",                     "de": "Vollzugriff",                     "fr": "Accès complet",                    "es": "Acceso completo"},
    "ftp.perm_read_dl":     {"it": "Lettura file (scarica)",             "en": "Read files (download)",           "de": "Dateien lesen (herunterladen)",   "fr": "Lire les fichiers (télécharger)",  "es": "Leer archivos (descargar)"},
    "ftp.perm_write_ul":    {"it": "Scrittura file (carica)",            "en": "Write files (upload)",            "de": "Dateien schreiben (hochladen)",   "fr": "Écrire les fichiers (téléverser)", "es": "Escribir archivos (subir)"},
    "ftp.perm_delete_files":{"it": "Cancellazione file e cartelle",      "en": "Delete files and folders",        "de": "Dateien und Ordner löschen",      "fr": "Supprimer fichiers et dossiers",   "es": "Eliminar archivos y carpetas"},
    "ftp.perm_list":        {"it": "Elenca contenuto cartelle",          "en": "List folder contents",            "de": "Ordnerinhalt auflisten",          "fr": "Lister le contenu des dossiers",   "es": "Listar contenido de carpetas"},
    "ftp.perm_rename_files":{"it": "Rinomina file e cartelle",           "en": "Rename files and folders",        "de": "Dateien und Ordner umbenennen",   "fr": "Renommer fichiers et dossiers",    "es": "Renombrar archivos y carpetas"},
    "ftp.col_name_user":    {"it": "Nome",                               "en": "Name",                            "de": "Name",                            "fr": "Nom",                              "es": "Nombre"},
    "ftp.label_password":   {"it": "Password:",                          "en": "Password:",                       "de": "Passwort:",                       "fr": "Mot de passe :",                   "es": "Contraseña:"},
    "ftp.log_connections":  {"it": "Log connessioni",                    "en": "Connection log",                  "de": "Verbindungsprotokoll",            "fr": "Journal des connexions",           "es": "Registro de conexiones"},

    # ── tunnel_manager — chiavi aggiuntive ────────────────────────────────────
    "tunnel.warn_active":   {"it": "Tunnel attivo",                      "en": "Active tunnel",                   "de": "Aktiver Tunnel",                  "fr": "Tunnel actif",                     "es": "Túnel activo"},
    "tunnel.warn_stop_first":{"it":"Ferma il tunnel prima di modificarlo.", "en": "Stop the tunnel before editing it.", "de": "Stoppe den Tunnel vor der Bearbeitung.", "fr": "Arrêtez le tunnel avant de le modifier.", "es": "Detén el túnel antes de editarlo."},
    "tunnel.field_ssh_user":{"it": "SSH utente:",                        "en": "SSH user:",                       "de": "SSH-Benutzer:",                   "fr": "Utilisateur SSH :",                "es": "Usuario SSH:"},
    "tunnel.field_ssh_pwd": {"it": "SSH password:",                      "en": "SSH password:",                   "de": "SSH-Passwort:",                   "fr": "Mot de passe SSH :",               "es": "Contraseña SSH:"},

    # ── sftp_browser — tooltip pulsanti ──────────────────────────────────────
    "sftp.tooltip_up":      {"it": "Cartella superiore",                 "en": "Parent folder",                   "de": "Übergeordneter Ordner",           "fr": "Dossier parent",                   "es": "Carpeta padre"},
    "sftp.tooltip_home":    {"it": "Home directory",                     "en": "Home directory",                  "de": "Home-Verzeichnis",                "fr": "Répertoire personnel",             "es": "Directorio de inicio"},
    "sftp.tooltip_refresh": {"it": "Aggiorna",                           "en": "Refresh",                         "de": "Aktualisieren",                   "fr": "Actualiser",                       "es": "Actualizar"},
    "sftp.tooltip_upload":  {"it": "Carica file",                        "en": "Upload file",                     "de": "Datei hochladen",                 "fr": "Téléverser un fichier",            "es": "Subir archivo"},
    "sftp.tooltip_download":{"it": "Scarica file",                       "en": "Download file",                   "de": "Datei herunterladen",             "fr": "Télécharger un fichier",           "es": "Descargar archivo"},
    "sftp.tooltip_mkdir":   {"it": "Nuova cartella",                     "en": "New folder",                      "de": "Neuer Ordner",                    "fr": "Nouveau dossier",                  "es": "Nueva carpeta"},
    "sftp.download_cancel": {"it": "Annulla",                            "en": "Cancel",                          "de": "Abbrechen",                       "fr": "Annuler",                          "es": "Cancelar"},
    "sftp.downloading":     {"it": "⬇ Download: {name}",                "en": "⬇ Download: {name}",              "de": "⬇ Herunterladen: {name}",         "fr": "⬇ Téléchargement : {name}",        "es": "⬇ Descargando: {name}"},
    "sftp.downloaded":      {"it": "Scaricato",                          "en": "Downloaded",                      "de": "Heruntergeladen",                 "fr": "Téléchargé",                       "es": "Descargado"},

    # ── winscp_widget — chiavi aggiuntive ────────────────────────────────────
    "winscp.status_wait":   {"it": "In attesa",                          "en": "Waiting",                         "de": "Warten",                          "fr": "En attente",                       "es": "En espera"},
    "winscp.status_running":{"it": "In corso",                           "en": "In progress",                     "de": "In Bearbeitung",                   "fr": "En cours",                         "es": "En progreso"},
    "winscp.col_ext":       {"it": "Ext",                                "en": "Ext",                             "de": "Ext",                             "fr": "Ext",                              "es": "Ext"},
    "winscp.col_modified":  {"it": "Modificato",                         "en": "Modified",                        "de": "Geändert",                        "fr": "Modifié",                          "es": "Modificado"},
    "winscp.col_attrs":     {"it": "Attributi",                          "en": "Attributes",                      "de": "Attribute",                       "fr": "Attributs",                        "es": "Atributos"},
    "winscp.col_transferred":{"it":"Trasferito",                         "en": "Transferred",                     "de": "Übertragen",                      "fr": "Transféré",                        "es": "Transferido"},
    "winscp.col_op":        {"it": "Op.",                                "en": "Op.",                             "de": "Op.",                             "fr": "Op.",                              "es": "Op."},
    "winscp.tooltip_home":  {"it": "Home",                               "en": "Home",                            "de": "Home",                            "fr": "Accueil",                          "es": "Inicio"},
    "winscp.tooltip_refresh":{"it":"Aggiorna",                           "en": "Refresh",                         "de": "Aktualisieren",                   "fr": "Actualiser",                       "es": "Actualizar"},
    "winscp.tooltip_up":    {"it": "Su",                                 "en": "Up",                              "de": "Nach oben",                       "fr": "Monter",                           "es": "Subir"},
    "winscp.queue_add":     {"it": "📋  Aggiungi a coda ({n} elementi)", "en": "📋  Add to queue ({n} items)",    "de": "📋  Zur Warteschlange hinzufügen ({n})", "fr": "📋  Ajouter à la file ({n} éléments)", "es": "📋  Agregar a cola ({n} elementos)"},
    "winscp.ctx_delete":    {"it": "🗑  Elimina",                         "en": "🗑  Delete",                      "de": "🗑  Löschen",                       "fr": "🗑  Supprimer",                     "es": "🗑  Eliminar"},
    "winscp.ctx_refresh":   {"it": "↺  Aggiorna",                        "en": "↺  Refresh",                     "de": "↺  Aktualisieren",                 "fr": "↺  Actualiser",                    "es": "↺  Actualizar"},
    "winscp.local_home":    {"it": "Home",                               "en": "Home",                            "de": "Home",                            "fr": "Accueil",                          "es": "Inicio"},
    "winscp.local_refresh": {"it": "Aggiorna",                           "en": "Refresh",                         "de": "Aktualisieren",                   "fr": "Actualiser",                       "es": "Actualizar"},

    # ── sftp_browser — chiavi aggiuntive ─────────────────────────────────────
    "sftp.select_files":    {"it": "Seleziona file da caricare",         "en": "Select files to upload",          "de": "Dateien zum Hochladen auswählen", "fr": "Sélectionner les fichiers à téléverser", "es": "Seleccionar archivos para subir"},
    "sftp.upload_cancel":   {"it": "Annulla",                            "en": "Cancel",                          "de": "Abbrechen",                       "fr": "Annuler",                          "es": "Cancelar"},
    "sftp.err_upload":      {"it": "Errore upload",                      "en": "Upload error",                    "de": "Hochladefehler",                  "fr": "Erreur de téléversement",          "es": "Error de subida"},
    "sftp.err_with_msg":    {"it": "✖ Errore: {msg}",                   "en": "✖ Error: {msg}",                  "de": "✖ Fehler: {msg}",                 "fr": "✖ Erreur : {msg}",                 "es": "✖ Error: {msg}"},
    "sftp.mkdir_label":     {"it": "Nuova cartella",                     "en": "New folder",                      "de": "Neuer Ordner",                    "fr": "Nouveau dossier",                  "es": "Nueva carpeta"},
    "sftp.mkdir_name_lbl":  {"it": "Nome:",                              "en": "Name:",                           "de": "Name:",                           "fr": "Nom :",                            "es": "Nombre:"},
    "sftp.err_generic":     {"it": "Errore",                             "en": "Error",                           "de": "Fehler",                          "fr": "Erreur",                           "es": "Error"},
    "sftp.upload":          {"it": "Carica",                            "en": "Upload",                          "de": "Hochladen",                       "fr": "Téléverser",                       "es": "Subir"},
    "sftp.download":        {"it": "Scarica",                           "en": "Download",                        "de": "Herunterladen",                   "fr": "Télécharger",                      "es": "Descargar"},
    "sftp.mkdir":           {"it": "Nuova cartella",                    "en": "New folder",                      "de": "Neuer Ordner",                    "fr": "Nouveau dossier",                  "es": "Nueva carpeta"},
    "sftp.delete":          {"it": "Elimina",                           "en": "Delete",                          "de": "Löschen",                         "fr": "Supprimer",                        "es": "Eliminar"},
    "sftp.rename":          {"it": "Rinomina",                          "en": "Rename",                          "de": "Umbenennen",                      "fr": "Renommer",                         "es": "Renombrar"},
    "sftp.loading":         {"it": "⏳ Connessione in corso…",          "en": "⏳ Connecting…",                  "de": "⏳ Verbindung wird hergestellt…", "fr": "⏳ Connexion en cours…",            "es": "⏳ Conectando…"},
    "sftp.ftp_err":         {"it": "✖ Errore FTP: {e}",                 "en": "✖ FTP error: {e}",                "de": "✖ FTP-Fehler: {e}",               "fr": "✖ Erreur FTP : {e}",               "es": "✖ Error FTP: {e}"},
    "sftp.ftp_dir_summary": {"it": "{dirs} cartelle, {files} file — {path}", "en": "{dirs} folders, {files} files — {path}", "de": "{dirs} Ordner, {files} Dateien — {path}", "fr": "{dirs} dossiers, {files} fichiers — {path}", "es": "{dirs} carpetas, {files} archivos — {path}"},
    "sftp.upload_done":     {"it": "✔ Caricato: {name}",                "en": "✔ Uploaded: {name}",              "de": "✔ Hochgeladen: {name}",           "fr": "✔ Téléversé : {name}",             "es": "✔ Subido: {name}"},
    "sftp.upload_err_detail":{"it":"✖ Errore upload: {e}",              "en": "✖ Upload error: {e}",             "de": "✖ Hochladefehler: {e}",           "fr": "✖ Erreur de téléversement : {e}", "es": "✖ Error de subida: {e}"},
    "sftp.download_done_name":{"it":"✔ Scaricato: {name}",              "en": "✔ Downloaded: {name}",            "de": "✔ Heruntergeladen: {name}",       "fr": "✔ Téléchargé : {name}",            "es": "✔ Descargado: {name}"},
    "sftp.download_err_detail":{"it":"✖ Errore download: {e}",          "en": "✖ Download error: {e}",           "de": "✖ Downloadfehler: {e}",           "fr": "✖ Erreur de téléchargement : {e}","es": "✖ Error de descarga: {e}"},
    "sftp.refresh":         {"it": "Aggiorna",                          "en": "Refresh",                         "de": "Aktualisieren",                   "fr": "Actualiser",                       "es": "Actualizar"},

    # ── winscp_widget — chiavi menu/dialogs ──────────────────────────────────
    "winscp.ctx_rename":    {"it": "✏  Rinomina",                        "en": "✏  Rename",                       "de": "✏  Umbenennen",                   "fr": "✏  Renommer",                      "es": "✏  Renombrar"},
    "winscp.ctx_mkdir_remote":{"it":"📁+  Nuova cartella",               "en": "📁+  New folder",                 "de": "📁+  Neuer Ordner",               "fr": "📁+  Nouveau dossier",             "es": "📁+  Nueva carpeta"},
    "winscp.col_operation": {"it": "Operazione",                         "en": "Operation",                       "de": "Operation",                       "fr": "Opération",                        "es": "Operación"},
    "winscp.col_time_speed":{"it": "Tempo/Velocità",                     "en": "Time/Speed",                      "de": "Zeit/Geschwindigkeit",            "fr": "Temps/Vitesse",                    "es": "Tiempo/Velocidad"},
    "winscp.col_progress":  {"it": "Progresso",                          "en": "Progress",                        "de": "Fortschritt",                     "fr": "Progression",                      "es": "Progreso"},
    "winscp.err_delete":    {"it": "Errore eliminazione",                "en": "Delete error",                    "de": "Löschfehler",                     "fr": "Erreur de suppression",            "es": "Error al eliminar"},
    "winscp.err_rename":    {"it": "Errore rinomina",                    "en": "Rename error",                    "de": "Umbenennungsfehler",              "fr": "Erreur de renommage",              "es": "Error al renombrar"},
    "winscp.err_generic2":  {"it": "Errore",                             "en": "Error",                           "de": "Fehler",                          "fr": "Erreur",                           "es": "Error"},
    "winscp.dlg_rename":    {"it": "Rinomina",                           "en": "Rename",                          "de": "Umbenennen",                      "fr": "Renommer",                         "es": "Renombrar"},
    "winscp.dlg_rename_input":{"it":"Nuovo nome:",                       "en": "New name:",                       "de": "Neuer Name:",                     "fr": "Nouveau nom :",                    "es": "Nuevo nombre:"},
    "winscp.dlg_delete":    {"it": "Elimina",                            "en": "Delete",                          "de": "Löschen",                         "fr": "Supprimer",                        "es": "Eliminar"},
    "winscp.dlg_delete_remote":{"it":"Elimina remoto",                   "en": "Delete remote",                   "de": "Remote löschen",                  "fr": "Supprimer à distance",             "es": "Eliminar remoto"},
    "winscp.dlg_delete_confirm":{"it":"Eliminare: {names}?",             "en": "Delete: {names}?",                "de": "{names} löschen?",                "fr": "Supprimer : {names} ?",            "es": "¿Eliminar: {names}?"},
    "winscp.no_jobs":       {"it": "Nessun job in coda da avviare.",     "en": "No jobs in queue to start.",      "de": "Keine Jobs in der Warteschlange.","fr": "Aucun travail en file à démarrer.", "es": "No hay trabajos en la cola."},
    "winscp.transfer_running":{"it":"Trasferimento in corso",            "en": "Transfer in progress",            "de": "Übertragung läuft",               "fr": "Transfert en cours",               "es": "Transferencia en curso"},
    "winscp.transfer_wait": {"it": "Attendi il completamento del trasferimento corrente.", "en": "Wait for the current transfer to complete.", "de": "Warte auf den Abschluss.", "fr": "Attendez la fin du transfert.", "es": "Espere el final de la transferencia."},
    "winscp.transferring":  {"it": "⏳ Trasferimento di {n} file in corso…", "en": "⏳ Transferring {n} file(s)…", "de": "⏳ Übertragung von {n} Datei(en)…", "fr": "⏳ Transfert de {n} fichier(s)…", "es": "⏳ Transfiriendo {n} archivo(s)…"},
    "winscp.queue_count":   {"it": "📋 {n} file aggiunti in coda ({m} tot.)", "en": "📋 {n} file(s) added to queue ({m} total)", "de": "📋 {n} Datei(en) zur Warteschlange hinzugefügt ({m} gesamt)", "fr": "📋 {n} fichier(s) ajouté(s) à la file ({m} total)", "es": "📋 {n} archivo(s) añadido(s) a la cola ({m} total)"},
    "winscp.no_local_sel":  {"it": "Seleziona almeno un file nel pannello locale.", "en": "Select at least one file in the local panel.", "de": "Wähle mindestens eine Datei im lokalen Panel.", "fr": "Sélectionnez au moins un fichier dans le panneau local.", "es": "Seleccione al menos un archivo en el panel local."},
    "winscp.no_remote_sel": {"it": "Seleziona almeno un file nel pannello remoto.", "en": "Select at least one file in the remote panel.", "de": "Wähle mindestens eine Datei im Remote-Panel.", "fr": "Sélectionnez au moins un fichier dans le panneau distant.", "es": "Seleccione al menos un archivo en el panel remoto."},
    "winscp.ctx_dl_local":  {"it": "⬇  Scarica in locale ({n} elementi)", "en": "⬇  Download to local ({n} items)", "de": "⬇  Lokal herunterladen ({n} Elemente)", "fr": "⬇  Télécharger en local ({n} éléments)", "es": "⬇  Descargar en local ({n} elementos)"},
    "winscp.ctx_ul_remote": {"it": "⬆  Carica su remoto ({n} elementi)", "en": "⬆  Upload to remote ({n} items)", "de": "⬆  Remote hochladen ({n} Elemente)", "fr": "⬆  Téléverser vers le distant ({n} éléments)", "es": "⬆  Subir al remoto ({n} elementos)"},
    "winscp.op_upload":     {"it": "⬆",                                  "en": "⬆",                              "de": "⬆",                               "fr": "⬆",                                "es": "⬆"},
    "winscp.op_download":   {"it": "⬇",                                  "en": "⬇",                              "de": "⬇",                               "fr": "⬇",                                "es": "⬇"},
    "winscp.status_wait_lbl":{"it":"In attesa",                          "en": "Waiting",                         "de": "Warten",                          "fr": "En attente",                       "es": "En espera"},
    "winscp.tooltip_btn_start":{"it":"▶  Avvia coda",                    "en": "▶  Start queue",                  "de": "▶  Warteschlange starten",        "fr": "▶  Démarrer la file",              "es": "▶  Iniciar cola"},
    "winscp.tooltip_start_all":{"it":"Avvia tutti i trasferimenti in coda", "en": "Start all queued transfers",   "de": "Alle Übertragungen starten",      "fr": "Démarrer tous les transferts en file", "es": "Iniciar todas las transferencias en cola"},
    "winscp.tooltip_new_folder":{"it":"Crea nuova cartella sul server remoto", "en": "Create new folder on remote server", "de": "Neuen Ordner auf dem Remote-Server erstellen", "fr": "Créer un nouveau dossier sur le serveur distant", "es": "Crear nueva carpeta en el servidor remoto"},
    "winscp.tooltip_delete_remote":{"it":"Elimina gli elementi selezionati sul remoto", "en": "Delete selected items on remote", "de": "Ausgewählte Elemente auf dem Remote löschen", "fr": "Supprimer les éléments sélectionnés à distance", "es": "Eliminar elementi seleccionados en remoto"},
    "winscp.tooltip_refresh_both":{"it":"Aggiorna entrambi i pannelli", "en": "Refresh both panels",             "de": "Beide Panels aktualisieren",      "fr": "Actualiser les deux panneaux",     "es": "Actualizar ambos paneles"},
    "winscp.tooltip_clear_queue":{"it":"Svuota la coda trasferimenti",   "en": "Clear transfer queue",            "de": "Übertragungswarteschlange leeren", "fr": "Vider la file de transferts",     "es": "Vaciar la cola de transferencias"},
    "winscp.dlg_upload":    {"it": "Upload",                             "en": "Upload",                          "de": "Hochladen",                       "fr": "Téléversement",                    "es": "Subida"},
    "winscp.dlg_download":  {"it": "Download",                           "en": "Download",                        "de": "Herunterladen",                   "fr": "Téléchargement",                   "es": "Descarga"},
    "winscp.dlg_queue":     {"it": "Coda",                               "en": "Queue",                           "de": "Warteschlange",                   "fr": "File d'attente",                   "es": "Cola"},
    "winscp.status_cancelled": {"it": "Annullato",                       "en": "Cancelled",                       "de": "Abgebrochen",                     "fr": "Annulé",                           "es": "Cancelado"},
    "winscp.btn_upload":       {"it": "⬆ Upload",                        "en": "⬆ Upload",                        "de": "⬆ Hochladen",                     "fr": "⬆ Envoyer",                        "es": "⬆ Subir"},
    "winscp.btn_download":     {"it": "⬇ Download",                      "en": "⬇ Download",                      "de": "⬇ Herunterladen",                 "fr": "⬇ Télécharger",                    "es": "⬇ Descargar"},
    "winscp.btn_delete":       {"it": "🗑 Elimina",                       "en": "🗑 Delete",                        "de": "🗑 Löschen",                       "fr": "🗑 Supprimer",                      "es": "🗑 Eliminar"},
    "winscp.btn_refresh":      {"it": "↺ Aggiorna",                      "en": "↺ Refresh",                       "de": "↺ Aktualisieren",                 "fr": "↺ Actualiser",                     "es": "↺ Actualizar"},
    "winscp.btn_new_folder_r": {"it": "📁+ Cartella",                    "en": "📁+ Folder",                      "de": "📁+ Ordner",                      "fr": "📁+ Dossier",                      "es": "📁+ Carpeta"},
    "winscp.tooltip_upload":   {"it": "Carica i file selezionati sul server remoto", "en": "Upload selected files to remote server", "de": "Ausgewählte Dateien auf Remote-Server hochladen", "fr": "Envoyer les fichiers sélectionnés vers le serveur distant", "es": "Subir los archivos seleccionados al servidor remoto"},
    "winscp.tooltip_download": {"it": "Scarica i file selezionati in locale", "en": "Download selected files to local", "de": "Ausgewählte Dateien lokal herunterladen", "fr": "Télécharger les fichiers sélectionnés en local", "es": "Descargar los archivos seleccionados en local"},
    "winscp.tooltip_delete":   {"it": "Elimina la selezione (locale o remota)", "en": "Delete selection (local or remote)", "de": "Auswahl löschen (lokal oder remote)", "fr": "Supprimer la sélection (local ou distant)", "es": "Eliminar la selección (local o remota)"},
    "winscp.tooltip_cancel_all":{"it":"Annulla il trasferimento in corso e tutti quelli in attesa", "en": "Cancel running and all pending transfers", "de": "Laufende und ausstehende Übertragungen abbrechen", "fr": "Annuler le transfert en cours et tous les transferts en attente", "es": "Cancelar la transferencia en curso y todas las pendientes"},

    # ── session_dialog — SSH key management (stringhe prima hardcoded) ───────
    "sd.keys.type_ed25519":  {"it": "ed25519  (consigliata)",              "en": "ed25519  (recommended)",            "de": "ed25519  (empfohlen)",             "fr": "ed25519  (recommandé)",            "es": "ed25519  (recomendado)"},
    "sd.keys.type_rsa":      {"it": "rsa 4096",                            "en": "rsa 4096",                         "de": "rsa 4096",                        "fr": "rsa 4096",                         "es": "rsa 4096"},
    "sd.keys.type_ecdsa":    {"it": "ecdsa 521",                           "en": "ecdsa 521",                        "de": "ecdsa 521",                       "fr": "ecdsa 521",                        "es": "ecdsa 521"},
    "sd.keys.comment_ph":    {"it": "commento (es. utente@host)",          "en": "comment (e.g. user@host)",         "de": "Kommentar (z.B. benutzer@host)",  "fr": "commentaire (ex. utilisateur@hôte)", "es": "comentario (ej. usuario@host)"},
    "sd.keys.reload_list":   {"it": "Ricarica lista chiavi",               "en": "Reload key list",                  "de": "Schlüsselliste neu laden",        "fr": "Recharger la liste des clés",      "es": "Recargar lista de claves"},
    "sd.keys.copy_server_tip":{"it": "Invia la chiave pubblica al server con ssh-copy-id", "en": "Send the public key to the server using ssh-copy-id", "de": "Öffentlichen Schlüssel mit ssh-copy-id an den Server senden", "fr": "Envoyer la clé publique au serveur via ssh-copy-id", "es": "Enviar la clave pública al servidor con ssh-copy-id"},
    "sd.keys.show_pub_alt":  {"it": "Visualizza e copia la chiave pubblica","en": "View and copy the public key",      "de": "Öffentlichen Schlüssel anzeigen und kopieren", "fr": "Afficher et copier la clé publique", "es": "Ver y copiar la clave pública"},
    "sd.keys.frame_label":   {"it": " 🔑 Gestione chiavi SSH ",            "en": " 🔑 SSH Key Management ",           "de": " 🔑 SSH-Schlüsselverwaltung ",     "fr": " 🔑 Gestion des clés SSH ",         "es": " 🔑 Gestión de claves SSH "},

    # ── Tooltip sessione ─────────────────────────────────────────────────────
    "tt.host":        {"it": "Indirizzo IP o hostname del server remoto. Es: 192.168.1.100 oppure server.example.com", "en": "IP address or hostname of the remote server. E.g.: 192.168.1.100 or server.example.com", "de": "IP-Adresse oder Hostname des Remote-Servers. Z.B.: 192.168.1.100 oder server.example.com", "fr": "Adresse IP ou nom d'hôte du serveur distant. Ex : 192.168.1.100 ou server.example.com", "es": "Dirección IP o nombre de host del servidor remoto. Ej: 192.168.1.100 o server.example.com"},
    "tt.port":        {"it": "Porta di rete del servizio. Default: SSH=22, Telnet=23, RDP=3389, VNC=5900, FTP=21", "en": "Network port of the service. Default: SSH=22, Telnet=23, RDP=3389, VNC=5900, FTP=21", "de": "Netzwerkport des Dienstes. Standard: SSH=22, Telnet=23, RDP=3389, VNC=5900, FTP=21", "fr": "Port réseau du service. Par défaut : SSH=22, Telnet=23, RDP=3389, VNC=5900, FTP=21", "es": "Puerto de red del servicio. Por defecto: SSH=22, Telnet=23, RDP=3389, VNC=5900, FTP=21"},
    "tt.user":        {"it": "Nome utente per l'autenticazione sul server remoto", "en": "Username for authentication on the remote server", "de": "Benutzername für die Authentifizierung am Remote-Server", "fr": "Nom d'utilisateur pour l'authentification sur le serveur distant", "es": "Nombre de usuario para la autenticación en el servidor remoto"},
    "tt.password":    {"it": "Password di accesso. Per SSH è preferibile usare una chiave privata invece della password", "en": "Login password. For SSH it is preferable to use a private key instead of a password", "de": "Anmeldepasswort. Bei SSH ist die Verwendung eines privaten Schlüssels einem Passwort vorzuziehen", "fr": "Mot de passe de connexion. Pour SSH, il est préférable d'utiliser une clé privée plutôt qu'un mot de passe", "es": "Contraseña de acceso. Para SSH es preferible usar una clave privada en lugar de contraseña"},
    "tt.pkey":        {"it": "Percorso alla chiave privata SSH (es. ~/.ssh/id_ed25519). Lasciare vuoto per usare la password", "en": "Path to the SSH private key (e.g. ~/.ssh/id_ed25519). Leave empty to use password", "de": "Pfad zum privaten SSH-Schlüssel (z.B. ~/.ssh/id_ed25519). Leer lassen für Passwort", "fr": "Chemin vers la clé privée SSH (ex. ~/.ssh/id_ed25519). Laisser vide pour utiliser le mot de passe", "es": "Ruta a la clave privada SSH (ej. ~/.ssh/id_ed25519). Dejar vacío para usar contraseña"},
    "tt.pkey_browse": {"it": "Sfoglia il filesystem per selezionare il file della chiave privata", "en": "Browse the filesystem to select the private key file", "de": "Dateisystem durchsuchen, um die private Schlüsseldatei auszuwählen", "fr": "Parcourir le système de fichiers pour sélectionner le fichier de clé privée", "es": "Explorar el sistema de archivos para seleccionar el archivo de clave privada"},
    "tt.ft_proto":    {"it": "Seleziona il protocollo di trasferimento file:\n• SFTP — cifrato, usa SSH (porta 22)\n• FTP — non cifrato (porta 21)\n• FTPS — FTP con TLS/SSL (porta 21)", "en": "Select the file transfer protocol:\n• SFTP — encrypted, uses SSH (port 22)\n• FTP — unencrypted (port 21)\n• FTPS — FTP with TLS/SSL (port 21)", "de": "Dateiübertragungsprotokoll auswählen:\n• SFTP — verschlüsselt, nutzt SSH (Port 22)\n• FTP — unverschlüsselt (Port 21)\n• FTPS — FTP mit TLS/SSL (Port 21)", "fr": "Sélectionner le protocole de transfert de fichiers :\n• SFTP — chiffré, utilise SSH (port 22)\n• FTP — non chiffré (port 21)\n• FTPS — FTP avec TLS/SSL (port 21)", "es": "Seleccionar el protocolo de transferencia de archivos:\n• SFTP — cifrado, usa SSH (puerto 22)\n• FTP — sin cifrar (puerto 21)\n• FTPS — FTP con TLS/SSL (puerto 21)"},
    "tt.keys_list":   {"it": "Chiavi private trovate in ~/.ssh/. Selezionane una per compilare automaticamente il campo chiave privata", "en": "Private keys found in ~/.ssh/. Select one to automatically fill the private key field", "de": "Private Schlüssel in ~/.ssh/ gefunden. Einen auswählen, um das Feld automatisch auszufüllen", "fr": "Clés privées trouvées dans ~/.ssh/. En sélectionner une pour remplir automatiquement le champ", "es": "Claves privadas encontradas en ~/.ssh/. Selecciona una para rellenar automáticamente el campo"},
    "tt.keys_reload": {"it": "Ricarica la lista delle chiavi presenti in ~/.ssh/", "en": "Reload the list of keys in ~/.ssh/", "de": "Liste der Schlüssel in ~/.ssh/ neu laden", "fr": "Recharger la liste des clés dans ~/.ssh/", "es": "Recargar la lista de claves en ~/.ssh/"},
    "tt.key_type":    {"it": "Algoritmo della nuova chiave:\n• Ed25519 — raccomandato, moderno e sicuro\n• RSA 4096 — compatibile con server più datati\n• ECDSA — alternativa a Ed25519", "en": "New key algorithm:\n• Ed25519 — recommended, modern and secure\n• RSA 4096 — compatible with older servers\n• ECDSA — alternative to Ed25519", "de": "Neuer Schlüsselalgorithmus:\n• Ed25519 — empfohlen, modern und sicher\n• RSA 4096 — kompatibel mit älteren Servern\n• ECDSA — Alternative zu Ed25519", "fr": "Algorithme de la nouvelle clé :\n• Ed25519 — recommandé, moderne et sécurisé\n• RSA 4096 — compatible avec les serveurs plus anciens\n• ECDSA — alternative à Ed25519", "es": "Algoritmo de la nueva clave:\n• Ed25519 — recomendado, moderno y seguro\n• RSA 4096 — compatible con servidores más antiguos\n• ECDSA — alternativa a Ed25519"},
    "tt.key_comment": {"it": "Commento descrittivo incorporato nella chiave pubblica. Utile per identificare la chiave (es. utente@macchina)", "en": "Descriptive comment embedded in the public key. Useful for identifying the key (e.g. user@machine)", "de": "Beschreibender Kommentar im öffentlichen Schlüssel. Nützlich zur Identifizierung (z.B. benutzer@rechner)", "fr": "Commentaire descriptif intégré dans la clé publique. Utile pour identifier la clé (ex. utilisateur@machine)", "es": "Comentario descriptivo incorporado en la clave pública. Útil para identificar la clave (ej. usuario@máquina)"},
    "tt.key_generate":{"it": "Genera una nuova coppia di chiavi SSH (privata + pubblica) nella cartella ~/.ssh/", "en": "Generate a new SSH key pair (private + public) in the ~/.ssh/ folder", "de": "Neues SSH-Schlüsselpaar (privat + öffentlich) im Ordner ~/.ssh/ generieren", "fr": "Générer une nouvelle paire de clés SSH (privée + publique) dans le dossier ~/.ssh/", "es": "Generar un nuevo par de claves SSH (privada + pública) en la carpeta ~/.ssh/"},
    "tt.key_copy_srv":{"it": "Copia la chiave pubblica sul server remoto tramite ssh-copy-id, abilitando l'accesso senza password", "en": "Copy the public key to the remote server via ssh-copy-id, enabling passwordless access", "de": "Öffentlichen Schlüssel via ssh-copy-id auf den Remote-Server kopieren für passwortlosen Zugang", "fr": "Copier la clé publique sur le serveur distant via ssh-copy-id pour un accès sans mot de passe", "es": "Copiar la clave pública al servidor remoto mediante ssh-copy-id para acceso sin contraseña"},
    "tt.key_show_pub":{"it": "Mostra il contenuto della chiave pubblica (.pub) per poterla copiare manualmente", "en": "Show the contents of the public key (.pub) so it can be copied manually", "de": "Inhalt des öffentlichen Schlüssels (.pub) anzeigen zum manuellen Kopieren", "fr": "Afficher le contenu de la clé publique (.pub) pour la copier manuellement", "es": "Mostrar el contenido de la clave pública (.pub) para copiarla manualmente"},
    "tt.serial_dev":  {"it": "Percorso del dispositivo seriale. Es: /dev/ttyUSB0, /dev/ttyACM0, /dev/ttyS0", "en": "Path to the serial device. E.g.: /dev/ttyUSB0, /dev/ttyACM0, /dev/ttyS0", "de": "Pfad zum seriellen Gerät. Z.B.: /dev/ttyUSB0, /dev/ttyACM0, /dev/ttyS0", "fr": "Chemin vers le périphérique série. Ex : /dev/ttyUSB0, /dev/ttyACM0, /dev/ttyS0", "es": "Ruta al dispositivo serie. Ej: /dev/ttyUSB0, /dev/ttyACM0, /dev/ttyS0"},
    "tt.serial_baud": {"it": "Velocità di trasmissione in baud. Deve corrispondere alla configurazione del dispositivo remoto", "en": "Transmission speed in baud. Must match the remote device configuration", "de": "Übertragungsgeschwindigkeit in Baud. Muss mit der Konfiguration des Remote-Geräts übereinstimmen", "fr": "Vitesse de transmission en bauds. Doit correspondre à la configuration du périphérique distant", "es": "Velocidad de transmisión en baudios. Debe coincidir con la configuración del dispositivo remoto"},
    "tt.serial_data": {"it": "Numero di bit dati per carattere. Il valore più comune è 8", "en": "Number of data bits per character. The most common value is 8", "de": "Anzahl der Datenbits pro Zeichen. Der häufigste Wert ist 8", "fr": "Nombre de bits de données par caractère. La valeur la plus courante est 8", "es": "Número de bits de datos por carácter. El valor más común es 8"},
    "tt.serial_parity":{"it": "Controllo di parità. None è il valore più comune per la maggior parte dei dispositivi", "en": "Parity check. None is the most common value for most devices", "de": "Paritätsprüfung. None ist der häufigste Wert für die meisten Geräte", "fr": "Contrôle de parité. None est la valeur la plus courante pour la plupart des appareils", "es": "Control de paridad. None es el valor más común para la mayoría de dispositivos"},
    "tt.serial_stop": {"it": "Bit di stop. Il valore standard è 1", "en": "Stop bits. The standard value is 1", "de": "Stoppbits. Der Standardwert ist 1", "fr": "Bits d'arrêt. La valeur standard est 1", "es": "Bits de parada. El valor estándar es 1"},
    "tt.term_theme":  {"it": "Tema colori del terminale. Scuro (Default) è ottimale per lunghe sessioni", "en": "Terminal color theme. Dark (Default) is optimal for long sessions", "de": "Farbthema des Terminals. Dunkel (Standard) ist optimal für lange Sitzungen", "fr": "Thème de couleurs du terminal. Sombre (Défaut) est optimal pour les longues sessions", "es": "Tema de colores del terminal. Oscuro (Predeterminado) es óptimo para sesiones largas"},
    "tt.term_font":   {"it": "Font del terminale. Usare un font monospazio per la corretta visualizzazione", "en": "Terminal font. Use a monospace font for correct display", "de": "Terminal-Schriftart. Für korrekte Darstellung eine Monospace-Schriftart verwenden", "fr": "Police du terminal. Utiliser une police monospace pour un affichage correct", "es": "Fuente del terminal. Usar una fuente monoespaciada para una visualización correcta"},
    "tt.term_fsize":  {"it": "Dimensione del font in punti. Usa Ctrl+scroll nel terminale per cambiarlo al volo", "en": "Font size in points. Use Ctrl+scroll in the terminal to change it on the fly", "de": "Schriftgröße in Punkt. Im Terminal Ctrl+Scroll verwenden, um sie anzupassen", "fr": "Taille de police en points. Utiliser Ctrl+défilement dans le terminal pour la modifier à la volée", "es": "Tamaño de fuente en puntos. Usa Ctrl+rueda en el terminal para cambiarlo al vuelo"},
    "tt.term_inf_sb": {"it": "Se attivo, il terminale conserva tutta la storia senza limite di righe (usa più memoria RAM)", "en": "If enabled, the terminal keeps full history with no line limit (uses more RAM)", "de": "Wenn aktiviert, behält das Terminal den gesamten Verlauf ohne Zeilenbegrenzung (mehr RAM)", "fr": "Si activé, le terminal conserve tout l'historique sans limite de lignes (utilise plus de RAM)", "es": "Si está activo, el terminal conserva todo el historial sin límite de líneas (usa más RAM)"},
    "tt.term_sb_lines":{"it": "Numero di righe di storia mantenute nel terminale. Valori alti consumano più memoria", "en": "Number of history lines kept in the terminal. Higher values use more memory", "de": "Anzahl der im Terminal gespeicherten Verlaufszeilen. Höhere Werte verbrauchen mehr Speicher", "fr": "Nombre de lignes d'historique conservées dans le terminal. Les valeurs élevées consomment plus de mémoire", "es": "Número de líneas de historial mantenidas en el terminal. Los valores altos consumen más memoria"},
    "tt.term_confirm":{"it": "Chiede conferma prima di chiudere un tab con un processo ancora attivo (es. connessione SSH aperta)", "en": "Asks for confirmation before closing a tab with an active process (e.g. open SSH connection)", "de": "Fragt vor dem Schließen eines Tabs mit aktivem Prozess nach Bestätigung (z.B. offene SSH-Verbindung)", "fr": "Demande une confirmation avant de fermer un onglet avec un processus actif (ex. connexion SSH ouverte)", "es": "Pide confirmación antes de cerrar una pestaña con un proceso activo (ej. conexión SSH abierta)"},
    "tt.term_warn_paste":{"it": "Mostra un avviso quando si incollano più righe contemporaneamente, prevenendo esecuzioni accidentali", "en": "Shows a warning when pasting multiple lines at once, preventing accidental execution", "de": "Zeigt eine Warnung beim Einfügen mehrerer Zeilen gleichzeitig, um versehentliche Ausführung zu verhindern", "fr": "Affiche un avertissement lors du collage de plusieurs lignes à la fois pour éviter les exécutions accidentelles", "es": "Muestra una advertencia al pegar varias líneas a la vez, evitando ejecuciones accidentales"},
    "tt.term_log":    {"it": "Registra tutto l'output del terminale su file nella cartella indicata sotto", "en": "Records all terminal output to a file in the folder specified below", "de": "Zeichnet die gesamte Terminalausgabe in einer Datei im angegebenen Ordner auf", "fr": "Enregistre toute la sortie du terminal dans un fichier dans le dossier indiqué ci-dessous", "es": "Registra toda la salida del terminal en un archivo en la carpeta indicada abajo"},
    "tt.term_log_dir":{"it": "Cartella dove salvare i file di log del terminale. Verrà creata automaticamente se non esiste", "en": "Folder where terminal log files are saved. Will be created automatically if it does not exist", "de": "Ordner zum Speichern der Terminal-Logdateien. Wird automatisch erstellt, falls nicht vorhanden", "fr": "Dossier où enregistrer les fichiers journaux du terminal. Sera créé automatiquement s'il n'existe pas", "es": "Carpeta donde guardar los archivos de registro del terminal. Se creará automáticamente si no existe"},
    "tt.term_paste_r":{"it": "Incolla il contenuto degli appunti con il clic destro del mouse (comportamento stile xterm)", "en": "Paste clipboard contents with right mouse click (xterm-style behaviour)", "de": "Zwischenablageninhalt per Rechtsklick einfügen (xterm-Verhalten)", "fr": "Coller le contenu du presse-papiers avec le clic droit de la souris (comportement style xterm)", "es": "Pegar el contenido del portapapeles con el clic derecho del ratón (comportamiento estilo xterm)"},
    "tt.term_ext":    {"it": "Emulatore di terminale esterno da usare quando la sessione viene aperta in una finestra separata", "en": "External terminal emulator to use when the session is opened in a separate window", "de": "Externer Terminalemulator für Sitzungen in einem separaten Fenster", "fr": "Émulateur de terminal externe à utiliser quand la session s'ouvre dans une fenêtre séparée", "es": "Emulador de terminal externo a usar cuando la sesión se abre en una ventana separada"},
    "tt.ssh_open":    {"it": "Come aprire la sessione SSH:\n• Interno — tab nel pannello principale\n• Esterno — finestra separata nell'emulatore scelto", "en": "How to open the SSH session:\n• Internal — tab in the main panel\n• External — separate window in the chosen emulator", "de": "SSH-Sitzung öffnen:\n• Intern — Tab im Hauptbereich\n• Extern — separates Fenster im gewählten Emulator", "fr": "Comment ouvrir la session SSH :\n• Interne — onglet dans le panneau principal\n• Externe — fenêtre séparée dans l'émulateur choisi", "es": "Cómo abrir la sesión SSH:\n• Interno — pestaña en el panel principal\n• Externo — ventana separada en el emulador elegido"},
    "tt.sftp_open":   {"it": "Come aprire la sessione SFTP:\n• Browser interno — pannello file integrato\n• Browser esterno — file manager di sistema\n• Terminale interno/esterno — client sftp da riga di comando", "en": "How to open the SFTP session:\n• Internal browser — integrated file panel\n• External browser — system file manager\n• Internal/external terminal — sftp command line client", "de": "SFTP-Sitzung öffnen:\n• Interner Browser — integriertes Dateifeld\n• Externer Browser — System-Dateimanager\n• Internes/externes Terminal — sftp-Kommandozeilenclient", "fr": "Comment ouvrir la session SFTP :\n• Navigateur interne — panneau de fichiers intégré\n• Navigateur externe — gestionnaire de fichiers système\n• Terminal interne/externe — client sftp en ligne de commande", "es": "Cómo abrir la sesión SFTP:\n• Navegador interno — panel de archivos integrado\n• Navegador externo — gestor de archivos del sistema\n• Terminal interno/externo — cliente sftp de línea de comandos"},
    "tt.ssh_x11":     {"it": "Abilita il forwarding X11: permette di eseguire applicazioni grafiche remote visualizzandole in locale. Richiede un server X attivo", "en": "Enable X11 forwarding: allows running remote graphical applications displayed locally. Requires an active X server", "de": "X11-Weiterleitung aktivieren: ermöglicht das Ausführen entfernter grafischer Anwendungen lokal. Erfordert einen aktiven X-Server", "fr": "Activer le transfert X11 : permet d'exécuter des applications graphiques distantes affichées localement. Nécessite un serveur X actif", "es": "Habilitar reenvío X11: permite ejecutar aplicaciones gráficas remotas mostrándolas localmente. Requiere un servidor X activo"},
    "tt.ssh_comp":    {"it": "Abilita la compressione del traffico SSH. Utile su connessioni lente, controproducente su reti veloci", "en": "Enable SSH traffic compression. Useful on slow connections, counterproductive on fast networks", "de": "SSH-Verkehrskomprimierung aktivieren. Nützlich bei langsamen Verbindungen, kontraproduktiv bei schnellen Netzwerken", "fr": "Activer la compression du trafic SSH. Utile sur les connexions lentes, contre-productif sur les réseaux rapides", "es": "Habilitar compresión del tráfico SSH. Útil en conexiones lentas, contraproducente en redes rápidas"},
    "tt.ssh_ka":      {"it": "Invia pacchetti keepalive per mantenere attiva la connessione attraverso firewall e NAT", "en": "Sends keepalive packets to keep the connection alive through firewalls and NAT", "de": "Sendet Keepalive-Pakete, um die Verbindung durch Firewalls und NAT aufrechtzuerhalten", "fr": "Envoie des paquets keepalive pour maintenir la connexion active à travers les pare-feu et le NAT", "es": "Envía paquetes keepalive para mantener la conexión activa a través de firewalls y NAT"},
    "tt.ssh_ka_int":  {"it": "Intervallo in secondi tra i pacchetti keepalive. 0 = disabilitato. Valori tipici: 30-120 secondi", "en": "Interval in seconds between keepalive packets. 0 = disabled. Typical values: 30-120 seconds", "de": "Intervall in Sekunden zwischen Keepalive-Paketen. 0 = deaktiviert. Typische Werte: 30-120 Sekunden", "fr": "Intervalle en secondes entre les paquets keepalive. 0 = désactivé. Valeurs typiques : 30-120 secondes", "es": "Intervalo en segundos entre paquetes keepalive. 0 = desactivado. Valores típicos: 30-120 segundos"},
    "tt.ssh_strict":  {"it": "Verifica rigorosa della chiave host del server. Disabilitare solo in ambienti di test controllati", "en": "Strict server host key verification. Disable only in controlled test environments", "de": "Strikte Überprüfung des Server-Host-Schlüssels. Nur in kontrollierten Testumgebungen deaktivieren", "fr": "Vérification stricte de la clé d'hôte du serveur. Désactiver uniquement dans des environnements de test contrôlés", "es": "Verificación estricta de la clave de host del servidor. Deshabilitar solo en entornos de prueba controlados"},
    "tt.ssh_sftp_br": {"it": "Apre automaticamente il browser SFTP laterale quando si connette a questo host via SSH", "en": "Automatically opens the lateral SFTP browser when connecting to this host via SSH", "de": "Öffnet automatisch den seitlichen SFTP-Browser beim Verbinden mit diesem Host über SSH", "fr": "Ouvre automatiquement le navigateur SFTP latéral lors de la connexion à cet hôte via SSH", "es": "Abre automáticamente el navegador SFTP lateral al conectarse a este host mediante SSH"},
    "tt.ssh_startup": {"it": "Comando da eseguire automaticamente all'apertura della sessione SSH. Es: htop, sudo -i, screen -r", "en": "Command to run automatically when the SSH session opens. E.g.: htop, sudo -i, screen -r", "de": "Befehl, der beim Öffnen der SSH-Sitzung automatisch ausgeführt wird. Z.B.: htop, sudo -i, screen -r", "fr": "Commande à exécuter automatiquement à l'ouverture de la session SSH. Ex : htop, sudo -i, screen -r", "es": "Comando a ejecutar automáticamente al abrir la sesión SSH. Ej: htop, sudo -i, screen -r"},
    "tt.jump_host":   {"it": "Host intermedio (bastion/jump server) attraverso cui raggiungere il server finale. Es: bastion.example.com", "en": "Intermediate host (bastion/jump server) through which to reach the final server. E.g.: bastion.example.com", "de": "Zwischenhost (Bastion/Jump-Server) zum Erreichen des Zielservers. Z.B.: bastion.example.com", "fr": "Hôte intermédiaire (bastion/jump server) par lequel atteindre le serveur final. Ex : bastion.example.com", "es": "Host intermedio (bastión/jump server) a través del cual llegar al servidor final. Ej: bastion.example.com"},
    "tt.jump_user":   {"it": "Nome utente per il jump host (se diverso dall'utente principale)", "en": "Username for the jump host (if different from the main user)", "de": "Benutzername für den Jump-Host (falls abweichend vom Hauptbenutzer)", "fr": "Nom d'utilisateur pour le jump host (si différent de l'utilisateur principal)", "es": "Nombre de usuario para el jump host (si es diferente del usuario principal)"},
    "tt.jump_port":   {"it": "Porta SSH del jump host (default 22)", "en": "SSH port of the jump host (default 22)", "de": "SSH-Port des Jump-Hosts (Standard 22)", "fr": "Port SSH du jump host (par défaut 22)", "es": "Puerto SSH del jump host (predeterminado 22)"},
    "tt.rdp_client":  {"it": "Client RDP da usare. xfreerdp3 è la versione più recente e raccomandata", "en": "RDP client to use. xfreerdp3 is the most recent and recommended version", "de": "Zu verwendender RDP-Client. xfreerdp3 ist die neueste und empfohlene Version", "fr": "Client RDP à utiliser. xfreerdp3 est la version la plus récente et recommandée", "es": "Cliente RDP a usar. xfreerdp3 es la versión más reciente y recomendada"},
    "tt.rdp_auth":    {"it": "Metodo di autenticazione RDP:\n• NTLM — standard per ambienti Windows\n• Kerberos — per ambienti con Active Directory", "en": "RDP authentication method:\n• NTLM — standard for Windows environments\n• Kerberos — for Active Directory environments", "de": "RDP-Authentifizierungsmethode:\n• NTLM — Standard für Windows-Umgebungen\n• Kerberos — für Active Directory-Umgebungen", "fr": "Méthode d'authentification RDP :\n• NTLM — standard pour les environnements Windows\n• Kerberos — pour les environnements Active Directory", "es": "Método de autenticación RDP:\n• NTLM — estándar para entornos Windows\n• Kerberos — para entornos con Active Directory"},
    "tt.rdp_domain":  {"it": "Dominio Windows per l'autenticazione. Lasciare vuoto per autenticazione locale", "en": "Windows domain for authentication. Leave empty for local authentication", "de": "Windows-Domäne für die Authentifizierung. Leer lassen für lokale Authentifizierung", "fr": "Domaine Windows pour l'authentification. Laisser vide pour une authentification locale", "es": "Dominio Windows para la autenticación. Dejar vacío para autenticación local"},
    "tt.rdp_fs":      {"it": "Apre la sessione RDP a schermo intero", "en": "Opens the RDP session in full screen", "de": "Öffnet die RDP-Sitzung im Vollbildmodus", "fr": "Ouvre la session RDP en plein écran", "es": "Abre la sesión RDP en pantalla completa"},
    "tt.rdp_clip":    {"it": "Condivide gli appunti tra il computer locale e il desktop remoto", "en": "Shares the clipboard between the local computer and the remote desktop", "de": "Teilt die Zwischenablage zwischen lokalem Computer und Remote-Desktop", "fr": "Partage le presse-papiers entre l'ordinateur local et le bureau distant", "es": "Comparte el portapapeles entre el equipo local y el escritorio remoto"},
    "tt.rdp_drives":  {"it": "Monta la home directory locale (/home) come unità di rete nel desktop remoto", "en": "Mounts the local home directory (/home) as a network drive in the remote desktop", "de": "Bindet das lokale Home-Verzeichnis (/home) als Netzlaufwerk im Remote-Desktop ein", "fr": "Monte le répertoire personnel local (/home) comme lecteur réseau dans le bureau distant", "es": "Monta el directorio personal local (/home) como unidad de red en el escritorio remoto"},
    "tt.rdp_open":    {"it": "Come aprire la sessione RDP:\n• Finestra esterna — xfreerdp nella propria finestra\n• Pannello interno — embedding nel pannello (richiede XWayland)", "en": "How to open the RDP session:\n• External window — xfreerdp in its own window\n• Internal panel — embedding in panel (requires XWayland)", "de": "RDP-Sitzung öffnen:\n• Externes Fenster — xfreerdp in eigenem Fenster\n• Internes Panel — Einbettung ins Panel (erfordert XWayland)", "fr": "Comment ouvrir la session RDP :\n• Fenêtre externe — xfreerdp dans sa propre fenêtre\n• Panneau interne — intégration dans le panneau (nécessite XWayland)", "es": "Cómo abrir la sesión RDP:\n• Ventana externa — xfreerdp en su propia ventana\n• Panel interno — incrustado en el panel (requiere XWayland)"},
    "tt.vnc_mode":    {"it": "Come aprire la sessione VNC:\n• Client esterno — usa il client VNC installato nel sistema\n• gtk-vnc integrato — widget nativo GTK embedded nel pannello (richiede gir1.2-gtk-vnc-2.0)", "en": "How to open the VNC session:\n• External client — uses the VNC client installed on the system\n• Embedded gtk-vnc — native GTK widget embedded in the panel (requires gir1.2-gtk-vnc-2.0)", "de": "VNC-Sitzung öffnen:\n• Externer Client — nutzt den installierten VNC-Client\n• Eingebettetes gtk-vnc — nativer GTK-Widget im Panel (erfordert gir1.2-gtk-vnc-2.0)", "fr": "Comment ouvrir la session VNC :\n• Client externe — utilise le client VNC installé sur le système\n• gtk-vnc intégré — widget GTK natif intégré dans le panneau (nécessite gir1.2-gtk-vnc-2.0)", "es": "Cómo abrir la sesión VNC:\n• Cliente externo — usa el cliente VNC instalado en el sistema\n• gtk-vnc integrado — widget GTK nativo incrustado en el panel (requiere gir1.2-gtk-vnc-2.0)"},
    "tt.vnc_client":  {"it": "Client VNC esterno da usare per la connessione", "en": "External VNC client to use for the connection", "de": "Externer VNC-Client für die Verbindung", "fr": "Client VNC externe à utiliser pour la connexion", "es": "Cliente VNC externo a usar para la conexión"},
    "tt.vnc_color":   {"it": "Profondità colore della sessione VNC. 32bpp è la qualità migliore, 8bpp è il più veloce", "en": "Color depth of the VNC session. 32bpp is the best quality, 8bpp is the fastest", "de": "Farbtiefe der VNC-Sitzung. 32bpp ist die beste Qualität, 8bpp die schnellste", "fr": "Profondeur de couleur de la session VNC. 32bpp est la meilleure qualité, 8bpp est le plus rapide", "es": "Profundidad de color de la sesión VNC. 32bpp es la mejor calidad, 8bpp es el más rápido"},
    "tt.vnc_quality": {"it": "Qualità di compressione video VNC. Alta qualità = più dettagli ma più banda; Veloce = meno banda ma artefatti", "en": "VNC video compression quality. High quality = more detail but more bandwidth; Fast = less bandwidth but artefacts", "de": "VNC-Videokomprimierungsqualität. Hohe Qualität = mehr Details aber mehr Bandbreite; Schnell = weniger Bandbreite aber Artefakte", "fr": "Qualité de compression vidéo VNC. Haute qualité = plus de détails mais plus de bande passante ; Rapide = moins de bande passante mais artefacts", "es": "Calidad de compresión de video VNC. Alta calidad = más detalles pero más ancho de banda; Rápido = menos ancho de banda pero artefactos"},
    "tt.ftp_tls":     {"it": "Abilita TLS/SSL per cifrare la connessione FTP (FTPS). Raccomandato se il server lo supporta", "en": "Enable TLS/SSL to encrypt the FTP connection (FTPS). Recommended if the server supports it", "de": "TLS/SSL zur Verschlüsselung der FTP-Verbindung (FTPS) aktivieren. Empfohlen wenn der Server es unterstützt", "fr": "Activer TLS/SSL pour chiffrer la connexion FTP (FTPS). Recommandé si le serveur le supporte", "es": "Habilitar TLS/SSL para cifrar la conexión FTP (FTPS). Recomendado si el servidor lo soporta"},
    "tt.ftp_passive": {"it": "Usa la modalità passiva FTP. Necessaria nella maggior parte delle reti con firewall o NAT", "en": "Use passive FTP mode. Necessary in most networks with firewalls or NAT", "de": "Passiven FTP-Modus verwenden. Notwendig in den meisten Netzwerken mit Firewalls oder NAT", "fr": "Utiliser le mode FTP passif. Nécessaire dans la plupart des réseaux avec pare-feu ou NAT", "es": "Usar modo FTP pasivo. Necesario en la mayoría de redes con firewalls o NAT"},
    "tt.ftp_open":    {"it": "Come aprire la sessione FTP:\n• Browser interno — pannello file integrato\n• Browser esterno — file manager di sistema\n• Terminale interno/esterno — client lftp da riga di comando", "en": "How to open the FTP session:\n• Internal browser — integrated file panel\n• External browser — system file manager\n• Internal/external terminal — lftp command line client", "de": "FTP-Sitzung öffnen:\n• Interner Browser — integriertes Dateifeld\n• Externer Browser — System-Dateimanager\n• Internes/externes Terminal — lftp-Kommandozeilenclient", "fr": "Comment ouvrir la session FTP :\n• Navigateur interne — panneau de fichiers intégré\n• Navigateur externe — gestionnaire de fichiers système\n• Terminal interne/externe — client lftp en ligne de commande", "es": "Cómo abrir la sesión FTP:\n• Navegador interno — panel de archivos integrado\n• Navegador externo — gestor de archivos del sistema\n• Terminal interno/externo — cliente lftp de línea de comandos"},
    "tt.wol_enable":  {"it": "Invia un Magic Packet per accendere il computer remoto prima di connettersi", "en": "Sends a Magic Packet to power on the remote computer before connecting", "de": "Sendet ein Magic Packet, um den Remote-Computer vor der Verbindung einzuschalten", "fr": "Envoie un Magic Packet pour allumer l'ordinateur distant avant de se connecter", "es": "Envía un Magic Packet para encender el equipo remoto antes de conectarse"},
    "tt.wol_mac":     {"it": "Indirizzo MAC del computer da svegliare. Formato: AA:BB:CC:DD:EE:FF", "en": "MAC address of the computer to wake up. Format: AA:BB:CC:DD:EE:FF", "de": "MAC-Adresse des aufzuweckenden Computers. Format: AA:BB:CC:DD:EE:FF", "fr": "Adresse MAC de l'ordinateur à réveiller. Format : AA:BB:CC:DD:EE:FF", "es": "Dirección MAC del equipo a despertar. Formato: AA:BB:CC:DD:EE:FF"},
    "tt.wol_wait":    {"it": "Secondi di attesa dopo l'invio del Magic Packet prima di tentare la connessione. Lasciare tempo al computer di avviarsi", "en": "Seconds to wait after sending the Magic Packet before attempting to connect. Allow time for the computer to boot", "de": "Sekunden Wartezeit nach dem Senden des Magic Packets vor dem Verbindungsversuch. Zeit zum Hochfahren geben", "fr": "Secondes d'attente après l'envoi du Magic Packet avant de tenter la connexion. Laisser le temps au PC de démarrer", "es": "Segundos de espera tras enviar el Magic Packet antes de intentar conectarse. Dar tiempo al equipo para arrancar"},
    "tt.precmd":      {"it": "Comando locale da eseguire prima di aprire la connessione. Es: per attivare una VPN prima di connettersi via SSH", "en": "Local command to run before opening the connection. E.g.: to activate a VPN before connecting via SSH", "de": "Lokaler Befehl vor dem Öffnen der Verbindung. Z.B.: VPN aktivieren, bevor SSH-Verbindung hergestellt wird", "fr": "Commande locale à exécuter avant d'ouvrir la connexion. Ex : pour activer un VPN avant de se connecter via SSH", "es": "Comando local a ejecutar antes de abrir la conexión. Ej: para activar una VPN antes de conectarse por SSH"},
    "tt.precmd_to":   {"it": "Secondi di attesa massimi per il completamento del pre-comando. Se supera il timeout la connessione viene annullata", "en": "Maximum seconds to wait for the pre-command to complete. If the timeout is exceeded the connection is cancelled", "de": "Maximale Wartezeit für den Abschluss des Vorbefehls. Bei Überschreitung des Timeouts wird die Verbindung abgebrochen", "fr": "Secondes d'attente maximales pour la fin du pré-commande. Si le délai est dépassé, la connexion est annulée", "es": "Segundos máximos de espera para que el pre-comando termine. Si supera el tiempo límite, la conexión se cancela"},
    "tt.tunnel_type": {"it": "Tipo di tunnel SSH:\n• Proxy SOCKS (-D) — proxy locale per tutto il traffico\n• Locale (-L) — porta locale → porta remota\n• Remoto (-R) — porta remota → porta locale", "en": "SSH tunnel type:\n• SOCKS proxy (-D) — local proxy for all traffic\n• Local (-L) — local port → remote port\n• Remote (-R) — remote port → local port", "de": "SSH-Tunneltyp:\n• SOCKS-Proxy (-D) — lokaler Proxy für gesamten Datenverkehr\n• Lokal (-L) — lokaler Port → Remote-Port\n• Remote (-R) — Remote-Port → lokaler Port", "fr": "Type de tunnel SSH :\n• Proxy SOCKS (-D) — proxy local pour tout le trafic\n• Local (-L) — port local → port distant\n• Distant (-R) — port distant → port local", "es": "Tipo de túnel SSH:\n• Proxy SOCKS (-D) — proxy local para todo el tráfico\n• Local (-L) — puerto local → puerto remoto\n• Remoto (-R) — puerto remoto → puerto local"},
    "tt.tunnel_lport":{"it": "Porta locale su cui il tunnel sarà in ascolto", "en": "Local port on which the tunnel will listen", "de": "Lokaler Port, auf dem der Tunnel lauscht", "fr": "Port local sur lequel le tunnel sera en écoute", "es": "Puerto local en el que el túnel estará escuchando"},
    "tt.tunnel_rhost":{"it": "Host remoto destinazione del tunnel (per -L e -R). Es: database.interno.lan", "en": "Remote destination host of the tunnel (for -L and -R). E.g.: database.internal.lan", "de": "Entfernter Zielhost des Tunnels (für -L und -R). Z.B.: datenbank.intern.lan", "fr": "Hôte distant de destination du tunnel (pour -L et -R). Ex : base-de-données.interne.lan", "es": "Host remoto de destino del túnel (para -L y -R). Ej: base-datos.interna.lan"},
    "tt.tunnel_rport":{"it": "Porta remota di destinazione del tunnel", "en": "Remote destination port of the tunnel", "de": "Entfernter Zielport des Tunnels", "fr": "Port distant de destination du tunnel", "es": "Puerto remoto de destino del túnel"},
}
