# Dépendances corrigées localement

## executor_lib 1.1.2

Utilisée par `vector_map_tiles` pour rendre les tuiles. En mode release, elle crée toujours des isolats,
ce qui est impossible sur le web : la carte restait vide dans la version web de l'app.

Correction (une ligne, `lib/src/executor.dart`) : sur le web (`kIsWeb`) ou avec `concurrency == 0`,
utiliser `QueueExecutor` (déjà fournie par la bibliothèque) au lieu de `PoolExecutor`.
Android et iOS gardent les isolats, **y compris en debug** (2026-10-14) : la bibliothèque d'origine décodait les
tuiles dans le fil principal en debug, et les tuiles de vue large de toute la Tunisie figeaient l'app plusieurs
minutes (image bloquée 167 s sur la ligne 5).

À supprimer quand une version publiée de `executor_lib` gérera le web.

## vector_map_tiles 8.0.0

Le cache de tuiles écrit sur disque (`dart:io` + `path_provider`), indisponible sur le web
(`MissingPluginException`, carte vide). Correction dans `lib/src/cache/storage_cache.dart` :
sur le web, cache en mémoire (400 entrées max). Android et iOS gardent le cache disque.

Mode raster (2026-10-14) : la couche passait `maxZoom: maximumZoom` (15) au `TileLayer` de flutter_map, qui
masque alors toute la couche au-delà de ce zoom. Le fond de carte disparaissait dès qu'on s'approchait d'une
rue (arrêt choisi sur une ligne, étapes d'un trajet, accueil). Correction dans `lib/src/grid/grid_layer.dart` :
seul `maxNativeZoom` est passé, et les tuiles du zoom 15 sont agrandies jusqu'au zoom 18.

## Remarque (pas un correctif)

Sur le web, `VectorTileLayer` doit utiliser `layerMode: VectorTileLayerMode.vector` : le mode raster
ne dessine aucune tuile. Réglé dans `lib/map/thniya_map.dart`.
