"""Résolution du calendrier : quel régime (période × type de jour) pour un réseau et une date.

Voir specs/04b-calendriers-regimes.md §6.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from citydata.timeutil import WEEKDAYS, date_range, parse_date


@dataclass(frozen=True)
class Event:
    id: str
    kind: str
    start: object
    end: object
    status: str
    name: dict
    where: str


@dataclass
class Regime:
    date: object
    period: str
    day_type: str
    holidays: list = field(default_factory=list)
    events: list = field(default_factory=list)


class Calendar:
    def __init__(self, ds):
        self.ds = ds
        self.events = []
        for year_events in ds.years.values():
            for ev in year_events:
                start = parse_date(ev.get("date") or ev["from"])
                end = parse_date(ev.get("date") or ev["to"])
                self.events.append(Event(ev["id"], ev["kind"], start, end, ev["status"],
                                         ev.get("name", {}), ev["_file"]))
        self.default_period = next((p for p in ds.periods.values() if p.get("default")), None)

    def events_on(self, d):
        return [e for e in self.events if e.start <= d <= e.end]

    def holidays_on(self, d):
        return [e for e in self.events_on(d) if e.kind == "holiday"]

    def period_active(self, period_id, d):
        period = self.ds.periods[period_id]
        if period.get("default"):
            return True
        extend = period.get("extend", {})
        before = timedelta(days=extend.get("before_days", 0))
        after = timedelta(days=extend.get("after_days", 0))

        def event_active(event_id):
            return any(e.id == event_id and e.start - before <= d <= e.end + after for e in self.events)

        if "from_events_all" in period:
            return all(event_active(e) for e in period["from_events_all"])
        return any(event_active(e) for e in period.get("from_events", []))

    def resolve(self, network, d):
        cal = network["calendar"]
        holidays = self.holidays_on(d)
        if holidays:
            day_type = cal["holiday_day_type"]
        else:
            day_type = cal["day_type_scheme"][WEEKDAYS[d.weekday()]]
        period = next((p for p in cal["periods"] if self.period_active(p, d)),
                      self.default_period["id"] if self.default_period else "NORMAL")
        return Regime(d, period, day_type, holidays, self.events_on(d))


def fallback_chain(mapping, start):
    """NORMAL <- RAMADAN : renvoie [RAMADAN, NORMAL] en suivant les replis, sans boucle."""
    chain = [start]
    while chain[-1] in mapping and mapping[chain[-1]] not in chain:
        chain.append(mapping[chain[-1]])
    return chain


def line_fallbacks(line, network):
    fb = line.get("schedule", {}).get("fallback", "inherit")
    net_fb = network["calendar"].get("fallback", {})
    if fb == "inherit":
        return net_fb.get("periods", {}), net_fb.get("day_types", {})
    return fb.get("periods", net_fb.get("periods", {})), fb.get("day_types", net_fb.get("day_types", {}))


def selector_matches(selector, period, day_type):
    return period in selector["periods"] and day_type in selector["day_types"]


def time_bands_for(ds, period, day_type):
    for group in ds.time_bands:
        if selector_matches(group["applies_to"], period, day_type):
            return group["bands"]
    return None


def resolve_window(cal, network, start, end):
    return {d: cal.resolve(network, d) for d in date_range(start, end)}
