"""Écriture du GTFS (specs/04c-generation-gtfs.md §3). Sortie déterministe : même source → même zip."""

import csv
import io
import zipfile
from collections import Counter, defaultdict

from citydata.timeutil import gtfs_time

LOCATION_TYPE = {"station": 1, "louage_station": 1, "platform": 0, "stop": 0, "louage_bay": 0,
                 "hail_point": 0, "entrance": 2}
WHEELCHAIR = {"yes": 1, "no": 2, "unknown": 0}


def _csv(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def headsign_text(ds, headsign, lang="fr"):
    if "stop_ref" in headsign:
        name = ds.places[headsign["stop_ref"]]["name"]
        return name.get(lang) or name["fr"]
    return headsign.get(lang) or headsign["fr"]


def assign_services(trips):
    """Regroupe les voyages par jeu de dates : un service_id lisible par clé, suffixé si les dates diffèrent."""
    by_key = defaultdict(dict)   # clé -> {frozenset(dates): service_id}
    for trip in sorted(trips, key=lambda t: t.trip_id):
        dates = frozenset(trip.dates)
        variants = by_key[trip.service_key]
        if dates not in variants:
            variants[dates] = trip.service_key if not variants else f"{trip.service_key}~{len(variants) + 1}"
        trip.service_id = variants[dates]
    services = {}
    for variants in by_key.values():
        for dates, sid in variants.items():
            services[sid] = dates
    return services


def write(ds, trips, window, data_version, out_path):
    trips = [t for t in trips if t.dates]
    services = assign_services(trips)
    used_lines = {t.line_id for t in trips}
    used_stops = {c.stop for t in trips for c in t.calls}

    published = [p for p in ds.places.values() if p["status"] in ("active", "suspended")]
    children = defaultdict(list)
    for p in published:
        if p.get("parent"):
            children[p["parent"]].append(p["id"])
    exported_stops = {p["id"] for p in published if p["id"] in used_stops or children.get(p["id"])}
    for p in published:   # parents des arrêts exportés
        if p["id"] in exported_stops and p.get("parent"):
            exported_stops.add(p["parent"])

    files = {}
    networks = sorted({ds.lines[l]["network"] for l in used_lines})
    files["agency.txt"] = _csv(
        ["agency_id", "agency_name", "agency_url", "agency_timezone", "agency_lang", "agency_phone"],
        [[n, ds.networks[n]["name"]["fr"], ds.networks[n].get("url", ds.feed["publisher_url"]),
          ds.networks[n]["timezone"], "fr", ds.networks[n].get("phone") or ""] for n in networks])

    stop_rows = []
    for sid in sorted(exported_stops):
        p = ds.places[sid]
        loc = LOCATION_TYPE[p["kind"]]
        if loc == 1 and not children.get(sid):
            loc = 0   # une gare sans quais déclarés est desservie directement
        stop_rows.append([sid, p.get("code", ""), p["name"]["fr"], f"{p['lat']:.6f}", f"{p['lon']:.6f}", loc,
                          p.get("parent", "") if p.get("parent") in exported_stops else "",
                          p.get("platform_code", ""), WHEELCHAIR[p.get("wheelchair", "unknown")]])
    files["stops.txt"] = _csv(["stop_id", "stop_code", "stop_name", "stop_lat", "stop_lon", "location_type",
                               "parent_station", "platform_code", "wheelchair_boarding"], stop_rows)

    route_rows = []
    for lid in sorted(used_lines):
        line = ds.lines[lid]
        mode = ds.modes[line["mode"]]
        color = (line.get("color") or mode.get("default_color", "#555555"))[1:]
        text = (line.get("text_color") or "#FFFFFF")[1:]
        long_name = (line.get("long_name") or line["name"])["fr"]
        desc = line["name"]["fr"] if line["name"]["fr"] != long_name else ""
        route_rows.append([lid, line["network"], line["public_code"], long_name, mode["gtfs_route_type"],
                           color, text, desc])
    files["routes.txt"] = _csv(["route_id", "agency_id", "route_short_name", "route_long_name", "route_type",
                                "route_color", "route_text_color", "route_desc"], route_rows)

    trip_rows, stop_time_rows, freq_rows = [], [], []
    for t in sorted(trips, key=lambda t: t.trip_id):
        line = ds.lines[t.line_id]
        dirs = [d["id"] for d in line["directions"]]
        direction_id = dirs.index(t.direction) if len(dirs) <= 2 else ""
        trip_rows.append([t.line_id, t.service_id, t.trip_id, headsign_text(ds, t.headsign), t.short_name or "",
                          direction_id])
        for seq, c in enumerate(t.calls, start=1):
            stop_time_rows.append([t.trip_id, gtfs_time(c.arrival), gtfs_time(c.departure), c.stop, seq,
                                   c.pickup, c.dropoff, 0 if c.continuous else "", 0 if c.continuous else "",
                                   1 if t.kind == "timetable" else 0])
        for start, end, headway in t.frequencies:
            # OTP compte une attente d'un intervalle complet pour exact_times=0 (pire cas, specs/05-otp.md §3 S1) :
            # on lui donne la moitié, soit l'attente moyenne d'un voyageur arrivant au hasard. L'intervalle réel
            # reste dans app-meta.json pour l'affichage (« toutes les 12 min »).
            freq_rows.append([t.trip_id, gtfs_time(start), gtfs_time(end), max(60, headway // 2), 0])
    files["trips.txt"] = _csv(["route_id", "service_id", "trip_id", "trip_headsign", "trip_short_name",
                               "direction_id"], trip_rows)
    files["stop_times.txt"] = _csv(["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence",
                                    "pickup_type", "drop_off_type", "continuous_pickup", "continuous_drop_off",
                                    "timepoint"], stop_time_rows)
    if freq_rows:
        files["frequencies.txt"] = _csv(["trip_id", "start_time", "end_time", "headway_secs", "exact_times"],
                                        freq_rows)

    files["calendar_dates.txt"] = _csv(
        ["service_id", "date", "exception_type"],
        [[sid, d.strftime("%Y%m%d"), 1] for sid in sorted(services) for d in sorted(services[sid])])

    translations = []   # liste : le nombre d'arrêts par orthographe départage les traductions
    for sid in exported_stops:
        name = ds.places[sid]["name"]
        if name.get("ar"):
            translations.append(("stops", "stop_name", "ar", name["ar"], name["fr"]))
    for lid in used_lines:
        line = ds.lines[lid]
        long_name = line.get("long_name") or line["name"]
        if long_name.get("ar"):
            translations.append(("routes", "route_long_name", "ar", long_name["ar"], long_name["fr"]))
        if line["name"].get("ar"):
            translations.append(("routes", "route_desc", "ar", line["name"]["ar"], line["name"]["fr"]))
    for t in trips:
        fr, ar = headsign_text(ds, t.headsign, "fr"), headsign_text(ds, t.headsign, "ar")
        if ar != fr:
            translations.append(("trips", "trip_headsign", "ar", ar, fr))
    for n in networks:
        if ds.networks[n]["name"].get("ar"):
            name = ds.networks[n]["name"]
            translations.append(("agency", "agency_name", "ar", name["ar"], name["fr"]))
    # Une traduction par valeur (clé GTFS : table, champ, langue, valeur) : deux arrêts de même nom français peuvent
    # avoir des orthographes arabes différentes (côtés d'une rue) ; on garde la plus fréquente, puis la plus courte.
    # Sans conséquence pour l'app : l'API prend les noms arabes de chaque arrêt dans app-meta.json.
    by_key = defaultdict(Counter)
    for table, field, lang, translation, value in translations:
        by_key[(table, field, lang, value)][translation] += 1
    rows = []
    for (table, field, lang, value), counts in by_key.items():
        best = min(counts, key=lambda t: (-counts[t], len(t), t))
        rows.append((table, field, lang, best, value))
    files["translations.txt"] = _csv(["table_name", "field_name", "language", "translation", "field_value"],
                                     sorted(rows))

    files["feed_info.txt"] = _csv(
        ["feed_publisher_name", "feed_publisher_url", "feed_lang", "default_lang", "feed_start_date",
         "feed_end_date", "feed_version", "feed_contact_email", "feed_contact_url"],
        [[ds.feed["publisher_name"], ds.feed["publisher_url"], ds.feed["default_lang"], ds.feed["default_lang"],
          window[0].strftime("%Y%m%d"), window[1].strftime("%Y%m%d"), data_version,
          ds.feed.get("contact_email") or "", ds.feed["publisher_url"]]])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    return {
        "routes": len(route_rows), "stops": len(stop_rows), "trips": len(trip_rows),
        "stop_times": len(stop_time_rows), "frequencies": len(freq_rows), "services": len(services),
    }
