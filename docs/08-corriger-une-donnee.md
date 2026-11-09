# Corriger une donnée

Les corrections les plus courantes, en quelques lignes. Après chaque correction, validez depuis `infra/` :

```bash
docker compose --profile tasks run --rm tools lint
```

Vous ne savez pas modifier un fichier ? Ouvrez simplement un ticket **« Correction de données »** sur GitHub, avec
votre source : quelqu'un fera la modification.

## Trouver le bon fichier

Cherchez un nom ou un identifiant dans tout `data/src` :

```bash
grep -rn -i "hammam lif" data/src --include=*.yaml | head
```

## Déplacer un arrêt mal placé

Dans le fichier du lieu, corrigez `lat` et `lon`, puis mettez à jour la provenance :

```yaml
- id: BUS-PLACE-BARCELONE
  …
  lat: 36.79630            # avant : 36.79410
  lon: 10.18080
  provenance: { source: TERRAIN, ref: "Position vérifiée sur place", verified_at: "2026-11-09", by: votre-pseudo }
```

## Corriger le nom arabe d'un arrêt

```yaml
  name: { fr: "Hammam Lif", ar: "حمام الأنف" }
```

Vérifiez le nom arabe auprès d'une source fiable (panneau, affiche, site officiel) : il s'affiche tel quel dans l'app.

## Corriger un horaire de train ou de car

Les horaires à heures fixes sont dans des fichiers CSV :
`data/src/networks/<réseau>/timetables/<ligne>/<version>/<période>/<jours>/<direction>.csv`.

Exemple : `data/src/networks/sncft/timetables/banlieue-sud/HIVER-2026-2027/NORMAL/TOUS/NORD.csv`

```
stop_id,102,108,110,112
@jours,A,-,-,A
TRN-ERRIADH,04:30,05:00,05:30,05:45
TRN-BORJCEDRIA,04:35,05:05,05:35,05:50
```

- **La 1re ligne** donne les numéros de train : une colonne par train.
- **La ligne `@jours`** dit quels jours circule chaque train. Les codes sont définis dans le fichier de la ligne
  (`day_codes`) : ici `A` = sauf dimanches et fêtes, `-` = tous les jours.
- **Les lignes suivantes** donnent l'heure de passage de chaque train à chaque arrêt, du premier au dernier.

| Dans une case | Signification |
|---|---|
| `07:20` | Le train s'arrête à 07:20 |
| `07:20/07:25` | Arrivée à 07:20, départ à 07:25 |
| `\|` | Le train passe sans s'arrêter |
| (vide) | Le train ne passe pas par cet arrêt |

Pour corriger, changez simplement l'heure dans la bonne case. Si l'affiche officielle contient une coquille, notez-la
dans le fichier de la ligne, au bloc `corrections`, pour garder la trace :

```yaml
corrections:
  - { direction: NORD, train: "110", stop: TRN-MEGRINE, printed: "16:12", corrected: "06:12", reason: "Entre 06:09 et 06:14" }
```

## Corriger une fréquence (métro, bus, louage)

Dans le fichier de la ligne, au bloc `schedule`, changez `headway_min` (minutes entre deux départs) dans la bonne
tranche :

```yaml
POINTE_MATIN: { headway_min: 8, run_time: CHARGE }     # avant : 10
```

Les fréquences Transtu actuelles sont **estimées** : un relevé de terrain précis est une vraie amélioration. Passez
alors la provenance à `source: TERRAIN`.

## Corriger un prix

Les prix sont en **millimes** (`1700` = 1,700 DT). Quand un prix change, **ne remplacez pas l'ancien** : ajoutez une
nouvelle version, avec la date d'entrée en vigueur. L'app garde ainsi l'historique.

```yaml
versions:
  - valid_from: "2026-01-01"
    price_millimes: { PLEIN: 1000 }
  - valid_from: "2026-12-01"           # nouveau prix
    price_millimes: { PLEIN: 1200 }
```

## Désactiver une ligne ou un arrêt qui n'existe plus

Ne supprimez pas le fichier : passez `status: active` à `status: archived`. Une donnée `draft` est en cours de
vérification et n'est pas publiée.

| `status` | Signification |
|---|---|
| `draft` | En cours de saisie ou à vérifier, non publié |
| `active` | Publié dans l'app |
| `suspended` | Interrompu temporairement (travaux…), mais toujours visible |
| `archived` | N'existe plus |

## Les règles d'or

1. **Toujours indiquer la provenance** : source, référence précise, date.
2. **Jamais de données copiées** depuis Google Maps, Moovit ou une autre application : leurs conditions l'interdisent.
3. **Jamais d'images d'affiches** dans le dépôt : on recopie les faits (heures, prix), avec la source.
4. **Toujours valider** avec `lint` avant de proposer.
