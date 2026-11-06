"""Recherche d'objets OSM (gares, arrêts, stations de louages…) pour aider à la saisie des données.

Exemple : python -m citydata osm-find --preset train --bbox 10.15,36.60,10.45,36.82
"""

import json
import subprocess
import tempfile
from pathlib import Path

from citydata import paths

PRESETS = {
    "train": ["n/railway=station,halt", "n/public_transport=station", "n/train=yes"],
    "station-area": ["nwr/railway=station,platform", "nwr/public_transport=platform,station",
                     "nwr/building=train_station", "nwr/railway=subway_entrance,train_station_entrance"],
    "metro": ["n/railway=tram_stop", "n/tram=yes", "n/light_rail=yes"],
    "bus": ["n/highway=bus_stop", "n/bus=yes"],
    "louage": ["n/amenity=bus_station", "n/amenity=taxi", "nw/name~louage", "nw/name:ar~لواج"],
    "routes": ["r/route=train,tram,light_rail,bus,share_taxi"],
}


def _centroid(geom):
    """Point, ligne ou polygone -> moyenne des sommets (suffisant pour situer un quai ou un bâtiment)."""
    coords = geom["coordinates"]
    if geom["type"] == "Point":
        return coords[0], coords[1]
    flat = []

    def walk(c):
        if isinstance(c[0], (int, float)):
            flat.append(c)
        else:
            for x in c:
                walk(x)
    walk(coords)
    return sum(p[0] for p in flat) / len(flat), sum(p[1] for p in flat) / len(flat)


def _keep(props, preset):
    if preset == "train":
        return props.get("railway") in ("station", "halt") or props.get("train") == "yes"
    return True


def find(preset, bbox=None, name=None, as_json=False, source=None):
    source = Path(source) if source else paths.OSM_GRAND_TUNIS
    with tempfile.TemporaryDirectory() as tmp:
        filtered = Path(tmp) / "f.osm.pbf"
        exported = Path(tmp) / "f.geojsonseq"
        subprocess.run(["osmium", "tags-filter", "-O", "-o", str(filtered), str(source), *PRESETS[preset]],
                       check=True, capture_output=True)
        if bbox:
            clipped = Path(tmp) / "c.osm.pbf"
            subprocess.run(["osmium", "extract", "-O", "-b", bbox, "-o", str(clipped), str(filtered)],
                           check=True, capture_output=True)
            filtered = clipped
        subprocess.run(["osmium", "export", "-O", "-f", "geojsonseq", "--add-unique-id=type_id",
                        "-o", str(exported), str(filtered)], check=True, capture_output=True)

        results = []
        for line in exported.read_text(encoding="utf-8").splitlines():
            line = line.strip("\x1e \t")
            if not line:
                continue
            feature = json.loads(line)
            props, geom = feature["properties"], feature["geometry"]
            if not _keep(props, preset):
                continue
            if name and name.lower() not in json.dumps(props, ensure_ascii=False).lower():
                continue
            lon, lat = _centroid(geom)
            results.append({
                "osm": feature.get("id"),
                "lat": round(lat, 6) if lat else None,
                "lon": round(lon, 6) if lon else None,
                "name": props.get("name"),
                "name_fr": props.get("name:fr"),
                "name_ar": props.get("name:ar"),
                "tags": {k: v for k, v in props.items() if not k.startswith("name")},
            })

    results.sort(key=lambda r: -(r["lat"] or 0))
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            kind = r["tags"].get("railway") or r["tags"].get("highway") or r["tags"].get("route") or r["tags"].get("amenity") or ""
            print(f'{r["osm"]:<16} {r["lat"] or "":<10} {r["lon"] or "":<10} {kind:<10} '
                  f'{r["name"] or ""} | fr={r["name_fr"] or "-"} | ar={r["name_ar"] or "-"}')
        print(f"{len(results)} résultat(s)")
    return 0
