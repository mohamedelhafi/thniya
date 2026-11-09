# L'API

L'API Spring Boot (dossier `backend/`) est la seule porte d'entrée de l'app. Toutes les routes commencent par
`/api/v1`. En local, passez par la passerelle : **http://127.0.0.1:8090/api/v1/…**

La documentation interactive (OpenAPI) est sur **http://127.0.0.1:8082/api/v1/docs**, quand les services tournent.

## La langue

Envoyez l'en-tête `Accept-Language: fr` ou `Accept-Language: ar` : les noms d'arrêts, de lignes et les messages
reviennent dans cette langue.

## Les routes

| Méthode et route | Rôle |
|---|---|
| `GET /meta` | Version des données, modes, réseaux, fenêtre de validité |
| `GET /geocode?q=…&lat=…&lon=…` | Recherche d'arrêts et d'adresses |
| `GET /reverse?lat=…&lon=…` | Le lieu le plus proche d'une position |
| `POST /itineraries` | Calcul d'itinéraires |
| `POST /itineraries/{id}/legs/{index}/departures` | Le même trajet avec un autre départ pour une étape |
| `GET /nearby?lat=…&lon=…&radius=800` | Les arrêts proches et leurs prochains passages |
| `GET /stops/in-bbox?bbox=ouest,sud,est,nord&zoom=…` | Les arrêts à afficher sur la carte |
| `GET /stops/{id}` | La fiche d'un arrêt |
| `GET /lines?mode=…` | La liste des lignes |
| `GET /lines/geometry` | Les tracés de toutes les lignes |
| `GET /lines/{id}` | La fiche d'une ligne |
| `GET /lines/{id}/timetable?direction=…` | Les horaires d'une ligne |
| `GET /lines/{id}/stops/{stopId}/departures` | Les prochains départs d'une ligne à un arrêt |
| `GET /alerts?line=…&stop=…&network=…` | Les perturbations en cours |
| `POST /feedback` | Un signalement envoyé depuis l'app |

## Exemples

Rechercher « Marsa », en arabe :

```bash
curl -H "Accept-Language: ar" "http://127.0.0.1:8090/api/v1/geocode?q=Marsa"
```

Les arrêts autour de la place de Barcelone, à Tunis :

```bash
curl "http://127.0.0.1:8090/api/v1/nearby?lat=36.7963&lon=10.1808&radius=800"
```

Un itinéraire de la place de Barcelone à La Marsa, maintenant :

```bash
curl -X POST "http://127.0.0.1:8090/api/v1/itineraries" -H "Content-Type: application/json" -H "Accept-Language: fr" -d '{"from":{"lat":36.7963,"lon":10.1808},"to":{"lat":36.8791,"lon":10.3277},"time":{"mode":"NOW"}}'
```

Le champ `time` accepte `{"mode":"NOW"}`, `{"mode":"DEPART_AT","at":"2026-11-10T08:00:00+01:00"}` ou
`{"mode":"ARRIVE_BY","at":"…"}`. La réponse contient des sections d'itinéraires, chacune avec ses étapes, son prix et
ses prochains départs.

## Comment le code est organisé

Un dossier par sujet dans `backend/src/main/java/tn/thniya/api/` (voir [Visite du dépôt](04-visite-du-depot.md)).
Le schéma typique d'une route :

```
Controller (routes, paramètres)  →  Service (logique)  →  OTP / index des arrêts / Photon
                                 ←  objets « view » renvoyés en JSON
```

- **Les données d'affichage** viennent de `app-meta.json`, chargé en mémoire et rechargé automatiquement quand le
  fichier change (`meta/`).
- **Les itinéraires** viennent d'OTP, interrogé en GraphQL (`otp/`). Plusieurs requêtes partent en parallèle (threads
  virtuels Java 21) pour proposer des trajets variés.
- **Les adresses** viennent de Photon (`geocode/`). Si Photon est en panne, l'API continue avec les seuls arrêts.

## Configuration

Les réglages sont dans `backend/src/main/resources/application*.yml` et dans les variables d'environnement définies
par `infra/compose.yml` (adresses d'OTP et de Photon, chemin d'`app-meta.json`…).

## Lancer les tests

Depuis `backend/` :

```bash
./mvnw test
```

Sous Windows, utilisez `mvnw.cmd test`. Les tests n'ont pas besoin d'OTP : ils utilisent un `app-meta.json` de test
(`src/test/resources`).

Pour aller plus loin : [specs/06-api-backend.md](../specs/06-api-backend.md).
