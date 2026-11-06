# 05 — OpenTripPlanner

> Statut : Brouillon · Mise à jour : 2026-10-13

## 1. Version

- **OTP 2.10.0** (sortie le 2026-09-09), figée dans `.env` (`OTP_VERSION`).
- Image officielle `opentripplanner/opentripplanner`.
- Montée de version = refaire les trajets de référence ([10-tests-qualite.md](10-tests-qualite.md)) avant d'adopter.

## 2. Fichiers de configuration (`infra/otp/`)

| Fichier | Contenu attendu |
|---|---|
| `otp-config.json` | Fonctionnalités activées (API GraphQL GTFS, client de débogage en local) |
| `build-config.json` | Sources : `*.osm.pbf` + `gtfs.zip` ; `transitServiceStart/End` couvrant la période des données ; fuseau `Africa/Tunis` |
| `router-config.json` | Paramètres de routage par défaut : vitesse de marche, distance de marche max, temps de correspondance minimal, nombre d'itinéraires renvoyés, timeout de recherche |

Valeurs de départ à affiner :

- Vitesse de marche : 1,3 m/s.
- Correspondance minimale : 2 min (train ↔ bus), à ajuster après les tests terrain.
- Nombre d'itinéraires : 5.

## 3. API utilisée par Spring

API **GraphQL GTFS** d'OTP : `POST /otp/gtfs/v1` (vérifié en 2.10). Langue via l'en-tête `Accept-Language`.

| Besoin | Requête GraphQL | Fonctionnalité PRD |
|---|---|---|
| Itinéraires | `planConnection` | F3, F4, F5, F9 |
| Arrêts proches | `stopsByRadius` ou `stopsByBbox` | F1 |
| Liste des lignes | `routes` | F10 |
| Arrêts d'une ligne par direction | `route { patterns { stops } }` | F10 |
| Prochains départs à un arrêt | `stop { stoptimesWithoutPatterns }` | F6 |
| Horaires d'une ligne pour une journée | `pattern { tripsForDate { stoptimes } }` | F10 |

Les requêtes GraphQL sont stockées dans `backend/src/main/resources/graphql/*.graphql` (une par besoin), jamais construites par concaténation de chaînes.

## 4. Comportements à vérifier (spikes du lot 2)

Ces points conditionnent la façon dont Spring présente les résultats. Le résultat de chaque spike est reporté ici.

| Spike | Question | Résultat |
|---|---|---|
| S1 | Comment OTP restitue-t-il un voyage `frequencies` avec `exact_times=0` dans `planConnection` (heure fixe ? attente moyenne ?) | ✅ OTP 2.10 compte le **pire cas** : montée = arrivée à l'arrêt + un intervalle complet (bus toutes les 12 min → 12 min d'attente à chaque montée, d'où des trajets multimodaux trop longs de 20 à 40 min). **Décision** : le générateur écrit dans `frequencies.txt` la **moitié** de l'intervalle (attente moyenne d'un voyageur arrivant au hasard, minimum 60 s). L'intervalle réel reste dans `app-meta.json` ; c'est lui que l'API et l'app affichent. |
| S2 | Les tarifs GTFS v1 (`fare_attributes`/`fare_rules`) sont-ils renvoyés de façon exploitable ? | _à faire_ |
| S3 | `translations.txt` est-il pris en compte (noms d'arrêts en arabe selon la langue demandée) ? | ✅ Oui (OTP 2.10) : avec `Accept-Language: ar`, `stop.name` et `route.longName` sont en arabe. `route_desc` n'est pas traduit. |
| S4 | Changement de tranche horaire : un louage parti à 8 h 55 garde-t-il bien la durée de la tranche 6 h – 9 h ? | _à faire_ |
| S5 | `route_type=3` vs `1501` (taxi collectif) pour les louages : lequel OTP route correctement sans paramètre spécial ? | ✅ `route_type=3` (BUS) : routé sans configuration. Bus et louages partagent le mode OTP `BUS` ; Spring les distingue par filtre de lignes (`include.routes`) et par `app-meta.json`. |
| S8 | Mémoire et durée du build : Grand Tunis, puis Tunisie entière | ✅ Grand Tunis : build 5 s, `graph.obj` 18 Mo. **Tunisie entière** (2026-10-14, extrait Geofabrik du 2026-10-13, 84 Mo) : build 31 s, `graph.obj` 126 Mo, OTP en service ≈ 1,1 Go de mémoire ; `-Xmx4g` en build et `-Xmx3g` en service suffisent. Le graphe couvre désormais **toute la Tunisie** (`OTP_REGION=tunisie`, défaut), pour les grandes lignes SNCFT et les autocars SNTRI. |

**Position par défaut, en attendant les spikes :** Spring ne fait confiance à OTP que pour les durées, les arrêts et les horaires des modes à horaires. Prix, nature « louage », fréquence affichée et noms arabes viennent de `app-meta.json`.

## 5. Leçons du lot 2

- **Position des arrêts** : les nœuds OSM « arrêt sur la voie » et l'intérieur des gares forment souvent des **îlots piétons** non reliés aux rues. OTP ne peut alors pas y accéder (`NO_STOPS_IN_RANGE`). Règle : placer une gare sur son **parvis ou une rue d'accès**, jamais sur les voies. La commande `otp-check` détecte ces cas pour chaque gare.
- Erreur de routage utile : `routingErrors { code inputField }` dans `planConnection`.

## 6. Exploitation

- Reconstruction du graphe : à chaque modification du GTFS, et une fois par mois pour OSM.
- Sur le VPS : construire le nouveau graphe **à côté** de l'ancien, puis redémarrer `otp` (coupure de quelques secondes ; un basculement sans coupure pourra venir plus tard).
- En local, le client de débogage d'OTP (`http://127.0.0.1:8080`) sert à vérifier visuellement un itinéraire.

## Critères d'acceptation

- [x] Lot 1 : itinéraire à pied entre deux points de Tunis via GraphQL.
- [x] Lot 2 : itinéraire train + marche sur la ligne de banlieue sud, à l'heure réelle.
- [x] Lot 2 : le louage est proposé, avec une durée différente selon la tranche horaire (profils FLUIDE/CHARGE).
- [ ] Lot 2 : spikes S1 à S5 renseignés dans le tableau ci-dessus.
