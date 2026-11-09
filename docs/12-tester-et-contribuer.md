# Tester et contribuer

## Votre première contribution, pas à pas

1. **Forkez** le dépôt sur GitHub (bouton « Fork »), puis clonez votre copie :

   ```bash
   git clone https://github.com/<votre-compte>/thniya.git
   ```

2. **Créez une branche** qui dit ce que vous faites :

   ```bash
   git switch -c louage-bab-alioua-hammam-lif
   ```

3. **Faites votre modification**, puis lancez les tests concernés (tableau ci-dessous).
4. **Commitez**, avec un message clair qui dit pourquoi :

   ```bash
   git add data/src/networks/louages
   git commit -m "Louage Bab Alioua – Hammam Lif : relevé de terrain du 9 novembre"
   ```

5. **Poussez** et ouvrez une **pull request** sur GitHub :

   ```bash
   git push -u origin louage-bab-alioua-hammam-lif
   ```

   Remplissez la liste de vérification proposée. La CI lance automatiquement les tests.

Vous ne codez pas ? Les tickets **« Correction de données »** et **« Bug »** sont là pour vous.

## Quels tests lancer ?

| J'ai modifié… | Commande | Depuis |
|---|---|---|
| des données (`data/src`) | `docker compose --profile tasks run --rm tools lint` | `infra/` |
| le générateur (`data/scripts`) | `docker compose --profile tasks run --rm --entrypoint python tools -m pytest data/scripts/tests -q` | `infra/` |
| un comportement des trajets | `docker compose --profile tasks run --rm tools golden` (OTP démarré) | `infra/` |
| l'API (`backend`) | `./mvnw test` | `backend/` |
| l'app (`mobile`) | `flutter analyze` puis `flutter test` | `mobile/` |

## Ce que vérifie la CI

À chaque pull request, GitHub lance 3 jobs ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) :

| Job | Ce qu'il fait |
|---|---|
| Données et générateur | Tests du générateur et validation de `data/src` |
| API Spring Boot | `./mvnw test` |
| App Flutter | `flutter analyze` et `flutter test` |

## Les trajets de référence (« golden »)

`data/golden-trips.yaml` décrit des trajets réels et ce qu'on attend d'OTP. Exemple :

```yaml
- id: HAMMAMLIF-PLAGE-MARSA
  description: "Hammam Lif (plage) → La Marsa un mercredi 08:00 : train A puis TGM"
  from: { lat: 36.7330, lon: 10.3400, label: "Hammam Lif plage" }
  to: { lat: 36.8791, lon: 10.3277, label: "La Marsa" }
  departAt: "mercredi 08:00"
  api_expect:
    some_itinerary_uses_lines:
      - [SNCFT-BS, TRANSTU-TGM]
    max_duration_min: 160
```

Si vous ajoutez une ligne importante, ajoutez un trajet de référence qui l'utilise : il protégera votre ligne des
régressions futures.

## Les conventions du projet

- **Une branche et une pull request par sujet**, courte et facile à relire.
- **La spec concernée est mise à jour dans le même commit** que le code ([specs/README.md](../specs/README.md)).
- **Une décision importante** (nouvelle bibliothèque, changement d'architecture) fait l'objet d'un
  [ADR](../specs/adr/000-modele.md).
- **Les textes visibles** sont traduits en français **et** en arabe.
- **Une modification d'interface** se vérifie en debug sur Android, dans les deux langues.
- **Les données** ont toujours une provenance.

## Licence de vos contributions

Le code est sous [Apache 2.0](../LICENSE) et les données sous [ODbL 1.0](../data/LICENSE.md). En proposant une
contribution, vous acceptez qu'elle soit publiée sous ces licences. Les règles complètes :
[CONTRIBUTING.md](../CONTRIBUTING.md).
