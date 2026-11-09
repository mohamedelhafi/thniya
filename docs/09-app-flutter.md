# L'app Flutter

L'application est dans `mobile/`. Elle tourne sur Android, iOS et le web, à partir du même code.

## Les bibliothèques principales

| Bibliothèque | Rôle |
|---|---|
| [flutter_riverpod](https://riverpod.dev) | L'état de l'app (langue, thème, position, données de l'API) |
| [go_router](https://pub.dev/packages/go_router) | La navigation entre écrans |
| [dio](https://pub.dev/packages/dio) | Les appels HTTP à l'API |
| [flutter_map](https://pub.dev/packages/flutter_map) + `vector_map_tiles` | La carte, à partir du fichier PMTiles |
| [geolocator](https://pub.dev/packages/geolocator) | La position GPS |

## Les écrans et leurs adresses

| Adresse | Écran | Fichier |
|---|---|---|
| `/` | Accueil : carte et arrêts à proximité | `features/home/home_screen.dart` |
| `/search` | Recherche d'un départ ou d'une arrivée | `features/search/search_screen.dart` |
| `/results` | Les itinéraires proposés | `features/results/results_screen.dart` |
| `/trip` | Le détail d'un trajet, et le mode étape | `features/trip/trip_screen.dart` |
| `/line/:id` | La fiche d'une ligne | `features/line/line_screen.dart` |
| `/stop/:id` | La fiche d'un arrêt | `features/stop/stop_screen.dart` |
| `/lines` | Toutes les lignes | `features/lines/lines_screen.dart` |
| `/settings` | Langue, thème, version des données | `features/settings/settings_screen.dart` |

Les adresses sont déclarées dans `lib/app/app.dart`.

## Comment un écran obtient ses données

L'app ne contient pas les données du réseau : elle les demande à l'API. Le chemin est toujours le même :

1. `lib/core/api.dart` : une méthode par route de l'API (`meta()`, `nearby()`, `itineraries()`, `line()`…).
2. `lib/core/models.dart` : la conversion du JSON en objets Dart (`fromJson`).
3. `lib/core/state.dart` : les « providers » Riverpod partagés (`apiProvider`, `metaProvider`, `localeProvider`,
   `locationProvider`…).
4. L'écran lit un provider avec `ref.watch(...)` et se redessine quand la valeur change.

Exemple, afficher la version des données :

```dart
class DataVersion extends ConsumerWidget {
  const DataVersion({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meta = ref.watch(metaProvider);          // FutureProvider : chargement, erreur ou valeur
    return meta.when(
      data: (m) => Text(m.dataVersion),
      loading: () => const CircularProgressIndicator(),
      error: (e, _) => const Text('—'),
    );
  }
}
```

La langue choisie est envoyée à l'API (en-tête `Accept-Language`) : les noms d'arrêts arrivent déjà en français ou en
arabe.

## Ajouter un texte (français et arabe)

**Aucun texte en dur dans le code.** Tout passe par les fichiers de traduction.

1. Ajoutez la clé dans `lib/l10n/app_fr.arb` :

   ```json
   "fareUnknown": "Prix inconnu",
   ```

2. Ajoutez la même clé dans `lib/l10n/app_ar.arb` :

   ```json
   "fareUnknown": "السعر غير معروف",
   ```

3. Régénérez les classes de traduction (depuis `mobile/`) :

   ```bash
   flutter gen-l10n
   ```

4. Utilisez-la dans un écran :

   ```dart
   final l = L.of(context);
   Text(l.fareUnknown);
   ```

## L'arabe et la mise en page de droite à gauche

En arabe, tout l'écran s'inverse. Pour que ce soit automatique :

- utilisez `EdgeInsetsDirectional`, `PositionedDirectional` et `AlignmentDirectional` (avec `start` et `end`) plutôt
  que `left` et `right` ;
- les icônes de direction (flèches) doivent suivre le sens de lecture ;
- vérifiez chaque nouvel écran **dans les deux langues**.

## Le design

`lib/design/tokens.dart` regroupe les couleurs, les espacements (`Space.s`, `Space.m`…) et les durées d'animation.
Réutilisez-les plutôt que des valeurs en dur. Les composants communs (pastilles de ligne, prochains départs…) sont dans
`lib/design/components/`. Les règles de design : [specs/13-design-ux.md](../specs/13-design-ux.md).

## La carte

`lib/map/thniya_map.dart` affiche le fond de carte depuis `tunisie.pmtiles`, avec 4 styles (clair ou sombre, libellés
en français ou en arabe) dans `assets/map/`. Ces styles sont générés par `tool/mapstyle` : ne les modifiez pas à la main.

## Les pièges connus

- **Vérifiez en mode debug sur un émulateur ou un téléphone**, pas seulement sur le web : la version web compilée
  masque les erreurs de mise en page (bandes jaunes et noires « overflowed »).
- **Pas d'`IntrinsicHeight` autour d'un contenu animé** (`AnimatedSize`) : il produit des débordements pendant
  l'animation. Pour un trait vertical sur toute la hauteur d'une rangée, utilisez un `Stack` avec
  `PositionedDirectional(top: 0, bottom: 0)`.
- **Pour déplacer la carte à l'ouverture**, utilisez le paramètre `initialFit` de `ThniyaMap`, pas un déplacement dans
  `onReady` : ce dernier annulait le chargement des tuiles.

## Commandes utiles (depuis `mobile/`)

| Commande | Effet |
|---|---|
| `flutter pub get` | Installe les dépendances |
| `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8090` | Lance l'app sur l'émulateur |
| `flutter analyze` | Analyse le code |
| `flutter test` | Lance les tests |
| `flutter gen-l10n` | Régénère les traductions |
| `flutter build apk --release --dart-define=API_BASE_URL=…` | Construit un APK |

Pour aller plus loin : [specs/07-app-flutter.md](../specs/07-app-flutter.md) et
[specs/08-i18n-fr-ar.md](../specs/08-i18n-fr-ar.md).
