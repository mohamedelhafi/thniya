# 06 — API Spring Boot

> Statut : Brouillon · Mise à jour : 2026-10-13 · Décision : [ADR-002](adr/ADR-002-spring-des-le-depart.md)

## 1. Stack

| Élément | Choix |
|---|---|
| Langage | Java 21 |
| Framework | Spring Boot (dernière 4.x stable, figée dans le `pom.xml`) |
| Build | Maven, via wrapper `./mvnw` |
| Web | Spring MVC + validation Jakarta ; threads virtuels activés |
| Client OTP | `HttpGraphQlClient` + requêtes `.graphql` en ressources |
| Cache | Caffeine via Spring Cache |
| Doc API | springdoc-openapi → `/api/v1/openapi.json` (désactivable en prod) |
| Observabilité | Actuator, logs JSON avec `requestId`, métriques de latence OTP |
| Tests | JUnit 5, WireMock (OTP simulé), intégration sur le vrai OTP (profil `it`) |
| Lot 8 | PostgreSQL + Flyway + Spring Data JPA |

## 2. Organisation du code

```
backend/src/main/java/tn/citymapper/
├── common/       # erreurs (ProblemDetail), langue, CORS, requestId, horloge (Africa/Tunis)
├── meta/         # chargement de app-meta.json, rechargement à chaud, accès typé
├── otp/          # client GraphQL, requêtes, mapping
├── calendar/     # période active, tranche horaire d'un instant (depuis app-meta)
├── itinerary/    # planification, sections, enrichissement, autres départs
├── home/         # à proximité
├── stops/        # fiche arrêt, tableau des départs
├── lines/        # annuaire, fiche ligne, schéma, horaires
├── alerts/       # état du réseau
├── geocode/      # recherche combinée Photon + arrêts
├── feedback/     # signalements
└── system/       # /meta
```

## 3. Conventions transverses

- **Préfixe** `/api/v1` ; changement incompatible → `/api/v2`.
- **Langue** : `Accept-Language` (`fr`/`ar`, défaut `fr`). Tous les libellés renvoyés sont déjà traduits ; à défaut de traduction, le français.
- **Dates** : ISO 8601 avec fuseau ; fuseau métier `Africa/Tunis`.
- **Argent** : entiers en **millimes** + `currency: "TND"`.
- **Coordonnées** : `{ "lat": 36.72, "lon": 10.33 }`.
- **Lignes** : toujours renvoyées sous forme de `LineRef` complète (id, code public, nom, couleurs, mode), pour que l'app affiche une pastille sans autre appel.
- **Confiance** : champ `estimated: true` sur toute valeur estimée (durée de louage, prix non officiel).
- **Erreurs** : RFC 9457 (`ProblemDetail`) + `code` stable : `OUT_OF_AREA`, `NO_ROUTE`, `OTP_UNAVAILABLE`, `VALIDATION_ERROR`, `NOT_FOUND`.
- **CORS** : configuré ici ([03](03-gateway-securite.md) §4).

### Objets partagés

```jsonc
// LineRef
{ "id": "SNCFT-BS-A", "mode": "TRAIN", "publicCode": "A", "name": "Banlieue Sud",
  "color": "#1E5AA8", "textColor": "#FFFFFF", "status": "active" }

// Departure (mode à horaires)
{ "type": "SCHEDULED", "time": "2026-10-13T07:40:00+01:00", "tripId": "…", "platform": "1", "notes": ["a"] }

// Departure (mode à fréquence)
{ "type": "FREQUENCY", "headwayMin": 10, "from": "06:00", "to": "09:00", "estimated": true }
```

## 4. Endpoints

| Méthode | Chemin | Écran | Rôle |
|---|---|---|---|
| `GET` | `/api/v1/meta` | démarrage | Version des données, modes, réseaux, période active, zones couvertes |
| `GET` | `/api/v1/geocode?q=&lat=&lon=&limit=` | Recherche | Arrêts (`type: STOP`, avec lignes) puis adresses et lieux OSM (`type: PLACE`, Photon) — [09](09-geocodage-tuiles.md) §1 |
| `GET` | `/api/v1/reverse?lat=&lon=` | Recherche (carte) | Nom du lieu sous un point |
| `GET` | `/api/v1/nearby?lat=&lon=&radius=&mode=` | Accueil | Arrêts proches + prochains départs par ligne |
| `GET` | `/api/v1/stops/in-bbox?bbox=` | Accueil (carte) | Arrêts visibles (léger : id, mode, position) |
| `POST` | `/api/v1/itineraries` | Résultats | Itinéraires groupés en sections |
| `POST` | `/api/v1/itineraries/{id}/legs/{index}/departures` | Fiche trajet | Recalcul avec un autre départ pour un segment |
| `GET` | `/api/v1/stops/{id}` | Fiche arrêt | Détail + tableau des départs (ou destinations de louage) |
| `GET` | `/api/v1/lines?mode=&q=` | Annuaire | Lignes par mode |
| `GET` | `/api/v1/lines/geometry` | Accueil (carte) | Tracé de chaque ligne active (suite de ses arrêts) pour dessiner le réseau |
| `GET` | `/api/v1/lines/{id}` | Fiche ligne | Directions, schéma, correspondances, alertes, période |
| `GET` | `/api/v1/lines/{id}/timetable?direction=&stop=&date=` | Horaires | Grille du bon régime, ou fréquences |
| `GET` | `/api/v1/lines/{id}/stops/{stopId}/departures?direction=&limit=` | Fiche ligne | Prochains passages d'une ligne à un arrêt |
| `GET` | `/api/v1/alerts?line=&stop=&network=` | État du réseau | Alertes actives et à venir |
| `POST` | `/api/v1/feedback` | Signaler une erreur | Signalement (texte, contexte du trajet) |

### 4.1 `POST /api/v1/itineraries`

Requête :

```json
{
  "from": { "lat": 36.7235, "lon": 10.3410, "label": "Ma position" },
  "to":   { "lat": 36.7990, "lon": 10.1800, "label": "Tunis Ville", "stopId": "TRN-TUNISVILLE" },
  "time": { "mode": "DEPART_AT", "at": "2026-10-13T07:30:00+01:00" },
  "preferences": {
    "modes": ["TRAIN", "METRO", "BUS", "LOUAGE"],
    "lessWalking": false,
    "fewerTransfers": false,
    "walkSpeed": "NORMAL"
  }
}
```

`time.mode` : `NOW`, `DEPART_AT`, `ARRIVE_BY`.

**Calcul des sections (façon Citymapper)** — implémenté dans `ItineraryService`, en deux passes de requêtes OTP
lancées **en parallèle** (threads virtuels) :

| Passe | Requêtes OTP | But |
|---|---|---|
| 1 | `ALL` : tous les modes autorisés (5 résultats) | les meilleurs trajets |
| 1 | `WITHOUT_<mode>` pour chaque mode présent (3 résultats) | alternatives « sans louage », « sans bus »… |
| 1 | `LESS_WALKING` : tous modes, marche très pénalisée | moins de marche |
| 1 | `WALK` : marche seule | durée à pied |
| 2 | `WITHOUT_LINE_<ligne>` : tous modes sauf **une ligne** du meilleur trajet, pour chacune de ses lignes (3 max) | OTP ne renvoie que des trajets optimaux ; retirer tour à tour chaque ligne du meilleur trajet fait apparaître les vraies alternatives (ex. louage → train A au lieu du louage direct, métro au lieu de 25 min de marche) |

Les bus et les louages partagent le mode OTP `BUS` : ils sont séparés par filtre de lignes (`include.routes`).

**La nuit** : si aucune requête ne trouve de transport (plus de service à l'heure demandée), une requête `ALL` est
relancée avec `searchWindow: PT10H` (et la deuxième passe avec la même fenêtre) : la réponse porte
`"notice": "FIRST_DEPARTURES"` et propose les premiers départs du matin, au lieu d'un `404 NO_ROUTE`. Le `404`
n'est renvoyé que s'il n'y a vraiment ni transport ni marche raisonnable.

Fusion :

1. **Une variante par suite de lignes** : deux trajets empruntant les mêmes lignes (départs différents, arrêt de
   montée voisin) ne sont montrés qu'une fois — le meilleur ; les autres départs restent accessibles par les puces.
2. **Coût de classement** (minutes) = arrivée − heure demandée (ou heure demandée − départ en « arriver à »)
   + 5 par correspondance + 1 par minute de marche au-delà de 8 min. 25 min de marche pour gagner 2 min ne font pas
   une bonne suggestion.
3. **Variantes absurdes écartées** : coût > meilleur coût + max(40 min, 75 % de la durée du meilleur).
4. **Sections** : `SUGGESTED` (3 meilleurs), puis une section par mode **réellement emprunté** — au moins 8 min et un
   quart du temps à bord (un trajet louage + métro + TGM apparaît sous « Louage » et « Train », pas sous « Métro »
   pour deux stations) —, `LESS_WALKING` (au moins 4 min de marche en moins que la meilleure suggestion), `WALK`
   (si ≤ 2 h). Une section qui ne ferait que répéter les suggestions n'est pas affichée.

Mesuré en local (réseau de test, 12 lignes) : 120 ms p50 à 4 recherches simultanées, 293 ms p50 / 706 ms p95 à 16,
52 recherches/s sans erreur (≈ 500 requêtes OTP/s).

Réponse :

```jsonc
{
  "dataVersion": "2026-10-13.1",
  "coverage": "FULL",                          // FULL | PARTIAL | WALK_ONLY
  "period": { "id": "NORMAL", "banner": null }, // ou { "id": "RAMADAN", "banner": "Horaires de Ramadan" }
  "sections": [
    { "key": "SUGGESTED", "title": "Suggestions", "itineraryIds": ["it1", "it2", "it3"] },
    { "key": "TRAIN", "title": "Train", "itineraryIds": ["it1", "it4"] },
    { "key": "LOUAGE", "title": "Louage", "itineraryIds": ["it5"] },
    { "key": "WALK", "title": "À pied", "itineraryIds": ["it9"] }
  ],
  "itineraries": {
    "it1": {
      "id": "it1",
      "departAt": "2026-10-13T07:35:00+01:00",
      "arriveAt": "2026-10-13T08:24:00+01:00",
      "durationMin": 49,
      "walkMin": 9,
      "transfers": 1,
      "price": { "millimes": 1800, "currency": "TND", "estimated": true },
      "summary": [                              // pour la chaîne de modes
        { "mode": "WALK", "minutes": 5 },
        { "mode": "TRAIN", "line": { "id": "SNCFT-BS-A", "publicCode": "A", "color": "#1E5AA8" } },
        { "mode": "LOUAGE", "line": { "id": "LOU-…", "publicCode": "→ Ariana" } }
      ],
      "nextDepartures": [ /* Departure du premier transport, 3 max */ ],
      "alerts": ["2026-11-05-GREVE-SNCFT"],
      "bounds": [[10.17, 36.72], [10.34, 36.80]],
      "legs": [
        { "type": "WALK", "durationMin": 5, "distanceM": 380,
          "from": { "name": "Ma position" }, "to": { "stopId": "TRN-HAMMAMLIF", "name": "Hammam Lif" },
          "steps": [ { "instruction": "Prendre l'avenue …", "distanceM": 120 } ],
          "polyline": "…" },
        { "type": "TRANSIT", "mode": "TRAIN", "line": { /* LineRef */ },
          "headsign": "Tunis Ville", "platform": "1",
          "from": { "stopId": "TRN-HAMMAMLIF", "name": "Hammam Lif" },
          "to":   { "stopId": "TRN-RADES", "name": "Radès" },
          "departAt": "…", "arriveAt": "…", "durationMin": 14,
          "intermediateStops": [ { "stopId": "…", "name": "…", "time": "…" } ],
          "departures": [ /* ce départ + les suivants, pour les puces */ ],
          "price": { "millimes": 800, "estimated": false },
          "notes": [], "polyline": "…" },
        { "type": "TRANSIT", "mode": "LOUAGE", "line": { /* LineRef */ },
          "from": { "stopId": "LOU-…", "name": "Station de louages de Radès", "bay": "Ariana" },
          "to": { "stopId": "…", "name": "…" },
          "departure": { "type": "FREQUENCY", "headwayMin": 10, "estimated": true },
          "waitMin": 5, "durationMin": 25, "durationEstimated": true,
          "departsWhenFull": true,
          "price": { "millimes": 1000, "estimated": false }, "polyline": "…" }
      ]
    }
  }
}
```

Règles d'enrichissement :

- Mode, couleurs, noms traduits, quai : depuis `app-meta.json`.
- **Louage** : jamais d'heure exacte ; `headwayMin` de la tranche active (lue dans l'identifiant de voyage généré, [04c](04c-generation-gtfs.md) §3) ; `waitMin = headwayMin / 2`. La pastille (`line.publicCode`) porte la **destination du sens emprunté** dans la langue de l'usager (« Bab Alioua » / « باب عليوة »).
- **Prix d'un segment** (`Fares`) : tarif de la ligne dans `app-meta.json` — `flat` : prix unique ; `od_pairs` : prix du couple montée/descente (ou de leurs gares parentes) ; montée ou descente en route (louage hélé) : prix du trajet complet le plus cher, marqué estimé. Sans tarif saisi : prix inconnu (`millimes: null`), jamais inventé.
- **Prix du trajet** : somme des segments ; inconnu si un segment l'est ; `estimated: true` si un segment est estimé.
- **Ligne estimée** : `line.estimated: true` quand la provenance de la ligne est `ESTIMATION` (l'app affiche « Horaires estimés »).
- **Alertes** : toute alerte active à l'heure du trajet sur une ligne ou un arrêt utilisés.
- `coverage` : selon les zones de `coverage.yaml` traversées.

### 4.2 Autres départs pour un segment

`POST /api/v1/itineraries/{id}/legs/{index}/departures` avec `{ "departAt": "…08:02…" }` → renvoie l'itinéraire recalculé à partir de ce départ (mêmes lignes si possible, étapes suivantes ajustées). Les itinéraires sont gardés en cache 30 min sous leur `id`. Mise en œuvre via un filtre de lignes dans OTP (spike S11).

### 4.3 `GET /api/v1/stops/{id}`

```jsonc
{
  "id": "TRN-HAMMAMLIF", "kind": "station", "name": "Hammam Lif", "area": "Hammam Lif",
  "location": { "lat": 0.0, "lon": 0.0 },
  "hub": { "id": "…", "members": [ { "stopId": "…", "name": "…", "walkMin": 3 } ] },
  "alerts": [],
  "board": [                                   // tableau des départs
    { "line": { /* LineRef */ }, "direction": "NORD", "headsign": "Tunis Ville",
      "departures": [ /* Departure ×3 */ ], "noServiceToday": false, "nextServiceAt": null }
  ],
  "louageDestinations": [                      // seulement pour une station de louages
    { "line": { /* LineRef */ }, "destination": "Tunis", "bay": "Quai 2",
      "price": { "millimes": 1000 }, "departure": { "type": "FREQUENCY", "headwayMin": 10 },
      "serviceHours": { "first": "05:30", "last": "21:00" } }
  ]
}
```

### 4.4 `GET /api/v1/lines/{id}`

```jsonc
{
  "line": { /* LineRef */ }, "network": "SNCFT",
  "period": { "id": "RAMADAN", "banner": "Horaires de Ramadan" },
  "alerts": [],
  "directions": [
    { "id": "NORD", "headsign": "Tunis Ville",
      "diagram": [
        { "stopId": "…", "name": "…", "branch": 0, "isTerminus": true,
          "interchanges": [ { /* LineRef compacte */ } ] }
      ] }
  ],
  "notes": { "a": "Ne circule pas les jours fériés" }
}
```

### 4.5 `GET /api/v1/lines/{id}/timetable`

- Résout le régime de la date demandée ([04b](04b-calendriers-regimes.md)) et renvoie :

```jsonc
{
  "date": "2027-02-10", "period": "RAMADAN", "dayType": "OUVRABLE", "fallbackFrom": null,
  "stop": { "stopId": "TRN-HAMMAMLIF", "name": "Hammam Lif" },
  "kind": "SCHEDULED",
  "hours": [ { "hour": 5, "minutes": [ { "m": 50, "trip": "501", "notes": [] } ] } ],
  "frequencies": null,
  "firstDeparture": "05:50", "lastDeparture": "24:40"
}
```

- Ligne à fréquence : `kind: "FREQUENCY"`, `hours: null`, `frequencies: [{ "from", "to", "headwayMin" }]`.

## 5. Performances et cache

### Index des arrêts (`StopIndex`)

Construit à chaque chargement d'`app-meta.json` (immuable, partagé sans verrou) :

- **STRtree (JTS 1.20)** : arrêts d'un rectangle (carte), arrêts dans un rayon, arrêt le plus proche (géocodage
  inverse) — plus aucun parcours linéaire ;
- **noms normalisés pré-calculés + index de trigrammes** pour l'autocomplétion (même classement qu'avant : 100 =
  identique, 80 = commence par, 75 = sans espaces, 60 = un mot commence par, 40 = contient ; alias −5).

Testé à 100 000 arrêts : construction en moins de 5 s, recherche et voisinage en quelques millisecondes.

### Cache HTTP (navigateurs, téléphones, nginx)

| Ressource | `Cache-Control` |
|---|---|
| `/meta`, `/lines`, `/lines/geometry`, `/lines/{id}`, `/lines/{id}/timetable` | `public, max-age=300` |
| `/geocode`, `/reverse` | `public, max-age=300` |
| `/stops/in-bbox` | `public, max-age=120` |
| `/alerts` | `public, max-age=60` |
| `/nearby`, `/stops/{id}`, `/lines/{id}/departures` (départs) | `public, max-age=15` |
| erreurs, `POST` | `no-store` |

`ETag` calculé sur le corps (`ShallowEtagHeaderFilter`) : un client qui renvoie `If-None-Match` reçoit `304` sans
corps. `Vary: Accept-Language`. La passerelle met ces réponses en cache ([03](03-gateway-securite.md) §6).

### Protection d'OTP

Client HTTP du JDK (connexions persistantes) et **cloison** : 32 requêtes OTP simultanées au plus
(`app.otp-max-concurrent`), attente d'une place 3 s au plus (`app.otp-queue-timeout`), puis `503 OTP_UNAVAILABLE`
plutôt que d'écrouler OTP.

### Mise à l'échelle

L'API est sans état (données en mémoire, rechargées à chaud) : plusieurs instances derrière nginx
(`docker compose up --scale api=N`). OTP se duplique de la même façon (chaque instance charge le graphe). La base de
saisie n'est jamais sur ce chemin ([04d](04d-base-de-saisie.md)).

### Caches applicatifs (Caffeine)

| Cache | Clé | TTL |
|---|---|---|
| `itineraries` | origine/destination arrondies (~50 m) + tranche de 5 min + mode de temps + préférences + langue | 2 min |
| `itineraryById` | id | 30 min |
| `lines`, `lineDetail`, `timetable` | id + direction + date + langue + `dataVersion` | 1 h |
| `nearby`, `stopsInBbox` | tuile géographique + langue | 30 s (départs) / 10 min (positions) |
| `geocode` | requête normalisée + langue + zone | 1 h |

Changement de `dataVersion` → vidage de tous les caches.

## 6. Résilience

- Timeouts : OTP 8 s, Photon 2 s.
- Section qui échoue (timeout d'une des requêtes parallèles) → les autres sections sont renvoyées quand même.
- Photon indisponible → la recherche ne renvoie que les arrêts.
- OTP indisponible → `503` `OTP_UNAVAILABLE`.

## 7. Signalements (`/feedback`)

- Corps : type (`WRONG_TIME`, `WRONG_PRICE`, `WRONG_STOP`, `OTHER`), texte, contexte (itinéraire, ligne, arrêt), version de l'app, langue.
- Jusqu'au lot 8 : ajout dans un fichier JSONL sur un volume (`data/feedback/`) ; ensuite PostgreSQL.
- Limite de requêtes stricte dans nginx (1 par minute et par IP, réserve de 5).

## 8. Configuration (`application.yml`)

```yaml
app:
  otp.base-url: http://otp:8080
  photon.base-url: http://photon:2322
  meta.path: /data/app-meta.json
  feedback.path: /data/feedback
  cors.allowed-origins: []
  default-language: fr
  itineraries:
    max-per-section: 3
    parallel-timeout: 6s
```

## Critères d'acceptation

- [ ] Tous les endpoints documentés dans OpenAPI, avec des exemples réels.
- [ ] Les trajets de référence passent via l'API.
- [ ] `Accept-Language: ar` renvoie tous les libellés en arabe.
- [ ] Un louage n'a jamais d'heure de départ exacte.
- [ ] La grille horaire d'une date de Ramadan renvoie `period: RAMADAN`.
- [ ] OTP arrêté → 503 propre ; Photon arrêté → recherche dégradée ; une section en échec n'empêche pas les autres.
