# Ajouter une ligne de louage

Exemple complet : un louage **Bab Alioua ⇄ Hammam Lif**. Vous créez 3 fichiers (dont 1 seule fois pour tout le réseau),
vous validez, et la ligne apparaît dans les trajets.

> Les fichiers de ce guide ont été testés tels quels : la validation passe et la ligne arrive dans le GTFS. Remplacez
> les horaires, temps et prix par **vos relevés** : ce sont des exemples.

## Avant de commencer : ce qu'il faut relever

| Information | Comment l'obtenir | Exemple |
|---|---|---|
| Les stations de départ et d'arrivée | Elles existent souvent déjà (étape 1) | Bab Alioua, Hammam Lif |
| La durée du trajet | Chronométrez, en heure creuse et en pointe | 20 min, 30 min en pointe |
| L'attente entre deux départs | Comptez les départs pendant 30 min | Un départ toutes les 10 min le matin |
| Les heures de service | Premier et dernier départ | 05:30 – 21:00 |
| Le prix | Demandez ou regardez l'affichage | 1,700 DT |

## Étape 1 : trouver les identifiants des stations

103 stations de louage sont déjà recensées dans `data/src/places/louages/stations.yaml`. Cherchez la vôtre :

```bash
grep -n -i -A3 "alioua" data/src/places/louages/stations.yaml
```

```
1538:- id: LOU-BAB-ALIOUA
1539-  kind: louage_station
1540-  name:
1541-    fr: Louages Bab Alioua
```

L'identifiant est `LOU-BAB-ALIOUA`. Celui de Hammam Lif est `LOU-HAMMAM-LIF`, dans
`data/src/places/grand-tunis/louages-stations.yaml`.

**La station n'existe pas ?** Ajoutez-la à la fin de `data/src/places/grand-tunis/louages-stations.yaml` :

```yaml
- id: LOU-MA-VILLE
  kind: louage_station
  name: { fr: "Louages Ma Ville", ar: "محطة اللواج مدينتي" }
  lat: 36.80000
  lon: 10.18000
  status: active
  provenance: { source: TERRAIN, ref: "Relevé sur place", verified_at: "2026-11-09", by: votre-pseudo }
```

## Étape 2 : créer le réseau Louages (une seule fois)

Si le fichier `data/src/networks/louages/network.yaml` n'existe pas encore, créez-le avec ce contenu :

```yaml
# yaml-language-server: $schema=../../../schemas/network.schema.json
id: LOUAGES
name: { fr: "Louages", ar: "اللواج" }
timezone: Africa/Tunis
calendar:
  day_type_scheme: { mon: OUVRABLE, tue: OUVRABLE, wed: OUVRABLE, thu: OUVRABLE, fri: OUVRABLE, sat: SAMEDI, sun: DIMANCHE }
  holiday_day_type: DIMANCHE
  periods: [RAMADAN, ETE, NORMAL]
  fallback:
    periods: { RAMADAN: NORMAL, ETE: NORMAL }
    day_types: { DIMANCHE: SAMEDI, SAMEDI: OUVRABLE }
status: active
provenance: { source: TERRAIN, ref: "Organisation des stations de louage", verified_at: "2026-11-09", by: votre-pseudo }
```

Le bloc `fallback` veut dire : sans horaire spécial pour le Ramadan ou l'été, on utilise les horaires normaux ; sans
horaire du dimanche, on prend celui du samedi, puis celui de la semaine.

## Étape 3 : créer la ligne

Créez `data/src/networks/louages/lines/lou-bab-alioua--hammam-lif.yaml` :

```yaml
# yaml-language-server: $schema=../../../../schemas/line.schema.json
id: LOU-BABALIOUA-HAMMAMLIF            # identifiant unique, en majuscules
network: LOUAGES
mode: LOUAGE
public_code: Hammam Lif                # pour un louage : la ville de destination affichée
name: { fr: "Louage Bab Alioua ⇄ Hammam Lif", ar: "لواج باب عليوة ⇄ حمام الأنف" }
color: "#E8A317"
text_color: "#111417"
status: active

directions:
  - { id: ALLER,  headsign: { fr: "Hammam Lif", ar: "حمام الأنف" } }
  - { id: RETOUR, headsign: { fr: "Bab Alioua", ar: "باب عليوة" } }

patterns:
  - id: ALLER
    direction: ALLER
    main: true
    stops: [LOU-BAB-ALIOUA, LOU-HAMMAM-LIF]   # identifiants de data/src/places
    run_times:                                 # minutes entre deux arrêts, selon le trafic
      FLUIDE: [20]
      CHARGE: [30]
  - id: RETOUR
    direction: RETOUR
    main: true
    stops: [LOU-HAMMAM-LIF, LOU-BAB-ALIOUA]
    run_times:
      FLUIDE: [20]
      CHARGE: [30]

schedule:
  kind: frequency                      # un départ dès que le louage est plein : pas d'horaire fixe
  regimes:
    - periods: [NORMAL, ETE]
      day_types: [OUVRABLE, SAMEDI]
      service_hours: { first: "05:30", last: "21:00" }
      bands:                           # tranches de data/src/calendar/time-bands.yaml
        NUIT:         { headway_min: null }                     # null = pas de service
        POINTE_MATIN: { headway_min: 10, run_time: CHARGE }     # un départ toutes les 10 min environ
        JOURNEE:      { headway_min: 20, run_time: FLUIDE }
        POINTE_SOIR:  { headway_min: 10, run_time: CHARGE }
        SOIREE:       { headway_min: 30, run_time: FLUIDE }

fare: FARE-LOU-BABALIOUA-HAMMAMLIF
provenance: { source: TERRAIN, ref: "Relevé à la station Bab Alioua, 3 matinées", verified_at: "2026-11-09", by: votre-pseudo }
```

**Ce qu'il faut adapter** : `id`, `public_code`, `name`, les `headsign`, les `stops`, les `run_times`, les heures de
service, les fréquences et la `provenance`. Le reste peut rester tel quel.

## Étape 4 : créer le tarif

Créez `data/src/networks/louages/fares/fare-lou-babalioua-hammamlif.yaml`. L'`id` doit être celui écrit dans `fare:`
à l'étape 3.

```yaml
# yaml-language-server: $schema=../../../../schemas/fare.schema.json
id: FARE-LOU-BABALIOUA-HAMMAMLIF
model: od_pairs                        # un prix par trajet « départ → arrivée »
currency: TND
categories: [PLEIN]
versions:
  - valid_from: "2026-11-01"
    pairs:
      - { from: LOU-BAB-ALIOUA, to: LOU-HAMMAM-LIF, price_millimes: { PLEIN: 1700 } }   # 1,700 DT
      - { from: LOU-HAMMAM-LIF, to: LOU-BAB-ALIOUA, price_millimes: { PLEIN: 1700 } }
provenance: { source: TERRAIN, ref: "Prix affiché à la station, novembre 2026", verified_at: "2026-11-09", by: votre-pseudo }
```

## Étape 5 : valider

Depuis `infra/` :

```bash
docker compose --profile tasks run --rm tools lint
```

Résultat attendu, à la fin :

```
0 erreur(s), … avertissement(s)
```

Une erreur ? Le message indique le code, l'explication et le fichier. Les plus fréquentes :

| Message (extrait) | Cause | Correction |
|---|---|---|
| `REF_UNKNOWN … arrêt inconnu LOU-BAB-ALIOUAX` | Un identifiant de `stops` est mal écrit ou n'existe pas | Corrigez l'identifiant, ou créez le lieu (étape 1) |
| `RUN_TIMES_LENGTH … profil FLUIDE a 2 durées pour 1 tronçons` | Avec N arrêts, il faut N − 1 durées dans chaque profil | Ajoutez ou retirez des durées |
| `REF_UNKNOWN … tarif inconnu FARE-…` | L'`id` du fichier tarif ne correspond pas à `fare:` | Écrivez le même identifiant aux deux endroits |
| `BAND_UNKNOWN … tranche MIDI inconnue pour NORMAL/OUVRABLE` | Un nom de tranche n'existe pas pour cette période | Utilisez les noms de `calendar/time-bands.yaml` |
| `SCHEMA (racine) : 'public_code' is a required property` | Un champ obligatoire manque | Ajoutez le champ cité |

## Étape 6 : voir la ligne dans l'app

```bash
docker compose --profile tasks run --rm tools build
docker compose --profile tasks run --rm tools otp-prepare
docker compose --profile tasks run --rm otp-build
docker compose -f compose.yml -f compose.local.yml restart otp
```

Puis, dans l'app, cherchez un trajet de Bab Alioua à Hammam Lif : le louage apparaît, avec sa destination sur la
pastille jaune et son prix. Ouvrez la fiche de la station Bab Alioua : la ligne figure dans « Louages au départ d'ici ».

## Étape 7 : proposer la ligne

Créez une pull request (voir [Tester et contribuer](12-tester-et-contribuer.md)). Dans la description, précisez
comment vous avez relevé les données : date, heure, nombre de départs observés.

## Aller plus loin

- **Un arrêt en route** où le louage peut prendre des passagers n'importe où entre deux points :
  `- { stop: LOU-RADES-ROUTE, continuous: true }` dans `stops`.
- **Des horaires de Ramadan ou du dimanche** différents : ajoutez un autre bloc dans `regimes`, avec les tranches de
  cette période (`MATIN`, `AVANT_FTOUR`, `FTOUR`, `SOIREE` en Ramadan ; `TOUTE_LA_JOURNEE` le dimanche).
- Le format complet : [specs/04-donnees-modele.md](../specs/04-donnees-modele.md) §8 à §11.
