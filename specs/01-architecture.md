# 01 — Architecture

> Statut : Brouillon · Mise à jour : 2026-10-13

## 1. Vue d'ensemble

```
                      Internet / réseau local
                               │  HTTPS (443)
                     ┌─────────▼──────────┐
 App Flutter ───────▶│  Gateway (nginx)   │  TLS, limite de requêtes, en-têtes, gzip
 (iOS / Android)     └───┬────────────┬───┘
                         │ /api/*     │ /tiles/*
               ┌─────────▼───────┐  ┌─▼────────────────────┐
               │ API Spring Boot │  │ Fichier .pmtiles      │ (servi en statique,
               │ (métier, cache, │  │ (fond de carte)       │  requêtes Range)
               │  i18n, CORS)    │  └──────────────────────┘
               └──┬──────────┬───┘
      GraphQL     │          │ HTTP
        ┌─────────▼───┐  ┌───▼──────────┐
        │     OTP     │  │   Photon     │  géocodage (adresses, lieux)
        │ itinéraires │  │              │
        └──────┬──────┘  └──────────────┘
               │ graphe construit à partir de
        ┌──────▼─────────────────────────────┐
        │ OSM (extrait) + GTFS (généré)      │
        └────────────────────────────────────┘

  Plus tard (lot 8) : PostgreSQL derrière Spring, pour les comptes uniquement.
```

**Règle d'or : seul nginx est exposé.** OTP, Photon, Spring et PostgreSQL sont sur un réseau Docker interne. En local, OTP et Spring peuvent être publiés sur `127.0.0.1` pour le débogage, jamais sur le VPS.

## 2. Composants

| Composant | Rôle | Port interne | Exposé ? |
|---|---|---|---|
| `gateway` (nginx) | Point d'entrée unique : TLS, limites, routage, tuiles | 80 / 443 | Oui |
| `api` (Spring Boot) | API publique `/api/v1`, logique tunisienne, cache, langue | 8080 | Non (dev : `127.0.0.1:8081`) |
| `otp` (OpenTripPlanner 2.x) | Calcul d'itinéraires, index des lignes et des arrêts | 8080 | Non (dev : `127.0.0.1:8080`, client de débogage) |
| `photon` | Géocodage (adresse/lieu → coordonnées) | 2322 | Non |
| `tools` (Python + osmium) | Tâches ponctuelles : découpe OSM, génération GTFS | — | — |
| `gtfs-validator` | Validation du GTFS (MobilityData) | — | — |
| `postgres` (lot 8) | Comptes, favoris, historique — **pas** les lignes | 5432 | Non |

## 3. Responsabilités

| Sujet | Où | Pourquoi |
|---|---|---|
| Calcul d'itinéraires | OTP | Natif, éprouvé |
| Données de transport | GTFS → OTP | Une seule source de vérité |
| Métadonnées locales (modes, prix, fréquences, noms FR/AR, schémas de lignes, périodes, alertes, couverture) | `app-meta.json` généré avec le GTFS ([04c](04c-generation-gtfs.md) §4), lu par Spring | Ne pas dépendre du support partiel des tarifs et traductions dans OTP |
| Régimes horaires (normal, été, Ramadan, Aïd…) | Générateur ([04b](04b-calendriers-regimes.md)) | OTP ne voit que des dates explicites |
| Présentation des louages (« environ toutes les 10 min ») | Spring | OTP fournit des heures fixes, voir spike S1 |
| Langue (FR/AR) | Spring (contenu) + Flutter (interface) | Voir [08-i18n-fr-ar.md](08-i18n-fr-ar.md) |
| HTTPS, limites, en-têtes de sécurité | nginx | Un seul endroit, facile à déplacer sur le VPS |
| CORS | Spring | Seule couche qui connaît les origines autorisées par profil |
| Cache | Spring (Caffeine) | Soulage OTP |

## 4. Flux principal : « je veux aller de A à B »

1. L'app envoie `GET /api/v1/geocode?q=...` pendant la saisie → nginx → Spring → Photon (+ arrêts GTFS correspondants).
2. L'utilisateur valide → `POST /api/v1/itineraries` avec origine, destination, heure de départ et `Accept-Language: ar|fr`.
3. Spring vérifie son cache, sinon interroge OTP (`planConnection` en GraphQL).
4. Spring enrichit le résultat avec `app-meta.json` : mode réel (LOUAGE), prix, fréquence, noms traduits et prochains départs.
5. L'app affiche la liste, puis le détail.

## 5. Environnements

| | Local (maintenant) | VPS (plus tard) |
|---|---|---|
| Orchestration | Docker Compose | Docker Compose (mêmes fichiers + `compose.prod.yml`) |
| TLS | Certificat local `mkcert` | Let's Encrypt (certbot) |
| OSM et fond de carte | **Toute la Tunisie** (depuis le 2026-10-14) | **Toute la Tunisie** |
| Ports de débogage | OTP et Spring sur `127.0.0.1` | Aucun |
| Profil Spring | `local` | `prod` |

## 6. Structure du dépôt

```
thniya/
├── docs/images/                ← captures et GIF du README
├── specs/                      ← ce dossier
├── infra/
│   ├── compose.yml             ← services communs
│   ├── compose.local.yml       ← surcharges locales (ports debug, mkcert)
│   ├── compose.prod.yml        ← surcharges VPS (lot 7)
│   ├── .env.example
│   ├── nginx/                  ← nginx.conf, conf.d/, certs/ (ignoré par git)
│   ├── otp/                    ← build-config.json, router-config.json, otp-config.json
│   └── tools/                  ← Dockerfile de l'image tools
├── data/
│   ├── schemas/                ← JSON Schema de chaque type de fichier
│   ├── templates/              ← gabarits (nouvelle ligne, station, alerte…)
│   ├── src/                    ← SOURCE DE VÉRITÉ (YAML + grilles CSV), voir 04
│   ├── scripts/                ← générateur (paquet Python citydata), découpe OSM, tests
│   ├── golden-trips.yaml       ← trajets de référence (tests)
│   ├── osm/                    ← .pbf téléchargés (ignoré par git)
│   └── build/                  ← gtfs.zip, app-meta.json, report.md, graph.obj (ignoré par git)
├── backend/                    ← Spring Boot (Maven wrapper)
└── mobile/                     ← Flutter
```

## Questions ouvertes

- Monorepo (proposé ci-dessus) ou plusieurs dépôts ? → monorepo recommandé tant qu'on est seul.
