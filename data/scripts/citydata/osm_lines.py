"""Extraction des lignes de transport décrites dans OpenStreetMap (relations route=*), avec leurs arrêts dans l'ordre.

Sert à amorcer les données (positions et noms réels) : les horaires restent à saisir ou à estimer.
Exemple : python -m citydata osm-lines --routes light_rail,tram,train --bbox 10.0,36.7,10.4,36.9
"""

import json
import math

import osmium

from citydata import paths

STOP_ROLES = ("stop", "stop_entry_only", "stop_exit_only", "platform", "platform_entry_only", "platform_exit_only")


class _Relations(osmium.SimpleHandler):
    def __init__(self, kinds):
        super().__init__()
        self.kinds = kinds
        self.routes = []
        self.node_ids = set()
        self.way_ids = set()

    def relation(self, r):
        if r.tags.get("type") != "route" or r.tags.get("route") not in self.kinds:
            return
        members = [(m.type, m.ref, m.role) for m in r.members if m.role in STOP_ROLES]
        if not members:
            return
        self.routes.append({
            "osm": f"relation/{r.id}",
            "route": r.tags.get("route"),
            "ref": r.tags.get("ref"),
            "name": r.tags.get("name"),
            "name_fr": r.tags.get("name:fr"),
            "name_ar": r.tags.get("name:ar"),
            "from": r.tags.get("from"),
            "to": r.tags.get("to"),
            "network": r.tags.get("network"),
            "operator": r.tags.get("operator"),
            "colour": r.tags.get("colour"),
            "members": members,
        })
        for t, ref, _ in members:
            (self.node_ids if t == "n" else self.way_ids).add(ref)


class _Objects(osmium.SimpleHandler):
    def __init__(self, node_ids, way_ids):
        super().__init__()
        self.node_ids, self.way_ids = node_ids, way_ids
        self.objects = {}

    @staticmethod
    def _tags(o):
        return {"name": o.tags.get("name"), "name_fr": o.tags.get("name:fr"), "name_ar": o.tags.get("name:ar")}

    def node(self, n):
        if n.id in self.node_ids and n.location.valid():
            self.objects[("n", n.id)] = {"lat": n.location.lat, "lon": n.location.lon, **self._tags(n)}

    def way(self, w):
        if w.id not in self.way_ids:
            return
        pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        if pts:
            self.objects[("w", w.id)] = {"lat": sum(p[0] for p in pts) / len(pts),
                                         "lon": sum(p[1] for p in pts) / len(pts), **self._tags(w)}


def _dist_m(a, b):
    k = math.pi / 180
    x = (b["lon"] - a["lon"]) * k * math.cos((a["lat"] + b["lat"]) / 2 * k)
    y = (b["lat"] - a["lat"]) * k
    return math.hypot(x, y) * 6_371_000


def extract(kinds, bbox=None, source=None):
    source = str(source or paths.OSM_GRAND_TUNIS)
    rel = _Relations(set(kinds))
    rel.apply_file(source)
    obj = _Objects(rel.node_ids, rel.way_ids)
    obj.apply_file(source, locations=True)

    west, south, east, north = map(float, bbox.split(",")) if bbox else (-180, -90, 180, 90)
    out = []
    for route in rel.routes:
        stops = []
        for t, ref, role in route["members"]:
            o = obj.objects.get((t, ref))
            if not o:
                continue
            # un arrêt = stop_position ou plateforme ; on fusionne les doublons proches (< 60 m) de même nom
            if stops and _dist_m(stops[-1], o) < 60:
                continue
            stops.append({"osm": f"{'node' if t == 'n' else 'way'}/{ref}", "role": role, **o})
        if not stops or not any(west <= s["lon"] <= east and south <= s["lat"] <= north for s in stops):
            continue
        route = {k: v for k, v in route.items() if k != "members"}
        route["stops"] = stops
        out.append(route)
    return out


def run(kinds, bbox=None, as_json=False):
    routes = extract(kinds, bbox)
    if as_json:
        print(json.dumps(routes, ensure_ascii=False, indent=1))
        return 0
    for r in sorted(routes, key=lambda r: (r["route"], r["ref"] or "", r["name"] or "")):
        names = " → ".join((s["name_fr"] or s["name"] or "?") for s in r["stops"])
        print(f"[{r['route']}] ref={r['ref']} {r['osm']} « {r['name']} » ({len(r['stops'])} arrêts)\n    {names}")
    print(f"{len(routes)} relation(s)")
    return 0
