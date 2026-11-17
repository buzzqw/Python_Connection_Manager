"""
test_terminal_search_f3.py - Test per la navigazione dei risultati di ricerca
nel terminale (F3 / Shift+F3) e per il flush della ricerca su Invio/F3.
"""

import types

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk

from terminal_widget import TerminalWidget


class _FakeBarra:
    """Sostituto minimo di TerminalWidget per i gestori dei tasti."""

    def __init__(self, aperta=True):
        self._search_bar = types.SimpleNamespace(
            get_search_mode=lambda: aperta)
        self.chiamate = []

    def _cerca_avanti(self):
        self.chiamate.append("next")

    def _cerca_indietro(self):
        self.chiamate.append("prev")


class _FakeFlush:
    """Sostituto minimo per _flush_ricerca."""

    _search_timer = None

    def __init__(self, ultima, testo="foo", case=False, regex=False):
        self._ultima_ricerca = ultima
        self._search_entry = types.SimpleNamespace(get_text=lambda: testo)
        self._chk_case = types.SimpleNamespace(get_active=lambda: case)
        self._chk_regex = types.SimpleNamespace(get_active=lambda: regex)
        self.aggiornamenti = 0

    def _aggiorna_ricerca(self):
        self.aggiornamenti += 1


def _evento(keyval, state=0):
    ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    ev.keyval = keyval
    ev.state = state
    return ev


class TestF3Ricerca:
    def test_f3_va_al_risultato_successivo(self):
        fake = _FakeBarra(aperta=True)
        assert TerminalWidget._on_searchbar_key_press(
            fake, None, _evento(Gdk.KEY_F3)) is True
        assert fake.chiamate == ["next"]

    def test_shift_f3_va_al_risultato_precedente(self):
        fake = _FakeBarra(aperta=True)
        assert TerminalWidget._on_searchbar_key_press(
            fake, None,
            _evento(Gdk.KEY_F3, Gdk.ModifierType.SHIFT_MASK)) is True
        assert fake.chiamate == ["prev"]

    def test_f3_a_barra_chiusa_non_intercettato(self):
        """A barra chiusa F3 deve arrivare ai programmi nel terminale (es. mc)."""
        fake = _FakeBarra(aperta=False)
        assert TerminalWidget._on_searchbar_key_press(
            fake, None, _evento(Gdk.KEY_F3)) is False
        assert fake.chiamate == []

    def test_f3_con_ctrl_non_intercettato(self):
        fake = _FakeBarra(aperta=True)
        assert TerminalWidget._on_searchbar_key_press(
            fake, None,
            _evento(Gdk.KEY_F3, Gdk.ModifierType.CONTROL_MASK)) is False
        assert fake.chiamate == []


class TestFlushRicerca:
    def test_flush_aggiorna_se_il_testo_e_cambiato(self):
        """Gtk.SearchEntry emette search-changed in ritardo: Invio/F3 devono
        applicare subito il testo digitato anche se il timer non è scattato."""
        fake = _FakeFlush(ultima=None, testo="foo")
        TerminalWidget._flush_ricerca(fake)
        assert fake.aggiornamenti == 1

    def test_flush_non_ripete_la_stessa_ricerca(self):
        fake = _FakeFlush(ultima=("foo", False, False), testo="foo")
        TerminalWidget._flush_ricerca(fake)
        assert fake.aggiornamenti == 0

    def test_flush_riapplica_dopo_cambio_opzioni(self):
        fake = _FakeFlush(ultima=("foo", False, False), testo="foo", case=True)
        TerminalWidget._flush_ricerca(fake)
        assert fake.aggiornamenti == 1
