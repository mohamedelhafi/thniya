# 04 — Modèle de données transport

> Statut : Brouillon · Mise à jour : 2026-10-14 · Décisions : [ADR-003](adr/ADR-003-source-gtfs-yaml.md), [ADR-006](adr/ADR-006-regimes-horaires.md)
> Suite : [04b — Calendriers et régimes](04b-calendriers-regimes.md) · [04c — Génération GTFS](04c-generation-gtfs.md)

## 1. Objectifs

Le modèle doit permettre de décrire **fidèlement** le transport tunisien, et de l'enrichir **petit à petit** sans jamais casser l'existant :

- tous les modes : train, métro léger, TGM, bus urbains et interurbains, louages, plus tard taxis collectifs et bacs ;
- des horaires qui changent selon la **période** (normal, été, Ramadan, Aïd…) et le **type de jour** (semaine, samedi, dimanche, férié) ;
- des lignes à **horaires** (train), à **fréquence** (louage) ou **mixtes** (bus avec horaires le matin et fréquence ensuite) ;
- des durées qui dépendent de l'**heure** (pointe, creuse, Ramadan avant l'iftar…) ;
- des **prix** par ligne, par zone ou par couple origine-destination, avec historique ;
- des **perturbations** (grève, travaux, déviation) avec date de début et de fin ;
- la **traçabilité** : d'où vient chaque donnée, quand elle a été vérifiée, avec quel niveau de confiance ;
- des données **en brouillon**, saisies mais pas encore publiées.

**Principe :** tout ce qu'on peut configurer l'est dans `data/src`, jamais dans le code. Le code (générateur, Spring, Flutter) ne contient aucune règle propre à une ligne.

## 2. Vue d'ensemble des entités

```
Mode ──< Réseau (opérateur) ──< Ligne ──< Direction ──< Parcours (pattern) ──< Arrêt desservi
                                   │                         │
                                   │                         └── Horaires : grille (CSV) ou fréquences par tranche
                                   ├── Tarif (modèle + prix datés)
                                   └── Notes, statut, provenance

Lieu : Pôle d'échange ──< Station ──< Quai / Arrêt ──< Entrée
Calendrier : Année (événements) → Périodes → Types de jour → Régimes → Tranches horaires
Transversal : Correspondances, Perturbations, Zones de couverture
```

## 3. Arborescence des sources

```
data/
├── schemas/                          # JSON Schema de chaque type de fichier (validation + autocomplétion)
├── templates/                        # modèles de fichiers pour créer une ligne, une station…
├── src/
│   ├── reference/
│   │   ├── modes.yaml                # modes de transport et leur comportement
│   │   ├── fare-categories.yaml      # plein tarif, étudiant, scolaire…
│   │   └── run-time-profiles.yaml    # profils de trafic réutilisables (option)
│   ├── calendar/                     # voir 04b
│   │   ├── years/2026.yaml
│   │   ├── years/2027.yaml
│   │   ├── periods.yaml
│   │   └── time-bands.yaml
│   ├── places/
│   │   ├── hubs.yaml                 # pôles d'échange (regroupent plusieurs stations)
│   │   └── grand-tunis/
│   │       ├── hammam-lif.yaml       # arrêts et stations, regroupés par commune
│   │       └── tunis-centre.yaml
│   ├── networks/
│   │   ├── sncft/
│   │   │   ├── network.yaml          # opérateur + règles de calendrier propres au réseau
│   │   │   ├── lines/banlieue-sud.yaml
│   │   │   ├── timetables/banlieue-sud/<PERIODE>/<TYPE_JOUR>/<DIRECTION>.csv
│   │   │   └── fares/banlieue-sud.yaml (+ matrice CSV)
│   │   ├── transtu/
│   │   └── louages/
│   │       ├── network.yaml
│   │       └── lines/hammam-lif--tunis.yaml
│   ├── transfers.yaml                # correspondances et temps de marche imposés
│   ├── coverage.yaml                 # zones où les données sont complètes / partielles
│   └── alerts/                       # perturbations, un fichier par événement
│       └── 2026-11-05-greve-sncft.yaml
└── golden-trips.yaml                 # trajets de référence (voir 10)
```

Chaque fichier YAML commence par une ligne qui le lie à son schéma, ce qui donne **l'autocomplétion et la validation en direct dans VS Code** (extension YAML de Red Hat) :

```yaml
# yaml-language-server: $schema=../../../schemas/line.schema.json
```

## 4. Champs communs à toutes les entités

| Champ | Obligatoire | Description |
|---|---|---|
| `id` | oui | Identifiant **stable**, majuscules, sans accents, `-` comme séparateur. Jamais renommé une fois publié. |
| `name` | selon l'entité | `{ fr, ar }`, les deux obligatoires pour une entité `active` |
| `aliases` | non | Variantes de recherche : orthographes, derja en lettres latines (`hammem lif`, `7ammam lif`) |
| `status` | oui | `draft` (non publié) · `active` · `suspended` (publié mais sans service, affiché « suspendu ») · `archived` |
| `provenance` | oui | Voir §4.1 |
| `notes_internes` | non | Texte libre, jamais exporté |

### 4.1 Provenance et confiance

```yaml
provenance:
  source: OFFICIEL        # OFFICIEL | TERRAIN | ESTIMATION | SIGNALEMENT | OSM
  ref: "Affiche SNCFT banlieue sud, hiver 2026-2027"
  verified_at: 2026-10-10
  by: contributeur
```

- La **confiance** sert à l'affichage : `ESTIMATION` → l'app affiche « environ ».
- Le rapport de qualité signale toute donnée dont `verified_at` dépasse l'âge maximal défini pour son mode dans `modes.yaml` (ex. prix d'un louage : 90 jours).

## 5. Modes (`reference/modes.yaml`)

```yaml
- id: TRAIN
  name: { fr: "Train", ar: "قطار" }
  gtfs_route_type: 2
  schedule_kinds: [timetable, frequency]   # frequency : TGM (seuls l'intervalle et les premiers/derniers départs sont publiés)
  shows_exact_times: true
  icon: train
  default_color: "#1E5AA8"
  max_data_age_days: { timetable: 180, fare: 365 }

- id: METRO
  name: { fr: "Métro léger", ar: "المترو الخفيف" }
  gtfs_route_type: 0
  schedule_kinds: [timetable, frequency]
  shows_exact_times: true

- id: BUS
  name: { fr: "Bus", ar: "حافلة" }
  gtfs_route_type: 3
  schedule_kinds: [timetable, frequency, mixed]
  shows_exact_times: true

- id: LOUAGE
  name: { fr: "Louage", ar: "لواج" }
  gtfs_route_type: 3                   # à confirmer (spike S5)
  schedule_kinds: [frequency]
  shows_exact_times: false             # l'app n'affiche jamais d'heure exacte
  departs_when_full: true
  seats: 8
  max_data_age_days: { frequency: 120, fare: 90 }

- id: TAXI_COLLECTIF                   # préparé, hors V1
  status: draft
- id: FERRY                            # préparé (bacs), hors V1
  status: draft
```

Ajouter un mode = ajouter une entrée ici + une icône dans l'app. Aucun autre code à modifier.

## 6. Réseaux (`networks/<reseau>/network.yaml`)

Un réseau = un opérateur avec ses propres règles de calendrier.

```yaml
id: SNCFT
name: { fr: "SNCFT", ar: "الشركة الوطنية للسكك الحديدية التونسية" }
url: "https://www.sncft.com.tn"
phone: null
timezone: Africa/Tunis
calendar:
  day_type_scheme:                     # quel type de jour pour chaque jour de la semaine
    mon: OUVRABLE
    tue: OUVRABLE
    wed: OUVRABLE
    thu: OUVRABLE
    fri: OUVRABLE
    sat: SAMEDI
    sun: DIMANCHE
  holiday_day_type: DIMANCHE           # un jour férié roule comme un dimanche
  periods: [AID, RAMADAN, ETE, NORMAL] # périodes utilisées, par priorité décroissante
  fallback:                            # si une ligne n'a pas de grille pour un régime
    periods: { AID: RAMADAN, RAMADAN: NORMAL, ETE: NORMAL }
    day_types: { DIMANCHE: SAMEDI, SAMEDI: OUVRABLE }
status: active
provenance: { source: OFFICIEL, verified_at: 2026-10-10, by: contributeur }
```

Le détail des périodes, types de jour et replis est dans [04b](04b-calendriers-regimes.md).

## 7. Lieux

### 7.1 Hiérarchie

| `kind` | GTFS | Exemple |
|---|---|---|
| `station` | `location_type=1` | Gare de Hammam Lif |
| `platform` | `location_type=0` + `parent_station` | Quai 1 (voie 1) de la gare de Hammam Lif |
| `stop` | `location_type=0` | Arrêt de bus « Hammam Lif Centre » côté nord |
| `louage_station` | `location_type=1` | Station de louages de Hammam Lif |
| `louage_bay` | `location_type=0` + parent | Quai « Tunis » de la station de louages |
| `entrance` | `location_type=2` | Entrée côté marché de la gare |
| `hail_point` | `location_type=0` | Point où l'on hèle couramment un louage sur l'axe |

Un **pôle d'échange** (`hubs.yaml`) regroupe plusieurs stations proches (ex. gare + station de métro + arrêts de bus d'une même place). Il sert à la recherche (« Barcelone » trouve tout le pôle), à l'écran Station et à la génération des correspondances.

### 7.2 Exemple

```yaml
# places/grand-tunis/hammam-lif.yaml
- id: TRN-HAMMAMLIF
  kind: station
  name: { fr: "Hammam Lif", ar: "حمام الأنف" }
  aliases: ["hammem lif", "hammam-lif", "7ammam lif"]
  area: { fr: "Hammam Lif", ar: "حمام الأنف" }   # commune ou quartier, affiché sous le nom
  lat: 0.0
  lon: 0.0
  wheelchair: unknown                 # yes | no | unknown
  status: draft
  provenance: { source: OSM, ref: "node/…", verified_at: 2026-10-13, by: contributeur }

- id: TRN-HAMMAMLIF-V1
  kind: platform
  parent: TRN-HAMMAMLIF
  platform_code: "1"
  name: { fr: "Hammam Lif — voie 1", ar: "حمام الأنف — السكة 1" }
  lat: 0.0
  lon: 0.0
  status: draft
  provenance: { source: TERRAIN, verified_at: 2026-10-13, by: contributeur }
```

Les quais sont **optionnels** : une ligne peut desservir la station directement, et on ajoute les quais quand on les connaît.

## 8. Lignes (`networks/<reseau>/lines/*.yaml`)

```yaml
id: SNCFT-BS-A
network: SNCFT
mode: TRAIN
public_code: "A"                       # affiché dans la pastille de ligne
name: { fr: "Banlieue Sud", ar: "الضاحية الجنوبية" }
color: "#1E5AA8"
text_color: "#FFFFFF"
status: draft

directions:
  - id: NORD
    headsign: { fr: "Tunis Ville", ar: "تونس" }
  - id: SUD
    headsign: { fr: "Erriadh", ar: "الرياض" }      # terminus à vérifier

patterns:                              # suites d'arrêts possibles
  - id: OMNIBUS-N
    direction: NORD
    main: true                         # parcours de référence pour le schéma de ligne
    stops: [TRN-…, TRN-HAMMAMLIF, TRN-…, TRN-TUNISVILLE]
    shape: auto                        # auto (réseau OSM) | osm_relation:<id> | file:<chemin.geojson>
  - id: DIRECT-N
    direction: NORD
    stops: [TRN-HAMMAMLIF, TRN-TUNISVILLE]
    shape: auto

notes:                                 # renvois réutilisés dans les grilles horaires
  a: { fr: "Ne circule pas les jours fériés", ar: "لا يسير أيام العطل الرسمية" }
  b: { fr: "Circule uniquement le vendredi", ar: "يسير يوم الجمعة فقط" }

day_codes:                             # codes « jours de circulation » de l'affiche officielle
  "A": { days: [OUVRABLE, SAMEDI], label: { fr: "Sauf dimanches et fêtes", ar: "ما عدى الآحاد و الأعياد" } }
  "B": { days: [DIMANCHE],         label: { fr: "Dimanches et fêtes seulement", ar: "أيام الآحاد و الأعياد" } }
  "C": { days: [OUVRABLE],         label: { fr: "Sauf samedis, dimanches et fêtes", ar: "ما عدى السبت و الأحد و الأعياد" } }
  "D": { days: [OUVRABLE, DIMANCHE], label: { fr: "Sauf samedi", ar: "ما عدى السبت" } }
  "-": { days: [OUVRABLE, SAMEDI, DIMANCHE], label: { fr: "Tous les jours", ar: "كامل أيام الأسبوع" } }

schedule:
  kind: timetable                      # timetable | frequency | mixed
  source_dir: timetables/banlieue-sud  # grilles CSV, voir §9
  versions:                            # une version = une affiche officielle avec sa période de validité
    - id: HIVER-2026-2027
      valid_from: 2026-09-01
      valid_to: 2027-06-30
      provenance: { source: OFFICIEL, ref: "sncft.com.tn — Horaire Erriadh-Tunis hiver 26-27", verified_at: 2026-10-13 }
  fallback: inherit                    # inherit (règles du réseau) | ou bloc spécifique

fare: FARE-SNCFT-BS
provenance: { source: OFFICIEL, ref: "Affiche SNCFT hiver 2026-2027", verified_at: 2026-10-10, by: contributeur }
```

### Desserte spéciale d'un arrêt dans un parcours

```yaml
stops:
  - TRN-A
  - { stop: TRN-B, pickup: none }              # descente seulement
  - { stop: TRN-C, dropoff: none }             # montée seulement
  - { stop: TRN-D, pickup: on_request }        # arrêt facultatif / à la demande
```

Pour les louages : `continuous: true` sur un tronçon = on peut héler le véhicule n'importe où entre deux arrêts (champs `continuous_pickup`/`continuous_drop_off` du GTFS, prise en charge par OTP à vérifier, spike S9).

## 9. Horaires « grille » (trains, métro, bus à horaires)

On saisit les horaires **comme sur l'affiche officielle** : une colonne par train, une ligne par gare.

Fichier : `timetables/<ligne>/<VERSION>/<PERIODE>/<TYPE_JOUR>/<DIRECTION>.csv`
(ex. `timetables/banlieue-sud/HIVER-2026-2027/RAMADAN/OUVRABLE/NORD.csv`)

- `<VERSION>` : une affiche officielle (voir `schedule.versions`) ; le générateur choisit la version valide à chaque date. Une nouvelle affiche = un nouveau dossier, l'ancienne reste pour l'historique.
- `<TYPE_JOUR>` = `TOUS` quand l'affiche mélange tous les jours avec une colonne « jours de circulation » : on recopie alors les codes de l'affiche dans la ligne `@jours`, et `day_codes` de la ligne les traduit en types de jour. C'est le cas de l'affiche SNCFT banlieue sud.

```csv
stop_id,         501,   503,   505,   507
@pattern,        ,      DIRECT-N, , 
@notes,          ,      ,      a,
@days,           ,      ,      ,      -FRI
TRN-ERRIADH,     05:40, 06:10, 06:40, 07:10
TRN-BORJCEDRIA,  05:44, |,     06:44, 07:14
TRN-HAMMAMLIF,   05:50, 06:18, 06:50, 07:20
TRN-…,           …,     |,     …,     …
TRN-TUNISVILLE,  06:25, 06:40, 07:25, 07:55
```

Conventions :

| Valeur | Signification |
|---|---|
| `HH:MM` | Heure de passage (départ = arrivée) |
| `HH:MM/HH:MM` | Arrivée / départ distincts (arrêt long) |
| `\|` | Le train passe sans s'arrêter |
| vide | Le train ne passe pas par cette gare |
| `24:15`, `25:05` | Après minuit, rattaché au jour de service précédent (soirées de Ramadan) |
| en-tête (`501`) | Numéro du train → identifiant stable du voyage |
| `@pattern` | Optionnel : sinon le parcours est **déduit** des gares desservies |
| `@notes` | Renvois vers `notes` de la ligne (affichés dans l'app) |
| `@jours` | Code « jours de circulation » de l'affiche (`A`, `B`, `-`…), traduit par `day_codes` |
| `@days` | Restriction à l'intérieur du régime : `-FRI` (sauf vendredi), `FRI` (vendredi seulement), `MON,TUE` |

### Corrections de l'affiche

Une affiche officielle peut contenir des coquilles. On ne les recopie pas en silence : la grille contient la **valeur corrigée**, et chaque correction est listée dans la ligne YAML :

```yaml
schedule:
  versions:
    - id: HIVER-2026-2027
      corrections:
        - { direction: NORD, train: "110", stop: TRN-MEGRINE, printed: "16:12", corrected: "06:12",
            reason: "Heure incohérente avec les gares voisines (06:09 → 06:14)" }
```

Le générateur vérifie que chaque correction correspond bien à la grille (la valeur corrigée y figure).
| `@platform` | Optionnel : voie de départ |

Un même dossier peut contenir un fichier `TOUS/` comme type de jour pour une grille valable tous les jours de la période.

> Dans un dossier de grilles, seuls les fichiers nommés d'après une direction (MAJUSCULES : `NORD.csv`, `SUD.yaml`) sont des grilles. Les fichiers en minuscules sont des annexes (trains ajoutés…).
>
> Le repli se fait **par direction** : une grille d'été qui ne couvre que le sens NORD n'efface pas le sens SUD, qui garde sa grille normale.

### Hériter au lieu de tout ressaisir

Une grille de période peut dériver d'une autre :

```yaml
# timetables/banlieue-sud/ETE/OUVRABLE/NORD.yaml   (à la place d'un CSV)
inherits: NORMAL/OUVRABLE/NORD
remove: ["531", "533"]                 # trains supprimés l'été
add_file: ajouts-nord.csv              # trains en plus (annexe : nom en minuscules)
shift:
  - { trains: ["541", "543"], minutes: 10 }
```

## 10. Horaires « fréquence » (louages, bus et métro à intervalle)

Les fréquences s'appuient sur les **tranches horaires nommées** définies dans le calendrier ([04b](04b-calendriers-regimes.md) §5). On ne réécrit pas « 6 h – 9 h » dans chaque ligne.

```yaml
# networks/louages/lines/hammam-lif--tunis.yaml
id: LOU-HAMMAMLIF-TUNIS
network: LOUAGES-GT
mode: LOUAGE
public_code: "→ Tunis"
name: { fr: "Hammam Lif → Tunis", ar: "حمام الأنف ← تونس" }
color: "#E8A317"
status: draft

directions:
  - id: ALLER
    headsign: { fr: "Tunis", ar: "تونس" }
  - id: RETOUR
    headsign: { fr: "Hammam Lif", ar: "حمام الأنف" }

patterns:
  - id: ALLER
    direction: ALLER
    main: true
    stops:
      - LOU-HAMMAMLIF-Q-TUNIS          # quai « Tunis » de la station
      - { stop: LOU-HP-…, continuous: true }
      - LOU-TUNIS-…
  - id: RETOUR
    direction: RETOUR
    stops: […]

run_times:                             # durée en minutes de chaque tronçon, par profil de trafic
  FLUIDE:  [8, 12]
  CHARGE:  [12, 20]
  BLOQUE:  [18, 30]

schedule:
  kind: frequency
  regimes:
    - periods: [NORMAL, ETE]
      day_types: [OUVRABLE, SAMEDI]
      service_hours: { first: "05:30", last: "21:00" }
      bands:
        POINTE_MATIN: { headway_min: 10, run_time: CHARGE }
        JOURNEE:      { headway_min: 20, run_time: FLUIDE }
        POINTE_SOIR:  { headway_min: 10, run_time: BLOQUE }
        SOIREE:       { headway_min: 30, run_time: FLUIDE }
    - periods: [RAMADAN]
      day_types: [OUVRABLE, SAMEDI]
      service_hours: { first: "06:30", last: "25:30" }
      bands:
        MATIN:        { headway_min: 15, run_time: FLUIDE }
        AVANT_FTOUR:  { headway_min: 8,  run_time: BLOQUE }
        FTOUR:        { headway_min: null }               # pas de départ pendant la rupture du jeûne
        SOIREE:       { headway_min: 20, run_time: CHARGE }
    - periods: [NORMAL, ETE, RAMADAN]
      day_types: [DIMANCHE]
      service_hours: { first: "07:00", last: "20:00" }
      bands:
        TOUTE_LA_JOURNEE: { headway_min: 25, run_time: FLUIDE }

fare: FARE-LOU-HL-TUN
provenance: { source: TERRAIN, verified_at: 2026-10-13, by: contributeur, ref: "Observation station, 3 matinées" }
```

- `run_times` : soit des minutes explicites par tronçon, soit `base` + un profil réutilisable de `reference/run-time-profiles.yaml` (ex. `RN1-SUD`) qui applique un coefficient selon la tranche.
- `headway_min: null` = pas de service dans cette tranche.
- `service_hours.by_direction` (option) : premier et dernier départ propres à une direction, ex. `{ CENTRE: { first: "04:26", last: "23:00" } }`, prioritaires sur `first`/`last` (qui restent l'amplitude globale, seule exposée dans `app-meta.json`). Les affiches du métro et des bus Transtu donnent des heures différentes dans chaque sens.
- **Lignes mixtes** (`kind: mixed`) : chaque régime précise `kind: timetable` (avec une grille) ou `kind: frequency` (avec des tranches).

## 11. Tarifs (`networks/<reseau>/fares/*.yaml`)

```yaml
id: FARE-SNCFT-BS
model: od_matrix                       # flat | zones | od_matrix | sections
currency: TND
categories: [PLEIN, ETUDIANT]          # définies dans reference/fare-categories.yaml
versions:                              # historique : la version applicable est choisie par date
  - valid_from: 2025-01-01
    matrix_file: banlieue-sud-2025.csv # millimes, lignes = origine, colonnes = destination
  - valid_from: 2026-07-01
    matrix_file: banlieue-sud-2026.csv
provenance: { source: OFFICIEL, verified_at: 2026-10-10, by: contributeur }
```

Exemples des autres modèles :

```yaml
model: flat                            # prix unique (ex. un bus urbain)
versions: [{ valid_from: 2026-01-01, price_millimes: { PLEIN: 700 } }]

model: od_pairs                        # louage : prix par destination depuis la station
versions:
  - valid_from: 2026-09-01
    pairs:
      - { from: LOU-HAMMAMLIF-Q-TUNIS, to: LOU-TUNIS-…, price_millimes: { PLEIN: 0 } }
```

Tous les prix sont des **entiers en millimes**. L'app affiche le tarif `PLEIN` en V1 ; les autres catégories sont prêtes pour plus tard.

## 12. Correspondances (`transfers.yaml`)

```yaml
- from: TRN-TUNISVILLE
  to: MET-BARCELONE
  min_transfer_min: 4                  # remplace le temps de marche calculé par OTP
  type: recommended                    # recommended | timed | min_time | forbidden
- from_hub: HUB-BARCELONE              # ou toutes les paires d'un pôle
  default_min_transfer_min: 3
```

## 13. Perturbations (`alerts/*.yaml`)

```yaml
id: 2026-11-05-GREVE-SNCFT
active_periods:
  - { from: "2026-11-05T00:00", to: "2026-11-06T23:59" }
scope:
  lines: [SNCFT-BS-A]
  stops: []
  networks: []
effect: NO_SERVICE        # NO_SERVICE | REDUCED_SERVICE | DETOUR | STOP_CLOSED | DELAYS | INFO
severity: severe          # info | warning | severe
title: { fr: "Grève SNCFT", ar: "إضراب الشركة الوطنية للسكك الحديدية" }
body:  { fr: "Aucun train sur la banlieue sud les 5 et 6 novembre.", ar: "…" }
url: null
status: active
provenance: { source: OFFICIEL, ref: "Communiqué SNCFT", verified_at: 2026-11-03, by: contributeur }
```

- `NO_SERVICE` et `STOP_CLOSED` sont **appliqués à la génération** : les voyages concernés disparaissent du GTFS pour ces dates, OTP ne les propose plus.
- Les autres effets sont **affichés** dans l'app (bandeau sur la ligne, l'arrêt, l'itinéraire), sans changer le calcul.

## 14. Zones de couverture (`coverage.yaml`)

```yaml
- id: COUV-HL-TUNIS
  name: { fr: "Couloir Hammam Lif – Tunis", ar: "…" }
  level: complete            # complete | partial
  modes: [TRAIN, BUS, LOUAGE]
  polygon: file:coverage/hl-tunis.geojson
```

L'app s'en sert pour dire honnêtement « itinéraires complets ici » ou « données partielles dans cette zone ».
Aucune zone n'est déclarée pour l'instant (2026-10-14) : l'API répond « données partielles » partout.

## 15. Schémas, gabarits et outils de saisie

- `data/schemas/*.schema.json` : un schéma par type de fichier (mode, réseau, lieu, ligne, grille annexe, tarif, perturbation, calendrier). Les énumérations (`status`, `kind`, `effect`…) y sont définies une seule fois.
- `data/templates/` : gabarits commentés pour une nouvelle ligne de train, de louage, de bus, une station, une perturbation.
- Commandes outils (conteneur `tools`, voir [04c](04c-generation-gtfs.md)) :
  - `new line --mode LOUAGE --network LOUAGES-GT --id …` : crée le fichier à partir du gabarit ;
  - `lint` : validation rapide (schémas + références), en quelques secondes ;
  - `calendar-preview` : quel régime s'applique chaque jour ([04b](04b-calendriers-regimes.md) §7) ;
  - `report` : rapport de qualité (données manquantes, périmées, replis utilisés).
- Plus tard : un **back-office web** pourra éditer ces mêmes données ; le modèle ne changera pas.

## Critères d'acceptation

- [ ] Chaque type de fichier a un schéma JSON et un gabarit ; VS Code autocomplète les champs.
- [ ] Une grille CSV recopiée d'une affiche SNCFT est acceptée telle quelle (passages sans arrêt, après minuit, renvois).
- [ ] Une ligne en `draft` n'apparaît ni dans le GTFS ni dans l'app.
- [ ] Ajouter un mode, une période ou une tranche horaire ne demande aucune modification de code.
- [ ] Toute entité publiée a un nom FR et AR et une provenance.

## Questions ouvertes

- Faut-il gérer dès la V1 les tarifs étudiants et les abonnements à l'affichage ? → proposé : non, mais le modèle les porte.
- Liste réelle des modes à couvrir hors Grand Tunis (SRT régionales, bus privés interurbains) : à préciser lors de l'extension.
