"""Métro léger (lignes 1 à 6), TGM et tarifs Transtu, depuis doc/metro-tramway/donnees/.

- Stations : positions OSM relevées le 2026-10-14 (écart contrôlé avec data.transport.tn et Wikipédia), noms FR/AR.
- Lignes : ordre des stations de doc ; horaires « fréquence » :
  - premiers et derniers départs de chaque sens et fréquence de pointe = affiche officielle hiver 2026-2027 [C] ;
  - autres tranches estimées d'après la synthèse de l'horaire détaillé open data (doc § 3) : intervalle de pointe
    toute la journée, doublé après 19 h ; le dimanche, rapport dimanche / semaine de l'open data, plafonné à 2 ;
  - modèles été et Ramadan 2026 [A] (affiches 2026), réutilisés pour 2027 : estimation ;
  - TGM : un train toutes les 45 min sur toutes les affiches 2026 (voie unique), toute la journée.
- Durées entre stations : estimées depuis les distances (vitesse commerciale), la Transtu n'en publie pas.
- Tarifs : grille par zones du 2021-06-01 ; la zone d'un trajet n'étant pas publiée, ticket de zone 1 (0,500 DT),
  confirmé par un relevé de voyageur pour un trajet d'une section : estimation.
"""

import csv
import re
from collections import OrderedDict
from pathlib import Path

import yaml

from citydata.import_doc.common import (
    clean_ar, doc_path, dist_m, prov, read_csv, remove_generated, run_minutes, scaled, write_yaml,
)

SRC_DOC = "metro-tramway/donnees"
AFFICHE = ("Affiche Transtu « marche horaire hiver 2026-2027 » métro et TGM (transtu.tn, page 0143, "
           "doc/sources-open-data/raw/transtu.tn/horaires-hiver-2026-2027/MetroTGMH26-27.jpg)")
COLORS = {"1": "#D32F2F", "2": "#F9A825", "3": "#2E7D32", "4": "#6A1B9A", "5": "#00838F", "6": "#C2410C"}
TEXT = {"2": "#111417"}
# Rapport dimanche / semaine de l'intervalle open data (doc/metro-tramway/donnees/horaires_opendata_intervalles.csv)
SPEED_KMH, DWELL_MIN, DETOUR = 24, 0.4, 1.1          # métro léger : mêmes hypothèses que le réseau de test
TGM_SPEED_KMH, TGM_DWELL_MIN, TGM_DETOUR = 40, 0.4, 1.05


def _existing(path):
    """Lieux déjà présents (générés) : on garde ce que doc/ ne fournit pas (commune affichée sous le nom)."""
    path = Path(path)
    if not path.exists():
        return {}
    return {p["id"]: p for p in (yaml.safe_load(path.read_text(encoding="utf-8")) or [])}


def _headway(text):
    """« 32 », « 20 / 10' », « 15'/10' » → intervalle le plus prudent (le plus long), en minutes."""
    values = [int(v) for v in re.findall(r"\d+", text or "")]
    return max(values) if values else None


def _t(text, last=False):
    """Heure de l'affiche → heure du jour de service : un dernier départ à 00:30 vaut 24:30 (jamais un premier)."""
    h, m = (int(x) for x in text.split(":"))
    return f"{h + 24 if last and h < 3 else h:02d}:{m:02d}"


def _sunday_ratios(rows):
    """Rapport intervalle dimanche / semaine (sens vers la banlieue, tranche 09-16 h), borné entre 1 et 2."""
    ratio = {}
    for line in {r["ligne"] for r in rows}:
        def iv(days):
            return next((int(r["intervalle_median_min_09h_16h"]) for r in rows if r["ligne"] == line
                         and r["jours"] == days and "banlieue" in r["sens"]), None)
        wk, su = iv("lundi-samedi"), iv("dimanche")
        ratio[line.removeprefix("L")] = min(2.0, max(1.0, su / wk)) if wk and su else 1.0
    return ratio


def _regimes(hours, ratio, is_tgm):
    """Régimes de fréquence : hiver (officiel), été et Ramadan (modèles 2026), dimanche (estimé)."""
    def by_dir(r, last_banlieue="dernier_vers_banlieue", last_centre="dernier_vers_centre"):
        return {
            "BANLIEUE": {"first": _t(r["premier_vers_banlieue"]), "last": _t(r[last_banlieue], last=True)},
            "CENTRE": {"first": _t(r["premier_vers_centre"]), "last": _t(r[last_centre], last=True)},
        }

    def envelope(d):
        return {"first": min(v["first"] for v in d.values()), "last": max(v["last"] for v in d.values()),
                "by_direction": d}

    def evening(h):
        return h if is_tgm else min(60, 2 * h)

    regimes = []
    hiver = hours.get("hiver_2026-2027")
    if hiver:
        h = _headway(hiver["frequence_pointe_affiche_min"])
        regimes.append({
            "periods": ["NORMAL", "AID"], "day_types": ["OUVRABLE", "SAMEDI"],
            "service_hours": envelope(by_dir(hiver)),
            "bands": {"NUIT": {"headway_min": h, "run_time": "FLUIDE"},
                      "POINTE_MATIN": {"headway_min": h, "run_time": "CHARGE"},
                      "JOURNEE": {"headway_min": h, "run_time": "FLUIDE"},
                      "POINTE_SOIR": {"headway_min": h, "run_time": "CHARGE"},
                      "SOIREE": {"headway_min": evening(h), "run_time": "FLUIDE"}},
        })
        sunday = h if is_tgm else min(60, round(h * ratio))
        regimes.append({
            "periods": ["NORMAL", "ETE", "RAMADAN", "AID"], "day_types": ["DIMANCHE"],
            "service_hours": envelope(by_dir(hiver)),
            "bands": {"TOUTE_LA_JOURNEE": {"headway_min": sunday, "run_time": "FLUIDE"}},
        })
    ete = hours.get("ete_2026")
    if ete:
        h = _headway(ete["frequence_pointe_affiche_min"])
        regimes.append({
            "periods": ["ETE"], "day_types": ["OUVRABLE", "SAMEDI"],
            "service_hours": envelope(by_dir(ete)),
            "bands": {"NUIT": {"headway_min": h, "run_time": "FLUIDE"},
                      "POINTE_MATIN": {"headway_min": h, "run_time": "CHARGE"},
                      "JOURNEE": {"headway_min": h, "run_time": "FLUIDE"},
                      "POINTE_SOIR": {"headway_min": h, "run_time": "CHARGE"},
                      "SOIREE": {"headway_min": evening(h), "run_time": "FLUIDE"}},
        })
    ram = hours.get("ramadan_2026")
    if ram:
        h = _headway(ram["frequence_pointe_affiche_min"])
        evening_service = bool(ram["dernier_vers_banlieue"])
        last_b = "dernier_vers_banlieue" if evening_service else "dernier_avant_iftar_vers_banlieue"
        last_c = "dernier_vers_centre" if evening_service else "dernier_avant_iftar_vers_centre"
        regimes.append({
            "periods": ["RAMADAN"], "day_types": ["OUVRABLE", "SAMEDI"],
            "service_hours": envelope(by_dir(ram, last_b, last_c)),
            "bands": {"NUIT": {"headway_min": h, "run_time": "FLUIDE"},
                      "MATIN": {"headway_min": h, "run_time": "FLUIDE"},
                      "AVANT_FTOUR": {"headway_min": h, "run_time": "CHARGE"},
                      "FTOUR": {"headway_min": None},
                      "SOIREE": {"headway_min": evening(h) if evening_service else None, "run_time": "FLUIDE"}},
        })
        if not evening_service:
            del regimes[-1]["bands"]["SOIREE"]["run_time"]
    return regimes


def _station(sid, name_fr, name_ar, lat, lon, source_coord, status, old, aliases=()):
    place = {"id": sid, "kind": "station", "name": {"fr": name_fr, "ar": clean_ar(name_ar)}}
    if aliases:
        place["aliases"] = sorted(set(aliases))
    if old.get("area"):
        place["area"] = old["area"]
    place.update({"lat": round(float(lat), 6), "lon": round(float(lon), 6), "status": status})
    source = "OSM" if source_coord.startswith("OSM") else "OFFICIEL"
    place["provenance"] = prov(source, f"Position : {source_coord} ; noms : doc/metro-tramway/stations.md "
                                       f"(plan Transtu, data.transport.tn)")
    return place


def _aliases(text, name_fr):
    """Variantes de nom utiles à la recherche (« Slimene Kehia »), sans les remarques entre guillemets."""
    out = []
    for part in re.split(r"[;,]", text or ""):
        part = part.strip()
        if part and "«" not in part and "arrêt" not in part and part.lower() != name_fr.lower() and len(part) < 40:
            out.append(part)
    return out


def run(doc, src):
    base = doc_path(doc, SRC_DOC)
    written, removed, rejected, notes = [], [], [], []
    stations = read_csv(base / "stations_metro.csv")
    tgm = read_csv(base / "stations_tgm.csv")
    order = read_csv(base / "lignes_metro_arrets.csv")
    hours_rows = read_csv(base / "horaires_premiers_derniers_departs.csv")
    ratios = _sunday_ratios(read_csv(base / "horaires_opendata_intervalles.csv"))
    hours = {}
    for r in hours_rows:
        hours.setdefault(r["ligne"], {})[r["regime"]] = r

    # --- Stations -----------------------------------------------------------------------------
    metro_file = src / "places" / "grand-tunis" / "metro-stations.yaml"
    old = _existing(metro_file)
    ids, places = {}, []
    for r in stations:
        sid = r["id_app"] or f"MET-{r['station_id']}"
        ids[r["station_id"]] = sid
        closed = not r["statut"].startswith("desservie")
        places.append(_station(sid, r["nom_fr"], r["nom_ar"], r["lat"], r["lon"], r["source_coord"],
                               "archived" if closed else "active", old.get(sid, {}),
                               _aliases(r["variantes_noms"], r["nom_fr"])))
        if closed:
            notes.append(f"{sid} ({r['nom_fr']}) : station fermée, archivée ({r['variantes_noms']})")
        if not r["id_app"]:
            notes.append(f"{sid} ({r['nom_fr']}) : station ajoutée (absente du réseau de test)")
    places.sort(key=lambda p: p["id"])
    written.append(write_yaml(metro_file, places, f"{SRC_DOC}/stations_metro.csv"))
    metro_pos = {p["id"]: (p["lat"], p["lon"]) for p in places}

    tgm_file = src / "places" / "grand-tunis" / "tgm-stations.yaml"
    old_tgm = _existing(tgm_file)
    tgm_places = []
    for r in tgm:
        sid = r["id_app"] or r["station_id"]
        tgm_places.append(_station(sid, r["nom_fr"], r["nom_ar"], r["lat"], r["lon"], r["source_coord"], "active",
                                   old_tgm.get(sid, {})))
    written.append(write_yaml(tgm_file, tgm_places, f"{SRC_DOC}/stations_tgm.csv"))
    tgm_pos = {p["id"]: (p["lat"], p["lon"]) for p in tgm_places}

    # --- Lignes de métro ----------------------------------------------------------------------
    by_line = OrderedDict()
    for r in sorted(order, key=lambda r: (r["ligne"], int(r["ordre"]))):
        by_line.setdefault(r["ligne"], []).append(r)
    n_lines = 0
    for ref, rows in by_line.items():
        if ref not in hours or "hiver_2026-2027" not in hours[ref]:
            rejected.append(f"Métro {ref} : pas d'horaires hiver 2026-2027")
            continue
        to_suburb = [ids[r["station_id"]] for r in rows]          # ordre de doc : du centre vers la banlieue
        to_centre = list(reversed(to_suburb))
        names = {p["id"]: p["name"] for p in places}
        centre, suburb = names[to_suburb[0]], names[to_suburb[-1]]
        patterns = []
        for did, stops in (("BANLIEUE", to_suburb), ("CENTRE", to_centre)):
            pts = [metro_pos[s] for s in stops]
            fluide = run_minutes(pts, SPEED_KMH, DWELL_MIN, DETOUR)
            patterns.append({"id": did, "direction": did, "main": True, "stops": stops,
                             "run_times": {"FLUIDE": fluide, "CHARGE": scaled(fluide, 1.1)}})
        hiver = hours[ref]["hiver_2026-2027"]
        line = {
            "id": f"TRANSTU-M{ref}", "network": "TRANSTU", "mode": "METRO", "public_code": f"M{ref}",
            "name": {"fr": f"Métro {ref}", "ar": f"المترو {ref}"},
            "long_name": {"fr": f"{centre['fr']} – {suburb['fr']}", "ar": f"{centre['ar']} – {suburb['ar']}"},
            "color": COLORS[ref], "text_color": TEXT.get(ref, "#FFFFFF"), "status": "active",
            "directions": [{"id": "BANLIEUE", "headsign": dict(suburb)}, {"id": "CENTRE", "headsign": dict(centre)}],
            "patterns": patterns,
            "schedule": {"kind": "frequency", "regimes": _regimes(hours[ref], ratios.get(ref, 1.0), False)},
            "fare": "FARE-TRANSTU-METRO",
            "provenance": prov("ESTIMATION",
                               f"Premiers et derniers départs, fréquence de pointe ({hiver['frequence_pointe_affiche_min']} min) : "
                               f"{AFFICHE}. Autres tranches estimées (intervalle de pointe en journée, doublé après "
                               f"19 h ; dimanche : rapport de l'horaire open data), été et Ramadan : modèles des "
                               f"affiches 2026. Durées entre stations estimées ({SPEED_KMH} km/h). "
                               f"Ordre des stations : doc/metro-tramway/reseau.md."),
        }
        written.append(write_yaml(src / "networks" / "transtu" / "lines" / f"metro-{ref}.yaml", line,
                                  f"{SRC_DOC}/lignes_metro_arrets.csv et horaires_premiers_derniers_departs.csv"))
        n_lines += 1

    # --- TGM ----------------------------------------------------------------------------------
    tgm_ids = [p["id"] for p in tgm_places]                       # ordre de doc : Tunis Marine → La Marsa Plage
    patterns = []
    for did, stops in (("BANLIEUE", tgm_ids), ("CENTRE", list(reversed(tgm_ids)))):
        fluide = run_minutes([tgm_pos[s] for s in stops], TGM_SPEED_KMH, TGM_DWELL_MIN, TGM_DETOUR)
        patterns.append({"id": did, "direction": did, "main": True, "stops": stops,
                         "run_times": {"FLUIDE": fluide, "CHARGE": scaled(fluide, 1.1)}})
    first, last = tgm_places[0]["name"], tgm_places[-1]["name"]
    tgm_line = {
        "id": "TRANSTU-TGM", "network": "TRANSTU", "mode": "TRAIN", "public_code": "TGM",
        "name": {"fr": "TGM", "ar": "ت.ح.م"},
        "long_name": {"fr": f"{first['fr']} – La Goulette – {last['fr']}",
                      "ar": f"{first['ar']} – حلق الوادي – {last['ar']}"},
        "color": "#00796B", "text_color": "#FFFFFF", "status": "active",
        "directions": [{"id": "BANLIEUE", "headsign": dict(last)}, {"id": "CENTRE", "headsign": dict(first)}],
        "patterns": patterns,
        "schedule": {"kind": "frequency", "regimes": _regimes(hours["TGM"], 1.0, True)},
        "fare": "FARE-TRANSTU-TGM",
        "provenance": prov("ESTIMATION",
                           f"Premiers et derniers départs, un train toutes les 45 min (voie unique Le Bac – Tunis "
                           f"Marine) : {AFFICHE} ; été et Ramadan : affiches 2026. Durées entre stations estimées "
                           f"({TGM_SPEED_KMH} km/h)."),
    }
    written.append(write_yaml(src / "networks" / "transtu" / "lines" / "tgm.yaml", tgm_line,
                              f"{SRC_DOC}/stations_tgm.csv et horaires_premiers_derniers_departs.csv"))
    # L'ancienne grille estimée du TGM (réseau de test, version ESTIME-*) est remplacée par les fréquences officielles ;
    # une grille saisie à la main dans un autre dossier de version n'est jamais touchée.
    for p in sorted((src / "networks" / "transtu" / "timetables" / "tgm").glob("ESTIME-*/**/*.csv")):
        p.unlink()
        removed.append(p)
    for d in sorted((src / "networks" / "transtu" / "timetables").rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    # --- Tarifs -------------------------------------------------------------------------------
    grid = ("Grille Transtu « nouvelle tarification » en vigueur depuis le 2021-06-01 (transtu.tn, pages 0067 et "
            "0068 ; doc/metro-tramway/tarifs.md)")
    fares = {
        "fare-transtu-metro.yaml": ("FARE-TRANSTU-METRO", 500, "ESTIMATION",
                                    f"{grid} : ticket zone 1 = 0,500 DT, zones 2 et 3 = 1,000 et 1,500 DT ; la zone "
                                    f"d'un trajet n'est pas publiée. 0,500 DT relevé pour un trajet d'une section "
                                    f"(Wikivoyage Tunis, 2025)."),
        "fare-transtu-bus.yaml": ("FARE-TRANSTU-BUS", 500, "ESTIMATION",
                                  f"{grid} : ticket zone 1 = 0,500 DT, zones 2 et 3 = 1,000 et 1,500 DT selon la "
                                  f"distance ; zone par ligne non publiée. 0,500 DT relevé pour un bus urbain "
                                  f"(Wikivoyage Tunis, 2025-06)."),
        "fare-transtu-tgm.yaml": ("FARE-TRANSTU-TGM", 800, "ESTIMATION",
                                  f"{grid} : TGM 2e classe 0,500 DT (1 section) ou 0,800 DT (2 sections), 1re classe "
                                  f"0,900 / 1,250 DT ; limites des sections non publiées : 2 sections (prix relevé "
                                  f"pour un aller, Wikivoyage Tunis, 2025)."),
    }
    for name, (fid, millimes, source, ref) in fares.items():
        written.append(write_yaml(src / "networks" / "transtu" / "fares" / name, {
            "id": fid, "model": "flat", "currency": "TND", "categories": ["PLEIN"],
            "versions": [{"valid_from": "2021-06-01", "price_millimes": {"PLEIN": millimes}}],
            "provenance": prov(source, ref),
        }, "metro-tramway/tarifs.md"))

    return {"written": [str(p) for p in written], "removed": [str(p) for p in removed],
            "counts": {"stations_metro": len(places), "stations_tgm": len(tgm_places), "lignes": n_lines + 1},
            "rejected": rejected, "notes": notes, "ids": ids}
