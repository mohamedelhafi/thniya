"""Point d'entrée : python -m citydata <commande>."""

import argparse
import os
import sys
from datetime import date


def main(argv=None):
    # Messages en arabe (noms d'arrêts) : une console Windows en cp1252 ne doit jamais faire échouer une commande.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="citydata",
        description="Outils de données Thniya (OSM, GTFS, calendrier).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("osm-download", help="Télécharge l'extrait OSM de la Tunisie (Geofabrik)")
    p.add_argument("--force", action="store_true", help="Retélécharger même si le fichier est à jour")

    p = sub.add_parser("osm-clip", help="Découpe l'extrait du Grand Tunis")
    p.add_argument("--bbox", help="ouest,sud,est,nord (défaut : OSM_CLIP_BBOX)")

    p = sub.add_parser("osm-find", help="Cherche gares, arrêts, stations de louages dans OSM")
    p.add_argument("--preset", choices=["train", "station-area", "metro", "bus", "louage", "routes"], required=True)
    p.add_argument("--bbox", help="ouest,sud,est,nord")
    p.add_argument("--name", help="Filtre texte sur les tags (ex. « Hammam »)")
    p.add_argument("--json", action="store_true", help="Sortie JSON")
    p.add_argument("--source", help="Fichier .osm.pbf (défaut : Grand Tunis)")

    p = sub.add_parser("osm-lines", help="Lignes de transport décrites dans OSM, avec leurs arrêts dans l'ordre")
    p.add_argument("--routes", default="light_rail,tram,train,subway,bus,share_taxi")
    p.add_argument("--bbox", help="ouest,sud,est,nord")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("import-doc", help="Importe les données retravaillées de recherches-privees/ dans data/src (specs/04e)")
    p.add_argument("--doc", help="Dossier de la base de connaissances (défaut : recherches-privees/ à la racine du dépôt)")
    p.add_argument("--only", help="Modules à exécuter, séparés par des virgules (défaut : tous)")

    sub.add_parser("lint", help="Vérifie les données (schémas, références, règles métier, grilles)")

    p = sub.add_parser("build", help="Génère gtfs.zip, app-meta.json et report.md")
    p.add_argument("--from", dest="start", type=date.fromisoformat, help="Début de la fenêtre (défaut : J-7)")
    p.add_argument("--days", type=int, help="Longueur de la fenêtre en jours (défaut : 127)")
    p.add_argument("--version", dest="data_version", help="Version des données (défaut : DATA_VERSION)")

    p = sub.add_parser("calendar-preview", help="Régime appliqué jour par jour pour un réseau")
    p.add_argument("--network", required=True)
    p.add_argument("--from", dest="start", type=date.fromisoformat, help="Premier jour (défaut : aujourd'hui)")
    p.add_argument("--days", type=int, default=45)
    p.add_argument("--line", action="append", help="Limiter à une ligne (répétable)")

    sub.add_parser("golden", help="Exécute les trajets de référence (data/golden-trips.yaml) contre OTP")

    p = sub.add_parser("otp-check", help="Vérifie dans OTP que chaque gare est accessible à pied")
    p.add_argument("--when", help="Date/heure ISO du test (défaut : lundi prochain 10:00)")

    p = sub.add_parser("otp-prepare", help="Prépare data/build/otp (config + OSM + GTFS)")
    p.add_argument("--region", choices=["grand-tunis", "tunisie"], default=os.environ.get("OTP_REGION") or "tunisie",
                   help="Extrait OSM du graphe (défaut : OTP_REGION, sinon toute la Tunisie)")

    sub.add_parser("db-migrate", help="Crée ou met à jour le schéma de la base de saisie (data/db/migrations)")

    p = sub.add_parser("db-import", help="Charge data/src dans la base de saisie")
    p.add_argument("--replace", action="store_true", help="Remplacer les données déjà présentes")
    p.add_argument("--src", help="Dossier source (défaut : data/src)")

    p = sub.add_parser("db-export", help="Écrit la base de saisie au format data/src")
    p.add_argument("--out", help="Dossier de sortie (défaut : data/build/src-db ; « data/src » pour l'instantané git)")

    sub.add_parser("db-check", help="Vérifie que la base produit exactement le même GTFS que data/src")

    sub.add_parser("backoffice-setup", help="Configure le back-office Directus (libellés, dossiers, rôle de saisie)")

    p = sub.add_parser("publish", help="Base de saisie → validation → GTFS et app-meta (journal des publications)")
    p.add_argument("--by", help="Auteur de la publication")

    args = parser.parse_args(argv)

    if args.command == "osm-download":
        from citydata import osm
        return osm.download(force=args.force)
    if args.command == "osm-clip":
        from citydata import osm
        return osm.clip(bbox=args.bbox)
    if args.command == "osm-find":
        from citydata import osm_find
        return osm_find.find(args.preset, bbox=args.bbox, name=args.name, as_json=args.json, source=args.source)
    if args.command == "osm-lines":
        from citydata import osm_lines
        return osm_lines.run(args.routes.split(","), bbox=args.bbox, as_json=args.json)
    if args.command == "import-doc":
        from citydata import import_doc
        return import_doc.run(doc=args.doc, only=args.only)
    if args.command == "lint":
        from citydata import build
        return build.lint()
    if args.command == "build":
        from citydata import build
        return build.build(start=args.start, days=args.days, data_version=args.data_version)
    if args.command == "calendar-preview":
        from citydata import build
        return build.calendar_preview(args.network, start=args.start, days=args.days, lines=args.line)
    if args.command == "golden":
        from citydata import golden
        return golden.run()
    if args.command == "otp-check":
        from citydata import otp_check
        return otp_check.check(when=args.when)
    if args.command == "otp-prepare":
        from citydata import otp_prepare
        return otp_prepare.prepare(region=args.region)
    if args.command == "backoffice-setup":
        from citydata import backoffice
        return backoffice.setup()
    if args.command.startswith("db-") or args.command == "publish":
        from citydata import db
        if args.command == "db-migrate":
            return db.migrate()
        if args.command == "db-import":
            return db.import_sources(src=args.src, replace=args.replace)
        if args.command == "db-export":
            db.export_sources(out=args.out)
            return 0
        if args.command == "db-check":
            return db.check()
        return db.publish(requested_by=args.by)
    return 1
