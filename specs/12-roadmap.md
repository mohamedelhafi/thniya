# 12 — Feuille de route par lots

> Statut : Brouillon · Mise à jour : 2026-10-13

Chaque lot se termine par une démonstration et la mise à jour des specs concernées. Durées : travail à temps plein avec assistance IA, **hors collecte terrain** (qui avance en parallèle à partir du lot 2).

| Lot | Contenu | Durée | Specs |
|---|---|---|---|
| 0 | Dépôt et outillage | 1–2 j | 01, 02 |
| 1 | OTP + OSM : marche à pied | 2–3 j | 02, 05 |
| 2 | Modèle de données, générateur, calendrier, 1 train + 1 louage, spikes → **go / no-go** | 3–4 sem | 04, 04b, 04c, 05, 10 |
| 3 | API Spring v1 | 3 sem | 06, 08 |
| 4 | Gateway nginx + Photon + tuiles | 1 sem | 03, 09 |
| 5 | App Flutter type Citymapper, FR/AR | 9–11 sem | 07, 08, 13 |
| 6 | Données du couloir complet + calendriers de l'année | en continu | 04, 04b, 10 |
| 6 bis | Base de saisie PostgreSQL/PostGIS + back-office, montée en charge de l'API — ✅ fait (2026-10-13) | 1 sem | 04d, 06, 03 |
| 7 | VPS + stores | 2–3 sem | 11 |
| 8 | Comptes (PostgreSQL, login optionnel, synchronisation des favoris) | 3–4 sem | 06 |

**Jusqu'à la publication (lots 0 à 7) : environ 4 à 5 mois.** L'écart avec l'estimation du PRD vient des deux demandes ajoutées : un modèle de données complet (régimes, grilles, tarifs, alertes) et une app au niveau de finition de Citymapper.

## Lot 0 — Dépôt et outillage

- [x] `git init`, `.gitignore` (data/osm, data/build, certs, .env), `.gitattributes` (LF)
- [x] Arborescence de [01-architecture.md](01-architecture.md) §6
- [x] `infra/compose.yml`, `infra/.env.example`, image `tools`
- [ ] Extension YAML de VS Code configurée pour les schémas
- **Fini quand :** `docker compose --profile tasks run --rm tools --help` fonctionne.

## Lot 1 — OTP + OSM

- [x] Téléchargement et découpe de l'extrait Grand Tunis
- [x] Configuration OTP minimale, build et service
- [x] Itinéraire à pied via GraphQL et le client de débogage
- [x] Mesures mémoire / durée du build (spike S8, Grand Tunis puis Tunisie entière le 2026-10-14)
- **Fini quand :** un itinéraire à pied Hammam Lif → Tunis s'affiche dans le client de débogage d'OTP.

## Lot 2 — Modèle de données et preuve de concept (go / no-go)

Étape A — Socle du modèle
- [x] Schémas JSON de tous les types de fichiers — [ ] gabarits ([04](04-donnees-modele.md) §15)
- [x] `lint` : schémas, références, règles métier bloquantes
- [x] Calendrier : années, périodes, types de jour, tranches, résolution, replis + `calendar-preview` ([04b](04b-calendriers-regimes.md))

Étape B — Génération
- [x] Lecture des grilles CSV (passages sans arrêt, après minuit, renvois, `@jours`, `@days`) et héritage
- [x] Expansion des fréquences par tranche avec `run_times`
- [ ] Tarifs (`flat`, `od_matrix`, `od_pairs`) — [x] perturbations NO_SERVICE — [ ] correspondances
- [x] Écriture GTFS + `app-meta.json` + rapport ([04c](04c-generation-gtfs.md))
- [x] Tests pytest de chaque règle (20 tests)

Étape C — Données réelles et spikes
- [x] Ligne de train banlieue sud : grille officielle hiver 2026-2027 (119 trains, 11 coquilles corrigées)
- [ ] Un louage du couloir avec tranches, durées et prix (en attente de données terrain)
- [x] Validation MobilityData sans erreur
- [ ] Spikes S1, S2, S4, S5, S9 (louage) — [x] S3
- [x] Trajets de référence, dont un en période de Ramadan (6/6)
- **Fini quand :** OTP propose le train le matin et le louage l'après-midi, et une date de Ramadan utilise bien les horaires de Ramadan. **Sinon, on revoit la modélisation avant d'écrire l'API.**

## Lot 3 — API Spring v1 — ✅ fait (2026-10-13)

- [ ] Squelette (Maven wrapper, Dockerfile, profils `local`/`prod`), chargement de `app-meta.json`
- [ ] `itineraries` avec sections parallèles (spike S10) et enrichissement
- [ ] `nearby`, `stops/in-bbox`, `stops/{id}`
- [ ] `lines`, `lines/{id}`, `timetable`, départs d'une ligne à un arrêt
- [ ] Autres départs d'un segment (spike S11)
- [ ] `alerts`, `meta`, `feedback`
- [ ] FR/AR, cache, erreurs `ProblemDetail`, OpenAPI
- [ ] Trajets de référence exécutés via l'API
- **Fini quand :** tous les critères de [06](06-api-backend.md) sont cochés sur les vraies données.

## Lot 4 — Gateway, géocodage, tuiles — nginx ✅, tuiles ✅, Photon à faire

- [ ] nginx : HTTPS mkcert, limites, en-têtes, routage, logs JSON
- [x] Photon (spike S6) + `geocode` combiné avec alias (2026-10-14 : index Tunisie, section « Adresses et lieux » dans l'app)
- [ ] Fichier PMTiles servi par nginx
- **Fini quand :** les critères de [03](03-gateway-securite.md) et [09](09-geocodage-tuiles.md) sont cochés.

## Lot 5 — App Flutter type Citymapper — en cours : 8 écrans en place (FR/AR, clair/sombre)

| Étape | Contenu | Durée |
|---|---|---|
| 5.1 | Socle : thème et jetons, i18n FR/AR + RTL, client API, stockage `drift`, `widgetbook` | 1 sem |
| 5.2 | Composants du design system ([13](13-design-ux.md) §4) avec tests golden | 1,5 sem |
| 5.3 | `MapSheetScaffold` + carte PMTiles (spike S7) + arrêts sur la carte | 1 sem |
| 5.4 | **Résultats** + **Fiche trajet** (le cœur), transitions | 2 sem |
| 5.5 | Recherche (récents, favoris, carte, options de départ) | 1 sem |
| 5.6 | Accueil (raccourcis, À proximité), Fiche arrêt | 1 sem |
| 5.7 | Fiche ligne (schéma, horaires par régime), annuaire, état du réseau | 1,5 sem |
| 5.8 | Favoris, réglages, finitions, budgets de performance sur Android d'entrée de gamme | 1 sem |

- **Fini quand :** un trajet réel du couloir est fait de bout en bout avec l'app, en FR et en AR, et les budgets de [13](13-design-ux.md) §7 sont tenus.

## Lot 6 — Couloir complet (en parallèle à partir du lot 2)

- [x] Import de `doc/` (2026-10-14, [04e](04e-import-doc.md)) : métro et TGM officiels, SNCFT complète (RFR D et E, Sahel, grandes lignes), 114 lignes de bus Transtu, 84 lignes SNTRI, stations de louages, pôles d'échange ; OTP et fond de carte sur toute la Tunisie
- [x] Réseau de test du Grand Tunis : métro M1–M6 et TGM (stations OSM réelles), bus B1 et 3 louages de test,
      horaires et prix estimés, signalés « estimés » dans l'app — remplacé par l'import de `doc/`, puis données de
      test supprimées (2026-10-14 : louages, zone de couverture, commande `seed-network`)
- [x] Trajets multimodaux de bout en bout : Boumhel → Les Berges du Lac (louage → train A → M6 → bus),
      Hammam Lif plage → La Marsa (train A → M6 → TGM, ou louage → M6 → TGM)
- [ ] Toutes les lignes de train, bus et louage du couloir Hammam Lif ↔ Tunis
- [ ] Calendrier de l'année : fériés, été, Ramadan, Aïd (dates estimées puis confirmées)
- [ ] Prix vérifiés, provenance renseignée partout
- [ ] Un trajet de référence par ligne ; rapport de qualité sans avertissement grave

## Lot 6 bis — Base de saisie et montée en charge — ✅ fait (2026-10-13)

- [x] PostgreSQL 18 / PostGIS 3.6 : schéma, contraintes, migrations versionnées ([04d](04d-base-de-saisie.md))
- [x] Import, export, aller-retour vérifié (GTFS identique à l'octet), publication journalisée
- [x] Back-office Directus en français : carte des lieux, listes imbriquées, rôle « Opérateur de saisie »
- [x] API : index spatial (STRtree) et index de recherche, cache HTTP + nginx, cloison OTP ; 52 itinéraires/s en local
- [ ] Bouton « Publier » dans le back-office (avec le VPS)
- [ ] Licence Directus acceptée par le porteur du projet ([99](99-questions-ouvertes.md))

## Lot 7 — VPS et stores

Voir [11-deploiement-vps.md](11-deploiement-vps.md). Régénération hebdomadaire des données planifiée. Démarrer le **test fermé Google Play (14 jours)** dès que l'app est stable.

## Lot 8 — Comptes

PostgreSQL + Flyway, login optionnel, synchronisation des favoris, signalements en base. Spec détaillée à écrire le moment venu.
