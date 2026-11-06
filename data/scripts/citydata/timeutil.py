"""Heures « HH:MM » en minutes depuis minuit (au-delà de 24:00 autorisé) et dates."""

import re
from datetime import date, timedelta

_TIME = re.compile(r"^(\d{1,2}):([0-5]\d)$")


def parse_time(text):
    """'05:30' -> 330 ; '25:10' -> 1510. Lève ValueError si le format est faux."""
    m = _TIME.match(text.strip())
    if not m:
        raise ValueError(f"heure invalide : {text!r} (attendu HH:MM)")
    return int(m.group(1)) * 60 + int(m.group(2))


def fmt_time(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def gtfs_time(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def parse_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def date_range(start, end):
    """Dates de start à end inclus."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAYS_FR = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")
