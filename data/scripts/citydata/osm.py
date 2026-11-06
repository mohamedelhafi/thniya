"""Téléchargement et découpe de l'extrait OpenStreetMap."""

import hashlib
import os
import subprocess
import urllib.request

from citydata import paths


def _md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(force=False):
    url = os.environ.get("OSM_SOURCE_URL", "https://download.geofabrik.de/africa/tunisia-latest.osm.pbf")
    target = paths.OSM_FULL
    target.parent.mkdir(parents=True, exist_ok=True)

    expected_md5 = urllib.request.urlopen(url + ".md5", timeout=30).read().decode().split()[0]
    if target.exists() and not force and _md5(target) == expected_md5:
        print(f"Déjà à jour : {target.name}")
        return 0

    print(f"Téléchargement de {url}")
    tmp = target.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
        total = int(response.headers.get("Content-Length", 0))
        done = 0
        next_report = 0
        for chunk in iter(lambda: response.read(1 << 20), b""):
            out.write(chunk)
            done += len(chunk)
            if total and done >= next_report:
                print(f"  {done / total:6.1%}  ({done >> 20} / {total >> 20} Mo)")
                next_report += total // 10

    if _md5(tmp) != expected_md5:
        tmp.unlink()
        print("Somme MD5 incorrecte, téléchargement rejeté.")
        return 1
    tmp.replace(target)
    print(f"OK : {target} ({target.stat().st_size >> 20} Mo)")
    return 0


def clip(bbox=None):
    bbox = bbox or os.environ.get("OSM_CLIP_BBOX")
    if not bbox:
        print("OSM_CLIP_BBOX non défini.")
        return 1
    if not paths.OSM_FULL.exists():
        print("Extrait Tunisie absent : lancer d'abord osm-download.")
        return 1

    cmd = [
        "osmium", "extract",
        "--bbox", bbox,
        "--strategy", "complete_ways",
        "--overwrite",
        "--output", str(paths.OSM_GRAND_TUNIS),
        str(paths.OSM_FULL),
    ]
    print("Découpe :", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"OK : {paths.OSM_GRAND_TUNIS} ({paths.OSM_GRAND_TUNIS.stat().st_size >> 20} Mo)")
    return 0
