# Specs — Thniya

Spécifications **vivantes** du projet : elles disent **comment**. Le PRD cité par endroits est le besoin produit initial, un document interne non publié.

## Règles de vie des specs

1. **Une spec par sujet.** Quand le code change un comportement décrit ici, la spec est mise à jour **dans le même commit**.
2. **En-tête obligatoire** dans chaque fichier : `Statut` et `Mise à jour`.
   - `Brouillon` : proposé, pas encore éprouvé.
   - `Validé` : relu et accepté, on peut coder dessus.
   - `Implémenté` : le code existe et correspond.
3. **Une décision structurante = un ADR** dans [`adr/`](adr/). Un ADR ne se réécrit pas : on en crée un nouveau qui le remplace (`Remplacé par ADR-00X`).
4. **Ce qui n'est pas tranché** va dans la section « Questions ouvertes » de la spec concernée, ou dans [99-questions-ouvertes.md](99-questions-ouvertes.md) si c'est transverse.
5. **Spikes** = petites expériences pour lever un doute technique. Ils sont listés dans [99-questions-ouvertes.md](99-questions-ouvertes.md) ; leur résultat est reporté dans la spec concernée puis le spike est marqué « fait ».
6. Les **critères d'acceptation** (cases à cocher) servent de « definition of done ».

## Index

| Fichier | Sujet | Statut |
|---|---|---|
| [01-architecture.md](01-architecture.md) | Vue d'ensemble, composants, flux, structure du dépôt | Brouillon |
| [02-infra-docker.md](02-infra-docker.md) | Docker Compose local, services, volumes, commandes | Brouillon |
| [03-gateway-securite.md](03-gateway-securite.md) | nginx : HTTPS, limite de requêtes, CORS, en-têtes | Brouillon |
| [04-donnees-modele.md](04-donnees-modele.md) | Modèle de données : modes, réseaux, lieux, lignes, grilles, fréquences, tarifs, alertes, provenance | Brouillon |
| [04b-calendriers-regimes.md](04b-calendriers-regimes.md) | Calendriers : fériés, été, Ramadan, Aïd, types de jour, tranches horaires, replis | Brouillon |
| [04c-generation-gtfs.md](04c-generation-gtfs.md) | Génération : contrôles, GTFS, `app-meta.json`, rapport de qualité | Brouillon |
| [04d-base-de-saisie.md](04d-base-de-saisie.md) | Base de saisie PostgreSQL/PostGIS, back-office Directus, publication | Implémenté |
| [04e-import-doc.md](04e-import-doc.md) | Import de la base de connaissances `doc/` : règles de fiabilité, dédoublonnage, volumes | Implémenté |
| [05-otp.md](05-otp.md) | OpenTripPlanner : version, configuration, requêtes | Brouillon |
| [06-api-backend.md](06-api-backend.md) | API Spring Boot : endpoints, contrats, cache, erreurs | Brouillon |
| [07-app-flutter.md](07-app-flutter.md) | App Flutter : fonctionnalités type Citymapper, écrans, critères | Brouillon |
| [08-i18n-fr-ar.md](08-i18n-fr-ar.md) | Français / arabe sur toutes les couches, RTL | Brouillon |
| [09-geocodage-tuiles.md](09-geocodage-tuiles.md) | Recherche d'adresses (Photon), tuiles de carte | Brouillon |
| [10-tests-qualite.md](10-tests-qualite.md) | Stratégie de test, trajets de référence | Brouillon |
| [11-deploiement-vps.md](11-deploiement-vps.md) | Passage du local au VPS, stores | Brouillon |
| [12-roadmap.md](12-roadmap.md) | Lots de travail et critères de fin | Brouillon |
| [13-design-ux.md](13-design-ux.md) | Design, composants, mouvement, budgets de fluidité | Brouillon |
| [99-questions-ouvertes.md](99-questions-ouvertes.md) | Spikes et questions non tranchées | Brouillon |

### Décisions (ADR)

| ADR | Décision | Statut |
|---|---|---|
| [ADR-001](adr/ADR-001-gateway-nginx.md) | nginx comme passerelle (pas Kong pour l'instant) | Proposé |
| [ADR-002](adr/ADR-002-spring-des-le-depart.md) | Backend Spring dès le MVP (écart avec le PRD) | Proposé |
| [ADR-003](adr/ADR-003-source-gtfs-yaml.md) | Données saisies en YAML, GTFS généré par script | Proposé |
| [ADR-004](adr/ADR-004-tuiles-pmtiles.md) | Tuiles vectorielles PMTiles auto-hébergées | Proposé |
| [ADR-005](adr/ADR-005-flutter-riverpod.md) | Flutter : Riverpod + go_router + dio | Proposé |
| [ADR-006](adr/ADR-006-regimes-horaires.md) | Régimes horaires calculés, dates explicites dans le GTFS | Proposé |
| [ADR-007](adr/ADR-007-base-de-saisie-postgis.md) | Base de saisie PostgreSQL/PostGIS + back-office Directus (remplace en partie ADR-003) | Accepté |

Modèle pour un nouvel ADR : [adr/000-modele.md](adr/000-modele.md).

## Journal

- **2026-10-13** — Création initiale des specs à partir du PRD v1.0 et de l'analyse de faisabilité.
- **2026-10-13** — Modèle de données complet (04, 04b, 04c remplacent l'ancien 04) : régimes horaires, grilles CSV, tarifs datés, alertes, provenance. App alignée sur les fonctionnalités de Citymapper sans « Go » (07), nouvelle spec design (13), API étendue (06), roadmap réestimée à 4–5 mois (12), ADR-006.
- **2026-10-13** — Lots 0 et 1 faits ; lot 2 : générateur, calendrier et banlieue sud réelle (affiche SNCFT hiver 2026-2027). Grilles « TOUS » avec codes de jours, versions d'affiche, corrections tracées, repli par direction. Spike S3 validé.
- **2026-10-13** — Lot 3 (API Spring Boot 4.1, 9 tests), lot 4 partiel (nginx HTTPS + limites, tuiles PMTiles Grand Tunis), lot 5 démarré : app Flutter « Thniya » avec accueil carte, recherche, résultats, fiche trajet, fiche ligne et horaires, fiche gare, lignes, réglages ; FR/AR et RTL ; heures de Tunis.
- **2026-10-13** — Réseau de test du Grand Tunis (métro M1–M6, TGM, bus B1, 3 louages ; positions OSM réelles, horaires et prix estimés). Itinéraires multimodaux réalistes (deuxième passe OTP, sections par mode emprunté, prix). Base de saisie PostgreSQL/PostGIS + back-office Directus (04d, ADR-007), aller-retour sans perte vérifié. API : index spatial, cache HTTP + nginx, cloison OTP ; 52 itinéraires/s en local. Trajets de référence de bout en bout : Boumhel → Lac, Hammam Lif plage → La Marsa.
- **2026-10-13** — Expérience mobile : fiche trajet à deux modes (vue d'ensemble / étape : la carte prend l'écran, cartes d'étape à glisser, tracés touchables), aperçu d'arrêt et repère par appui long sur l'accueil, fiche ligne carte + feuille avec départs dépliés, résultats ⇅ et tirer pour actualiser, caméra animée partout (07, 13).
