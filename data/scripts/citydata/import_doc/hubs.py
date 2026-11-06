"""Pôles d'échange : regroupe les lieux de réseaux différents qui forment une même correspondance.

Un pôle réunit, à moins de RADIUS_M les uns des autres (WIDE_RADIUS_M avec une station de louages ou une gare
routière), des lieux « structurants » d'au moins deux familles
différentes : gare SNCFT, station de métro, station du TGM, station de louages, gare routière SNTRI, arrêt de bus
d'un pôle Transtu. Les simples arrêts de bus ne créent pas de pôle (il y en a près de chaque station).

Chaque pôle est centré sur son lieu le plus structurant (gare SNCFT, puis métro, TGM, gare routière, louages, bus) :
tous ses membres sont à portée de ce centre. Les pôles déjà connus gardent leur identifiant et leur nom ; les nouveaux
prennent le nom de la gare SNCFT, sinon de la gare routière, sinon de la station de métro…
"""

from citydata.import_doc.common import dist_m, norm_name, slug, write_yaml
from citydata.issues import Issues
from citydata.loader import load

RADIUS_M = 250
WIDE_RADIUS_M = 450      # gares routières et stations de louages : grandes emprises, on y marche plus loin
FAMILY_ORDER = ["SNCFT", "METRO", "TGM", "SNTRI", "LOUAGE", "BUS"]     # centre du pôle
NAME_ORDER = ["SNCFT", "SNTRI", "METRO", "TGM", "LOUAGE", "BUS"]       # nom du pôle (gare routière avant le métro)


def _family(place, lines_at):
    """Famille d'un lieu structurant, ou None (simple arrêt de bus, point de montée…)."""
    pid = place["id"]
    lines = lines_at.get(pid, set())
    if pid.startswith("TRN-"):
        return "SNCFT"
    if pid.startswith("MET-"):
        return "METRO"
    if pid.startswith("TGM-"):
        return "TGM"
    if place["kind"] == "louage_station":
        return "LOUAGE"
    if pid.startswith("SNTRI-") and place["kind"] == "station":
        return "SNTRI"
    if pid.startswith("BUS-") and place["kind"] == "station":       # arrêts de pôle Transtu (station de bus)
        return "BUS"
    if pid.startswith("BUS-") and len(lines) >= 6:                  # grand arrêt de correspondance des bus
        return "BUS"
    return None


def run(doc, src):
    issues = Issues()
    ds = load(issues, src=src)
    if issues.errors:
        # des lieux non chargés feraient disparaître leurs pôles : on garde hubs.yaml tel quel
        return {"written": [], "removed": [], "counts": {"poles": len(ds.hubs)},
                "rejected": [f"Pôles non recalculés : {len(issues.errors)} erreur(s) de chargement "
                             f"(lancer lint), ex. {issues.errors[0].where} : {issues.errors[0].message}"],
                "notes": []}
    lines_at = {}
    for line in ds.lines.values():
        if line["status"] not in ("active", "suspended"):
            continue
        for pat in line["patterns"]:
            for entry in pat["stops"]:
                sid = entry if isinstance(entry, str) else entry["stop"]
                lines_at.setdefault(sid, set()).add(line["id"])

    nodes = [p for p in ds.places.values() if p["status"] == "active" and not p.get("parent")
             and _family(p, lines_at)]
    # Pôles en étoile autour d'un lieu principal (gare, puis métro, TGM, gare routière, louages, bus) : chaque membre est
    # à portée du centre, jamais de proche en proche (sinon une chaîne d'arrêts relie des places éloignées d'1 km).
    seeds = sorted(nodes, key=lambda p: (FAMILY_ORDER.index(_family(p, lines_at)), p["id"]))
    taken, clusters = set(), []
    for seed in seeds:
        if seed["id"] in taken:
            continue
        group = [seed]
        for q in seeds:
            if q["id"] in taken or q is seed:
                continue
            wide = {_family(seed, lines_at), _family(q, lines_at)} & {"LOUAGE", "SNTRI"}
            if dist_m((seed["lat"], seed["lon"]), (q["lat"], q["lon"])) <= (WIDE_RADIUS_M if wide else RADIUS_M):
                group.append(q)
        if len({_family(x, lines_at) for x in group}) >= 2:
            clusters.append(group)
            taken.update(x["id"] for x in group)

    existing = list(ds.hubs.values())
    hubs, rejected, notes = [], [], []
    used_ids = set()
    for group in clusters:
        members = sorted(x["id"] for x in group)
        free = [h for h in existing if h["id"] not in used_ids]          # un ancien pôle ne sert qu'une fois
        old = max(free, key=lambda h: len(set(h["members"]) & set(members)), default=None)
        if old and set(old["members"]) & set(members):
            hid, name = old["id"], old["name"]
        else:
            main = min(group, key=lambda x: (NAME_ORDER.index(_family(x, lines_at)), x["id"]))
            name = dict(main["name"])
            for prefix in ("Louages ", "محطة اللواج "):
                for k in ("fr", "ar"):
                    name[k] = name[k].removeprefix(prefix)
            hid = f"HUB-{slug(norm_name(name['fr']))}"
        base, n = hid, 2
        while hid in used_ids:
            hid, n = f"{base}-{n}", n + 1
        used_ids.add(hid)
        hubs.append({"id": hid, "name": name, "members": members, "status": "active"})

    for old in existing:
        if old["id"] not in used_ids:
            rejected.append(f"Pôle {old['id']} retiré : ses lieux ne forment plus une correspondance "
                            f"({', '.join(old['members'])})")
    hubs.sort(key=lambda h: h["id"])
    path = write_yaml(src / "places" / "hubs.yaml", hubs,
                      "tous les lieux importés (pôles calculés : 250 m, 450 m autour des gares routières et louages)")
    notes.extend(f"{h['id']} : {', '.join(h['members'])}" for h in hubs)
    return {"written": [str(path)], "removed": [], "counts": {"poles": len(hubs)}, "rejected": rejected,
            "notes": notes}
