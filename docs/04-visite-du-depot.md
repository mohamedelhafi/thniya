# Visite du dépôt

```
thniya/
├── README.md                 ← présentation du projet
├── CONTRIBUTING.md           ← règles de contribution
├── docs/                     ← cette documentation, et les images du README
├── specs/                    ← spécifications détaillées et décisions (ADR)
├── data/                     ← les données et l'outil qui les transforme
├── backend/                  ← l'API Spring Boot
├── mobile/                   ← l'application Flutter
├── infra/                    ← Docker Compose et la configuration des services
└── .github/                  ← CI et modèles de tickets
```

## `data/` : les données

| Chemin | Contenu |
|---|---|
| `data/src/` | **La source de vérité.** Tout le réseau, en YAML et CSV |
| `data/src/places/` | Les arrêts, gares et stations, rangés par réseau ou par région |
| `data/src/networks/<réseau>/network.yaml` | La fiche d'un réseau (nom, fuseau horaire, calendrier) |
| `data/src/networks/<réseau>/lines/` | Une ligne par fichier |
| `data/src/networks/<réseau>/fares/` | Les tarifs |
| `data/src/networks/<réseau>/timetables/` | Les grilles horaires en CSV (trains, cars) |
| `data/src/calendar/` | Jours fériés, périodes (été, Ramadan), tranches horaires |
| `data/src/reference/modes.yaml` | Les modes de transport (train, bus, louage, taxi jamaï…) |
| `data/src/places/hubs.yaml` | Les pôles d'échange (gare + métro + bus proches) |
| `data/schemas/` | Les schémas JSON qui définissent le format de chaque fichier |
| `data/scripts/citydata/` | Le générateur Python (validation, GTFS, import…) |
| `data/scripts/tests/` | Les tests du générateur |
| `data/golden-trips.yaml` | Les trajets de référence, testés contre OTP |
| `data/db/migrations/` | Le schéma SQL du back-office |
| `data/build/` | **Généré**, ignoré par Git : GTFS, graphe OTP, tuiles, index Photon |

## `backend/` : l'API

Le code est dans `backend/src/main/java/tn/thniya/api/`, un dossier par sujet :

| Dossier | Contenu |
|---|---|
| `itinerary/` | Calcul et mise en forme des itinéraires (`POST /itineraries`) |
| `otp/` | Le client GraphQL d'OpenTripPlanner |
| `stops/` | Arrêts : à proximité, sur la carte, fiche d'un arrêt |
| `lines/` | Lignes : liste, fiche, tracés, horaires |
| `geocode/` | Recherche d'adresses avec Photon |
| `meta/` | Lecture et rechargement de `app-meta.json`, index des arrêts |
| `system/` | `/meta`, `/geocode`, `/reverse`, `/alerts`, `/feedback` |
| `view/` | Les objets renvoyés à l'app |
| `common/` | Configuration, langue, erreurs, cache HTTP |

## `mobile/` : l'application

| Chemin | Contenu |
|---|---|
| `lib/main.dart`, `lib/app/` | Démarrage et navigation |
| `lib/core/` | Client API (`api.dart`), modèles JSON, état global (`state.dart`), configuration |
| `lib/features/<écran>/` | Un dossier par écran : `home`, `search`, `results`, `trip`, `line`, `lines`, `stop`, `settings` |
| `lib/design/` | Couleurs, espacements, thème, composants réutilisables (pastilles de ligne…) |
| `lib/map/` | La carte (`thniya_map.dart`) et ses mouvements de caméra |
| `lib/l10n/` | Les textes en français (`app_fr.arb`) et en arabe (`app_ar.arb`) |
| `assets/map/` | Les styles de carte (clair, sombre, FR, AR), générés par `tool/mapstyle` |
| `third_party/` | Deux bibliothèques corrigées localement (voir leur README) |
| `test/` | Les tests de l'app |

## `infra/` : les services

| Chemin | Contenu |
|---|---|
| `compose.yml` | Tous les services, communs à tous les environnements |
| `compose.local.yml` | Ajouts pour le développement local (ports, HTTP sans TLS) |
| `.env.example` | Les variables à copier dans `.env` (versions, mémoire, secrets) |
| `nginx/` | Configuration de la passerelle et script de certificats locaux |
| `otp/` | Configuration d'OpenTripPlanner |
| `photon/` | Image Docker de Photon |
| `tools/` | Image Docker du générateur `citydata` |
| `scripts/` | `publish.sh` (base → GTFS → OTP) et `photon-import.sh` |

## `specs/` : les spécifications

Chaque fichier traite un sujet : `04-donnees-modele.md` pour le format des données, `06-api-backend.md` pour l'API,
`07-app-flutter.md` pour l'app, etc. Le sommaire est dans [specs/README.md](../specs/README.md).
