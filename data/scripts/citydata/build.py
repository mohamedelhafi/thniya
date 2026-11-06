"""Orchestration : lint, build, calendar-preview (specs/04c-generation-gtfs.md §1)."""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from citydata import gtfs, meta, paths, report, validate
from citydata.calendar import Calendar, resolve_window
from citydata.expand import ExpandStats, apply_alerts, expand_frequency_line, expand_timetable_line
from citydata.issues import Issues
from citydata.loader import load, read_yaml
from citydata.timeutil import WEEKDAYS_FR, date_range

DEFAULT_PAST_DAYS = 7
DEFAULT_HORIZON_DAYS = 120


def today_tunis():
    return datetime.now(ZoneInfo("Africa/Tunis")).date()


def _load_and_check(src=None, schemas=None):
    issues = Issues()
    ds = load(issues, src=src, schemas=schemas)
    if not issues.errors:
        validate.check(ds, issues)
    return ds, issues


def _expand(ds, issues, start, end, src_root):
    cal = Calendar(ds)
    stats = ExpandStats()
    regimes_by_network = {nid: resolve_window(cal, n, start, end)
                          for nid, n in ds.networks.items() if n["status"] in ("active", "suspended")}
    trips = []
    for line in sorted(ds.lines.values(), key=lambda l: l["id"]):
        if line["status"] != "active":
            continue
        network = ds.networks[line["network"]]
        regimes = regimes_by_network.get(network["id"], {})
        kind = line["schedule"]["kind"]
        if kind in ("timetable", "mixed") and line["schedule"].get("versions"):
            trips += expand_timetable_line(ds, line, network, regimes, issues, stats, src_root)
        if kind in ("frequency", "mixed"):
            trips += expand_frequency_line(ds, line, network, regimes, issues, stats)
    return cal, stats, regimes_by_network, trips


def _sources_hash(src_root):
    """Empreinte courte de toutes les sources : change dès qu'une donnée change."""
    import hashlib
    h = hashlib.sha256()
    for f in sorted(Path(src_root).rglob("*")):
        if f.is_file():
            h.update(f.relative_to(src_root).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


def _golden_lines(path):
    if not Path(path).exists():
        return set()
    data = read_yaml(path) or []
    return {line for g in data for line in (g.get("expect", {}).get("uses_line"), g.get("line")) if line}


def lint(src=None):
    ds, issues = _load_and_check(src)
    if not issues.errors:
        start = today_tunis()
        _expand(ds, issues, start, start + timedelta(days=DEFAULT_HORIZON_DAYS), Path(src or paths.SRC))
    issues.print()
    return 1 if issues.errors else 0


def build(start=None, days=None, src=None, out_dir=None, data_version=None, now=None):
    src_root = Path(src or paths.SRC)
    out_dir = Path(out_dir or paths.BUILD)
    today = (now.date() if now else today_tunis())
    start = start or today - timedelta(days=DEFAULT_PAST_DAYS)
    end = start + timedelta(days=(days or DEFAULT_PAST_DAYS + DEFAULT_HORIZON_DAYS))
    data_version = data_version or os.environ.get("DATA_VERSION") or "dev"
    if data_version == "dev":
        data_version = f"dev-{today.isoformat()}-{_sources_hash(src_root)}"

    ds, issues = _load_and_check(src_root)
    if issues.errors:
        issues.print()
        print("Génération interrompue : corriger les erreurs ci-dessus.")
        return 1

    cal, stats, regimes_by_network, trips = _expand(ds, issues, start, end, src_root)
    if issues.errors:
        issues.print()
        print("Génération interrompue : corriger les erreurs ci-dessus.")
        return 1

    alerts_applied = apply_alerts(ds, trips, issues)
    counts = gtfs.write(ds, trips, (start, end), data_version, out_dir / "gtfs.zip")
    app_meta = meta.build(ds, trips, regimes_by_network, (start, end), data_version, now=now)
    meta.write(app_meta, out_dir / "app-meta.json")
    text = report.build(ds, issues, cal, trips, stats, counts, alerts_applied, today,
                        _golden_lines(paths.DATA / "golden-trips.yaml"), data_version)
    (out_dir / "report.md").write_text(text, encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(
        {"dataVersion": data_version, "counts": counts,
         "issues": [i.__dict__ for i in issues.items]}, ensure_ascii=False, indent=1), encoding="utf-8")

    issues.print(max_per_level=15)
    print(f"Fenêtre : {start.isoformat()} → {end.isoformat()} | version {data_version}")
    print("GTFS : " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"Écrit : {out_dir / 'gtfs.zip'}, app-meta.json, report.md")
    return 0


def calendar_preview(network_id, start=None, days=45, src=None, lines=None):
    src_root = Path(src or paths.SRC)
    ds, issues = _load_and_check(src_root)
    if issues.errors:
        issues.print()
        return 1
    if network_id not in ds.networks:
        print(f"Réseau inconnu : {network_id}. Réseaux : {', '.join(sorted(ds.networks))}")
        return 1
    start = start or today_tunis()
    end = start + timedelta(days=days - 1)

    # On ne garde que les lignes demandées du réseau
    selected = [l for l in ds.lines.values() if l["network"] == network_id and l["status"] == "active"
                and (not lines or l["id"] in lines)]
    keep = {l["id"] for l in selected}
    ds.lines = {k: v for k, v in ds.lines.items() if k in keep}
    cal, stats, regimes_by_network, trips = _expand(ds, issues, start, end, src_root)
    regimes = regimes_by_network[network_id]

    per_line_day = {}
    for t in trips:
        for d in t.dates:
            per_line_day.setdefault((t.line_id, d), set()).add(f"{t.period}/{t.day_type}")
    fallback_days = {}
    for (lid, real, used), _ in stats.fallbacks.items():
        fallback_days.setdefault(lid, {})[real.split(" ")[0]] = used

    line_ids = sorted(keep)
    header = f"{'date':<11} {'jour':<4} {'événements':<28} {'période':<8} {'type jour':<10} " + \
             " ".join(f"{l:<26}" for l in line_ids)
    print(header)
    print("-" * len(header))
    for d in date_range(start, end):
        r = regimes[d]
        events = ", ".join(f"{e.id}{' (estimé)' if e.status == 'estimated' else ''}" for e in r.events) or "—"
        cells = []
        for lid in line_ids:
            used = per_line_day.get((lid, d))
            if not used:
                cells.append("✕ pas de service")
                continue
            real = f"{r.period}/{r.day_type}"
            label = ", ".join(sorted(used))
            fb = fallback_days.get(lid, {}).get(real)
            cells.append(f"↪ {label}" if fb else label)
        print(f"{d.isoformat():<11} {WEEKDAYS_FR[d.weekday()]:<4} {events[:28]:<28} {r.period:<8} {r.day_type:<10} "
              + " ".join(f"{c:<26}" for c in cells))
    print("\n↪ = repli (pas de grille pour ce régime), ✕ = aucun voyage ce jour-là")
    return 0
