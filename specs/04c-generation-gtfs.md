# 04c — Génération : du YAML au GTFS et à `app-meta.json`

> Statut : Brouillon · Mise à jour : 2026-10-13

## 1. Chaîne de génération

```
data/src ──▶ 1. Chargement
            2. Validation des schémas JSON              (bloquant)
            3. Résolution des références (ID inconnus)  (bloquant)
            4. Règles métier                            (bloquant ou avertissement)
            5. Résolution du calendrier (04b §6)        → régime par réseau et par date
            6. Expansion des horaires
                 grilles CSV + héritages → voyages
                 tranches de fréquence   → voyages modèles + frequencies
            7. Application des perturbations NO_SERVICE / STOP_CLOSED
            8. Tarifs (version valide à chaque date)
            9. Écriture GTFS          → data/build/gtfs.zip
           10. Écriture app-meta.json → data/build/app-meta.json
           11. Rapport de qualité     → data/build/report.md (+ report.json)
──▶ gtfs-validator (MobilityData) ──▶ otp-build ──▶ trajets de référence
```

Implémentation : Python 3.12, paquet `data/scripts/citydata/`, tests `pytest`. Commandes exposées par le conteneur `tools` :

| Commande | Rôle | Durée visée |
|---|---|---|
| `lint` | Étapes 1 à 4 | < 5 s |
| `calendar-preview` | Étape 5, affichée en tableau | < 5 s |
| `build` | Étapes 1 à 11 | < 30 s pour le Grand Tunis |
| `report` | Rapport seul, sans écrire de GTFS | < 10 s |
| `new <type>` | Crée un fichier depuis un gabarit | — |
| `golden` | Lance les trajets de référence sur l'API locale | < 1 min |

## 2. Règles métier vérifiées

**Bloquantes**

- Identifiant dupliqué, référence inconnue, entité `active` qui dépend d'une entité `draft`.
- Coordonnées absentes, à `0.0` ou hors de la Tunisie.
- Horaires non croissants dans un voyage ; grille dont une gare n'est pas dans la ligne.
- Tranches horaires qui se chevauchent ou laissent un trou.
- Nom `fr` ou `ar` manquant sur une entité `active`.
- Ligne à fréquence dont le nombre de durées `run_times` ne correspond pas au nombre de tronçons.

**Avertissements (rapport)**

- Donnée plus vieille que `max_data_age_days` de son mode.
- Événement `estimated` dans les 30 prochains jours.
- Repli de régime utilisé (liste complète).
- Ligne `active` sans trajet de référence.
- Vitesse anormale entre deux arrêts (ex. > 150 km/h pour un train, > 90 km/h pour un louage) → probable erreur de saisie.
- Arrêt sans aucune ligne active.

## 3. Correspondance avec le GTFS

| GTFS | Source | Règles |
|---|---|---|
| `agency.txt` | `networks/*/network.yaml` | `agency_timezone=Africa/Tunis`, `agency_lang=fr` |
| `stops.txt` | `places/**` | `stop_name` = FR ; hiérarchie via `parent_station` ; `platform_code` |
| `routes.txt` | lignes | `route_type` depuis le mode ; `route_short_name` = `public_code` ; couleurs |
| `trips.txt` | voyages générés | `trip_short_name` = numéro du train ; `direction_id` ; `shape_id` |
| `stop_times.txt` | grilles / `run_times` | `pickup_type`, `drop_off_type`, `continuous_*` ; heures > 24:00 conservées |
| `frequencies.txt` | tranches | `exact_times=0` ; un voyage modèle par (ligne, régime, tranche, direction) |
| `calendar_dates.txt` | résolution 04b | **dates explicites uniquement** (`exception_type=1`) |
| `shapes.txt` | `shape: auto/osm_relation/file` | `auto` = itinéraire calculé sur le réseau OSM entre les arrêts |
| `transfers.txt` | `transfers.yaml` | |
| `fare_*.txt` | tarifs | Générés pour information ; Spring utilise `app-meta.json` (spike S2) |
| `translations.txt` | noms `ar` | `stops.stop_name`, `routes.route_long_name`, `trips.trip_headsign`, `agency.agency_name` |
| `feed_info.txt` | build | `feed_version = DATA_VERSION`, `feed_start_date`/`feed_end_date` = fenêtre |

### Identifiants générés (stables et lisibles)

| Objet | Format | Exemple |
|---|---|---|
| `service_id` | `<RESEAU>:[<VERSION>:]<PERIODE>:<TYPE_JOUR>[:<code>][:<jours>][~n]` | `SNCFT:HIVER-2026-2027:NORMAL:TOUS:A` |
| `trip_id` (grille) | `<LIGNE>:<VERSION>:<PERIODE>:<TYPE_JOUR>:<numéro>` | `SNCFT-BS:HIVER-2026-2027:NORMAL:TOUS:134` |
| `trip_id` (fréquence) | `<LIGNE>:<PERIODE>:<TYPE_JOUR>:<TRANCHE>:<PATTERN>` | `LOU-HAMMAMLIF-TUNIS:NORMAL:OUVRABLE:POINTE_MATIN:ALLER` |

Spring peut ainsi retrouver la période, le type de jour et la tranche d'un voyage proposé par OTP **juste en lisant son identifiant**.

## 4. `app-meta.json` (contrat avec Spring)

Produit à chaque build, chargé par Spring au démarrage et rechargé à chaud quand `dataVersion` change.

```jsonc
{
  "dataVersion": "2026-10-13.1",
  "generatedAt": "2026-10-13T10:00:00+01:00",
  "window": { "from": "2026-10-06", "to": "2027-02-10" },

  "modes": {
    "LOUAGE": { "name": { "fr": "Louage", "ar": "لواج" }, "icon": "louage",
                "showsExactTimes": false, "departsWhenFull": true }
  },

  "networks": {
    "SNCFT": { "name": { "fr": "SNCFT", "ar": "…" }, "url": "…" }
  },

  "lines": {
    "SNCFT-BS-A": {
      "network": "SNCFT", "mode": "TRAIN", "publicCode": "A",
      "name": { "fr": "Banlieue Sud", "ar": "الضاحية الجنوبية" },
      "color": "#1E5AA8", "textColor": "#FFFFFF", "status": "active",
      "directions": [{ "id": "NORD", "headsign": { "fr": "Tunis Ville", "ar": "تونس" } }],
      "diagram": {                       // schéma de ligne pour l'écran Ligne
        "NORD": [
          { "stop": "TRN-…", "branch": 0, "interchanges": ["MET-1", "BUS-…"] }
        ]
      },
      "notes": { "a": { "fr": "Ne circule pas les jours fériés", "ar": "…" } },
      "confidence": "OFFICIEL",
      "verifiedAt": "2026-10-10"
    },
    "LOU-HAMMAMLIF-TUNIS": {
      "mode": "LOUAGE",
      "frequencies": {                   // pour afficher « environ toutes les X min »
        "NORMAL:OUVRABLE": [{ "band": "POINTE_MATIN", "from": "06:00", "to": "09:00", "headwayMin": 10 }]
      },
      "serviceHours": { "NORMAL:OUVRABLE": { "first": "05:30", "last": "21:00" } }
    }
  },

  "stops": {
    "TRN-HAMMAMLIF": {
      "kind": "station", "name": { "fr": "Hammam Lif", "ar": "حمام الأنف" },
      "aliases": ["hammem lif"], "area": { "fr": "Hammam Lif", "ar": "…" },
      "lat": 0.0, "lon": 0.0, "hub": null, "lines": ["SNCFT-BS-A"], "platformCode": null
    }
  },

  "hubs": { "HUB-BARCELONE": { "name": { "fr": "…", "ar": "…" }, "members": ["…"] } },

  "fares": {
    "SNCFT-BS-A": { "model": "od_matrix", "currency": "TND",
                    "matrix": { "TRN-HAMMAMLIF": { "TRN-TUNISVILLE": 800 } } }
  },

  "calendar": {                         // période active par réseau et par date
    "SNCFT": { "2027-02-08": { "period": "RAMADAN", "dayType": "OUVRABLE" } }
  },
  "periods": { "RAMADAN": { "name": { "fr": "Horaires de Ramadan", "ar": "…" }, "showBanner": true } },

  "alerts": [ { "id": "…", "effect": "DELAYS", "severity": "warning", "scope": {}, "activePeriods": [],
                "title": { "fr": "…", "ar": "…" }, "body": { "fr": "…", "ar": "…" } } ],

  "coverage": [ { "id": "COUV-HL-TUNIS", "level": "complete", "modes": ["TRAIN"], "polygon": [[10.3, 36.7]] } ]
}
```

Toute modification de ce format = mise à jour de cette spec **et** de [06-api-backend.md](06-api-backend.md).

### Compléments (2026-10-13)

- **Fréquences et OTP** : `frequencies.txt` reçoit la **moitié** de l'intervalle réel (attente moyenne d'un voyageur
  arrivant au hasard), car OTP compte sinon un intervalle complet d'attente à chaque montée ([05](05-otp.md) S1).
  L'intervalle réel reste dans `app-meta.json` (`frequencies`) pour l'affichage.
- **Tarifs** : `app-meta.json` contient `fares` (version en vigueur au début de la fenêtre) : `model`, `currency`,
  `estimated` (provenance `ESTIMATION`), `flat` ou `pairs` (« DÉPART|ARRIVÉE » → millimes, tarif plein).
- **Version des données** : `dev-AAAA-MM-JJ-<empreinte des sources>` : toute modification des données change la
  version, donc vide les caches de l'API.
- **Tranches de fréquence** triées par heure de début (l'ordre des clés n'a pas de sens, la base jsonb ne le garde pas).
- **Traductions** (`translations.txt`) : une seule par valeur française (clé GTFS) ; si deux arrêts de même nom ont des
  orthographes arabes différentes, on garde la plus fréquente (l'API lit le nom arabe de chaque arrêt dans `app-meta.json`).

## 5. Rapport de qualité (`data/build/report.md`)

Sections :

1. Résumé : nombre de lignes, arrêts et voyages par mode et par statut.
2. Erreurs bloquantes (s'il y en a, le build s'arrête avant).
3. Avertissements, classés par gravité.
4. Fraîcheur : données périmées par ligne.
5. Calendrier : événements estimés à confirmer, replis utilisés.
6. Couverture : lignes `active` sans trajet de référence, arrêts sans nom arabe.

## Critères d'acceptation

- [ ] `build` produit `gtfs.zip`, `app-meta.json` et `report.md`.
- [ ] Le validateur MobilityData ne remonte aucune erreur.
- [ ] Deux builds successifs sur les mêmes sources produisent des fichiers identiques (génération déterministe).
- [ ] Les tests pytest couvrent : lecture des grilles CSV (y compris `|`, après minuit, renvois, `@days`), héritage de grilles, expansion des fréquences, résolution du calendrier, replis et perturbations.
