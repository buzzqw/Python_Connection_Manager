"""Test per il menu sessioni del system tray."""

from tray_icon import session_menu_entries
from translations import _T as TRANSLATIONS
from config_manager import DEFAULT_SETTINGS


def _profiles(n=5):
    return {
        f"S{i}": {"protocol": "ssh", "host": f"host{i}"}
        for i in range(n)
    }


class TestSessionMenuEntries:
    def test_empty_profiles(self):
        assert session_menu_entries({}, []) == []

    def test_ignores_internal_and_invalid_profiles(self):
        profiles = {
            "_corrupted": {"host": "x"},
            "_error": "boom",
            "buona": {"host": "ok"},
            "non_dict": "nope",
        }
        assert session_menu_entries(profiles, []) == [("session", "buona")]

    def test_recent_first_and_deduplicated(self):
        entries = session_menu_entries(_profiles(4), ["S2", "S0", "S2", "missing"])
        nomi = [v for k, v in entries if k == "session"]
        assert nomi[:2] == ["S2", "S0"]
        assert len(nomi) == len(set(nomi))

    def test_remaining_in_alphabetical_order(self):
        entries = session_menu_entries(_profiles(4), ["S3"])
        nomi = [v for k, v in entries if k == "session"]
        assert nomi == ["S3", "S0", "S1", "S2"]

    def test_separator_between_recent_and_rest(self):
        entries = session_menu_entries(_profiles(3), ["S2"])
        assert ("separator", None) in entries

    def test_total_limit_and_more_entry(self):
        profiles = _profiles(30)
        entries = session_menu_entries(profiles, [], max_total=20)
        nomi = [v for k, v in entries if k == "session"]
        assert len(nomi) == 20
        more = [v for k, v in entries if k == "more"]
        assert more == [10]
        assert ("separator", None) in entries

    def test_recent_limit(self):
        profiles = _profiles(20)
        entries = session_menu_entries(profiles, [f"S{i}" for i in range(20)],
                                       max_recent=8, max_total=20)
        nomi = [v for k, v in entries if k == "session"]
        assert nomi[:8] == [f"S{i}" for i in range(8)]


class TestTrayTranslations:
    KEYS = (
        "tray.show",
        "tray.connect_to",
        "tray.new_session",
        "tray.local_terminal",
        "tray.quit",
        "tray.no_sessions",
        "tray.more_sessions",
        "tray.session_missing",
        "tray.running_msg",
        "close.minimize_tray",
        "settings.general.tray_enabled",
        "settings.general.tray_enabled_tt",
    )

    def test_all_languages_present(self):
        for key in self.KEYS:
            entry = TRANSLATIONS.get(key)
            assert entry, f"chiave mancante: {key}"
            for lang in ("it", "en", "de", "fr", "es"):
                assert entry.get(lang), f"{key} senza traduzione {lang}"


class TestTraySetting:
    def test_tray_enabled_by_default(self):
        assert DEFAULT_SETTINGS["general"]["tray_enabled"] is True
