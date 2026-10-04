"""
test_cron_explainer.py - Test per la spiegazione human-readable delle espressioni cron.
"""

from cron_explainer import spiega_cron


class TestCronExplainer:
    def test_shortcuts(self):
        assert "avvio" in spiega_cron("@reboot", lang="it").lower()
        assert "startup" in spiega_cron("@reboot", lang="en").lower()

        assert "mezzanotte" in spiega_cron("@daily", lang="it").lower()
        assert "midnight" in spiega_cron("@daily", lang="en").lower()

        assert "domenica" in spiega_cron("@weekly", lang="it").lower()
        assert "sunday" in spiega_cron("@weekly", lang="en").lower()

        assert "1°" in spiega_cron("@monthly", lang="it")
        assert "day 1" in spiega_cron("@monthly", lang="en").lower()

        assert "gennaio" in spiega_cron("@yearly", lang="it").lower()
        assert "january" in spiega_cron("@yearly", lang="en").lower()

    def test_wildcards_and_intervals(self):
        assert spiega_cron("* * * * *", lang="it") == "Ogni minuto"
        assert spiega_cron("* * * * *", lang="en") == "Every minute"

        assert spiega_cron("*/10 * * * *", lang="it") == "Ogni 10 minuti"
        assert spiega_cron("*/5 * * * *", lang="en") == "Every 5 minutes"

        assert "ogni ora" in spiega_cron("0 * * * *", lang="it").lower()
        assert "every hour" in spiega_cron("0 * * * *", lang="en").lower()

        assert "ogni 3 ore" in spiega_cron("0 */3 * * *", lang="it").lower()
        assert "every 3 hours" in spiega_cron("0 */3 * * *", lang="en").lower()

    def test_specific_time_and_days(self):
        # Specific time every day
        s = spiega_cron("30", "4", "*", "*", "*", lang="it")
        assert "04:30" in s
        assert "ogni giorno" in s.lower()

        # Monday through Friday
        s_workdays = spiega_cron("0", "2", "*", "*", "1-5", lang="it")
        assert "02:00" in s_workdays
        assert "lunedì al venerdì" in s_workdays.lower()

        s_workdays_en = spiega_cron("0", "2", "*", "*", "1-5", lang="en")
        assert "02:00" in s_workdays_en
        assert "monday through friday" in s_workdays_en.lower()

        # Weekend
        s_we = spiega_cron("0", "12", "*", "*", "0,6", lang="it")
        assert "fine settimana" in s_we.lower()

        # Specific day of week (e.g. 0 = Sunday)
        s_sun = spiega_cron("0", "8", "*", "*", "0", lang="it")
        assert "domenica" in s_sun.lower()

        # Day of month
        s_dom = spiega_cron("0", "0", "15", "*", "*", lang="it")
        assert "15" in s_dom
        assert "mese" in s_dom.lower()

    def test_all_supported_languages(self):
        for lang in ("it", "en", "de", "fr", "es"):
            res = spiega_cron("*/15 * * * *", lang=lang)
            assert "15" in res
            assert len(res) > 5
