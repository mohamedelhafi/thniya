"""Écriture de app-meta.json, le contrat avec l'API Spring (specs/04c-generation-gtfs.md §4)."""

import json
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from citydata.calendar import time_bands_for

PUBLISHED = ("active", "suspended")


def _i18n(value):
    return {k: v for k, v in (value or {}).items() if k in ("fr", "ar")}


def _stop_id(entry):
    return entry if isinstance(entry, str) else entry["stop"]


def build(ds, trips, regimes_by_network, window, data_version, now=None):
    now = now or datetime.now(ZoneInfo("Africa/Tunis")).replace(microsecond=0)
    live_trips = [t for t in trips if t.dates]
    lines_at_stop = defaultdict(set)
    for t in live_trips:
        for c in t.calls:
            lines_at_stop[c.stop].add(t.line_id)

    meta = {
        "dataVersion": data_version,
        "generatedAt": now.isoformat(),
        "window": {"from": window[0].isoformat(), "to": window[1].isoformat()},
        "modes": {},
        "networks": {},
        "lines": {},
        "stops": {},
        "hubs": {},
        "fares": {},
        "periods": {},
        "calendar": {},
        "alerts": [],
        "coverage": [],
    }

    for m in ds.modes.values():
        if m["status"] not in PUBLISHED:
            continue
        meta["modes"][m["id"]] = {
            "name": _i18n(m["name"]), "icon": m["icon"], "color": m.get("default_color"),
            "showsExactTimes": m["shows_exact_times"], "departsWhenFull": m.get("departs_when_full", False),
            "seats": m.get("seats"),
        }

    for n in ds.networks.values():
        if n["status"] in PUBLISHED:
            meta["networks"][n["id"]] = {"name": _i18n(n["name"]), "longName": _i18n(n.get("long_name")),
                                         "url": n.get("url"), "phone": n.get("phone")}

    for line in sorted(ds.lines.values(), key=lambda l: l["id"]):
        if line["status"] not in PUBLISHED:
            continue
        meta["lines"][line["id"]] = _line_meta(ds, line, lines_at_stop)

    for p in sorted(ds.places.values(), key=lambda p: p["id"]):
        if p["status"] not in PUBLISHED:
            continue
        hub = next((h["id"] for h in ds.hubs.values() if p["id"] in h["members"]), None)
        meta["stops"][p["id"]] = {
            "kind": p["kind"], "name": _i18n(p["name"]), "aliases": p.get("aliases", []),
            "area": _i18n(p.get("area")), "lat": p["lat"], "lon": p["lon"], "parent": p.get("parent"),
            "hub": hub, "lines": sorted(lines_at_stop.get(p["id"], [])), "platformCode": p.get("platform_code"),
            "code": p.get("code"), "confidence": p["provenance"]["source"],
        }

    for h in ds.hubs.values():
        if h["status"] in PUBLISHED:
            meta["hubs"][h["id"]] = {"name": _i18n(h["name"]), "members": h["members"],
                                     "aliases": h.get("aliases", [])}

    used_fares = {l.get("fare") for l in ds.lines.values() if l["status"] in PUBLISHED and l.get("fare")}
    for fid in sorted(used_fares):
        fare = ds.fares.get(fid)
        if not fare:
            continue
        versions = sorted(fare["versions"], key=lambda v: v["valid_from"])
        current = [v for v in versions if v["valid_from"] <= window[0].isoformat()] or versions[:1]
        v = current[-1]
        entry = {"model": fare["model"], "currency": fare["currency"],
                 "estimated": fare["provenance"]["source"] == "ESTIMATION", "validFrom": v["valid_from"]}
        if fare["model"] == "flat":
            entry["flat"] = v["price_millimes"].get("PLEIN")
        elif fare["model"] == "od_pairs":
            entry["pairs"] = {f"{p['from']}|{p['to']}": p["price_millimes"].get("PLEIN") for p in v.get("pairs", [])}
        meta["fares"][fid] = entry

    for p in ds.periods.values():
        meta["periods"][p["id"]] = {"name": _i18n(p["name"]), "showBanner": p.get("show_banner", False)}

    for network_id, regimes in regimes_by_network.items():
        meta["calendar"][network_id] = {
            d.isoformat(): {
                "period": r.period, "dayType": r.day_type,
                "holidays": [{"id": e.id, "name": _i18n(e.name), "estimated": e.status == "estimated"}
                             for e in r.holidays],
            }
            for d, r in sorted(regimes.items())
        }

    for a in ds.alerts:
        if a["status"] != "active":
            continue
        meta["alerts"].append({
            "id": a["id"], "effect": a["effect"], "severity": a["severity"], "scope": a["scope"],
            "activePeriods": a["active_periods"], "title": _i18n(a["title"]), "body": _i18n(a.get("body")),
            "url": a.get("url"),
        })

    for c in ds.coverage:
        if c["status"] in PUBLISHED:
            meta["coverage"].append({"id": c["id"], "name": _i18n(c["name"]), "level": c["level"],
                                     "modes": c["modes"], "polygon": c["polygon"]})
    return meta


def _line_meta(ds, line, lines_at_stop):
    out = {
        "network": line["network"], "mode": line["mode"], "publicCode": line["public_code"],
        "name": _i18n(line["name"]), "longName": _i18n(line.get("long_name")),
        "color": line.get("color") or ds.modes[line["mode"]].get("default_color"),
        "textColor": line.get("text_color") or "#FFFFFF", "status": line["status"],
        "scheduleKind": line["schedule"]["kind"],
        "directions": [{"id": d["id"], "headsign": _i18n(d["headsign"])} for d in line["directions"]],
        "diagram": {},
        "notes": {k: _i18n(v) for k, v in line.get("notes", {}).items()},
        "dayCodes": {k: {"days": v["days"], "label": _i18n(v["label"])} for k, v in line.get("day_codes", {}).items()},
        "fare": line.get("fare"),
        "confidence": line["provenance"]["source"],
        "verifiedAt": line["provenance"]["verified_at"],
        "timetableVersions": [
            {"id": v["id"], "validFrom": v["valid_from"], "validTo": v["valid_to"],
             "source": (v.get("provenance") or {}).get("ref"), "corrections": len(v.get("corrections", []))}
            for v in line["schedule"].get("versions", [])
        ],
    }
    for pat in line["patterns"]:
        if not pat.get("main"):
            continue
        stops = [_stop_id(e) for e in pat["stops"]]
        out["diagram"][pat["direction"]] = [
            {"stop": s, "branch": 0, "isTerminus": i in (0, len(stops) - 1),
             "interchanges": sorted(lines_at_stop.get(s, set()) - {line["id"]})}
            for i, s in enumerate(stops)
        ]
    if line["schedule"]["kind"] in ("frequency", "mixed"):
        out["frequencies"] = {}
        out["serviceHours"] = {}
        for regime in line["schedule"].get("regimes", []):
            for p in regime["periods"]:
                for dt in regime["day_types"]:
                    key = f"{p}:{dt}"
                    bands = {b["id"]: b for b in (time_bands_for(ds, p, dt) or [])}
                    # tri par heure de début : l'ordre des clés ne compte pas (la base jsonb ne le garde pas)
                    out["frequencies"][key] = sorted((
                        {"band": bid, "from": bands[bid]["from"], "to": bands[bid]["to"],
                         "headwayMin": cfg.get("headway_min")}
                        for bid, cfg in regime.get("bands", {}).items() if bid in bands
                    ), key=lambda b: b["from"])
                    if regime.get("service_hours"):
                        # contrat app-meta inchangé : amplitude globale (by_direction reste propre à la génération)
                        hours = regime["service_hours"]
                        out["serviceHours"][key] = {"first": hours["first"], "last": hours["last"]}
    return out


def write(meta, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=False), encoding="utf-8")
