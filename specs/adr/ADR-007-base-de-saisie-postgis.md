# ADR-007 — Base de saisie PostgreSQL/PostGIS avec back-office Directus

> Statut : Accepté · Date : 2026-10-13 · Remplace partiellement : [ADR-003](ADR-003-source-gtfs-yaml.md) (source de vérité)

## Contexte

Les données étaient saisies en YAML/CSV dans `data/src` ([ADR-003](ADR-003-source-gtfs-yaml.md)). C'est solide pour
un développeur, mais pas pour des opérateurs de saisie, ni pour la Tunisie entière (milliers d'arrêts, centaines de
lignes) : pas de carte pour placer un arrêt, pas de contrôle à la saisie, conflits de fichiers, pas de rôles.

Le porteur du projet demande un back-office de saisie sur PostgreSQL/PostGIS et une plateforme qui tient la charge.

## Options envisagées

1. **Garder le YAML** et ajouter un éditeur de fichiers : ne résout ni la carte, ni les rôles, ni la concurrence.
2. **Base + back-office développé sur mesure** (Spring + écrans Flutter web) : contrôle total, mais des semaines de
   travail pour des écrans de saisie standards (listes, formulaires, carte, droits, historique).
3. **Base PostgreSQL/PostGIS + Directus** : back-office généré à partir du schéma, en français, avec carte, rôles,
   historique des modifications et API ; notre schéma reste du SQL standard, sans dépendance à Directus.
4. **Lire la base directement depuis l'API** : couplerait la disponibilité de l'app à la base et à la saisie en cours.

## Décision

**Option 3**, avec le principe de l'option 4 rejeté :

- PostgreSQL 18 + PostGIS 3.6 devient la **source de vérité** ;
- Directus 12 sert de back-office ; il est **remplaçable** (le schéma est le nôtre, migrations SQL versionnées) ;
- la base est **exportée au format `data/src`** à chaque publication : le générateur, ses contrôles et ses tests
  restent l'unique chemin vers le GTFS ; `db-check` garantit que la base et les fichiers produisent le même GTFS ;
- l'API et OTP ne lisent que les produits publiés (`app-meta.json`, graphe) : la charge voyageurs ne touche jamais la
  base.

## Conséquences

- Nouveaux services Docker : `db`, `directus` (secrets dans `infra/.env`).
- Le YAML devient un **format d'échange et d'instantané** (revue git, restauration), plus la source principale.
- Licence Directus : gratuite pour les petites structures, mais soumise à conditions (acceptation demandée au premier
  lancement) — à valider par le porteur du projet ; en cas de refus, l'option 2 reste possible sans toucher au schéma.
- Sur le VPS, le back-office n'est pas exposé publiquement (accès restreint : VPN ou liste d'adresses IP).
