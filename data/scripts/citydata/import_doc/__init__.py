"""Import de la base de connaissances `doc/` vers `data/src` (specs/04e-import-doc.md).

Usage : python -m citydata import-doc [--doc CHEMIN] [--only sncft,transtu-bus,…]

Chaque module lit `doc/<thème>/donnees/*.csv`, écrit ses fichiers `data/src` (en-tête « Généré par … import-doc ») et
renvoie un rapport : fichiers écrits ou retirés, volumes, éléments écartés et pourquoi. Le rapport complet est écrit
dans `data/build/import-doc-report.json`. Les pôles d'échange sont recalculés en dernier, à partir de tous les lieux.

La suite habituelle : `lint`, puis `db-import --replace` (la base de saisie devient la source de vérité).
"""

import importlib
import json
from pathlib import Path

from citydata import paths
from citydata.import_doc.common import DOC

# Ordre d'exécution : les pôles d'échange (hubs) en dernier, car ils regroupent les lieux de tous les réseaux.
MODULES = {
    "transtu-rail": "citydata.import_doc.transtu_rail",   # métro léger, TGM, tarifs Transtu
    "sncft": "citydata.import_doc.sncft",                 # banlieues de Tunis et du Sahel, grandes lignes
    "transtu-bus": "citydata.import_doc.transtu_bus",     # bus du Grand Tunis
    "sntri": "citydata.import_doc.sntri",                 # autocars interurbains
    "louage": "citydata.import_doc.louage",               # stations de louages
    "hubs": "citydata.import_doc.hubs",                   # pôles d'échange
}


def run(doc=None, only=None):
    doc = Path(doc) if doc else DOC
    if not doc.exists():
        print(f"Dossier doc/ introuvable : {doc}")
        return 1
    wanted = list(MODULES) if not only else [m.strip() for m in only.split(",") if m.strip()]
    unknown = [m for m in wanted if m not in MODULES]
    if unknown:
        print(f"Module(s) inconnu(s) : {', '.join(unknown)} (connus : {', '.join(MODULES)})")
        return 2

    report = {}
    for name in MODULES:
        if name not in wanted:
            continue
        module = importlib.import_module(MODULES[name])
        result = module.run(doc, paths.SRC) or {}
        report[name] = result
        counts = ", ".join(f"{k} {v}" for k, v in result.get("counts", {}).items())
        print(f"{name:13s} {len(result.get('written', []))} fichier(s) écrit(s)"
              f"{', ' + str(len(result.get('removed', []))) + ' retiré(s)' if result.get('removed') else ''}"
              f"{' — ' + counts if counts else ''}")
        for item in result.get("rejected", [])[:5]:
            print(f"    écarté : {item}")
        if len(result.get("rejected", [])) > 5:
            print(f"    … {len(result['rejected']) - 5} autre(s) élément(s) écarté(s) (voir le rapport)")

    out = paths.BUILD / "import-doc-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Rapport : {out.relative_to(paths.ROOT).as_posix()} — étape suivante : python -m citydata lint")
    return 0
