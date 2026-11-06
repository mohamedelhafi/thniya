# ADR-003 — Données saisies en YAML, GTFS généré par script

> Statut : Remplacé partiellement par [ADR-007](ADR-007-base-de-saisie-postgis.md) (la base de saisie devient la source de vérité ; le YAML reste le format d'échange et d'instantané) · Date : 2026-10-13

## Contexte

Le PRD prévoit un GTFS « créé à la main ». Le GTFS est un ensemble de CSV liés par des identifiants ; un louage à durées variables demande plusieurs voyages modèles et des fréquences par tranche. Saisi directement, c'est long et source d'erreurs silencieuses.

## Options envisagées

1. **CSV GTFS édités à la main** : aucun outil, mais erreurs fréquentes, pas de traductions faciles, répétitions.
2. **Éditeur GTFS graphique** (outils existants) : pratique pour les arrêts, mais mal adapté aux tranches horaires des louages et aux métadonnées locales (prix, noms arabes, alias).
3. **YAML + générateur Python** : source lisible et commentée, contrôles de cohérence, génération des voyages modèles et de `app-meta.json`.

## Décision

**Option 3.** Le YAML dans `data/src/` est la seule source de vérité ; `gtfs.zip` et `app-meta.json` sont des produits de build, jamais modifiés à la main ni versionnés.

## Conséquences

- Le générateur est du code à tester (pytest).
- Ajouter une ligne = éditer un YAML + un trajet de référence.
- Si un jour un opérateur fournit un GTFS officiel, le générateur devra savoir le **fusionner** avec nos données.
