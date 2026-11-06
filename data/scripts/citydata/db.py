"""Base de saisie PostgreSQL/PostGIS (specs/04d-base-de-saisie.md, ADR-007).

- `migrate` : applique data/db/migrations/V*.sql dans l'ordre (table thniya_migration) ;
- `import_sources` : charge data/src (validé) dans la base ;
- `export_sources` : réécrit la base au format data/src (YAML + grilles CSV), relu ensuite par le générateur ;
- `check` : vérifie que la génération depuis la base produit exactement le même GTFS que depuis les fichiers.

Aucune information ne se perd : les champs sans colonne dédiée vont dans la colonne `extra` (jsonb) et en
reviennent à l'export.
"""

import hashlib
import json
import os
import shutil
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from citydata import paths
from citydata.issues import Issues
from citydata.loader import load

TABLES = ["publication", "alert", "coverage", "transfer", "timetable_file", "pattern_stop", "pattern",
          "line_direction", "line", "fare_pair", "fare_version", "fare", "hub_member", "hub", "place", "network",
          "time_band_group", "calendar_event", "calendar_period", "mode", "feed"]
DATA_TABLES = [t for t in TABLES if t != "publication"]

# Sans date : une base inchangée produit un export identique, donc la même version des données
HEADER = ("# Exporté de la base de saisie Thniya. Pour modifier ces données, passer par le back-office :\n"
          "# ce fichier sera réécrit à la prochaine exportation (specs/04d-base-de-saisie.md).\n")


# --- Connexion et migrations ----------------------------------------------------------------------

def connect(url=None):
    import psycopg
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL n'est pas défini (voir infra/.env)")
    # autocommit : chaque bloc `with conn.transaction()` est une vraie transaction, validée à sa sortie
    return psycopg.connect(url, autocommit=True)


def migrate(conn=None, directory=None):
    conn = conn or connect()
    directory = Path(directory or paths.DB_MIGRATIONS)
    with conn.transaction():
        conn.execute("CREATE TABLE IF NOT EXISTS thniya_migration (version text PRIMARY KEY, name text NOT NULL, "
                     "checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
    applied = {v: c for v, c in conn.execute("SELECT version, checksum FROM thniya_migration")}
    done = 0
    for f in sorted(directory.glob("V*__*.sql")):
        version, name = f.stem.split("__", 1)
        sql = f.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode()).hexdigest()
        if version in applied:
            if applied[version] != checksum:
                raise SystemExit(f"La migration {f.name} a été modifiée après application : en créer une nouvelle")
            continue
        with conn.transaction():
            conn.execute(sql)
            conn.execute("INSERT INTO thniya_migration (version, name, checksum) VALUES (%s, %s, %s)",
                         (version, name, checksum))
        print(f"appliquée : {f.name}")
        done += 1
    print(f"Base à jour ({done} migration(s) appliquée(s), {len(applied) + done} au total)")
    return 0


# --- Outils de correspondance ---------------------------------------------------------------------

def _rest(item, mapped):
    return {k: v for k, v in item.items() if k not in mapped and not k.startswith("_")}


def _fr(value):
    return (value or {}).get("fr")


def _ar(value):
    return (value or {}).get("ar")


def _i18n(fr, ar):
    if fr is None and ar is None:
        return None
    out = {"fr": fr}
    if ar:
        out["ar"] = ar
    return out


def _json(value):
    from psycopg.types.json import Jsonb
    return None if value is None else Jsonb(value)


def _iso(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _put(d, key, value):
    """N'écrit la clé que si la valeur est renseignée (les fichiers restent lisibles)."""
    if value is not None and value != [] and value != {}:
        d[key] = value


def _insert(conn, table, row, geom=None):
    cols = list(row)
    values = [row[c] for c in cols]
    placeholders = ["%s"] * len(cols)
    if geom:
        cols.append("geom")
        placeholders.append(geom[0])
        values += geom[1]
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
    if table in ("fare_version", "pattern"):
        sql += " RETURNING uid"
        return conn.execute(sql, values).fetchone()[0]
    conn.execute(sql, values)
    return None


# --- Import : data/src → base ---------------------------------------------------------------------

def import_sources(src=None, conn=None, replace=False):
    src = Path(src or paths.SRC)
    issues = Issues()
    ds = load(issues, src=src)
    if issues.errors:
        issues.print()
        print("Import annulé : corriger les erreurs des sources d'abord.")
        return 1
    conn = conn or connect()
    with conn.transaction():
        existing = conn.execute("SELECT count(*) FROM place").fetchone()[0]
        if existing and not replace:
            raise SystemExit("La base contient déjà des données : relancer avec --replace pour tout remplacer")
        conn.execute(f"TRUNCATE {', '.join(DATA_TABLES)} RESTART IDENTITY CASCADE")
        counts = _import(conn, ds, src)
    print("Importé : " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def _import(conn, ds, src):
    counts = {}
    f = ds.feed
    _insert(conn, "feed", {"publisher_name": f["publisher_name"], "publisher_url": f["publisher_url"],
                           "default_lang": f["default_lang"], "contact_email": f.get("contact_email"),
                           "extra": _json(_rest(f, {"publisher_name", "publisher_url", "default_lang",
                                                    "contact_email"}))})

    for i, m in enumerate(ds.modes.values()):
        _insert(conn, "mode", {
            "id": m["id"], "position": i, "name_fr": _fr(m["name"]), "name_ar": _ar(m["name"]),
            "gtfs_route_type": m["gtfs_route_type"], "schedule_kinds": _json(m["schedule_kinds"]),
            "shows_exact_times": m["shows_exact_times"], "icon": m["icon"], "default_color": m.get("default_color"),
            "status": m["status"],
            "extra": _json(_rest(m, {"id", "name", "gtfs_route_type", "schedule_kinds", "shows_exact_times", "icon",
                                     "default_color", "status"}))})
    counts["modes"] = len(ds.modes)

    for i, p in enumerate(ds.periods.values()):
        _insert(conn, "calendar_period", {
            "id": p["id"], "position": i, "name_fr": _fr(p["name"]), "name_ar": _ar(p["name"]),
            "show_banner": p.get("show_banner", False),
            "extra": _json(_rest(p, {"id", "name", "show_banner"}))})

    for year, events in ds.years.items():
        for i, e in enumerate(events):
            _insert(conn, "calendar_event", {
                "year": year, "id": e["id"], "position": i, "kind": e["kind"],
                "date_from": e.get("date") or e["from"], "date_to": e.get("date") or e["to"],
                "status": e["status"], "name_fr": _fr(e["name"]), "name_ar": _ar(e["name"]),
                "extra": _json(_rest(e, {"id", "kind", "date", "from", "to", "status", "name"}))})
    counts["événements"] = sum(len(v) for v in ds.years.values())

    for i, g in enumerate(ds.time_bands):
        applies = g["applies_to"]
        extra = _rest(g, {"applies_to", "bands"})
        if _rest(applies, {"periods", "day_types"}):
            extra["applies_to"] = _rest(applies, {"periods", "day_types"})
        _insert(conn, "time_band_group", {"position": i, "periods": _json(applies["periods"]),
                                          "day_types": _json(applies["day_types"]), "bands": _json(g["bands"]),
                                          "extra": _json(extra)})

    network_by_dir = {}
    for n in ds.networks.values():
        network_by_dir[n["_dir"]] = n["id"]
        _insert(conn, "network", {
            "id": n["id"], "name_fr": _fr(n["name"]), "name_ar": _ar(n["name"]),
            "long_name_fr": _fr(n.get("long_name")), "long_name_ar": _ar(n.get("long_name")),
            "url": n.get("url"), "phone": n.get("phone"), "timezone": n["timezone"],
            "calendar": _json(n["calendar"]), "status": n["status"], "provenance": _json(n["provenance"]),
            "extra": _json(_rest(n, {"id", "name", "long_name", "url", "phone", "timezone", "calendar", "status",
                                     "provenance"})),
            "source_dir": n["_dir"]})
    counts["réseaux"] = len(ds.networks)

    position_in_file = {}
    for p in ds.places.values():
        k = position_in_file[p["_file"]] = position_in_file.get(p["_file"], -1) + 1
        area = p.get("area")
        _insert(conn, "place", {
            "id": p["id"], "position": k, "kind": p["kind"], "name_fr": _fr(p["name"]), "name_ar": _ar(p["name"]),
            "aliases": _json(p.get("aliases", [])), "area_fr": _fr(area), "area_ar": _ar(area),
            "parent_id": p.get("parent"), "code": p.get("code"), "platform_code": p.get("platform_code"),
            "wheelchair": p.get("wheelchair"), "status": p["status"], "provenance": _json(p["provenance"]),
            "note": p.get("notes_internes"),
            "extra": _json(_rest(p, {"id", "kind", "name", "aliases", "area", "lat", "lon", "parent", "code",
                                     "platform_code", "wheelchair", "status", "provenance", "notes_internes"})),
            "source_file": p["_file"]},
            geom=("ST_SetSRID(ST_MakePoint(%s, %s), 4326)", [p["lon"], p["lat"]]))
    counts["lieux"] = len(ds.places)

    for i, h in enumerate(ds.hubs.values()):
        _insert(conn, "hub", {"id": h["id"], "position": i, "name_fr": _fr(h["name"]), "name_ar": _ar(h["name"]),
                              "aliases": _json(h.get("aliases", [])), "status": h["status"],
                              "extra": _json(_rest(h, {"id", "name", "aliases", "members", "status"}))})
        for k, member in enumerate(h["members"]):
            _insert(conn, "hub_member", {"hub_id": h["id"], "place_id": member, "position": k})

    for fare in ds.fares.values():
        net_dir = fare["_file"].split("/fares/")[0]
        _insert(conn, "fare", {
            "id": fare["id"], "network_id": network_by_dir.get(net_dir), "model": fare["model"],
            "currency": fare["currency"], "categories": _json(fare.get("categories", [])),
            "provenance": _json(fare["provenance"]),
            "extra": _json(_rest(fare, {"id", "model", "currency", "categories", "versions", "provenance"})),
            "source_file": fare["_file"]})
        for v in fare["versions"]:
            uid = _insert(conn, "fare_version", {
                "fare_id": fare["id"], "valid_from": v["valid_from"], "price_millimes": _json(v.get("price_millimes")),
                "matrix_file": v.get("matrix_file"),
                "extra": _json(_rest(v, {"valid_from", "price_millimes", "matrix_file", "pairs"}))})
            for k, pair in enumerate(v.get("pairs", [])):
                _insert(conn, "fare_pair", {"fare_version_uid": uid, "position": k, "from_place_id": pair["from"],
                                            "to_place_id": pair["to"],
                                            "price_millimes": _json(pair["price_millimes"])})
    counts["tarifs"] = len(ds.fares)

    for line in ds.lines.values():
        _insert(conn, "line", {
            "id": line["id"], "network_id": line["network"], "mode_id": line["mode"],
            "public_code": line["public_code"], "name_fr": _fr(line["name"]), "name_ar": _ar(line["name"]),
            "long_name_fr": _fr(line.get("long_name")), "long_name_ar": _ar(line.get("long_name")),
            "color": line.get("color"), "text_color": line.get("text_color"), "status": line["status"],
            "fare_id": line.get("fare"), "schedule": _json(line["schedule"]), "provenance": _json(line["provenance"]),
            "extra": _json(_rest(line, {"id", "network", "mode", "public_code", "name", "long_name", "color",
                                        "text_color", "status", "fare", "schedule", "provenance", "directions",
                                        "patterns"})),
            "source_file": line["_file"]})
        for k, d in enumerate(line["directions"]):
            _insert(conn, "line_direction", {"line_id": line["id"], "id": d["id"], "position": k,
                                             "headsign_fr": _fr(d["headsign"]), "headsign_ar": _ar(d["headsign"]),
                                             "extra": _json(_rest(d, {"id", "headsign"}))})
        for k, pat in enumerate(line["patterns"]):
            uid = _insert(conn, "pattern", {
                "line_id": line["id"], "id": pat["id"], "position": k, "direction_id": pat["direction"],
                "main": pat.get("main", False), "run_times": _json(pat.get("run_times")),
                "extra": _json(_rest(pat, {"id", "direction", "main", "run_times", "stops"}))})
            for seq, entry in enumerate(pat["stops"]):
                stop = entry if isinstance(entry, str) else entry["stop"]
                extra = {} if isinstance(entry, str) else _rest(entry, {"stop"})
                _insert(conn, "pattern_stop", {"pattern_uid": uid, "position": seq, "place_id": stop,
                                               "extra": _json(extra)})
    counts["lignes"] = len(ds.lines)

    line_by_dir = {}
    for line in ds.lines.values():
        source_dir = line["schedule"].get("source_dir")
        if source_dir:
            line_by_dir[f"{line['_dir']}/{source_dir}"] = line["id"]
    files = 0
    for path in sorted(src.glob("networks/*/timetables/**/*")):
        if not path.is_file() or path.suffix not in (".csv", ".yaml"):
            continue
        rel = path.relative_to(src).as_posix()
        line_id = next((lid for prefix, lid in line_by_dir.items() if rel.startswith(prefix + "/")), None)
        _insert(conn, "timetable_file", {"path": rel, "network_id": network_by_dir.get(rel.split("/timetables/")[0]),
                                         "line_id": line_id, "kind": path.suffix[1:],
                                         "content": path.read_text(encoding="utf-8")})
        files += 1
    counts["grilles"] = files

    for i, t in enumerate(ds.transfers):
        _insert(conn, "transfer", {"position": i, "from_place_id": t.get("from"), "to_place_id": t.get("to"),
                                   "extra": _json(_rest(t, {"from", "to"}))})

    for i, c in enumerate(ds.coverage):
        _insert(conn, "coverage", {"id": c["id"], "position": i, "name_fr": _fr(c["name"]), "name_ar": _ar(c["name"]),
                                   "level": c["level"], "modes": _json(c["modes"]), "status": c["status"],
                                   "extra": _json(_rest(c, {"id", "name", "level", "modes", "status", "polygon"}))},
                geom=("ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)",
                      [json.dumps({"type": "Polygon", "coordinates": [c["polygon"]]})]))

    for i, a in enumerate(ds.alerts):
        _insert(conn, "alert", {
            "id": a["id"], "position": i, "effect": a["effect"], "severity": a["severity"], "status": a["status"],
            "title_fr": _fr(a["title"]), "title_ar": _ar(a["title"]), "body_fr": _fr(a.get("body")),
            "body_ar": _ar(a.get("body")), "url": a.get("url"), "scope": _json(a["scope"]),
            "active_periods": _json(a["active_periods"]), "provenance": _json(a["provenance"]),
            "extra": _json(_rest(a, {"id", "effect", "severity", "status", "title", "body", "url", "scope",
                                     "active_periods", "provenance"})),
            "source_file": a["_file"]})
    counts["alertes"] = len(ds.alerts)
    return counts


# --- Export : base → data/src ---------------------------------------------------------------------

def _rows(conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def export_sources(out=None, conn=None):
    """Écrit la base au format data/src dans `out` (vidé au préalable). Renvoie le nombre de fichiers écrits."""
    out = Path(out or paths.SRC_FROM_DB)
    conn = conn or connect()
    files = _collect(conn)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in sorted(files.items()):
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            text = yaml.safe_dump(content, allow_unicode=True, sort_keys=False, width=120, default_flow_style=None)
            path.write_text(HEADER + text, encoding="utf-8")
    print(f"Exporté : {len(files)} fichiers dans {out}")
    return len(files)


def _collect(conn):
    files = {}

    f = _rows(conn, "SELECT * FROM feed")
    if f:
        f = f[0]
        feed = {"publisher_name": f["publisher_name"], "publisher_url": f["publisher_url"],
                "default_lang": f["default_lang"], "contact_email": f["contact_email"]}
        files["reference/feed.yaml"] = {**feed, **f["extra"]}

    modes = []
    for m in _rows(conn, "SELECT * FROM mode ORDER BY position, id"):
        d = {"id": m["id"], "name": _i18n(m["name_fr"], m["name_ar"]), "gtfs_route_type": m["gtfs_route_type"],
             "schedule_kinds": m["schedule_kinds"], "shows_exact_times": m["shows_exact_times"], "icon": m["icon"]}
        _put(d, "default_color", m["default_color"])
        modes.append({**d, **m["extra"], "status": m["status"]})
    files["reference/modes.yaml"] = modes

    periods = []
    for p in _rows(conn, "SELECT * FROM calendar_period ORDER BY position, id"):
        periods.append({"id": p["id"], "name": _i18n(p["name_fr"], p["name_ar"]), **p["extra"],
                        "show_banner": p["show_banner"]})
    files["calendar/periods.yaml"] = periods

    years = {}
    for e in _rows(conn, "SELECT * FROM calendar_event ORDER BY year, position, id"):
        d = {"id": e["id"], "kind": e["kind"]}
        if e["date_from"] == e["date_to"]:
            d["date"] = _iso(e["date_from"])
        else:
            d["from"], d["to"] = _iso(e["date_from"]), _iso(e["date_to"])
        d.update({"status": e["status"], "name": _i18n(e["name_fr"], e["name_ar"]), **e["extra"]})
        years.setdefault(e["year"], []).append(d)
    for year, events in years.items():
        files[f"calendar/years/{year}.yaml"] = {"year": year, "events": events}

    bands = []
    for g in _rows(conn, "SELECT * FROM time_band_group ORDER BY position"):
        extra = dict(g["extra"])
        applies = {"periods": g["periods"], "day_types": g["day_types"], **extra.pop("applies_to", {})}
        bands.append({"applies_to": applies, "bands": g["bands"], **extra})
    files["calendar/time-bands.yaml"] = bands

    net_dirs = {}
    for n in _rows(conn, "SELECT * FROM network ORDER BY id"):
        net_dir = n["source_dir"] or f"networks/{n['id'].lower()}"
        net_dirs[n["id"]] = net_dir
        d = {"id": n["id"], "name": _i18n(n["name_fr"], n["name_ar"])}
        _put(d, "long_name", _i18n(n["long_name_fr"], n["long_name_ar"]))
        _put(d, "url", n["url"])
        _put(d, "phone", n["phone"])
        d.update({"timezone": n["timezone"], "calendar": n["calendar"], **n["extra"], "status": n["status"],
                  "provenance": n["provenance"]})
        files[f"{net_dir}/network.yaml"] = d

    for p in _rows(conn, "SELECT *, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM place "
                         "ORDER BY source_file NULLS LAST, position, id"):
        d = {"id": p["id"], "kind": p["kind"]}
        _put(d, "parent", p["parent_id"])
        d["name"] = _i18n(p["name_fr"], p["name_ar"])
        _put(d, "aliases", p["aliases"])
        _put(d, "area", _i18n(p["area_fr"], p["area_ar"]))
        _put(d, "code", p["code"])
        _put(d, "platform_code", p["platform_code"])
        d["lat"], d["lon"] = round(p["lat"], 7), round(p["lon"], 7)
        _put(d, "wheelchair", p["wheelchair"])
        d.update({"status": p["status"], "provenance": p["provenance"], **p["extra"]})
        _put(d, "notes_internes", p["note"])
        files.setdefault(p["source_file"] or "places/saisie.yaml", []).append(d)

    hubs = []
    members = {}
    for m in _rows(conn, "SELECT hub_id, place_id FROM hub_member ORDER BY hub_id, position, uid"):
        members.setdefault(m["hub_id"], []).append(m["place_id"])
    for h in _rows(conn, "SELECT * FROM hub ORDER BY position, id"):
        d = {"id": h["id"], "name": _i18n(h["name_fr"], h["name_ar"])}
        _put(d, "aliases", h["aliases"])
        d.update({"members": members.get(h["id"], []), **h["extra"], "status": h["status"]})
        hubs.append(d)
    if hubs:
        files["places/hubs.yaml"] = hubs

    pairs = {}
    for p in _rows(conn, "SELECT * FROM fare_pair ORDER BY fare_version_uid, position, uid"):
        pairs.setdefault(p["fare_version_uid"], []).append(
            {"from": p["from_place_id"], "to": p["to_place_id"], "price_millimes": p["price_millimes"]})
    versions = {}
    for v in _rows(conn, "SELECT * FROM fare_version ORDER BY fare_id, valid_from"):
        d = {"valid_from": _iso(v["valid_from"])}
        _put(d, "price_millimes", v["price_millimes"])
        _put(d, "matrix_file", v["matrix_file"])
        _put(d, "pairs", pairs.get(v["uid"]))
        versions.setdefault(v["fare_id"], []).append({**d, **v["extra"]})
    for fare in _rows(conn, "SELECT * FROM fare ORDER BY id"):
        d = {"id": fare["id"], "model": fare["model"], "currency": fare["currency"]}
        _put(d, "categories", fare["categories"])
        d.update({"versions": versions.get(fare["id"], []), **fare["extra"], "provenance": fare["provenance"]})
        default = f"{net_dirs.get(fare['network_id'], 'networks/commun')}/fares/{fare['id'].lower()}.yaml"
        files[fare["source_file"] or default] = d

    directions, patterns, stops = {}, {}, {}
    for d in _rows(conn, "SELECT * FROM line_direction ORDER BY line_id, position, uid"):
        directions.setdefault(d["line_id"], []).append(
            {"id": d["id"], "headsign": _i18n(d["headsign_fr"], d["headsign_ar"]), **d["extra"]})
    for s in _rows(conn, "SELECT * FROM pattern_stop ORDER BY pattern_uid, position"):
        stops.setdefault(s["pattern_uid"], []).append(
            {"stop": s["place_id"], **s["extra"]} if s["extra"] else s["place_id"])
    for p in _rows(conn, "SELECT * FROM pattern ORDER BY line_id, position, uid"):
        d = {"id": p["id"], "direction": p["direction_id"]}
        if p["main"]:
            d["main"] = True
        d["stops"] = stops.get(p["uid"], [])
        _put(d, "run_times", p["run_times"])
        patterns.setdefault(p["line_id"], []).append({**d, **p["extra"]})
    for line in _rows(conn, "SELECT * FROM line ORDER BY id"):
        d = {"id": line["id"], "network": line["network_id"], "mode": line["mode_id"],
             "public_code": line["public_code"], "name": _i18n(line["name_fr"], line["name_ar"])}
        _put(d, "long_name", _i18n(line["long_name_fr"], line["long_name_ar"]))
        _put(d, "color", line["color"])
        _put(d, "text_color", line["text_color"])
        d.update({"status": line["status"], "directions": directions.get(line["id"], []),
                  "patterns": patterns.get(line["id"], []), **line["extra"], "schedule": line["schedule"]})
        _put(d, "fare", line["fare_id"])
        d["provenance"] = line["provenance"]
        default = f"{net_dirs.get(line['network_id'], 'networks/commun')}/lines/{line['id'].lower()}.yaml"
        files[line["source_file"] or default] = d

    for t in _rows(conn, "SELECT path, content FROM timetable_file ORDER BY path"):
        files[t["path"]] = t["content"]

    files["transfers.yaml"] = [
        {**({"from": t["from_place_id"]} if t["from_place_id"] else {}),
         **({"to": t["to_place_id"]} if t["to_place_id"] else {}), **t["extra"]}
        for t in _rows(conn, "SELECT * FROM transfer ORDER BY position, uid")]

    coverage = []
    for c in _rows(conn, "SELECT *, ST_AsGeoJSON(geom, 7) AS polygon FROM coverage ORDER BY position, id"):
        ring = json.loads(c["polygon"])["coordinates"][0]
        coverage.append({"id": c["id"], "name": _i18n(c["name_fr"], c["name_ar"]), "level": c["level"],
                         "modes": c["modes"], "polygon": ring, **c["extra"], "status": c["status"]})
    if coverage:
        files["coverage.yaml"] = coverage

    for a in _rows(conn, "SELECT * FROM alert ORDER BY position, id"):
        d = {"id": a["id"], "active_periods": a["active_periods"], "scope": a["scope"], "effect": a["effect"],
             "severity": a["severity"], "title": _i18n(a["title_fr"], a["title_ar"])}
        _put(d, "body", _i18n(a["body_fr"], a["body_ar"]))
        _put(d, "url", a["url"])
        d.update({**a["extra"], "status": a["status"], "provenance": a["provenance"]})
        files[a["source_file"] or f"alerts/{a['id'].lower()}.yaml"] = d
    return files


# --- Vérification et publication ------------------------------------------------------------------

def check(conn=None):
    """La génération depuis la base doit produire exactement le même GTFS que depuis data/src."""
    from citydata import build
    conn = conn or connect()
    tmp = paths.BUILD / "db-check"
    if tmp.exists():
        shutil.rmtree(tmp)
    export_sources(tmp / "src", conn)
    now = datetime.now(ZoneInfo("Africa/Tunis")).replace(microsecond=0)
    results = {}
    for name, src in (("fichiers", paths.SRC), ("base", tmp / "src")):
        out = tmp / name
        code = build.build(src=src, out_dir=out, data_version="check", now=now)
        if code:
            print(f"Échec de la génération depuis {name}")
            return 1
        meta = json.loads((out / "app-meta.json").read_text(encoding="utf-8"))
        results[name] = ((out / "gtfs.zip").read_bytes(), meta)
    same_gtfs = results["fichiers"][0] == results["base"][0]
    same_meta = results["fichiers"][1] == results["base"][1]
    print(f"GTFS identique : {'oui' if same_gtfs else 'NON'} | app-meta identique : {'oui' if same_meta else 'NON'}")
    if not same_meta:
        a, b = results["fichiers"][1], results["base"][1]
        for key in a:
            if a[key] != b.get(key):
                print(f"  différence dans app-meta.{key}")
    return 0 if same_gtfs and same_meta else 1


def publish(requested_by=None, conn=None):
    """Export de la base → validation et génération (GTFS, app-meta) → journal `publication`.

    La reconstruction du graphe OTP se fait ensuite hors du conteneur (infra/scripts/publish.sh).
    """
    from citydata import build
    conn = conn or connect()
    with conn.transaction():
        uid = conn.execute("INSERT INTO publication (requested_by) VALUES (%s) RETURNING uid",
                           (requested_by or os.environ.get("USER") or "publish",)).fetchone()[0]
    try:
        export_sources(paths.SRC_FROM_DB, conn)
        code = build.build(src=paths.SRC_FROM_DB)
        report = json.loads((paths.BUILD / "report.json").read_text(encoding="utf-8"))
        levels = [i["level"] for i in report.get("issues", [])]
        status = "ok" if code == 0 else "failed"
        with conn.transaction():
            conn.execute(
                "UPDATE publication SET status = %s, finished_at = now(), data_version = %s, errors = %s, "
                "warnings = %s, counts = %s, report = %s WHERE uid = %s",
                (status, report.get("dataVersion"), levels.count("error"), levels.count("warning"),
                 _json(report.get("counts")), (paths.BUILD / "report.md").read_text(encoding="utf-8"), uid))
        print(f"Publication n°{uid} : {status}")
        return code
    except Exception as exc:
        with conn.transaction():
            conn.execute("UPDATE publication SET status = 'failed', finished_at = now(), report = %s WHERE uid = %s",
                         (f"{type(exc).__name__}: {exc}", uid))
        raise
