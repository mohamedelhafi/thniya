"""Calage des arrêts sur le réseau piéton principal d'OSM.

Dans OSM, beaucoup de stations (métro au milieu d'une avenue, quais de gare) sont dessinées sur des chemins
isolés (îlots) que le calculateur d'itinéraires ne peut pas atteindre à pied. On ramène chaque arrêt sur le
point du réseau piéton principal (la plus grande composante connexe) le plus proche, à moins de `max_m` mètres.
Voir specs/05-otp.md §5.
"""

import math

import osmium

from citydata import paths

WALKABLE = {"footway", "path", "pedestrian", "steps", "residential", "living_street", "service", "unclassified",
            "tertiary", "tertiary_link", "secondary", "secondary_link", "primary", "primary_link", "track",
            "cycleway", "road"}
CELL = 0.002  # ~200 m


class _Ways(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.parent = {}
        self.coords = {}

    def _find(self, x):
        root = x
        while self.parent.get(root, root) != root:
            root = self.parent[root]
        while self.parent.get(x, x) != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def _union(self, a, b):
        ra, rb = self._find(a), self._find(b)
        if ra != rb:
            self.parent[ra] = rb

    def way(self, w):
        t = w.tags
        if t.get("highway") not in WALKABLE or t.get("area") == "yes":
            return
        if t.get("access") in ("no", "private") or t.get("foot") in ("no", "private"):
            return
        prev = None
        for nd in w.nodes:
            if not nd.location.valid():
                continue
            self.coords[nd.ref] = (nd.location.lat, nd.location.lon)
            self.parent.setdefault(nd.ref, nd.ref)
            if prev is not None:
                self._union(prev, nd.ref)
            prev = nd.ref


class WalkNetwork:
    """Nœuds de la plus grande composante piétonne, indexés par grille pour la recherche du plus proche."""

    def __init__(self, source=None):
        h = _Ways()
        h.apply_file(str(source or paths.OSM_GRAND_TUNIS), locations=True)
        sizes = {}
        for n in h.coords:
            r = h._find(n)
            sizes[r] = sizes.get(r, 0) + 1
        main = max(sizes, key=sizes.get)
        self.grid = {}
        for n, (lat, lon) in h.coords.items():
            if h._find(n) == main:
                self.grid.setdefault((int(lat / CELL), int(lon / CELL)), []).append((lat, lon))
        self.nodes = sum(len(v) for v in self.grid.values())

    def nearest(self, lat, lon):
        ci, cj = int(lat / CELL), int(lon / CELL)
        best, best_d = None, float("inf")
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for p in self.grid.get((ci + di, cj + dj), ()):
                    d = _dist_m((lat, lon), p)
                    if d < best_d:
                        best, best_d = p, d
        return best, best_d


def _dist_m(a, b):
    k = math.pi / 180
    x = (b[1] - a[1]) * k * math.cos((a[0] + b[0]) / 2 * k)
    y = (b[0] - a[0]) * k
    return math.hypot(x, y) * 6_371_000


def snap(places, network, max_m=150):
    """Cale les lieux (dicts lat/lon) sur le réseau principal. Renvoie [(id, distance déplacée)]."""
    moved = []
    for p in places:
        node, d = network.nearest(p["lat"], p["lon"])
        if node is None or d > max_m or d < 3:
            continue
        p["lat"], p["lon"] = round(node[0], 6), round(node[1], 6)
        moved.append((p["id"], round(d)))
    return moved
