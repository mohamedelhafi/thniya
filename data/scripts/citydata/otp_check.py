"""Vérifie que chaque arrêt actif est accessible à pied dans OTP (pas posé sur un îlot du réseau piéton).

Pour chaque arrêt, on demande à OTP les arrêts atteignables à pied (distances calculées sur le réseau de rues)
depuis 4 points situés à ~150 m autour. Si l'arrêt n'apparaît depuis aucun d'eux, il est sur un îlot.
"""

import json
import os
import urllib.request

from citydata.issues import Issues
from citydata.loader import load

OFFSETS = [(0.0013, 0), (-0.0013, 0), (0, 0.0016), (0, -0.0016)]   # ~150 m
QUERY = "{ stopsByRadius(lat:%f, lon:%f, radius:600, first:200) { edges { node { stop { gtfsId } } } } }"


def _reachable(url, lat, lon):
    req = urllib.request.Request(url, json.dumps({"query": QUERY % (lat, lon)}).encode(),
                                 {"Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=30))["data"]["stopsByRadius"]
    return {e["node"]["stop"]["gtfsId"].split(":", 1)[1] for e in (data or {}).get("edges", [])}


def check(otp_url=None, when=None):
    otp_url = otp_url or os.environ.get("OTP_URL", "http://otp:8080/otp/gtfs/v1")
    issues = Issues()
    ds = load(issues)
    served = {s if isinstance(s, str) else s["stop"]
              for line in ds.lines.values() if line["status"] == "active"
              for p in line["patterns"] for s in p["stops"]}
    failures = []
    for sid in sorted(served):
        place = ds.places[sid]
        if not any(sid in _reachable(otp_url, place["lat"] + a, place["lon"] + b) for a, b in OFFSETS):
            failures.append(sid)
            print(f"ÎLOT   {sid:<34} {place['name']['fr']}")
    print(f"{len(served) - len(failures)}/{len(served)} arrêts accessibles à pied depuis les rues voisines")
    return 1 if failures else 0
