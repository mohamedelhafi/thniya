# ADR-004 — Tuiles vectorielles PMTiles auto-hébergées

> Statut : Proposé (à confirmer par le spike S7) · Date : 2026-10-13

## Contexte

L'app affiche une carte dès l'ouverture. Les tuiles publiques OSM ne sont pas autorisées pour un usage en production. Il faut aussi des libellés en français **et** en arabe.

## Options envisagées

1. **Tuiles publiques OSM** : gratuites, mais interdites en production intensive ; libellés dans la langue locale uniquement.
2. **Fournisseur commercial** (MapTiler, Stadia…) : simple, offre gratuite limitée, coût variable avec l'audience, dépendance externe.
3. **Serveur de tuiles raster auto-hébergé** : lourd (rendu, base PostGIS).
4. **PMTiles vectorielles** : un fichier unique servi par nginx, style et langue choisis côté app, coût quasi nul.

## Décision

**Option 4**, avec l'option 2 comme solution de repli si le rendu dans Flutter n'est pas satisfaisant.

## Conséquences

- Il faut produire un `.pmtiles` de la Tunisie et un style.
- Côté Flutter, rendu vectoriel : à valider (performances sur téléphone d'entrée de gamme, liaison des lettres arabes).
- Le fond de carte est indépendant du graphe OTP.
