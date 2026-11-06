"""Expansion des horaires en voyages datés : grilles (trains) et fréquences par tranche (louages, bus).

Voir specs/04c-generation-gtfs.md §1 étape 6.
"""

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from citydata.calendar import fallback_chain, line_fallbacks, selector_matches, time_bands_for
from citydata.geo import distance_m
from citydata.timeutil import WEEKDAYS, fmt_time, parse_date, parse_time
from citydata.timetable import discover_grids, read_grid

PICKUP = {"regular": 0, "none": 1, "phone": 2, "on_request": 3}
MAX_SPEED_KMH = {"TRAIN": 160, "METRO": 90}
DEFAULT_MAX_SPEED_KMH = 100


@dataclass
class OutCall:
    stop: str
    arrival: int
    departure: int
    pickup: int = 0
    dropoff: int = 0
    continuous: bool = False


@dataclass
class OutTrip:
    trip_id: str
    line_id: str
    network_id: str
    direction: str
    headsign: dict
    calls: list
    service_key: str
    kind: str                            # timetable | frequency
    dates: set = field(default_factory=set)
    short_name: str = None
    frequencies: list = field(default_factory=list)   # [(début, fin, intervalle en secondes)]
    notes: list = field(default_factory=list)
    code: str = None
    version: str = None
    period: str = None
    day_type: str = None
    band: str = None
    pattern_id: str = None


@dataclass
class ExpandStats:
    fallbacks: dict = field(default_factory=lambda: defaultdict(int))   # (ligne, régime réel, régime utilisé) -> nb jours
    no_version: dict = field(default_factory=lambda: defaultdict(list))  # ligne -> dates sans grille valide
    no_service: dict = field(default_factory=lambda: defaultdict(int))   # (ligne, régime) -> nb jours


def _stop_entry(entry):
    if isinstance(entry, str):
        return {"stop": entry}
    return entry


def _matching_pattern(line, direction, served):
    """Premier parcours déclaré de la direction qui contient les arrêts desservis dans le même ordre."""
    for pat in line["patterns"]:
        if pat["direction"] != direction:
            continue
        stops = [_stop_entry(e) for e in pat["stops"]]
        ids = [s["stop"] for s in stops]
        pos = -1
        ok = True
        for sid in served:
            try:
                pos = ids.index(sid, pos + 1)
            except ValueError:
                ok = False
                break
        if ok:
            return pat, {s["stop"]: s for s in stops}
    return None, {}


def _days_filter_ok(spec, d):
    if not spec:
        return True
    tokens = [t.strip().lower() for t in spec.split(",") if t.strip()]
    weekday = WEEKDAYS[d.weekday()]
    excluded = {t[1:] for t in tokens if t.startswith("-")}
    included = {t for t in tokens if not t.startswith("-")}
    if weekday in excluded:
        return False
    return not included or weekday in included


def _no_service(line, period, day_type):
    return any(selector_matches(sel, period, day_type) for sel in line["schedule"].get("no_service", []))


def _valid_version(line, d):
    for v in line["schedule"].get("versions", []):
        if parse_date(v["valid_from"]) <= d <= parse_date(v["valid_to"]):
            return v
    return None


def expand_timetable_line(ds, line, network, regimes, issues, stats, src_root):
    where = line["_file"]
    lid = line["id"]
    grids_by_version = discover_grids(network["_dir"], line, issues, src_root)
    period_fb, day_fb = line_fallbacks(line, network)
    day_codes = line.get("day_codes", {})
    direction_ids = [d["id"] for d in line["directions"]]
    cache = {}

    def grid(version_id, key, direction):
        path = grids_by_version[version_id][key][direction]
        if path not in cache:
            vdir = path.parent.parent.parent
            cache[path] = read_grid(path, issues, vdir, src_root)
            if cache[path]:
                _check_grid(ds, line, direction, cache[path], issues)
        return cache[path]

    # Vérifie toutes les grilles une fois, même celles qui ne tombent pas dans la fenêtre
    for version_id, grids in grids_by_version.items():
        for key, by_direction in grids.items():
            for direction in by_direction:
                if direction not in direction_ids:
                    issues.error("GRID_DIRECTION", f"Grille pour une direction inconnue : {direction}",
                                 by_direction[direction].relative_to(src_root).as_posix())
                    continue
                g = grid(version_id, key, direction)
                if g and key[1] == "TOUS":
                    for t in g.trips:
                        if not t.code:
                            issues.error("GRID_DAY_CODE", f"Train {t.train} sans code @jours dans une grille TOUS", g.path)
                        elif t.code not in day_codes:
                            issues.error("GRID_DAY_CODE", f"Train {t.train} : code « {t.code} » absent de day_codes",
                                         g.path)
    _check_corrections(line, grids_by_version, grid, issues)

    accumulated = {}
    for d, regime in sorted(regimes.items()):
        if _no_service(line, regime.period, regime.day_type):
            stats.no_service[(lid, f"{regime.period}/{regime.day_type}")] += 1
            continue
        version = _valid_version(line, d)
        if version is None or version["id"] not in grids_by_version:
            stats.no_version[lid].append(d)
            continue
        grids = grids_by_version[version["id"]]
        served_any = False
        # Le choix de la grille se fait par direction : une grille d'été peut ne couvrir qu'un sens.
        for direction in direction_ids:
            chosen = None
            for p in fallback_chain(period_fb, regime.period):
                if direction in grids.get((p, "TOUS"), {}):
                    chosen = (p, "TOUS")
                    break
                for dt in fallback_chain(day_fb, regime.day_type):
                    if direction in grids.get((p, dt), {}):
                        chosen = (p, dt)
                        break
                if chosen:
                    break
            if chosen is None:
                continue
            served_any = True
            used = f"{chosen[0]}/{chosen[1]}"
            if chosen[0] != regime.period or chosen[1] not in ("TOUS", regime.day_type):
                stats.fallbacks[(lid, f"{regime.period}/{regime.day_type} {direction}", used)] += 1
            g = grid(version["id"], chosen, direction)
            if not g:
                continue
            for t in g.trips:
                if chosen[1] == "TOUS" and (t.code not in day_codes
                                            or regime.day_type not in day_codes[t.code]["days"]):
                    continue
                if not _days_filter_ok(t.days, d):
                    continue
                key = (version["id"], chosen, direction, t.train)
                if key not in accumulated:
                    accumulated[key] = (_out_trip(line, network, version["id"], chosen, direction, t), set())
                accumulated[key][1].add(d)
        if not served_any:
            stats.no_version[lid].append(d)

    trips = []
    seen_ids = {}
    for (version_id, chosen, direction, train), (trip, dates) in accumulated.items():
        if trip.trip_id in seen_ids and seen_ids[trip.trip_id] != direction:
            issues.error("TRIP_ID_CLASH", f"Le train {train} apparaît dans deux directions", where)
            continue
        seen_ids[trip.trip_id] = direction
        trip.dates = dates
        trips.append(trip)
    return trips


def _out_trip(line, network, version_id, chosen, direction, t):
    pattern, attrs = _matching_pattern(line, direction, [c.stop for c in t.calls])
    calls = []
    for c in t.calls:
        a = attrs.get(c.stop, {})
        calls.append(OutCall(c.stop, c.arrival, c.departure,
                             PICKUP[a.get("pickup", "regular")], PICKUP[a.get("dropoff", "regular")],
                             bool(a.get("continuous"))))
    calls[0].dropoff = 1
    calls[-1].pickup = 1
    headsign = next(d["headsign"] for d in line["directions"] if d["id"] == direction)
    main = next((p for p in line["patterns"] if p["direction"] == direction and p.get("main")), None)
    if main and _stop_entry(main["stops"][-1])["stop"] != t.calls[-1].stop:
        headsign = {"stop_ref": t.calls[-1].stop}
    key = f"{network['id']}:{version_id}:{chosen[0]}:{chosen[1]}"
    if t.code:
        key += f":{t.code}"
    if t.days:
        key += f":{t.days}"
    return OutTrip(
        trip_id=f"{line['id']}:{version_id}:{chosen[0]}:{chosen[1]}:{t.train}",
        line_id=line["id"], network_id=network["id"], direction=direction, headsign=headsign,
        calls=calls, service_key=key, kind="timetable", short_name=t.train, notes=t.notes, code=t.code,
        version=version_id, period=chosen[0], day_type=chosen[1], pattern_id=pattern["id"] if pattern else None,
    )


def _check_corrections(line, grids_by_version, grid, issues):
    for v in line["schedule"].get("versions", []):
        grids = grids_by_version.get(v["id"], {})
        for corr in v.get("corrections", []):
            found = False
            for key, by_direction in grids.items():
                if corr["direction"] not in by_direction:
                    continue
                g = grid(v["id"], key, corr["direction"])
                trip = next((t for t in g.trips if t.train == corr["train"]), None) if g else None
                call = trip.time_at(corr["stop"]) if trip else None
                if call and fmt_time(call.departure) == corr["corrected"]:
                    found = True
            if not found:
                issues.error("CORRECTION_MISMATCH",
                             f"Correction non retrouvée dans la grille : train {corr['train']} à {corr['stop']} "
                             f"devrait valoir {corr['corrected']}", line["_file"])


def _check_grid(ds, line, direction, g, issues):
    """Contrôles de qualité : arrêts connus, vitesses plausibles, écarts à la durée habituelle."""
    allowed = {_stop_entry(e)["stop"] for p in line["patterns"] if p["direction"] == direction for e in p["stops"]}
    for stop in g.stops:
        if stop not in allowed:
            issues.error("GRID_STOP", f"{stop} n'appartient à aucun parcours {direction} de la ligne {line['id']}", g.path)
    max_kmh = MAX_SPEED_KMH.get(line["mode"], DEFAULT_MAX_SPEED_KMH)

    segments = defaultdict(list)
    for t in g.trips:
        for a, b in zip(t.calls, t.calls[1:]):
            segments[(a.stop, b.stop)].append((b.arrival - a.departure, t.train))
    for (a, b), samples in segments.items():
        pa, pb = ds.places.get(a), ds.places.get(b)
        dist = distance_m(pa["lat"], pa["lon"], pb["lat"], pb["lon"]) if pa and pb else None
        durations = [s for s, _ in samples]
        median = statistics.median(durations)
        for duration, train in samples:
            if dist is not None:
                if duration == 0 and dist > 1500:
                    issues.warning("SPEED_IMPLAUSIBLE", f"Train {train} : 0 min entre {a} et {b} ({dist / 1000:.1f} km)",
                                   g.path)
                elif duration > 0 and dist / 1000 / (duration / 60) > max_kmh:
                    issues.warning("SPEED_IMPLAUSIBLE",
                                   f"Train {train} : {dist / 1000 / (duration / 60):.0f} km/h entre {a} et {b}", g.path)
            if len(samples) >= 5 and abs(duration - median) >= 4:
                issues.warning("RUN_TIME_OUTLIER",
                               f"Train {train} : {duration} min entre {a} et {b} (habituellement {median:g} min)", g.path)


def _service_hours(entry, direction):
    """Premier et dernier départ (minutes) d'un régime pour une direction : `by_direction` l'emporte sur first/last."""
    hours = entry.get("service_hours") or {}
    own = (hours.get("by_direction") or {}).get(direction) or hours
    first = parse_time(own["first"]) if own.get("first") else 0
    last = parse_time(own["last"]) if own.get("last") else 26 * 60
    return first, last


def expand_frequency_line(ds, line, network, regimes, issues, stats):
    lid = line["id"]
    period_fb, day_fb = line_fallbacks(line, network)
    entries = [r for r in line["schedule"].get("regimes", []) if r.get("kind", "frequency") == "frequency"]

    accumulated = defaultdict(set)   # (index du régime, période, type de jour) -> dates
    for d, regime in sorted(regimes.items()):
        if _no_service(line, regime.period, regime.day_type):
            stats.no_service[(lid, f"{regime.period}/{regime.day_type}")] += 1
            continue
        chosen = None
        for p in fallback_chain(period_fb, regime.period):
            for dt in fallback_chain(day_fb, regime.day_type):
                idx = next((i for i, e in enumerate(entries) if selector_matches(e, p, dt)), None)
                if idx is not None:
                    chosen = (idx, p, dt)
                    break
            if chosen:
                break
        if chosen is None:
            stats.no_version[lid].append(d)
            continue
        if (chosen[1], chosen[2]) != (regime.period, regime.day_type):
            stats.fallbacks[(lid, f"{regime.period}/{regime.day_type}", f"{chosen[1]}/{chosen[2]}")] += 1
        accumulated[chosen].add(d)

    trips = []
    for (idx, p, dt), dates in sorted(accumulated.items()):
        entry = entries[idx]
        bands = {b["id"]: b for b in (time_bands_for(ds, p, dt) or [])}
        for band_id, cfg in entry.get("bands", {}).items():
            if not cfg.get("headway_min") or band_id not in bands:
                continue
            for pat in line["patterns"]:
                first, last = _service_hours(entry, pat["direction"])
                start = max(parse_time(bands[band_id]["from"]), first)
                end = min(parse_time(bands[band_id]["to"]), last + 1)
                if end <= start:
                    continue
                run = {**line.get("run_times", {}), **pat.get("run_times", {})}.get(cfg["run_time"])
                stops = [_stop_entry(e) for e in pat["stops"]]
                if run is None:
                    continue
                if len(run) != len(stops) - 1:
                    continue
                t = start
                calls = []
                for i, s in enumerate(stops):
                    if i:
                        t += run[i - 1]
                    calls.append(OutCall(s["stop"], t, t, PICKUP[s.get("pickup", "regular")],
                                         PICKUP[s.get("dropoff", "regular")], bool(s.get("continuous"))))
                calls[0].dropoff = 1
                calls[-1].pickup = 1
                headsign = next(d["headsign"] for d in line["directions"] if d["id"] == pat["direction"])
                trips.append(OutTrip(
                    trip_id=f"{lid}:{p}:{dt}:{band_id}:{pat['id']}", line_id=lid, network_id=network["id"],
                    direction=pat["direction"], headsign=headsign, calls=calls,
                    service_key=f"{network['id']}:{p}:{dt}", kind="frequency", dates=set(dates),
                    frequencies=[(start, end, cfg["headway_min"] * 60)], period=p, day_type=dt, band=band_id,
                    pattern_id=pat["id"],
                ))
    return trips


def apply_alerts(ds, trips, issues):
    """NO_SERVICE : retire les dates concernées. Les autres effets sont seulement affichés (app-meta)."""
    applied = defaultdict(int)
    for alert in ds.alerts:
        if alert["status"] != "active":
            continue
        if alert["effect"] == "STOP_CLOSED":
            issues.info("ALERT_DISPLAY_ONLY", f"Alerte {alert['id']} : fermeture d'arrêt affichée, pas encore appliquée "
                                              f"au calcul d'itinéraires", alert["_file"])
        if alert["effect"] != "NO_SERVICE":
            continue
        scope = alert["scope"]
        windows = [(datetime.fromisoformat(p["from"]), datetime.fromisoformat(p["to"])) for p in alert["active_periods"]]
        for trip in trips:
            if not (trip.line_id in scope.get("lines", []) or trip.network_id in scope.get("networks", [])):
                continue
            start_min = trip.frequencies[0][0] if trip.frequencies else trip.calls[0].departure
            for d in sorted(trip.dates):
                departure = datetime(d.year, d.month, d.day) + timedelta(minutes=start_min)
                if any(a <= departure <= b for a, b in windows):
                    trip.dates.discard(d)
                    applied[alert["id"]] += 1
    return dict(applied)
