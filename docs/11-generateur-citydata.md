# Le générateur citydata

`citydata` est un outil en Python (dossier `data/scripts/citydata`). Il lit les données de `data/src`, les vérifie, et
produit les fichiers dont les services ont besoin.

```
data/src (YAML, CSV)  →  citydata lint  →  citydata build  →  data/build/gtfs.zip      (pour OTP)
                                                          →  data/build/app-meta.json (pour l'API)
                                                          →  data/build/report.md     (rapport de qualité)
```

## Comment le lancer

Le plus simple : dans le conteneur `tools`, depuis `infra/`. Rien à installer à part Docker.

```bash
docker compose --profile tasks run --rm tools <commande>
```

Ou directement avec Python 3.13, depuis la racine du dépôt :

```bash
pip install -r infra/tools/requirements.txt
```

```bash
PYTHONPATH=data/scripts python -m citydata <commande>
```

## Les commandes

### Au quotidien

| Commande | Effet |
|---|---|
| `lint` | Vérifie les données : format, références entre fichiers, règles métier, grilles horaires |
| `build` | Génère `gtfs.zip`, `app-meta.json` et `report.md` |
| `calendar-preview --network SNCFT` | Montre jour par jour quel régime horaire s'applique (période, type de jour) |

### Moteur d'itinéraires

| Commande | Effet |
|---|---|
| `otp-prepare` | Prépare `data/build/otp` : configuration, carte OSM et GTFS |
| `otp-check` | Vérifie dans OTP que chaque gare est accessible à pied |
| `golden` | Lance les trajets de référence de `data/golden-trips.yaml` contre OTP |

La construction du graphe elle-même n'est pas une commande `citydata`, mais un service :
`docker compose --profile tasks run --rm otp-build`.

### OpenStreetMap

| Commande | Effet |
|---|---|
| `osm-download` | Télécharge l'extrait OSM de la Tunisie (Geofabrik) |
| `osm-clip` | Découpe l'extrait du Grand Tunis |
| `osm-find --preset louage --name "Hammam"` | Cherche des gares, arrêts ou stations de louage dans OSM, avec leur position |
| `osm-lines` | Liste les lignes de transport décrites dans OSM, avec leurs arrêts dans l'ordre |

`osm-find` est très pratique pour trouver la position exacte d'une station avant de l'ajouter.

### Back-office (optionnel)

| Commande | Effet |
|---|---|
| `db-migrate` | Crée ou met à jour le schéma de la base |
| `db-import --replace` | Charge `data/src` dans la base |
| `db-export` | Écrit la base au format `data/src` |
| `db-check` | Vérifie que la base produit exactement le même GTFS que `data/src` |
| `backoffice-setup` | Configure Directus (libellés, dossiers, rôle de saisie) |
| `publish` | Base → validation → GTFS et `app-meta.json` |

Le script `infra/scripts/publish.sh` enchaîne `publish`, `otp-prepare`, la construction du graphe et le redémarrage
d'OTP.

### Import de la base de connaissances

`import-doc` régénère une partie de `data/src` à partir d'une base de connaissances privée (`doc/`), qui n'est pas
publiée. Vous n'en avez pas besoin pour contribuer : corrigez directement les fichiers de `data/src`.

## Comprendre un rapport de `lint`

```
ERREUR        REF_UNKNOWN            Parcours ALLER : arrêt inconnu LOU-BAB-ALIOUAX  [networks/louages/lines/…yaml]
AVERTISSEMENT FARE_MISSING           Ligne SNCFT-L5 : pas de tarif renseigné (prix affiché « inconnu »)
0 erreur(s), 214 avertissement(s)
```

- Une **ERREUR** bloque la génération : il faut la corriger.
- Un **AVERTISSEMENT** signale une donnée à vérifier (tarif manquant, vitesse surprenante…) sans bloquer.
- Le code (`REF_UNKNOWN`, `FARE_MISSING`…) et le fichier entre crochets disent où chercher.

## Les tests du générateur

```bash
docker compose --profile tasks run --rm --entrypoint python tools -m pytest data/scripts/tests -q
```

Ils couvrent les règles de génération et les erreurs de saisie. Ajoutez un test quand vous modifiez une règle.

Pour aller plus loin : [specs/04c-generation-gtfs.md](../specs/04c-generation-gtfs.md) et
[specs/04d-base-de-saisie.md](../specs/04d-base-de-saisie.md).
