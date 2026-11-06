# 04d — Base de saisie (PostgreSQL/PostGIS) et back-office

> Statut : Implémenté · Mise à jour : 2026-10-13 · Décision : [ADR-007](adr/ADR-007-base-de-saisie-postgis.md)

## 1. Rôle

La base de saisie est la **source de vérité** des données de transport : on y crée et corrige les gares, arrêts,
lignes, parcours, grilles horaires, fréquences, tarifs, calendriers et perturbations, depuis un **back-office web**
(Directus) au lieu d'éditer des fichiers YAML.

Elle reste **hors du chemin des requêtes voyageurs** : l'API ne la lit jamais. Une **publication** l'exporte au format
`data/src`, le générateur la valide et produit `gtfs.zip` + `app-meta.json`, OTP reconstruit son graphe. Ainsi :

- la charge des voyageurs (des milliers de requêtes par seconde) ne touche jamais la base ;
- une saisie en cours, incomplète ou fausse ne casse jamais l'app : seule une publication validée est servie ;
- toutes les règles de [04c](04c-generation-gtfs.md) (schémas, références, calendrier, cohérence des grilles)
  s'appliquent à l'identique, quelle que soit l'origine des données.

```
 Opérateur ──► Directus (back-office) ──► PostgreSQL/PostGIS ──publish──► data/build/src-db (format data/src)
                                                                             │ validation + génération (04c)
                                                                             ▼
                                         OTP (graphe) ◄── gtfs.zip      app-meta.json ──► API Spring ──► app
```

## 2. Schéma (`data/db/migrations/V*.sql`)

Règles de conception :

- **colonnes explicites** pour tout ce qui se saisit, se filtre ou se recherche (noms FR/AR, statut, couleurs,
  position, liens entre entités) ;
- colonne **`extra` (jsonb)** pour le reste : rien ne se perd à l'import ni à l'export, et le modèle peut s'enrichir
  sans migration ;
- **clé primaire sur une seule colonne** (exigence de Directus) : identifiant métier pour les entités (`TRN-HAMMAMLIF`,
  `SNCFT-BS`), `uid` technique pour les lignes de détail, avec contrainte d'unicité sur la clé métier ;
- **contraintes** alignées sur les schémas JSON (types de lieu, statuts, effets d'alerte, provenance obligatoire,
  coordonnées plausibles en Tunisie) : le back-office refuse une saisie invalide avant même la publication ;
- géométries **WGS 84 (SRID 4326)** avec index **GiST** ; recherche tolérante avec **pg_trgm + unaccent**
  (`place.search`, tenu à jour par déclencheur) ;
- `updated_at` mis à jour automatiquement ; l'historique complet des modifications (qui, quand, avant/après) est tenu
  par Directus (`directus_activity`, `directus_revisions`).

| Domaine | Tables | Notes |
|---|---|---|
| Référentiels | `feed`, `mode` | une ligne pour `feed` |
| Calendrier | `calendar_period`, `calendar_event`, `time_band_group` | `date_from = date_to` pour un jour |
| Réseaux et lieux | `network`, `place` (`geom` Point), `hub`, `hub_member` | `place.parent_id` = gare parente |
| Tarifs | `fare`, `fare_version`, `fare_pair` | millimes ; `od_pairs` = prix par couple d'arrêts |
| Lignes | `line`, `line_direction`, `pattern`, `pattern_stop` | `line.schedule` (jsonb) : versions de grilles ou régimes de fréquences |
| Grilles | `timetable_file` | CSV des affiches **stockés tels quels** (chemin = emplacement dans `data/src`) |
| Info voyageurs | `alert`, `coverage` (`geom` Polygon), `transfer` | |
| Exploitation | `publication`, `thniya_migration` | journal des publications, migrations appliquées |

Migrations : fichiers `V001__…sql`, `V002__…sql`… appliqués dans l'ordre par `citydata db-migrate` ; un fichier déjà
appliqué ne se modifie jamais (empreinte vérifiée) : on en ajoute un nouveau.

Volumes visés : Tunisie entière ≈ 30 000 lieux, 1 500 lignes, quelques milliers de grilles — quelques dizaines de Mo,
très loin des limites de PostgreSQL. Les index GiST et trigrammes gardent la saisie fluide (recherche d'un arrêt par
nom ou sur la carte en quelques millisecondes).

## 3. Commandes (`python -m citydata …`, conteneur `tools`)

| Commande | Effet |
|---|---|
| `db-migrate` | crée ou met à jour le schéma |
| `db-import [--replace]` | charge `data/src` (validé) dans la base ; refuse d'écraser des données sans `--replace` |
| `db-export [--out DIR]` | écrit la base au format `data/src` (défaut `data/build/src-db`) ; `--out data/src` pour un instantané versionné dans git |
| `db-check` | génère depuis `data/src` **et** depuis la base, et exige un `gtfs.zip` **identique à l'octet** et un `app-meta.json` identique |
| `publish [--by NOM]` | export → validation → GTFS + app-meta, avec une ligne dans `publication` (statut, version, erreurs, volumes, rapport) |
| `backoffice-setup` | configure Directus (voir §4) ; idempotent, à relancer après chaque migration |

Chaîne complète : `infra/scripts/publish.sh [--local] [--by NOM]` (publication, préparation OTP, graphe, redémarrage
d'OTP). L'API recharge `app-meta.json` d'elle-même et vide ses caches quand la version change.

La version des données (`dev-AAAA-MM-JJ-<empreinte>`) est une empreinte des sources : une base inchangée republiée
garde la même version, donc les caches restent valides.

## 4. Back-office (Directus)

- Accès local : <http://127.0.0.1:8055/admin> ; identifiants de l'administrateur dans `infra/.env`
  (`DIRECTUS_ADMIN_EMAIL`, `DIRECTUS_ADMIN_PASSWORD`, générés, jamais versionnés).
- Interface **en français**, menu en dossiers : *Réseau* (réseaux, lignes, grilles), *Lieux* (lieux et arrêts, pôles),
  *Tarifs*, *Calendrier* (périodes, événements, tranches horaires), *Info voyageurs* (perturbations, couverture,
  correspondances), *Paramètres* (modes, éditeur du flux, publications).
- Saisie guidée : listes déroulantes pour les valeurs fermées, **carte** pour placer un arrêt ou dessiner une zone,
  étiquettes pour les alias, sélecteur de couleur, éditeur JSON pour les horaires et la provenance, **listes
  imbriquées** ligne → directions / parcours → arrêts ordonnés (glisser-déposer), tarif → versions → prix par trajet.
- Listes par défaut avec les colonnes utiles (code, noms FR/AR, réseau, mode, statut, modifié le).
- Rôle **« Opérateur de saisie »** (politique « Saisie des données ») : création, modification, suppression sur les
  données ; lecture seule du journal des publications ; pas d'accès à l'administration.

Au premier lancement, Directus demande un **propriétaire de projet** et l'acceptation de sa licence : c'est une
décision du porteur du projet (voir [99](99-questions-ouvertes.md)) ; l'outil fonctionne en attendant.

## 5. Sauvegarde et instantanés

- Base : `pg_dump` quotidien sur le VPS ([11](11-deploiement-vps.md)), conservé 30 jours.
- Instantané lisible : `db-export --out data/src` puis commit — l'historique git reste un journal relisible des
  données, utile pour les revues et pour reconstruire une base (`db-import --replace`).

## Critères d'acceptation

- [x] `db-migrate` crée le schéma sur une base vide ; relancé, il ne fait rien.
- [x] `db-import` puis `db-check` : GTFS identique à l'octet et `app-meta.json` identique (réseau de test : 118 lieux,
      12 lignes, 653 voyages).
- [x] Une saisie invalide (type de lieu inconnu, coordonnées hors Tunisie, provenance sans source) est refusée par la base.
- [x] Directus affiche les collections en français, la carte des lieux et les listes imbriquées des lignes.
- [x] `publish` journalise chaque publication (statut, version, erreurs, avertissements, volumes, rapport).
- [ ] Publication déclenchée depuis le back-office (bouton « Publier ») — à faire avec le VPS (lot 7).
- [ ] Rôle « Relecteur » (valide avant publication) si plusieurs opérateurs saisissent.
