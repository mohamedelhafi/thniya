"""Exécute les trajets de référence (data/golden-trips.yaml) contre OTP. Voir specs/10-tests-qualite.md §2."""

import json
import os
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from citydata import paths
from citydata.loader import read_yaml

TZ = ZoneInfo("Africa/Tunis")
JOURS = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6}

QUERY = """{ planConnection(origin:{location:{coordinate:{latitude:%f,longitude:%f}}},
  destination:{location:{coordinate:{latitude:%f,longitude:%f}}}, dateTime:{earliestDeparture:"%s"}, first:3) {
  routingErrors { code inputField }
  edges { node { start end legs { mode route { gtfsId } trip { tripShortName } } } } } }"""


def resolve_departure(spec, today):
    if spec.split()[0] in JOURS:
        day, hhmm = spec.split()
        delta = (JOURS[day] - today.weekday()) % 7 or 7
        d = today + timedelta(days=delta)
        h, m = map(int, hhmm.split(":"))
        return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)
    return datetime.fromisoformat(spec).replace(tzinfo=TZ)


def _plan(url, case, when):
    q = QUERY % (case["from"]["lat"], case["from"]["lon"], case["to"]["lat"], case["to"]["lon"], when.isoformat())
    req = urllib.request.Request(url, json.dumps({"query": q}).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["data"]["planConnection"]


def _check(expect, result):
    nodes = [e["node"] for e in result["edges"]]
    failures = []

    def transit_legs(node):
        return [l for l in node["legs"] if l["mode"] != "WALK"]

    first = nodes[0] if nodes else None
    if "no_transit" in expect:
        if any(transit_legs(n) for n in nodes):
            failures.append("un transport est proposé alors qu'aucun n'était attendu")
        return failures
    if not first:
        return [f"aucun itinéraire ({result['routingErrors']})"]
    if "first_modes_include" in expect:
        modes = {l["mode"] for l in first["legs"]}
        missing = set(expect["first_modes_include"]) - modes
        if missing:
            failures.append(f"modes {sorted(missing)} absents du 1er itinéraire ({sorted(modes)})")
    if "uses_line" in expect:
        routes = {l["route"]["gtfsId"].split(":", 1)[1] for l in transit_legs(first) if l.get("route")}
        if expect["uses_line"] not in routes:
            failures.append(f"ligne {expect['uses_line']} non utilisée ({sorted(routes)})")
    if "first_trip_short_name" in expect:
        trips = [l["trip"]["tripShortName"] for l in transit_legs(first) if l.get("trip")]
        if not trips or trips[0] != expect["first_trip_short_name"]:
            failures.append(f"1er train {trips[:1]} au lieu de {expect['first_trip_short_name']}")
    if "max_duration_min" in expect:
        start, end = datetime.fromisoformat(first["start"]), datetime.fromisoformat(first["end"])
        minutes = (end - start).total_seconds() / 60
        if minutes > expect["max_duration_min"]:
            failures.append(f"durée {minutes:.0f} min > {expect['max_duration_min']}")
    return failures


def _api_plan(api_url, case, when):
    body = {"from": case["from"], "to": case["to"], "time": {"mode": "DEPART_AT", "at": when.isoformat()}}
    req = urllib.request.Request(api_url + "/api/v1/itineraries", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Accept-Language": "fr"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def _check_api(expect, response):
    """Vérifie la réponse complète de l'API (sections, deuxième passe, prix) : ce que voit l'usager."""
    failures = []
    its = response["itineraries"].values()
    keys = [s["key"] for s in response["sections"]]
    for key in expect.get("sections_include", []):
        if key not in keys:
            failures.append(f"section {key} absente ({keys})")
    for wanted in expect.get("some_itinerary_uses_lines", []):
        found = [it for it in its if set(wanted) <= {l["line"]["id"] for l in it["legs"] if l.get("line")}]
        if not found:
            failures.append(f"aucun itinéraire n'enchaîne {wanted}")
        elif "max_duration_min" in expect and min(it["durationMin"] for it in found) > expect["max_duration_min"]:
            failures.append(f"{wanted} : {min(it['durationMin'] for it in found)} min > {expect['max_duration_min']}")
    if "notice" in expect and response.get("notice") != expect["notice"]:
        failures.append(f"mention {response.get('notice')} au lieu de {expect['notice']}")
    if expect.get("prices_known") and any(it["price"]["millimes"] is None for it in its):
        failures.append("prix inconnu sur au moins un itinéraire")
    return failures


def run(otp_url=None, api_url=None):
    otp_url = otp_url or os.environ.get("OTP_URL", "http://otp:8080/otp/gtfs/v1")
    api_url = api_url or os.environ.get("API_URL", "http://api:8080")
    cases = read_yaml(paths.DATA / "golden-trips.yaml") or []
    meta_path = paths.BUILD / "app-meta.json"
    window = None
    if meta_path.exists():
        w = json.loads(meta_path.read_text(encoding="utf-8"))["window"]
        window = (date.fromisoformat(w["from"]), date.fromisoformat(w["to"]))
    today = datetime.now(TZ).date()
    passed = failed = skipped = 0
    for case in cases:
        when = resolve_departure(case["departAt"], today)
        if window and not (window[0] <= when.date() <= window[1]):
            print(f"IGNORÉ  {case['id']:<32} {when.date()} hors fenêtre des données")
            skipped += 1
            continue
        if "api_expect" in case:
            failures = _check_api(case["api_expect"], _api_plan(api_url, case, when))
        else:
            failures = _check(case["expect"], _plan(otp_url, case, when))
        if failures:
            failed += 1
            print(f"ÉCHEC   {case['id']:<32} {when:%a %d/%m %H:%M} — " + " ; ".join(failures))
        else:
            passed += 1
            print(f"OK      {case['id']:<32} {when:%a %d/%m %H:%M}")
    print(f"{passed} réussi(s), {failed} échec(s), {skipped} ignoré(s)")
    return 1 if failed else 0
