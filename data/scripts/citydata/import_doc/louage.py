"""Stations de louages, depuis doc/louage/donnees/stations.csv (référentiel national d'arrêts + OSM).

- Statut [C] (station du référentiel national ou gare de Tunis vérifiée) → lieu publié ; [I] (station OSM, rattachement
  à une ville déduit) → brouillon, à vérifier dans le back-office avant publication.
- Doublons : une station [I] à moins de 400 m d'une station [C] de la même ville est la même station (on garde [C]) ;
  deux points [I] à moins de 150 m aussi.
- Nom arabe : celui de la source quand c'est un vrai nom ; sinon « محطة اللواج » + nom arabe de la ville (donné par
  doc/) ; à défaut, brouillon.
- Les stations saisies à la main (places/grand-tunis/louages-stations.yaml, ex. Hammam-Lif d'après OSM) que doc/
  connaît sont reprises ici avec leur identifiant et retirées de ce fichier : aucun lieu en double.
- Aucune ligne de louage n'est créée : doc/ ne donne ni durées ni fréquences fiables (destinations seulement,
  gardées dans notes_internes pour la saisie).
"""

import re
from pathlib import Path

import yaml

from citydata.import_doc.common import (
    clean_ar, dist_m, doc_path, dump_yaml, prov, read_csv, slug, write_text, write_yaml,
)

SRC_DOC = "louage/donnees/stations.csv"
HAND_FILE = Path("places") / "grand-tunis" / "louages-stations.yaml"
GENERIC = re.compile(r"(louage|louaget|station|gare|routi|taxi|bus|rural|agence|محطة|لواج|سيارات|تكسي|^\W*$)", re.I)


# Dans « Localité, Délégation (عربي) », le nom arabe est en général celui de la délégation ; sauf pour ces localités,
# où doc/ donne le nom arabe de la localité elle-même (relu le 2026-10-14).
ARABIC_OF_LOCALITY = {"Oued Zarga", "Houmt Souk", "Midoun"}


def _ville(text):
    """Ville (ou localité) et quartier de doc/, avec leurs noms arabes quand ils sont connus.

    « Tunis — Bab Alioua (باب عليوة) » → lieu « Bab Alioua » / « باب عليوة » ;
    « Tamra, Nefza (نفزة) » → lieu « Tamra » (arabe inconnu), délégation « Nefza » / « نفزة ».
    Renvoie (lieu_fr, lieu_ar, zone_fr, zone_ar) : la zone sert de commune affichée sous le nom.
    """
    text = text.replace("— à vérifier", "").strip()
    town, _, quarter = (x.strip() for x in text.partition("—"))

    def split(part):
        ar = re.search(r"\(([^)]*[؀-ۿ][^)]*)\)", part)
        fr = re.sub(r"\([^)]*\)", "", part).strip(" ,")
        return fr, clean_ar(ar.group(1)) if ar else ""

    town_fr, town_ar = split(town)
    quarter_fr, quarter_ar = split(quarter)
    if town_fr == "Tunis" and quarter_fr:                      # gares de Tunis : le quartier (Bab Alioua…)
        return quarter_fr, quarter_ar, quarter_fr, quarter_ar
    if "," in town_fr:
        locality, delegation = (x.strip() for x in town_fr.split(",", 1))
        if locality in ARABIC_OF_LOCALITY:
            return locality, town_ar, locality, town_ar
        return locality, "", delegation, town_ar
    place_fr = town_fr + (f" – {quarter_fr}" if quarter_fr else "")
    place_ar = town_ar if not quarter_fr else (f"{town_ar} – {quarter_ar}" if town_ar and quarter_ar else "")
    return place_fr, place_ar, town_fr, town_ar


def _names(r):
    """Noms construits de la même façon en FR et en AR : « Louages <lieu> » / « محطة اللواج <lieu> ».

    Les noms de la source (« Station Louages », « Louaget », descriptions en arabe) ne sont pas des noms d'usage.
    Sans nom arabe connu pour le lieu, le nom arabe reste vide (station en brouillon).
    """
    place_fr, place_ar, zone_fr, zone_ar = _ville(r["ville"])
    fr = f"Louages {place_fr}"
    ar = f"محطة اللواج {place_ar}" if place_ar else ""
    area = {"fr": zone_fr, "ar": zone_ar} if zone_fr and zone_ar else None
    return fr, ar, area


def run(doc, src):
    rows = read_csv(doc_path(doc, SRC_DOC))
    written, rejected, notes = [], [], []

    # 1. Doublons : on garde la station la plus sûre de chaque grappe.
    keep = []
    for r in sorted(rows, key=lambda r: (r["statut"] != "C", r["gouvernorat"], r["station"])):
        p = (float(r["lat"]), float(r["lon"]))
        twin = next((k for k in keep if k["gouvernorat"] == r["gouvernorat"]
                     and dist_m(p, (float(k["lat"]), float(k["lon"]))) < (400 if k["statut"] == "C" else 150)), None)
        if twin and r["statut"] != "C":
            rejected.append(f"{r['station']} ({r['ville']}) : doublon de « {twin['station']} » "
                            f"à {dist_m(p, (float(twin['lat']), float(twin['lon']))):.0f} m")
            continue
        keep.append(r)

    # 2. Stations saisies à la main : celles que doc/ connaît prennent leur identifiant (même lieu à moins de 300 m).
    hand_path = src / HAND_FILE
    hand = (yaml.safe_load(hand_path.read_text(encoding="utf-8")) or []) if hand_path.exists() else []
    known_ids = {}
    for t in hand:
        if t["kind"] != "louage_station":
            continue
        near = min(keep, key=lambda r: dist_m((t["lat"], t["lon"]), (float(r["lat"]), float(r["lon"]))))
        if dist_m((t["lat"], t["lon"]), (float(near["lat"]), float(near["lon"]))) < 300:
            known_ids[id(near)] = t["id"]

    # Identifiants déjà attribués par un import précédent (même station à moins de 50 m) : on les garde.
    previous_path = src / "places" / "louages" / "stations.yaml"
    previous = yaml.safe_load(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else []
    for r in keep:
        if id(r) in known_ids:
            continue
        here = (float(r["lat"]), float(r["lon"]))
        old = next((p for p in previous or [] if dist_m(here, (p["lat"], p["lon"])) < 50), None)
        if old:
            known_ids[id(r)] = old["id"]

    places, used = [], set()
    for r in sorted(keep, key=lambda r: (r["gouvernorat"], r["ville"], r["station"])):
        fr, ar, area = _names(r)
        sid = known_ids.get(id(r)) or f"LOU-{slug(fr.removeprefix('Louages '))}"
        base, n = sid, 2
        while sid in used:
            sid, n = f"{base}-{n}", n + 1
        used.add(sid)
        confirmed = r["statut"] == "C"
        status = "active" if confirmed and fr and ar else "draft"
        if confirmed and status == "draft":
            notes.append(f"{sid} : nom arabe inconnu → brouillon")
        source = "OSM" if r["source_coordonnees"] == "osm" else "OFFICIEL"
        ref = ("OpenStreetMap" if source == "OSM" else "Référentiel national d'arrêts (data.transport.tn, 2026-03-10)")
        place = {"id": sid, "kind": "louage_station", "name": {"fr": fr, "ar": ar or fr}}
        if area:
            place["area"] = area
        place.update({"lat": round(float(r["lat"]), 6), "lon": round(float(r["lon"]), 6), "status": status,
                      "provenance": prov(source, f"{ref} ({r['identifiants']}) ; doc/louage/stations.md")})
        internal = [f"Gouvernorat : {r['gouvernorat']}"]
        if r["destinations"]:
            internal.append(f"Destinations : {r['destinations']} ({r['source_destinations']})")
        if r["type"]:
            internal.append(f"Type : {r['type']}")
        if r["remarque"]:
            internal.append(r["remarque"])
        if not ar:
            internal.append("Nom arabe à saisir (provisoirement le nom français)")
        if not confirmed:
            internal.append("À vérifier avant publication (statut [I] dans doc/)")
        place["notes_internes"] = " ; ".join(internal)
        places.append(place)

    written.append(write_yaml(src / "places" / "louages" / "stations.yaml", places, SRC_DOC))

    # 3. Le fichier saisi à la main ne garde que ce que doc/ ne connaît pas (aucun lieu en double).
    reused = {t["id"] for t in hand} & set(known_ids.values())
    if reused:
        lines = hand_path.read_text(encoding="utf-8").splitlines()
        header = "".join(f"{l}\n" for l in lines if l.startswith("#"))
        remaining = [t for t in hand if t["id"] not in reused]
        written.append(write_text(hand_path, header + dump_yaml(remaining)))
        notes.extend(f"{i} : repris de doc/ (même station)" for i in sorted(reused))

    return {"written": [str(p) for p in written], "removed": [],
            "counts": {"stations": len(places), "publiees": sum(p["status"] == "active" for p in places),
                       "brouillons": sum(p["status"] == "draft" for p in places)},
            "rejected": rejected, "notes": notes}
