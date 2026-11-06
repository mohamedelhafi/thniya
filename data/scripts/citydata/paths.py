"""Chemins du dépôt, valables dans le conteneur tools (dépôt monté sur /work) comme en local."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

DATA = ROOT / "data"
SRC = DATA / "src"
SCHEMAS = DATA / "schemas"
OSM_DIR = DATA / "osm"
BUILD = DATA / "build"
SRC_FROM_DB = BUILD / "src-db"
DB_MIGRATIONS = DATA / "db" / "migrations"
OTP_BUILD_DIR = BUILD / "otp"

INFRA = ROOT / "infra"
OTP_CONFIG_DIR = INFRA / "otp"

OSM_FULL = OSM_DIR / "tunisia-latest.osm.pbf"
OSM_GRAND_TUNIS = OSM_DIR / "grand-tunis.osm.pbf"
GTFS_ZIP = BUILD / "gtfs.zip"
