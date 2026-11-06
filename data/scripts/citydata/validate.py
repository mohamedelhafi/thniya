"""Contrôles de références et règles métier (specs/04c §2), après la validation des schémas."""

from citydata.calendar import time_bands_for
from citydata.geo import contrast_ratio
from citydata.timeutil import parse_time

PUBLISHED = ("active", "suspended")
DAY_TYPES_KNOWN = None  # déduits des réseaux


def _ar_missing(obj, field="name"):
    value = obj.get(field) or {}
    return not value.get("ar")


def _pattern_stop_id(entry):
    return entry if isinstance(entry, str) else entry["stop"]


def check(ds, issues):
    _check_modes_and_periods(ds, issues)
    _check_places(ds, issues)
    _check_networks(ds, issues)
    _check_time_bands(ds, issues)
    for line in ds.lines.values():
        _check_line(ds, line, issues)
    _check_alerts(ds, issues)
    _check_transfers_and_coverage(ds, issues)


def _check_modes_and_periods(ds, issues):
    for m in ds.modes.values():
        if m["status"] in PUBLISHED and _ar_missing(m):
            issues.error("I18N_AR_MISSING", f"Mode {m['id']} : nom arabe manquant", m["_file"])
    if not any(p.get("default") for p in ds.periods.values()):
        issues.error("PERIOD_DEFAULT", "Aucune période par défaut (default: true)", "calendar/periods.yaml")
    known_events = {ev["id"] for evs in ds.years.values() for ev in evs}
    for p in ds.periods.values():
        if _ar_missing(p):
            issues.error("I18N_AR_MISSING", f"Période {p['id']} : nom arabe manquant", p["_file"])
        for ev in p.get("from_events", []) + p.get("from_events_all", []):
            if ev not in known_events:
                issues.warning("PERIOD_EVENT_UNKNOWN", f"Période {p['id']} : l'événement {ev} n'apparaît dans aucune année",
                               p["_file"])


def _check_places(ds, issues):
    for p in ds.places.values():
        where = p["_file"]
        if p.get("parent"):
            parent = ds.places.get(p["parent"])
            if not parent:
                issues.error("REF_UNKNOWN", f"Lieu {p['id']} : parent inconnu {p['parent']}", where)
            elif p["status"] in PUBLISHED and parent["status"] not in PUBLISHED:
                issues.error("REF_DRAFT", f"Lieu publié {p['id']} rattaché au lieu non publié {parent['id']}", where)
        if p["status"] in PUBLISHED and _ar_missing(p):
            issues.error("I18N_AR_MISSING", f"Lieu {p['id']} : nom arabe manquant", where)
        if not (30.2 <= p["lat"] <= 37.6 and 7.5 <= p["lon"] <= 11.7):
            issues.error("GEO_OUTSIDE", f"Lieu {p['id']} hors de la Tunisie ({p['lat']}, {p['lon']})", where)
    for h in ds.hubs.values():
        for m in h["members"]:
            if m not in ds.places:
                issues.error("REF_UNKNOWN", f"Pôle {h['id']} : membre inconnu {m}", h["_file"])


def _check_networks(ds, issues):
    for n in ds.networks.values():
        where = n["_file"]
        cal = n["calendar"]
        for p in cal["periods"]:
            if p not in ds.periods:
                issues.error("REF_UNKNOWN", f"Réseau {n['id']} : période inconnue {p}", where)
        fb = cal.get("fallback", {})
        for a, b in fb.get("periods", {}).items():
            for p in (a, b):
                if p not in ds.periods:
                    issues.error("REF_UNKNOWN", f"Réseau {n['id']} : période de repli inconnue {p}", where)
        if n["status"] in PUBLISHED and _ar_missing(n):
            issues.error("I18N_AR_MISSING", f"Réseau {n['id']} : nom arabe manquant", where)


def _check_time_bands(ds, issues):
    seen = {}
    for group in ds.time_bands:
        where = group["_file"]
        sel = group["applies_to"]
        for p in sel["periods"]:
            if p not in ds.periods:
                issues.error("REF_UNKNOWN", f"Tranches : période inconnue {p}", where)
            for dt in sel["day_types"]:
                if (p, dt) in seen:
                    issues.error("BANDS_DUPLICATE", f"Deux groupes de tranches pour {p}/{dt}", where)
                seen[(p, dt)] = True
        bands = sorted(group["bands"], key=lambda b: parse_time(b["from"]))
        cursor = 0
        for b in bands:
            start, end = parse_time(b["from"]), parse_time(b["to"])
            if end <= start:
                issues.error("BANDS_ORDER", f"Tranche {b['id']} : fin avant le début", where)
            if start > cursor:
                issues.error("BANDS_GAP", f"Trou entre {cursor // 60:02d}:{cursor % 60:02d} et {b['from']} "
                                          f"({'/'.join(sel['periods'])})", where)
            elif start < cursor:
                issues.error("BANDS_OVERLAP", f"Tranche {b['id']} chevauche la précédente ({'/'.join(sel['periods'])})",
                             where)
            cursor = max(cursor, end)
        if cursor < 24 * 60:
            issues.error("BANDS_GAP", f"Les tranches s'arrêtent à {cursor // 60:02d}:{cursor % 60:02d} "
                                      f"({'/'.join(sel['periods'])})", where)


def _check_line(ds, line, issues):
    where = line["_file"]
    lid = line["id"]
    published = line["status"] in PUBLISHED
    network = ds.networks.get(line["network"])
    mode = ds.modes.get(line["mode"])
    if not network:
        issues.error("REF_UNKNOWN", f"Ligne {lid} : réseau inconnu {line['network']}", where)
    elif published and network["status"] not in PUBLISHED:
        issues.error("REF_DRAFT", f"Ligne publiée {lid} sur un réseau non publié", where)
    if not mode:
        issues.error("REF_UNKNOWN", f"Ligne {lid} : mode inconnu {line['mode']}", where)
    elif published and mode["status"] not in PUBLISHED:
        issues.error("REF_DRAFT", f"Ligne publiée {lid} avec le mode non publié {mode['id']}", where)
    if published and _ar_missing(line):
        issues.error("I18N_AR_MISSING", f"Ligne {lid} : nom arabe manquant", where)

    if line.get("color") and line.get("text_color"):
        ratio = contrast_ratio(line["color"], line["text_color"])
        if ratio < 4.5:
            issues.warning("COLOR_CONTRAST", f"Ligne {lid} : contraste {ratio:.1f}:1 < 4,5:1 (lisibilité de la pastille)",
                           where)

    direction_ids = [d["id"] for d in line["directions"]]
    for d in line["directions"]:
        if published and _ar_missing(d, "headsign"):
            issues.error("I18N_AR_MISSING", f"Ligne {lid} : direction {d['id']} sans libellé arabe", where)
    for pat in line["patterns"]:
        if pat["direction"] not in direction_ids:
            issues.error("REF_UNKNOWN", f"Parcours {pat['id']} : direction inconnue {pat['direction']}", where)
        for entry in pat["stops"]:
            sid = _pattern_stop_id(entry)
            place = ds.places.get(sid)
            if not place:
                issues.error("REF_UNKNOWN", f"Parcours {pat['id']} : arrêt inconnu {sid}", where)
            elif published and place["status"] not in PUBLISHED:
                issues.error("REF_DRAFT", f"Ligne publiée {lid} : l'arrêt {sid} n'est pas publié", where)
    for d in direction_ids:
        if not any(p["direction"] == d and p.get("main") for p in line["patterns"]):
            issues.warning("PATTERN_MAIN", f"Ligne {lid} : pas de parcours principal (main: true) pour {d}", where)

    schedule = line["schedule"]
    kind = schedule["kind"]
    if mode and kind not in mode["schedule_kinds"]:
        issues.error("SCHEDULE_KIND", f"Ligne {lid} : horaires « {kind} » non autorisés pour le mode {mode['id']}", where)
    if kind in ("timetable", "mixed") and not schedule.get("versions"):
        issues.error("SCHEDULE_VERSIONS", f"Ligne {lid} : aucune version de grille (schedule.versions)", where)
    for v in schedule.get("versions", []):
        if v["valid_to"] < v["valid_from"]:
            issues.error("VERSION_DATES", f"Version {v['id']} : fin avant le début", where)
    if kind in ("frequency", "mixed"):
        _check_frequency(ds, line, issues)
    if line.get("fare") and line["fare"] not in ds.fares:
        issues.error("REF_UNKNOWN", f"Ligne {lid} : tarif inconnu {line['fare']}", where)
    if published and not line.get("fare"):
        issues.warning("FARE_MISSING", f"Ligne {lid} : pas de tarif renseigné (prix affiché « inconnu »)", where)


def _check_frequency(ds, line, issues):
    where = line["_file"]
    run_times = line.get("run_times", {})
    for pat in line["patterns"]:
        for profile, values in {**run_times, **pat.get("run_times", {})}.items():
            if len(values) != len(pat["stops"]) - 1:
                issues.error("RUN_TIMES_LENGTH",
                             f"Ligne {line['id']} : profil {profile} a {len(values)} durées pour "
                             f"{len(pat['stops']) - 1} tronçons du parcours {pat['id']}", where)
    direction_ids = {d["id"] for d in line["directions"]}
    for regime in line["schedule"].get("regimes", []):
        if regime.get("kind", "frequency") != "frequency":
            continue
        for direction in (regime.get("service_hours") or {}).get("by_direction", {}):
            if direction not in direction_ids:
                issues.error("REF_UNKNOWN", f"Ligne {line['id']} : service_hours.by_direction vise la direction "
                                            f"inconnue {direction}", where)
        for p in regime["periods"]:
            for dt in regime["day_types"]:
                bands = time_bands_for(ds, p, dt)
                if bands is None:
                    issues.error("BANDS_MISSING", f"Ligne {line['id']} : aucune tranche horaire définie pour {p}/{dt}",
                                 where)
                    continue
                known = {b["id"] for b in bands}
                for band_id, band in regime.get("bands", {}).items():
                    if band_id not in known:
                        issues.error("BAND_UNKNOWN", f"Ligne {line['id']} : tranche {band_id} inconnue pour {p}/{dt}",
                                     where)
                    known_profiles = set(run_times) | {k for p in line["patterns"] for k in p.get("run_times", {})}
                    if band.get("headway_min") and band.get("run_time") not in known_profiles:
                        issues.error("RUN_TIME_UNKNOWN",
                                     f"Ligne {line['id']} : profil de durée « {band.get('run_time')} » inconnu", where)


def _check_alerts(ds, issues):
    for a in ds.alerts:
        where = a["_file"]
        for lid in a["scope"].get("lines", []):
            if lid not in ds.lines:
                issues.error("REF_UNKNOWN", f"Alerte {a['id']} : ligne inconnue {lid}", where)
        for sid in a["scope"].get("stops", []):
            if sid not in ds.places:
                issues.error("REF_UNKNOWN", f"Alerte {a['id']} : arrêt inconnu {sid}", where)
        for nid in a["scope"].get("networks", []):
            if nid not in ds.networks:
                issues.error("REF_UNKNOWN", f"Alerte {a['id']} : réseau inconnu {nid}", where)
        for period in a["active_periods"]:
            if period["to"] < period["from"]:
                issues.error("ALERT_DATES", f"Alerte {a['id']} : fin avant le début", where)


def _check_transfers_and_coverage(ds, issues):
    for t in ds.transfers:
        for key in ("from", "to"):
            if key in t and t[key] not in ds.places:
                issues.error("REF_UNKNOWN", f"Correspondance : arrêt inconnu {t[key]}", "transfers.yaml")
        if "from_hub" in t and t["from_hub"] not in ds.hubs:
            issues.error("REF_UNKNOWN", f"Correspondance : pôle inconnu {t['from_hub']}", "transfers.yaml")
    for c in ds.coverage:
        for m in c["modes"]:
            if m not in ds.modes:
                issues.error("REF_UNKNOWN", f"Couverture {c['id']} : mode inconnu {m}", c["_file"])
        if c["polygon"][0] != c["polygon"][-1]:
            issues.error("POLYGON_OPEN", f"Couverture {c['id']} : le polygone doit se refermer (1er point = dernier)",
                         c["_file"])
