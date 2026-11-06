#!/usr/bin/env bash
# Publication des données saisies dans le back-office (specs/04d-base-de-saisie.md §5) :
#   base de saisie → export data/src → validation → GTFS + app-meta → graphe OTP → redémarrage d'OTP.
# L'API recharge app-meta.json d'elle-même (30 s) et vide ses caches si la version change.
# Usage : infra/scripts/publish.sh [--by "Nom"] [--local]
set -euo pipefail
cd "$(dirname "$0")/.."

BY="${USER:-publish}"
FILES=(-f compose.yml)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --by) BY="$2"; shift 2 ;;
    --local) FILES+=(-f compose.local.yml); shift ;;
    *) echo "Option inconnue : $1" >&2; exit 2 ;;
  esac
done
C=(docker compose "${FILES[@]}")

echo "1/4 Génération depuis la base de saisie"
"${C[@]}" run --rm tools publish --by "$BY"

echo "2/4 Préparation d'OTP"
"${C[@]}" run --rm tools otp-prepare

echo "3/4 Construction du graphe OTP"
"${C[@]}" --profile tasks run --rm otp-build

echo "4/4 Redémarrage d'OTP"
"${C[@]}" restart otp
echo "Publication terminée. Vérifier : python -m citydata golden (conteneur tools) une fois OTP prêt."
