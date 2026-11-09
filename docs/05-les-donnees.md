# Les données en bref

Tout le réseau est décrit dans `data/src`, en fichiers texte. Ce guide explique les 5 notions à connaître, avec un
exemple pour chacune. Le format complet est dans [specs/04-donnees-modele.md](../specs/04-donnees-modele.md).

## 1. Le lieu (arrêt, gare, station)

Un endroit où l'on monte ou descend. Il a un identifiant unique, un nom en français **et** en arabe, et une position.

```yaml
- id: LOU-BAB-ALIOUA                 # identifiant unique, en majuscules
  kind: louage_station               # le type de lieu (voir le tableau)
  name: { fr: "Louages Bab Alioua", ar: "محطة اللواج باب عليوة" }
  lat: 36.788997                     # latitude
  lon: 10.181827                     # longitude
  status: active
  provenance: { source: OSM, ref: "OpenStreetMap", verified_at: "2026-10-14", by: import-doc }
```

| `kind` | Pour quoi |
|---|---|
| `station` | Une gare ou une station (métro, train) |
| `platform` | Un quai d'une gare |
| `stop` | Un arrêt simple (bus, taxi jamaï) |
| `louage_station` | Une station de louages |
| `louage_bay` | Un quai d'une station de louages (« quai Tunis ») |
| `hail_point` | Un point où l'on hèle couramment un louage au bord de la route |
| `entrance` | Une entrée de gare |

Pour trouver la position d'un lieu : clic droit dans [openstreetmap.org](https://www.openstreetmap.org) → « Afficher
l'adresse » donne la latitude et la longitude.

## 2. Le réseau

Un opérateur, ou une famille de transports, avec ses règles de calendrier. Un fichier par réseau :
`data/src/networks/<réseau>/network.yaml`. Il existe aujourd'hui `sncft`, `sntri` et `transtu`.

## 3. La ligne

Un fichier par ligne dans `data/src/networks/<réseau>/lines/`. Une ligne contient :

- son **identité** : `id`, `mode`, `public_code` (le code affiché : « M6 », « 20B », ou la destination d'un louage),
  `name`, `color` ;
- ses **directions** : en général `ALLER` et `RETOUR`, chacune avec sa destination affichée (`headsign`) ;
- ses **parcours** (`patterns`) : la liste ordonnée des arrêts pour chaque direction, et les temps de trajet entre
  deux arrêts (`run_times`) ;
- son **horaire** (`schedule`) : une grille ou une fréquence (voir ci-dessous) ;
- son **tarif** (`fare`) et sa **provenance**.

Les temps de trajet peuvent dépendre du trafic : `FLUIDE`, `CHARGE`, et éventuellement `BLOQUE`.

```yaml
run_times:
  FLUIDE: [20]       # 20 min entre le 1er et le 2e arrêt quand ça roule
  CHARGE: [30]       # 30 min aux heures de pointe
```

Avec 3 arrêts, il faut 2 valeurs : `[12, 8]`.

## 4. L'horaire : grille ou fréquence

| Type | Quand l'utiliser | Exemple |
|---|---|---|
| `timetable` (grille) | Des heures de passage fixes, publiées | Trains SNCFT, cars SNTRI |
| `frequency` (fréquence) | « Un départ toutes les N minutes », sans heure fixe | Louages, taxis jamaï, métro, bus |

Une **fréquence** se décrit par tranche horaire. Les tranches sont définies dans
`data/src/calendar/time-bands.yaml` :

| Tranche | Heures (jours normaux, ouvrables et samedi) |
|---|---|
| `NUIT` | 00:00 – 06:00 |
| `POINTE_MATIN` | 06:00 – 09:00 |
| `JOURNEE` | 09:00 – 16:00 |
| `POINTE_SOIR` | 16:00 – 19:00 |
| `SOIREE` | 19:00 – 26:00 (soit 02:00 le lendemain) |

```yaml
bands:
  POINTE_MATIN: { headway_min: 10, run_time: CHARGE }   # un départ toutes les 10 min, temps « chargé »
  JOURNEE:      { headway_min: 20, run_time: FLUIDE }
  NUIT:         { headway_min: null }                   # null = pas de service
```

Le **calendrier** combine les **périodes** (`NORMAL`, `ETE`, `RAMADAN`, `AID`) et les **types de jour** (`OUVRABLE`,
`SAMEDI`, `DIMANCHE`, les jours fériés comptant comme un dimanche). Si une ligne ne décrit pas une période, le réseau
prévoit un **repli** : par exemple, en Ramadan, on reprend les horaires normaux. Détails :
[specs/04b-calendriers-regimes.md](../specs/04b-calendriers-regimes.md).

## 5. Le tarif

Les prix sont en **millimes** : `1700` = 1,700 DT. Deux modèles suffisent dans la plupart des cas :

| Modèle | Quand | Exemple |
|---|---|---|
| `flat` | Même prix pour tout trajet sur la ligne | Taxi jamaï à 1,200 DT |
| `od_pairs` | Un prix par trajet « départ → arrivée » | Louage Bab Alioua → Hammam Lif à 1,700 DT |

## 6. La provenance : d'où vient l'information ?

**Obligatoire sur chaque donnée.** Elle permet de savoir ce qui est fiable et ce qui doit être revérifié.

```yaml
provenance: { source: TERRAIN, ref: "Relevé à la station Bab Alioua, 3 matinées", verified_at: "2026-11-09", by: votre-pseudo }
```

| `source` | Signification |
|---|---|
| `OFFICIEL` | Publié par l'opérateur (site, affiche, communiqué) |
| `TERRAIN` | Observé sur place par un contributeur |
| `OSM` | Venu d'OpenStreetMap |
| `ESTIMATION` | Calculé ou supposé ; l'app affiche « estimé » |
| `SIGNALEMENT` | Rapporté par un tiers (presse, usager), non vérifié |

## Les fichiers « Généré par »

Certains fichiers commencent par `# Généré par python -m citydata import-doc`. Ils ont été produits automatiquement à
partir d'une base de connaissances privée. **Vous pouvez quand même les corriger** dans une pull request : la
correction sera reportée dans cette base lors de la revue, pour qu'un futur import ne l'efface pas.

## Toujours valider

Après chaque modification, depuis `infra/` :

```bash
docker compose --profile tasks run --rm tools lint
```

Le résultat doit se terminer par `0 erreur(s)`. Les avertissements (`AVERTISSEMENT …`) signalent des données à vérifier
mais ne bloquent pas.
