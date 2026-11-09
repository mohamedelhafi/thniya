# Installer et lancer

Ce guide vous mène de zéro à l'application qui tourne sur votre PC.

## 1. Les prérequis

| Outil | Version | À quoi ça sert |
|---|---|---|
| [Git](https://git-scm.com) | récente | Récupérer le code |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | récente | Faire tourner les services (API, OTP, carte…) |
| [Flutter](https://docs.flutter.dev/get-started/install) | 3.47 | L'application mobile et web |
| Java | 21 | Seulement pour lancer les tests de l'API hors Docker |
| Android Studio | récente | Seulement pour l'émulateur Android |

Dans Docker Desktop, donnez **au moins 8 Go de mémoire** (Settings → Resources) : le calcul du graphe d'itinéraires
de toute la Tunisie en a besoin. Prévoyez environ 5 Go de disque.

> Sous Windows, lancez les commandes dans **Git Bash**. Si un chemin du type `/tiles` devient `C:/Program Files/Git/…`,
> préfixez la commande par `MSYS_NO_PATHCONV=1` (voir [Dépannage](13-depannage.md)).

## 2. Récupérer le code et configurer

```bash
git clone https://github.com/mohamedelhafi/thniya.git
cd thniya/infra
cp .env.example .env
```

Ouvrez `infra/.env` et remplacez chaque `change-me` par un secret. Pour en générer un :

```bash
openssl rand -hex 32
```

## 3. Préparer les données (une seule fois)

Toutes ces commandes se lancent **depuis `infra/`**. Le premier lancement est long (téléchargements, puis construction
du graphe) : comptez de 20 minutes à 1 heure selon votre connexion et votre PC.

| Étape | Commande | Ce qu'elle fait |
|---|---|---|
| Carte OSM | `docker compose --profile tasks run --rm tools osm-download` | Télécharge OpenStreetMap pour la Tunisie |
| Découpe | `docker compose --profile tasks run --rm tools osm-clip` | Prépare l'extrait du Grand Tunis (outils) |
| Données | `docker compose --profile tasks run --rm tools build` | Transforme `data/src` en GTFS et en `app-meta.json` |
| OTP (1) | `docker compose --profile tasks run --rm tools otp-prepare` | Rassemble carte et GTFS pour OTP |
| OTP (2) | `docker compose --profile tasks run --rm otp-build` | Construit le graphe d'itinéraires (le plus long) |
| Adresses | `bash scripts/photon-import.sh` | Construit l'index de recherche d'adresses |

Puis le **fond de carte**. Remplacez `AAAAMMJJ` par une date récente de
[maps.protomaps.com/builds](https://maps.protomaps.com/builds/) :

```bash
docker compose --profile tasks run --rm pmtiles extract https://build.protomaps.com/AAAAMMJJ.pmtiles /tiles/tunisie.pmtiles --bbox=7.5,30.2,11.7,37.6 --maxzoom=15
```

Enfin les **certificats HTTPS locaux**, avec l'adresse IP de votre PC sur le Wi-Fi :

```bash
docker run --rm -v "$PWD/nginx:/w" -e LAN_IP=192.168.1.20 alpine:3.22 sh /w/make-dev-certs.sh
```

## 4. Démarrer

Construisez l'app web (depuis `infra/`) :

```bash
(cd ../mobile && flutter build web --profile --pwa-strategy=none)
```

Démarrez tous les services :

```bash
docker compose -f compose.yml -f compose.local.yml up -d
```

Vérifiez que l'API répond (environ 30 secondes après le démarrage) :

```bash
curl http://127.0.0.1:8090/api/v1/meta
```

Vous devez voir un JSON qui commence par `{"dataVersion":…`. Ouvrez ensuite **http://127.0.0.1:8090** dans un
navigateur.

| Adresse | Service |
|---|---|
| http://127.0.0.1:8090 | App web, API et tuiles (passerelle, sans TLS) |
| http://127.0.0.1:8082/api/v1/docs | Documentation OpenAPI de l'API (accès direct) |
| http://127.0.0.1:8080 | Client de débogage d'OTP |

Pour tout arrêter :

```bash
docker compose -f compose.yml -f compose.local.yml stop
```

## 5. Lancer l'app sur Android

Depuis `mobile/`, sur un **émulateur** (`10.0.2.2` est l'adresse du PC vue depuis l'émulateur) :

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8090
```

Sur un **vrai téléphone** branché en USB (débogage USB activé), redirigez d'abord le port du téléphone vers le PC :

```bash
adb reverse tcp:8090 tcp:8090
```

```bash
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8090
```

La redirection saute à chaque installation de l'app ou débranchement du câble : si l'app affiche « pas de connexion »,
relancez `adb reverse`.

Pour juger de la fluidité, utilisez une version release : le mode debug est bien plus lent.

```bash
flutter run --release --dart-define=API_BASE_URL=http://127.0.0.1:8090
```

## 6. Après une modification des données

Si vous modifiez `data/src`, régénérez puis reconstruisez le graphe, et redémarrez OTP :

```bash
docker compose --profile tasks run --rm tools build
docker compose --profile tasks run --rm tools otp-prepare
docker compose --profile tasks run --rm otp-build
docker compose -f compose.yml -f compose.local.yml restart otp
```

L'API recharge seule le nouveau `app-meta.json` (en 30 secondes environ). La passerelle garde certaines réponses en
cache jusqu'à 5 minutes.

Un problème ? Voir [Dépannage](13-depannage.md).
