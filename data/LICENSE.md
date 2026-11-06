# Licence et sources des données

Les données de [`data/src`](src/) (arrêts, lignes, horaires, tarifs) sont mises à disposition sous
**[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/)**. Les droits sur les contenus
individuels de la base relèvent de la
[Database Contents License 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).

Cette licence s'applique parce que la base est en partie dérivée d'OpenStreetMap. Elle ne couvre que ce que le projet
peut licencier : **les droits des producteurs ci-dessous restent les leurs**.

Ce jeu de données n'est **ni officiel, ni approuvé** par les opérateurs ou le ministère cités. Il peut contenir des
erreurs : vérifiez auprès de l'opérateur avant un trajet important.

## Sources

Chaque entité indique sa source dans son champ `provenance` (origine, référence, date de vérification).

| Source | Producteur | Utilisation | Conditions |
|---|---|---|---|
| [data.transport.tn](https://data.transport.tn/fr/) | Ministère du Transport, Transtu, SNTRI, ATTT… | Référentiel national d'arrêts, itinéraires de bus | Licence nationale de données publiques ouvertes (décret n° 2021-3) : citer le producteur et la date. Jeu ATTT : règle ODbL retenue par prudence |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | © contributeurs d'OpenStreetMap | Positions de gares et de stations | ODbL 1.0 |
| [transtu.tn](https://www.transtu.tn) | Transtu | Premiers et derniers départs, fréquences (affiche hiver 2026-2027) | Aucune licence publiée : faits structurés, avec source et date |
| [sncft.com.tn](https://www.sncft.com.tn) | SNCFT | Horaires hiver 2026-2027 ; derniers tarifs connus | Aucune licence publiée : faits structurés, avec source et date |
| [sntri.com.tn](https://www.sntri.com.tn) | SNTRI | Horaires et tarifs des lignes interurbaines (site consulté le 2026-10-14) | Aucune licence publiée : faits structurés, avec source et date |

Vous êtes producteur de l'une de ces données et souhaitez une correction ou un retrait ?
Ouvrez un ticket dans ce dépôt : la demande sera traitée en priorité.

## Fiabilité

| Niveau | Données |
|---|---|
| Publié par l'opérateur | Horaires SNCFT et SNTRI, positions du référentiel national |
| **Estimé** (affiché comme tel dans l'app) | Horaires Transtu arrêt par arrêt (calculés à partir de la fréquence et de la distance), prix SNTRI vers les arrêts intermédiaires (au prorata) |
| Possiblement périmé | 3 tarifs SNCFT (derniers connus : 2021, 2023) ; tarif du bus de l'aéroport (presse) |
