# 08 — Français / arabe (i18n)

> Statut : Brouillon · Mise à jour : 2026-10-13

## 1. Principes

- Deux langues dès la V1 : **français** (par défaut) et **arabe**.
- Langue initiale = langue du téléphone si `fr` ou `ar`, sinon `fr`. L'utilisateur peut la changer dans l'app ; le choix est mémorisé.
- L'arabe implique une **mise en page de droite à gauche (RTL)** sur tout l'écran.
- On traduit **trois types de contenu**, chacun à un endroit précis :

| Contenu | Exemple | Où vit la traduction |
|---|---|---|
| Interface | « Itinéraires », « Partir maintenant » | Flutter, fichiers ARB |
| Données de transport | « Hammam Lif » / « حمام الأنف » | `data/src/**` → `app-meta.json` + `translations.txt` |
| Lieux et adresses | « Avenue Habib Bourguiba » | OSM (`name:fr`, `name:ar`) via Photon |

## 2. Couche par couche

### Données (`data/src`)

- Chaque arrêt et chaque ligne a `name.fr` **et** `name.ar`. Le générateur refuse un nom manquant.
- Les consignes génériques (« Marcher jusqu'à… ») ne sont **pas** dans les données ; elles sont construites par l'app.

### API Spring

- Lit `Accept-Language` (`ar`, `ar-TN`, `fr`, `fr-FR`… → `ar` ou `fr`).
- Renvoie les noms dans la langue demandée ; si une traduction manque, renvoie le français (jamais de champ vide).
- Messages d'erreur `ProblemDetail` : `title` traduit, `code` stable non traduit.
- Les noms de lieux viennent de Photon avec `lang=fr|ar` (voir spike S6).

### App Flutter

- Fichiers `lib/l10n/app_fr.arb` et `app_ar.arb` ; génération avec `flutter gen-l10n`. Aucun texte en dur dans les widgets (lint à activer).
- `supportedLocales: [fr, ar]` et `localizationsDelegates` standard → le RTL est automatique pour les widgets Material.
- Utiliser `EdgeInsetsDirectional`, `AlignmentDirectional` et `start`/`end` au lieu de `left`/`right`.
- Icônes directionnelles (flèches, « retour ») : miroir en RTL. **Exception :** la suite de pictogrammes d'un trajet (🚶 → 🚆 → 🚐) suit le sens de lecture, donc elle est aussi inversée en arabe.
- La **carte ne se met pas en miroir** (nord en haut, est à droite) ; seuls les contrôles par-dessus suivent le RTL.

## 3. Formats

| Élément | Français | Arabe | Décision |
|---|---|---|---|
| Chiffres | 0–9 | 0–9 (chiffres occidentaux, usage courant en Tunisie) | Chiffres occidentaux partout |
| Heure | 08:10 | 08:10 | Format 24 h |
| Durée | 1 h 15 min | 1 س 15 د | Formatage via `intl` + ARB |
| Prix | 1,500 DT | 1,500 د.ت | Millimes → dinars avec 3 décimales |
| Pluriels | 1 correspondance / 2 correspondances | règles de pluriel arabes (6 formes) | Toujours via ICU dans les ARB |

## 4. Texte mixte

- Un nom de ligne latin (« A », « TGM ») dans une phrase arabe doit rester lisible : isoler avec `Directionality` ou des marques Unicode d'isolation si nécessaire.
- Tester systématiquement : nom d'arrêt arabe + heure + prix dans la même ligne.

## Critères d'acceptation

- [ ] Chaque écran est vérifié en FR et en AR (captures dans la revue du lot).
- [ ] Aucun texte d'interface en dur (vérifié par lint ou recherche).
- [ ] Aucun nom d'arrêt ou de ligne vide en arabe.
- [ ] Les tests de widgets tournent dans les deux langues pour les écrans principaux.

## Questions ouvertes

- Faut-il aussi la *derja* (dialecte tunisien) en caractères latins pour la recherche (« hammem lif », « bab saadoun ») ? → utile pour l'autocomplétion : prévoir des **alias** de recherche (`aliases`) dans les fichiers `places/` — prévu dans le modèle ([04](04-donnees-modele.md) §4).
- L'anglais pour les touristes : hors V1.
