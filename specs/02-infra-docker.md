# 02 — Infrastructure locale (Docker)

> Statut : Brouillon · Mise à jour : 2026-10-13

## 1. Principes

- **Tout tourne en Docker**, y compris les outils (Python, osmium, validateur). Rien d'obligatoire sur la machine hôte à part Docker Desktop, Java/Maven (via wrapper) et Flutter.
- **Mêmes commandes en local et sur le VPS.** Seuls les fichiers de surcharge et le `.env` changent.
- **Versions figées** dans `.env` (pas de tag `latest`).

## 2. Services (`infra/compose.yml`)

| Service | Image | Dépend de | Volumes | Healthcheck |
|---|---|---|---|---|
| `gateway` | `nginx:<version>-alpine` | `api` | `./nginx/conf.d`, `./nginx/certs`, `../data/build/tiles` | `GET /healthz` |
| `api` | construite depuis `../backend` | `otp`, `photon` | `../data/build/app-meta.json` (lecture seule) | `/actuator/health` |
| `otp` | `opentripplanner/opentripplanner:${OTP_VERSION}` | — | `../data/build/otp` | `GET /otp/` |
| `photon` | construite depuis `infra/photon` (Photon 1.3.0, jar officiel vérifié) — [09](09-geocodage-tuiles.md) | — | `../data/build/photon` (index Tunisie, `scripts/photon-import.sh`) | `GET /api?q=tunis` |
| `tools` | construite depuis `./tools` (Python 3.12 + osmium-tool) | — | `../data` | — (ponctuel) |
| `gtfs-validator` | `ghcr.io/mobilitydata/gtfs-validator:<version>` | — | `../data/build` | — (ponctuel) |
| `postgres` (lot 8) | `postgres:<version>` | — | `pg-data` | `pg_isready` |

Les services ponctuels (`tools`, `gtfs-validator`, `otp-build`) utilisent le **profil Compose** `tasks` et ne démarrent pas avec `up`.

### Réseaux

- `edge` : `gateway` uniquement (ports publiés).
- `internal` : `gateway`, `api`, `otp`, `photon`, `postgres`. Réseau `internal: true` sur le VPS.

### Base de saisie et back-office ([04d](04d-base-de-saisie.md))

| Service | Image | Rôle | Port local |
|---|---|---|---|
| `db` | `postgis/postgis:18-3.6` | base de saisie (volume `db-data`) | `127.0.0.1:5433` |
| `directus` | `directus/directus:12.4.1` | back-office (volume `directus-uploads`) | `127.0.0.1:8055` |

Secrets dans `infra/.env` (jamais versionné) : `POSTGRES_PASSWORD`, `DIRECTUS_KEY`, `DIRECTUS_SECRET`,
`DIRECTUS_ADMIN_EMAIL`, `DIRECTUS_ADMIN_PASSWORD`. Le conteneur `tools` reçoit `DATABASE_URL`, `DIRECTUS_URL`,
`API_URL` et les identifiants Directus (pour `backoffice-setup`).

Publication : `infra/scripts/publish.sh --local` (base → GTFS → graphe OTP → redémarrage d'OTP).

## 3. OTP : construction puis service

OTP fonctionne en deux temps :

1. **Build** (ponctuel, gourmand en mémoire) : lit OSM + GTFS → écrit `graph.obj`.
   - Service `otp-build` : `--build --save /var/opentripplanner`
2. **Serve** (permanent) : charge `graph.obj` → répond aux requêtes.
   - Service `otp` : `--load --serve /var/opentripplanner`

Le dossier monté `data/build/otp/` contient : `*.osm.pbf`, `gtfs.zip`, les 3 fichiers JSON de configuration (copiés depuis `infra/otp/`), puis `graph.obj`.

Mémoire (`JAVA_TOOL_OPTIONS=-Xmx…`) : `OTP_BUILD_XMX` et `OTP_SERVE_XMX` dans `.env`. Point de départ : 3 Go en build et 2 Go en service pour le Grand Tunis ; à mesurer (spike S8).

## 4. Variables (`infra/.env.example`)

```dotenv
COMPOSE_PROJECT_NAME=citymapper
OTP_VERSION=2.x.y            # figer à la dernière stable au lot 1
OTP_BUILD_XMX=3g
OTP_SERVE_XMX=2g
NGINX_VERSION=1.x
PUBLIC_HOST=citymapper.localhost
HTTP_PORT=80
HTTPS_PORT=443
SPRING_PROFILES_ACTIVE=local
OSM_SOURCE_URL=https://download.geofabrik.de/africa/tunisia-latest.osm.pbf
OSM_CLIP_BBOX=9.95,36.60,10.45,37.00    # Grand Tunis (outils osm-clip, osm-find)
OTP_REGION=tunisie                      # extrait OSM du graphe OTP : tunisie (défaut) ou grand-tunis
DATA_VERSION=dev
```

## 5. Commandes

À lancer depuis `infra/`. Des alias (`scripts/*.ps1` et `*.sh`) pourront les envelopper plus tard.

```bash
# Données
docker compose --profile tasks run --rm tools osm-download     # télécharge la Tunisie
docker compose --profile tasks run --rm tools osm-clip         # découpe Grand Tunis (outils seulement)
docker compose --profile tasks run --rm tools build            # YAML → gtfs.zip + app-meta.json + report.md
docker compose --profile tasks run --rm gtfs-validator         # rapport HTML dans data/build/validation/
docker compose --profile tasks run --rm tools otp-prepare      # config + OSM (OTP_REGION) + GTFS dans data/build/otp
docker compose --profile tasks run --rm otp-build              # graph.obj (Tunisie entière : ≈ 30 s, 126 Mo)
# Fond de carte de toute la Tunisie (161 Mo, zoom 0–15), servi par nginx sous /tiles/
docker compose --profile tasks run --rm pmtiles extract https://build.protomaps.com/20261012.pmtiles /tiles/tunisie.pmtiles --bbox=7.5,30.2,11.7,37.6 --maxzoom=15
# Recherche d'adresses : index Photon de la Tunisie (≈ 2 min 30), puis démarrage du service photon
bash scripts/photon-import.sh            # --local avec compose.local.yml

# Services
docker compose -f compose.yml -f compose.local.yml up -d
docker compose logs -f api otp
```

**Chaîne complète après modification des données :** `build` → `gtfs-validator` → `otp-build` → `docker compose restart otp api`.

## 6. Spécificités Windows (poste de dev)

- Docker Desktop utilise WSL2 : prévoir au moins **8 Go** pour WSL (`%UserProfile%\.wslconfig`, `memory=8GB`) dès qu'on construit le graphe de toute la Tunisie.
- Fichier `.gitattributes` : `*.sh text eol=lf`, `*.conf text eol=lf` (sinon nginx et les scripts cassent dans les conteneurs).
- Les volumes montés depuis `C:\` sont lents ; OTP lit le graphe une seule fois au démarrage, donc acceptable.

## Critères d'acceptation

- [ ] `docker compose up -d` démarre `gateway`, `api`, `otp`, `photon` sans erreur, healthchecks verts.
- [ ] La chaîne de données complète s'exécute sans rien installer d'autre que Docker.
- [ ] Aucune image en `latest`.
- [ ] Seuls les ports 80/443 sont publiés hors `127.0.0.1`.

## Questions ouvertes

- Photon : image communautaire maintenue ou Dockerfile maison ? → voir spike S6.
