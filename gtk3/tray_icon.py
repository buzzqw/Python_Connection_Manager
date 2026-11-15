"""tray_icon.py - Icona nel system tray per PCM.

Usa AyatanaAppIndicator/AppIndicator quando disponibile (integrazione nativa
con GNOME/KDE e Wayland), con fallback a Gtk.StatusIcon sui desktop classici.

Il modulo non importa GTK al caricamento: la scelta del backend avviene in
TrayIcon.__init__, così i test possono usare session_menu_entries() senza
un display grafico.
"""

import importlib
import os

from pcm_logging import get_logger

_log = get_logger("pcm.tray")


# ---------------------------------------------------------------------------
# Composizione del menu sessioni (funzione pura, testabile)
# ---------------------------------------------------------------------------

def session_menu_entries(profiles: dict, recent_names, max_recent: int = 8,
                         max_total: int = 20) -> list:
    """Restituisce le voci del sottomenu "Connetti a…".

    Prima le sessioni usate di recente (max_recent), poi le altre in ordine
    alfabetico fino a max_total voci complessive. L'ultima voce può essere
    ("more", n) quando restano sessioni non mostrate.

    Ogni voce sessione è ("session", nome).
    """
    validi = {n: p for n, p in profiles.items()
              if isinstance(p, dict) and not str(n).startswith("_")}
    if not validi:
        return []

    recenti = []
    visti = set()
    for nome in recent_names or []:
        if nome in validi and nome not in visti:
            recenti.append(nome)
            visti.add(nome)

    voci = [("session", n) for n in recenti[:max_recent]]
    restanti = [n for n in sorted(validi) if n not in visti]

    # max_total conta le sessioni mostrate, non i separatori.
    posti = max(0, max_total - len(voci))
    if restanti:
        if voci:
            voci.append(("separator", None))
        da_mostrare = restanti[:posti]
        voci.extend(("session", n) for n in da_mostrare)
        if len(restanti) > len(da_mostrare):
            voci.append(("separator", None))
            voci.append(("more", len(restanti) - len(da_mostrare)))

    return voci


# ---------------------------------------------------------------------------
# Wrapper backend
# ---------------------------------------------------------------------------

class TrayIcon:
    """Piccola astrazione su AppIndicator/Gtk.StatusIcon."""

    def __init__(self, icon_path: str, tooltip: str):
        self._icon_path = icon_path
        self._tooltip = tooltip
        self._menu = None
        self._activate_cb = None
        self._backend = None
        self._indicator = None
        self._indicator_mod = None
        self._status_icon = None
        self._pixbuf = None

        if not self._create_backend():
            raise RuntimeError("Nessun backend system tray disponibile")

    # -- creazione ---------------------------------------------------------

    @staticmethod
    def _load_gi():
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GdkPixbuf  # noqa: F401
        return Gtk, GdkPixbuf

    def _create_backend(self) -> bool:
        if self._create_appindicator():
            return True
        return self._create_status_icon()

    def _create_appindicator(self) -> bool:
        for namespace in ("AyatanaAppIndicator3", "AppIndicator3"):
            try:
                import gi
                gi.require_version(namespace, "0.1")
                mod = importlib.import_module(f"gi.repository.{namespace}")
            except Exception:
                continue

            try:
                indicator = mod.Indicator.new(
                    "it.pcm.connectionmanager",
                    "pcm_icon",
                    mod.IndicatorCategory.APPLICATION_STATUS,
                )
                indicator.set_icon_theme_path(os.path.dirname(self._icon_path))
                indicator.set_title(self._tooltip)
                indicator.set_icon_full("pcm_icon", self._tooltip)
                indicator.set_status(mod.IndicatorStatus.ACTIVE)
                self._indicator = indicator
                self._indicator_mod = mod
                self._backend = "appindicator"
                _log.info("Tray: backend %s", namespace)
                return True
            except Exception as e:
                _log.debug("Tray: %s non utilizzabile: %s", namespace, e)

        return False

    @staticmethod
    def _status_icon_supported_host() -> bool:
        """Gtk.StatusIcon non funziona su Wayland e GNOME senza estensione."""
        backend = os.environ.get("GDK_BACKEND", "").lower()
        on_wayland = (backend == "wayland" or
                      (os.environ.get("WAYLAND_DISPLAY") and backend != "x11"))
        if on_wayland:
            return False
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "gnome" in desktop or "unity" in desktop:
            return False
        return True

    def _create_status_icon(self) -> bool:
        if not self._status_icon_supported_host():
            _log.debug("Tray: Gtk.StatusIcon non supportato su questo desktop")
            return False
        try:
            Gtk, GdkPixbuf = self._load_gi()
            if not hasattr(Gtk, "StatusIcon"):
                return False
            self._pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                self._icon_path, 22, 22)
            icon = Gtk.StatusIcon.new_from_pixbuf(self._pixbuf)
            icon.set_tooltip_text(self._tooltip)
            icon.connect("activate", self._on_status_activate)
            icon.connect("popup-menu", self._on_status_popup)
            icon.set_visible(True)
            self._status_icon = icon
            self._backend = "statusicon"
            _log.info("Tray: backend Gtk.StatusIcon")
            return True
        except Exception as e:
            _log.debug("Tray: Gtk.StatusIcon non utilizzabile: %s", e)
            return False

    # -- API ---------------------------------------------------------------

    @property
    def backend(self) -> str:
        return self._backend or ""

    def set_activate_callback(self, callback):
        """Callback per il clic primario (solo Gtk.StatusIcon)."""
        self._activate_cb = callback

    def set_menu(self, menu):
        self._menu = menu
        if self._menu is not None:
            self._menu.show_all()
        if self._indicator is not None:
            self._indicator.set_menu(menu)

    def set_tooltip(self, text: str):
        self._tooltip = text
        if self._indicator is not None:
            self._indicator.set_title(text)
        if self._status_icon is not None:
            self._status_icon.set_tooltip_text(text)

    def set_visible(self, visible: bool):
        if self._indicator is not None and self._indicator_mod is not None:
            try:
                status = (self._indicator_mod.IndicatorStatus.ACTIVE if visible
                          else self._indicator_mod.IndicatorStatus.PASSIVE)
                self._indicator.set_status(status)
            except Exception as e:
                _log.debug("Tray: cambio stato fallito: %s", e)
        if self._status_icon is not None:
            self._status_icon.set_visible(visible)

    def destroy(self):
        self.set_visible(False)
        self._indicator = None
        self._indicator_mod = None
        self._status_icon = None
        self._menu = None
        self._pixbuf = None
        self._backend = None

    # -- callback Gtk.StatusIcon ------------------------------------------

    def _on_status_activate(self, *_args):
        cb = self._activate_cb
        if cb:
            cb()

    def _on_status_popup(self, icon, button, activate_time):
        menu = self._menu
        if menu is None:
            return
        try:
            from gi.repository import Gtk
            menu.popup(None, None, Gtk.StatusIcon.position_menu,
                       icon, button, activate_time)
        except Exception as e:
            _log.debug("Tray: popup menu fallito: %s", e)
