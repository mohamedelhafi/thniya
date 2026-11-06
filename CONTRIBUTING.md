# Contribuer à Thniya

Merci de votre aide ! Les contributions les plus utiles ne sont pas toujours du code : **une correction d'horaire, de
tarif ou d'arrêt vérifiée sur le terrain vaut de l'or**.

## Signaler une erreur de données

Ouvrez un ticket « Correction de données » en indiquant la ligne ou l'arrêt, ce qui est faux, et votre source
(photo d'affiche, relevé terrain, lien officiel).

## Modifier les données

1. Modifiez les fichiers de [`data/src`](data/src/) ; le format est décrit dans
   [`specs/04-donnees-modele.md`](specs/04-donnees-modele.md).
2. Renseignez `provenance` : source, référence, date de vérification.
3. Lancez la validation depuis `infra/` :

   ```bash
   docker compose --profile tasks run --rm tools lint
   ```

**À ne jamais faire :** extraire des données de Google Maps, Moovit ou d'une autre application (leurs conditions
l'interdisent), ou ajouter des images d'affiches : on ne publie que des faits structurés, avec leur source.

Les fichiers qui commencent par `# Généré par` viennent de `import-doc`, à partir d'une base de connaissances privée
qui n'est pas publiée ([`specs/04e-import-doc.md`](specs/04e-import-doc.md)). Corrigez-les directement : la correction
sera reportée dans cette base au moment de la revue.

## Modifier le code

- Une branche par sujet et une pull request courte, qui explique le pourquoi.
- **Mettez à jour la spec concernée dans le même commit** ([`specs/`](specs/README.md)).
- Une décision structurante fait l'objet d'un ADR ([`specs/adr/`](specs/adr/)).
- Une modification d'interface se vérifie **en mode debug sur un émulateur ou un téléphone Android**, en français et
  en arabe : le web compilé masque certaines erreurs de mise en page.
- Tout texte visible passe par les traductions ([`mobile/lib/l10n/`](mobile/lib/l10n/)), en français **et** en arabe.

## Tests à lancer

| Partie | Commande | Depuis |
|---|---|---|
| Générateur | `docker compose --profile tasks run --rm --entrypoint python tools -m pytest data/scripts/tests -q` | `infra/` |
| Données | `docker compose --profile tasks run --rm tools lint` | `infra/` |
| Trajets de référence (OTP démarré) | `docker compose --profile tasks run --rm tools golden` | `infra/` |
| API | `./mvnw test` | `backend/` |
| App | `flutter analyze` puis `flutter test` | `mobile/` |

## Licence des contributions

Sauf mention contraire, le code proposé est publié sous [Apache 2.0](LICENSE) et les données sous
[ODbL 1.0](data/LICENSE.md).
