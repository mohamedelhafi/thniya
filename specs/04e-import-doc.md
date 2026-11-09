# 04e — Import de la base de connaissances `doc/`

> Depuis le 2026-11-09, ce dossier privé s'appelle `recherches-privees/`, pour ne plus le confondre avec la
> documentation publique `docs/`. Les références `doc/…` de cette spec, des en-têtes « Généré par » et des
> provenances de `data/src` désignent ce dossier.

> Statut : Implémenté · Mise à jour : 2026-10-14 · Suite de [04d](04d-base-de-saisie.md)

## 1. Rôle

`doc/` (non versionné) rassemble ce qu'on sait du transport en Tunisie : fiches sourcées par mode et fichiers retravaillés
`doc/<thème>/donnees/*.csv`, chacun avec son statut ([C] confirmé, [I] incertain, [A] ancien). L'import transforme ces
fichiers en données `data/src` ordinaires, validées par le générateur ([04c](04c-generation-gtfs.md)) comme n'importe
quelle saisie, puis chargées dans la base de saisie ([04d](04d-base-de-saisie.md)).

C'est un **amorçage** : une fois la base chargée, elle devient la source de vérité et les corrections se font dans le
back-office. Réimporter remplace les fichiers générés ; on ne le fait que pour repartir de `doc/` (base vide ou
volontairement écrasée).

```
doc/<thème>/donnees/*.csv ──import-doc──► data/src (fichiers « Généré par … import-doc »)
                                              │ lint (0 erreur) · build · gtfs-validator
                                              ▼
                            db-import --replace ──► base de saisie ──publish──► GTFS + app-meta ──► OTP (Tunisie)
```

## 2. Commande

`python -m citydata import-doc [--doc CHEMIN] [--only module,…]` (local ou conteneur `tools`). Rapport complet :
`data/build/import-doc-report.json` (fichiers écrits ou retirés, volumes, éléments écartés et pourquoi). Deux passages
successifs produisent exactement les mêmes fichiers.

| Module | Lit (doc/…) | Écrit (data/src/…) |
|---|---|---|
| `transtu-rail` | `metro-tramway/donnees/` | stations du métro et du TGM, lignes M1–M6 et TGM, tarifs Transtu |
| `sncft` | `trains-banlieue/donnees/`, `trains-grandes-lignes/donnees/` | `places/sncft/`, lignes RFR D et E, Sahel, grandes lignes, grilles, tarifs |
| `transtu-bus` | `bus/grand-tunis-transtu/donnees/` | arrêts `places/grand-tunis/bus-transtu.yaml`, lignes `bus-*.yaml` |
| `sntri` | `bus/regional-interurbain/donnees/sntri-*.csv` + bruts `sources-open-data/raw/` | réseau `networks/sntri/`, arrêts `places/sntri/` |
| `louage` | `louage/donnees/stations.csv` | `places/louages/stations.yaml` |
| `hubs` (en dernier) | tous les lieux importés | `places/hubs.yaml` |

Un module n'écrase **jamais** un fichier saisi à la main (sans l'en-tête « Généré par ») : la banlieue sud SNCFT, son
réseau et ses gares, le calendrier et les modes restent tels quels. Les données de test d'avant l'import (louages
et zone de couverture générés par l'ancienne commande `seed-network`) ont été supprimées le 2026-10-14 : la base ne
contient plus que des données issues de sources (officielles, OSM, presse) ou estimées à partir d'elles.

## 3. Règles de fiabilité

| Donnée de doc/ | Dans data/src |
|---|---|
| [C], source officielle en vigueur (affiche, site de l'opérateur) | `provenance.source: OFFICIEL`, entité `active` |
| Position OpenStreetMap | `provenance.source: OSM` |
| Valeur estimée (heures creuses, dimanche, durées entre arrêts, ancien tarif, prix par tronçon) | `provenance.source: ESTIMATION` : l'app affiche « environ » |
| [I] non vérifié, nom arabe inconnu, parcours douteux | `status: draft` : en base pour être complété dans le back-office, jamais publié |
| Introuvable, incohérent, hors de Tunisie | écarté, avec la raison dans le rapport |

Rien n'est inventé : un nom arabe absent n'est pas traduit (brouillon), une gare sans coordonnées est retirée des
parcours, un prix inconnu reste inconnu (la ligne n'a pas de tarif).

**Sans doublon** : identifiants existants conservés (`id_app` des CSV, fichiers déjà générés) ; une gare servie par
plusieurs lignes = un seul lieu ; arrêts de bus fusionnés s'ils ont les mêmes coordonnées, ou le même nom et le même côté
de rue à moins de 40 m ; stations de louages fusionnées à moins de 400 m (même ville) ; pôles d'échange en étoile autour
d'une gare ou d'une station (250 m, 450 m autour d'une gare routière ou de louages), jamais de proche en proche.

## 4. Hypothèses par réseau

- **Métro et TGM** : premiers et derniers départs de chaque sens et fréquence de pointe = affiche hiver 2026-2027.
  Autres tranches : intervalle de pointe en journée, doublé après 19 h ; dimanche : rapport dimanche / semaine de
  l'horaire open data (plafonné à 2) ; été et Ramadan : modèles des affiches 2026. TGM : 45 min toute la journée.
  Durées entre stations estimées (24 km/h métro, 40 km/h TGM). Le mode TRAIN accepte désormais les fréquences (TGM).
- **Bus Transtu** : lignes publiées seulement si l'itinéraire open data concorde avec l'affiche et que les quatre
  heures et la fréquence sont publiées. Heures creuses et dimanche estimés d'après 2 271 départs open data du dépôt de
  Ben Arous (soirée ×1,25, dimanche ×1,3 et premier départ +30 min ; 13 lignes sans service le dimanche). Durées :
  24 km/h en trafic fluide, 17 km/h en trafic chargé, détour ×1,25.
- **SNCFT** : grilles transcrites train par train (version HIVER-2026-2027, 2026-09-01 → 2027-06-30) ; pas de grille de
  Ramadan (repli sur la grille normale) ; Tunis – Annaba limité aux gares tunisiennes ; tarifs = derniers connus
  (2020-2023), en estimation.
- **SNTRI** : horaires du site (version SITE-2026-10-14, revérifier avant le 2027-04-12) ; arrêts géolocalisés par
  rapprochement des noms avec le référentiel national, la cartographie SNTRI et les arrêts SRT, contrôlé par les km et
  les heures du site (93,5 % des libellés placés) ; prix terminus–terminus du site, prix des tronçons au prorata des km.
- **Louages** : stations seulement (aucune durée ni fréquence fiable dans doc/) ; [C] publiées, [I] en brouillon.

## 5. Volumes (import du 2026-10-14)

| | Lieux | Lignes publiées | Brouillons | Voyages / tarifs |
|---|---|---|---|---|
| Métro + TGM | 66 + 18 stations | 7 | 2 stations fermées (archivées) | fréquences |
| SNCFT (hors banlieue sud saisie) | 128 gares | 10 | — | 272 trains, 3 tarifs |
| Bus Transtu | 1 558 arrêts (1 315 publiés) | 114 | 57 lignes | fréquences, 1 tarif spécial |
| SNTRI | 260 arrêts (258 publiés) | 84 | 1 (Tripoli) | 167 voyages, 84 tarifs (31 522 couples) |
| Louages | 102 stations (46 publiées) | — | 56 stations | — |
| Pôles d'échange | 42 | | | |

Après chargement : 2 155 lieux, 277 lignes, 94 tarifs, 189 grilles en base ; GTFS publié : 219 lignes, 1 807 arrêts,
2 926 voyages ; `db-check` identique à l'octet ; 12 trajets de référence réussis (dont Tunis – Sousse en train,
Tunis – Kairouan en autocar, Tunis Marine – aéroport).

## Critères d'acceptation

- [x] `import-doc` puis `lint` : 0 erreur ; deux passages successifs produisent les mêmes fichiers.
- [x] Aucun fichier saisi à la main n'est écrasé ; aucune entité en double (identifiants et positions).
- [x] Toute donnée estimée porte `provenance.source: ESTIMATION` ; toute donnée incomplète est en brouillon.
- [x] `db-import --replace`, `db-check` (GTFS identique) et `publish` réussissent ; trajets de référence verts.
- [ ] Revue dans le back-office des brouillons (57 lignes de bus, 56 stations de louages, 243 arrêts) — à faire par
      l'équipe de saisie.

## Questions ouvertes

- Codes publics des grandes lignes (« 1 » Bizerte, « 5 », « 6 », « TA » Ghardimaou, « TM » Annaba, « BN », « RM »).
- Le train Tunis – Annaba prend-il des voyageurs pour un trajet intérieur ?
- Lignes de louage interurbaines : à saisir quand on aura des durées et des fréquences observées.
