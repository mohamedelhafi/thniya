# Ajouter une ligne de taxi jamaï

Le taxi jamaï (taxi collectif urbain) suit le même principe qu'un louage : un trajet fixe, des départs quand le
véhicule est plein, un prix par place. Exemple : **Ariana ⇄ Passage**.

> Les fichiers de ce guide ont été testés tels quels : la validation passe et la ligne arrive dans le GTFS. Les
> positions, temps et prix sont des **exemples** : remplacez-les par vos relevés.

Lisez d'abord le [guide du louage](06-ajouter-une-ligne-de-louage.md) : les explications ne sont pas répétées ici.

## Étape 1 : activer le mode taxi jamaï (une seule fois)

Le mode est prêt dans l'app (icône, couleur), mais il est désactivé tant qu'aucune ligne n'existe. Dans
`data/src/reference/modes.yaml`, au bloc `TAXI_COLLECTIF`, remplacez `status: draft` par `status: active` :

```yaml
- id: TAXI_COLLECTIF
  name: { fr: "Taxi collectif", ar: "تاكسي جماعي" }
  # … le reste ne change pas
  status: active
```

Sans cette étape, la validation refuse la ligne :

```
ERREUR        REF_DRAFT              Ligne publiée TAXI-ARIANA-PASSAGE avec le mode non publié TAXI_COLLECTIF
```

## Étape 2 : créer les points de prise en charge

Créez `data/src/places/grand-tunis/taxis-collectifs.yaml` (ou ajoutez à la fin s'il existe) :

```yaml
# yaml-language-server: $schema=../../../schemas/places.schema.json
- id: TAXI-ARIANA-CENTRE
  kind: stop                           # point de prise en charge ; « louage_station » pour une vraie station
  name: { fr: "Ariana centre (taxis collectifs)", ar: "أريانة المركز (تاكسي جماعي)" }
  lat: 36.8625
  lon: 10.1956
  status: active
  provenance: { source: TERRAIN, ref: "Relevé sur place", verified_at: "2026-11-09", by: votre-pseudo }
- id: TAXI-TUNIS-PASSAGE
  kind: stop
  name: { fr: "Le Passage (taxis collectifs)", ar: "الباساج (تاكسي جماعي)" }
  lat: 36.8075
  lon: 10.1797
  status: active
  provenance: { source: TERRAIN, ref: "Relevé sur place", verified_at: "2026-11-09", by: votre-pseudo }
```

## Étape 3 : créer le réseau (une seule fois)

Créez `data/src/networks/taxis/network.yaml` :

```yaml
# yaml-language-server: $schema=../../../schemas/network.schema.json
id: TAXIS-COLLECTIFS
name: { fr: "Taxis collectifs", ar: "التاكسي الجماعي" }
timezone: Africa/Tunis
calendar:
  day_type_scheme: { mon: OUVRABLE, tue: OUVRABLE, wed: OUVRABLE, thu: OUVRABLE, fri: OUVRABLE, sat: SAMEDI, sun: DIMANCHE }
  holiday_day_type: DIMANCHE
  periods: [RAMADAN, ETE, NORMAL]
  fallback:
    periods: { RAMADAN: NORMAL, ETE: NORMAL }
    day_types: { DIMANCHE: SAMEDI, SAMEDI: OUVRABLE }
status: active
provenance: { source: TERRAIN, ref: "Organisation des taxis collectifs", verified_at: "2026-11-09", by: votre-pseudo }
```

## Étape 4 : créer la ligne

Créez `data/src/networks/taxis/lines/taxi-ariana--passage.yaml` :

```yaml
# yaml-language-server: $schema=../../../../schemas/line.schema.json
id: TAXI-ARIANA-PASSAGE
network: TAXIS-COLLECTIFS
mode: TAXI_COLLECTIF
public_code: Passage                   # la destination affichée sur la pastille
name: { fr: "Taxi collectif Ariana ⇄ Passage", ar: "تاكسي جماعي أريانة ⇄ الباساج" }
color: "#F9A825"
text_color: "#111417"
status: active

directions:
  - { id: ALLER,  headsign: { fr: "Passage", ar: "الباساج" } }
  - { id: RETOUR, headsign: { fr: "Ariana", ar: "أريانة" } }

patterns:
  - id: ALLER
    direction: ALLER
    main: true
    stops: [TAXI-ARIANA-CENTRE, TAXI-TUNIS-PASSAGE]
    run_times: { FLUIDE: [15], CHARGE: [25] }
  - id: RETOUR
    direction: RETOUR
    main: true
    stops: [TAXI-TUNIS-PASSAGE, TAXI-ARIANA-CENTRE]
    run_times: { FLUIDE: [15], CHARGE: [25] }

schedule:
  kind: frequency
  regimes:
    - periods: [NORMAL, ETE]
      day_types: [OUVRABLE, SAMEDI]
      service_hours: { first: "06:00", last: "20:00" }
      bands:
        NUIT:         { headway_min: null }
        POINTE_MATIN: { headway_min: 5, run_time: CHARGE }
        JOURNEE:      { headway_min: 10, run_time: FLUIDE }
        POINTE_SOIR:  { headway_min: 5, run_time: CHARGE }
        SOIREE:       { headway_min: 15, run_time: FLUIDE }

fare: FARE-TAXI-ARIANA-PASSAGE
provenance: { source: TERRAIN, ref: "Relevé à la station d'Ariana", verified_at: "2026-11-09", by: votre-pseudo }
```

## Étape 5 : créer le tarif

Pour un taxi jamaï, le prix est souvent le même pour tout le trajet : le modèle `flat` suffit. Créez
`data/src/networks/taxis/fares/fare-taxi-ariana-passage.yaml` :

```yaml
# yaml-language-server: $schema=../../../../schemas/fare.schema.json
id: FARE-TAXI-ARIANA-PASSAGE
model: flat                            # même prix quel que soit le trajet sur la ligne
currency: TND
categories: [PLEIN]
versions:
  - valid_from: "2026-11-01"
    price_millimes: { PLEIN: 1200 }    # 1,200 DT par place
provenance: { source: TERRAIN, ref: "Prix demandé par le chauffeur, novembre 2026", verified_at: "2026-11-09", by: votre-pseudo }
```

## Étape 6 : valider, voir dans l'app, proposer

Comme pour le louage ([étapes 5 à 7](06-ajouter-une-ligne-de-louage.md#étape-5--valider)) :

```bash
docker compose --profile tasks run --rm tools lint
```

Puis `build`, `otp-prepare`, `otp-build` et redémarrage d'OTP, et une pull request qui explique vos relevés.

La première ligne de taxi jamaï est aussi la première occasion de vérifier son affichage dans l'app (pastille,
filtres, fiche d'arrêt) : signalez dans la pull request tout ce qui s'affiche mal.
