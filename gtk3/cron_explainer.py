"""
cron_explainer.py - Traduzione ed interpretazione human-readable delle espressioni cron.
Supporta:
  • Shortcut standard (@reboot, @daily, @hourly, @weekly, @monthly, @yearly)
  • Espressioni a 5 campi (minuto, ora, giorno del mese, mese, giorno della settimana)
  • Multilingua (it, en, de, fr, es)
"""

from __future__ import annotations

import re

try:
    import translations
    _GET_LANG = translations.get_lang
except (ImportError, AttributeError):
    _GET_LANG = lambda: "it"


_DAYS = {
    "it": {0: "domenica", 1: "lunedì", 2: "martedì", 3: "mercoledì", 4: "giovedì", 5: "venerdì", 6: "sabato", 7: "domenica"},
    "en": {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"},
    "de": {0: "Sonntag", 1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag", 6: "Samstag", 7: "Sonntag"},
    "fr": {0: "dimanche", 1: "lundi", 2: "mardi", 3: "mercredi", 4: "jeudi", 5: "vendredi", 6: "samedi", 7: "dimanche"},
    "es": {0: "domingo", 1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 7: "domingo"},
}

_MONTHS = {
    "it": {1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"},
    "en": {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"},
    "de": {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni", 7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"},
    "fr": {1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin", 7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"},
    "es": {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio", 7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"},
}

_SHORTCUTS = {
    "@reboot": {
        "it": "All'avvio del sistema",
        "en": "At system startup",
        "de": "Beim Systemstart",
        "fr": "Au démarrage du système",
        "es": "Al inicio del sistema",
    },
    "@hourly": {
        "it": "Ogni ora (:00)",
        "en": "Every hour (:00)",
        "de": "Jede Stunde (:00)",
        "fr": "Toutes les heures (:00)",
        "es": "Cada hora (:00)",
    },
    "@daily": {
        "it": "Ogni giorno a mezzanotte (00:00)",
        "en": "Every day at midnight (00:00)",
        "de": "Jeden Tag um Mitternacht (00:00)",
        "fr": "Tous les jours à minuit (00:00)",
        "es": "Todos los días a medianoche (00:00)",
    },
    "@midnight": {
        "it": "Ogni giorno a mezzanotte (00:00)",
        "en": "Every day at midnight (00:00)",
        "de": "Jeden Tag um Mitternacht (00:00)",
        "fr": "Tous les jours à minuit (00:00)",
        "es": "Todos los días a medianoche (00:00)",
    },
    "@weekly": {
        "it": "Ogni domenica a mezzanotte (00:00)",
        "en": "Every Sunday at midnight (00:00)",
        "de": "Jeden Sonntag um Mitternacht (00:00)",
        "fr": "Tous les dimanches à minuit (00:00)",
        "es": "Cada domingo a medianoche (00:00)",
    },
    "@monthly": {
        "it": "Il 1° giorno del mese alle 00:00",
        "en": "On day 1 of every month at 00:00",
        "de": "Am 1. Tag des Monats um 00:00",
        "fr": "Le 1er du mois à 00:00",
        "es": "El día 1 del mes a las 00:00",
    },
    "@yearly": {
        "it": "Il 1° gennaio alle 00:00",
        "en": "On January 1st at 00:00",
        "de": "Am 1. Januar um 00:00",
        "fr": "Le 1er janvier à 00:00",
        "es": "El 1 de enero a las 00:00",
    },
    "@annually": {
        "it": "Il 1° gennaio alle 00:00",
        "en": "On January 1st at 00:00",
        "de": "Am 1. Januar um 00:00",
        "fr": "Le 1er janvier à 00:00",
        "es": "El 1 de enero a las 00:00",
    },
}


def _desc_dow(dow: str, lang: str) -> str:
    """Descrizione human-readable per giorno della settimana."""
    dow = dow.strip()
    if dow == "*":
        return ""
    if dow in ("1-5", "1,2,3,4,5"):
        return {
            "it": "dal lunedì al venerdì",
            "en": "Monday through Friday",
            "de": "Montag bis Freitag",
            "fr": "du lundi au vendredi",
            "es": "de lunes a viernes",
        }.get(lang, "Monday through Friday")
    if dow in ("0,6", "6,0", "0,7", "7,6", "6,7"):
        return {
            "it": "nel fine settimana",
            "en": "on weekends",
            "de": "am Wochenende",
            "fr": "le week-end",
            "es": "los fines de semana",
        }.get(lang, "on weekends")

    # Singolo giorno numerico
    if dow.isdigit():
        d_int = int(dow)
        nome = _DAYS.get(lang, _DAYS["en"]).get(d_int, str(d_int))
        return {
            "it": f"ogni {nome}",
            "en": f"every {nome}",
            "de": f"jeden {nome}",
            "fr": f"chaque {nome}",
            "es": f"cada {nome}",
        }.get(lang, f"every {nome}")

    return {
        "it": f"giorno sett. {dow}",
        "en": f"day of week {dow}",
        "de": f"Wochentag {dow}",
        "fr": f"jour sem. {dow}",
        "es": f"día sem. {dow}",
    }.get(lang, f"day of week {dow}")


def _desc_dom(dom: str, lang: str) -> str:
    """Descrizione human-readable per giorno del mese."""
    dom = dom.strip()
    if dom == "*":
        return ""
    if dom == "1":
        return {
            "it": "il 1° del mese",
            "en": "on the 1st of the month",
            "de": "am 1. des Monats",
            "fr": "le 1er du mois",
            "es": "el día 1 del mes",
        }.get(lang, "on the 1st of the month")
    if dom.isdigit():
        return {
            "it": f"il giorno {dom} del mese",
            "en": f"on day {dom} of the month",
            "de": f"am {dom}. des Monats",
            "fr": f"le {dom} du mois",
            "es": f"el día {dom} del mes",
        }.get(lang, f"on day {dom} of the month")
    return {
        "it": f"giorno del mese {dom}",
        "en": f"day of month {dom}",
        "de": f"Tag des Monats {dom}",
        "fr": f"jour du mois {dom}",
        "es": f"día del mes {dom}",
    }.get(lang, f"day of month {dom}")


def _desc_mon(mon: str, lang: str) -> str:
    """Descrizione human-readable per mese."""
    mon = mon.strip()
    if mon == "*":
        return ""
    if mon.isdigit():
        m_int = int(mon)
        nome = _MONTHS.get(lang, _MONTHS["en"]).get(m_int, str(m_int))
        return {
            "it": f"a {nome}",
            "en": f"in {nome}",
            "de": f"im {nome}",
            "fr": f"en {nome}",
            "es": f"en {nome}",
        }.get(lang, f"in {nome}")
    return {
        "it": f"nel mese {mon}",
        "en": f"in month {mon}",
        "de": f"im Monat {mon}",
        "fr": f"au mois {mon}",
        "es": f"en el mes {mon}",
    }.get(lang, f"in month {mon}")


def spiega_cron(
    min_f: str,
    hour_f: str | None = None,
    dom_f: str | None = None,
    mon_f: str | None = None,
    dow_f: str | None = None,
    lang: str | None = None,
) -> str:
    """
    Ritorna una spiegazione chiara e naturale dell'espressione cron fornita.
    Supporta shortcut (passati nel primo parametro) oppure i 5 campi separati.
    """
    if lang is None:
        lang = _GET_LANG() or "it"
    if lang not in ("it", "en", "de", "fr", "es"):
        lang = "en"

    # Gestione shortcut (@reboot, @daily, ecc.)
    token = min_f.strip()
    if token.startswith("@") or hour_f is None:
        sc = token.lower()
        if sc in _SHORTCUTS:
            return _SHORTCUTS[sc].get(lang, _SHORTCUTS[sc]["en"])
        # Se passata una riga con 5 token separati da spazi
        parts = token.split()
        if len(parts) == 5:
            min_f, hour_f, dom_f, mon_f, dow_f = parts
        else:
            return token

    min_s = (min_f or "*").strip()
    hour_s = (hour_f or "*").strip()
    dom_s = (dom_f or "*").strip()
    mon_s = (mon_f or "*").strip()
    dow_s = (dow_f or "*").strip()

    # Pattern ultra-comuni
    # 1. * * * * *
    if min_s == "*" and hour_s == "*" and dom_s == "*" and mon_s == "*" and dow_s == "*":
        return {
            "it": "Ogni minuto",
            "en": "Every minute",
            "de": "Jede Minute",
            "fr": "Chaque minute",
            "es": "Cada minuto",
        }.get(lang, "Every minute")

    # 2. */N * * * *
    m_step_min = re.match(r"^\*/(\d+)$", min_s)
    if m_step_min and hour_s == "*" and dom_s == "*" and mon_s == "*" and dow_s == "*":
        n = m_step_min.group(1)
        return {
            "it": f"Ogni {n} minuti",
            "en": f"Every {n} minutes",
            "de": f"Alle {n} Minuten",
            "fr": f"Toutes les {n} minutes",
            "es": f"Cada {n} minutos",
        }.get(lang, f"Every {n} minutes")

    # 3. 0 * * * *
    if min_s == "0" and hour_s == "*" and dom_s == "*" and mon_s == "*" and dow_s == "*":
        return {
            "it": "Ogni ora all'inizio dell'ora (:00)",
            "en": "Every hour at minute :00",
            "de": "Jede Stunde zur Minute :00",
            "fr": "Toutes les heures à la minute :00",
            "es": "Cada hora en el minuto :00",
        }.get(lang, "Every hour at minute :00")

    # 4. 0 */N * * *
    m_step_hour = re.match(r"^\*/(\d+)$", hour_s)
    if min_s == "0" and m_step_hour and dom_s == "*" and mon_s == "*" and dow_s == "*":
        n = m_step_hour.group(1)
        return {
            "it": f"Ogni {n} ore al minuto :00",
            "en": f"Every {n} hours at minute :00",
            "de": f"Alle {n} Stunden zur Minute :00",
            "fr": f"Toutes les {n} heures à la minute :00",
            "es": f"Cada {n} horas en el minuto :00",
        }.get(lang, f"Every {n} hours at minute :00")

    # Costruzione componibile
    parti_tempo: list[str] = []
    
    # Orario
    if min_s.isdigit() and hour_s.isdigit():
        hh = int(hour_s)
        mm = int(min_s)
        time_str = f"{hh:02d}:{mm:02d}"
        t_at = {
            "it": f"alle {time_str}",
            "en": f"at {time_str}",
            "de": f"um {time_str}",
            "fr": f"à {time_str}",
            "es": f"a las {time_str}",
        }.get(lang, f"at {time_str}")
        parti_tempo.append(t_at)
    elif min_s.isdigit() and hour_s == "*":
        t_at_m = {
            "it": f"al minuto {min_s} di ogni ora",
            "en": f"at minute {min_s} of every hour",
            "de": f"zur Minute {min_s} jeder Stunde",
            "fr": f"à la minute {min_s} de chaque heure",
            "es": f"en el minuto {min_s} de cada hora",
        }.get(lang, f"at minute {min_s} of every hour")
        parti_tempo.append(t_at_m)
    elif min_s.startswith("*/"):
        step = min_s[2:]
        t_step = {
            "it": f"ogni {step} minuti",
            "en": f"every {step} minutes",
            "de": f"alle {step} Minuten",
            "fr": f"toutes les {step} minutes",
            "es": f"cada {step} minutos",
        }.get(lang, f"every {step} minutes")
        parti_tempo.append(t_step)
        if hour_s.isdigit():
            parti_tempo.append({
                "it": f"nell'ora {hour_s}",
                "en": f"during hour {hour_s}",
                "de": f"in Stunde {hour_s}",
                "fr": f"pendant l'heure {hour_s}",
                "es": f"durante la hora {hour_s}",
            }.get(lang, f"during hour {hour_s}"))
    else:
        parti_tempo.append(f"{min_s} {hour_s}")

    # Giorno settimana
    desc_w = _desc_dow(dow_s, lang)
    if desc_w:
        parti_tempo.append(desc_w)

    # Giorno mese
    desc_d = _desc_dom(dom_s, lang)
    if desc_d:
        parti_tempo.append(desc_d)

    # Mese
    desc_m = _desc_mon(mon_s, lang)
    if desc_m:
        parti_tempo.append(desc_m)

    # Se non c'è restrizione di giorno o mese e abbiamo un orario specifico, aggiungi "Ogni giorno"
    if dow_s == "*" and dom_s == "*" and mon_s == "*" and min_s.isdigit() and hour_s.isdigit():
        prefisso = {
            "it": "Ogni giorno",
            "en": "Every day",
            "de": "Jeden Tag",
            "fr": "Tous les jours",
            "es": "Todos los días",
        }.get(lang, "Every day")
        return f"{prefisso} {' '.join(parti_tempo)}"

    risultato = " ".join(p for p in parti_tempo if p)
    # Capitalizza la prima lettera
    if risultato:
        risultato = risultato[0].upper() + risultato[1:]
    return risultato
