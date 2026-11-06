#!/usr/bin/env bash
# Index Photon de la Tunisie (recherche d'adresses et de lieux, specs/09-geocodage-tuiles.md) :
#   export GraphHopper de l'Afrique du Nord → import limité à la Tunisie (tn), noms fr/ar/en → redémarrage de Photon.
# À relancer tous les 1 à 3 mois (OSM change peu). Usage : infra/scripts/photon-import.sh [--local]
set -euo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1   # Git Bash sous Windows : ne pas réécrire les chemins des conteneurs

FILES=(-f compose.yml)
[[ "${1:-}" == "--local" ]] && FILES+=(-f compose.local.yml)
C=(docker compose "${FILES[@]}")

DEFAULT_URL="https://download1.graphhopper.com/public/africa/northern-africa/photon-dump-northern-africa-1.0-latest.jsonl.zst"
URL="$(grep -E '^PHOTON_DUMP_URL=' .env 2>/dev/null | cut -d= -f2- || true)"
URL="${URL:-$DEFAULT_URL}"
DUMP_DIR="../data/build/photon-dump"
DUMP="$DUMP_DIR/$(basename "$URL")"
mkdir -p "$DUMP_DIR" ../data/build/photon

echo "1/4 Export GraphHopper : $URL"
curl -fsSL -o "$DUMP.md5" "$URL.md5"
expected="$(cut -d' ' -f1 "$DUMP.md5")"
if [[ ! -f "$DUMP" ]] || [[ "$(md5sum "$DUMP" | cut -d' ' -f1)" != "$expected" ]]; then
  curl -fL --retry 3 -o "$DUMP" "$URL"
fi
echo "$expected  $DUMP" | md5sum -c -

echo "2/4 Image Photon"
"${C[@]}" build photon

echo "3/4 Import (Tunisie seulement, quelques minutes)"
"${C[@]}" stop photon || true
"${C[@]}" run --rm --no-deps -v "$(cd "$DUMP_DIR" && pwd):/dump:ro" --entrypoint sh photon -c \
  "zstd -d --stdout /dump/$(basename "$DUMP") | java -jar /opt/photon.jar import -import-file - \
   -country-codes tn -languages fr,ar,en -data-dir /photon"

echo "4/4 Démarrage de Photon"
"${C[@]}" up -d photon
echo "Index prêt. Essai : curl 'http://127.0.0.1:2322/api?q=hammam+lif&limit=3' (avec --local)"
