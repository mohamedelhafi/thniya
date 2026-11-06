"""Prépare le dossier lu par OTP : configuration, extrait OSM et GTFS."""

import json
import shutil

from citydata import paths

OTP_FEED_ID = "TN"


def prepare(region="grand-tunis"):
    source_pbf = {"grand-tunis": paths.OSM_GRAND_TUNIS, "tunisie": paths.OSM_FULL}[region]
    if not source_pbf.exists():
        print(f"Extrait OSM absent : {source_pbf}")
        return 1

    out = paths.OTP_BUILD_DIR
    out.mkdir(parents=True, exist_ok=True)
    for stale in [*out.glob("*.pbf"), *out.glob("*.zip")]:
        stale.unlink()

    for name in ("otp-config.json", "router-config.json"):
        shutil.copy2(paths.OTP_CONFIG_DIR / name, out / name)

    build_config = json.loads((paths.OTP_CONFIG_DIR / "build-config.json").read_text(encoding="utf-8"))
    build_config["osm"] = [{"source": source_pbf.name}]
    shutil.copy2(source_pbf, out / source_pbf.name)

    if paths.GTFS_ZIP.exists():
        shutil.copy2(paths.GTFS_ZIP, out / "gtfs.zip")
        build_config["transitFeeds"] = [{"type": "gtfs", "source": "gtfs.zip", "feedId": OTP_FEED_ID}]
        print("GTFS inclus : gtfs.zip")
    else:
        print("Pas de GTFS : graphe piéton uniquement.")

    (out / "build-config.json").write_text(json.dumps(build_config, indent=2), encoding="utf-8")
    print(f"Dossier OTP prêt : {out}")
    return 0
