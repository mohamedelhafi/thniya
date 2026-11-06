# 09 — Géocodage et tuiles de carte

> Statut : Implémenté · Mise à jour : 2026-10-14 · Décision tuiles : [ADR-004](adr/ADR-004-tuiles-pmtiles.md)

## 1. Géocodage (recherche d'adresses et de lieux)

OTP ne sait pas transformer « Lycée de Hammam Lif » en coordonnées. Il faut un géocodeur.

### Choix : Photon, auto-hébergé — ✅ en place (2026-10-14)

- Basé sur OSM, conçu pour l'**autocomplétion** (contrairement à Nominatim).
- Le service public `nominatim.openstreetmap.org` est **exclu** : autocomplétion interdite, 1 requête/s maximum.
- **Photon 1.3.0** (image `infra/photon/Dockerfile`, jar officiel vérifié par empreinte SHA-256, Java 21), service
  `photon` du réseau interne : seule l'API l'interroge (port 2322 ouvert sur 127.0.0.1 en local pour le débogage).
- **Index** : export GraphHopper de l'Afrique du Nord (`photon-dump-northern-africa-1.0-latest.jsonl.zst`, 217 Mo),
  importé **pour la Tunisie seulement** (`-country-codes tn`) avec les noms `fr`, `ar` et `en` : 75 750 lieux et
  adresses, 2 min 30 d'import (`infra/scripts/photon-import.sh [--local]`, à relancer tous les 1 à 3 mois).
- Spike S6 (fait) : la recherche en arabe fonctionne (« حمام الأنف », « جامع الزيتونة », « مستشفى شارل نيكول ») ;
  en français, lieux et rues (« Hôpital Charles Nicolle », « rue de Marseille », « lac 2 ») ; numéros de rue rares.

### Recherche combinée (dans Spring)

1. Arrêts dont le nom FR/AR ou un **alias** correspond (prioritaires : c'est notre donnée), type `STOP`.
2. Résultats Photon (type `PLACE`), dans la langue de l'app, biaisés autour de la position de l'utilisateur
   (`lat`/`lon`) et limités à la Tunisie (`bbox`) ; ils gardent au moins la moitié des places quand il y en a.
3. Dédoublonnage : un arrêt ou une gare OSM à moins de 150 m d'un de nos arrêts est écarté (notre arrêt, avec ses
   lignes, est déjà proposé) ; deux lieux de même nom à moins de 300 m, ou dans le même quartier, n'en font qu'un.
4. Photon absent, lent (> 2 s) ou en panne : la recherche d'arrêts répond seule, sans erreur.

L'app affiche deux sections : « Arrêts et stations », puis « Adresses et lieux » ; un lieu choisi sert de départ ou
d'arrivée comme un arrêt (ses coordonnées).

### Limites connues

- Les numéros de rue sont rares dans OSM en Tunisie → privilégier les **lieux** (écoles, mosquées, gares, commerces, quartiers).
- Orthographes multiples (Hammam Lif / Hammam-Lif / Hammem Lif) → alias dans les fichiers `places/` et normalisation (minuscules, sans accents ni tirets) côté Spring.

## 2. Tuiles de carte

### Pourquoi pas les tuiles publiques OSM

La politique d'usage de `tile.openstreetmap.org` interdit l'usage intensif par une app en production. Toléré pour les tout premiers essais, **pas** au-delà.

### Choix : PMTiles vectorielles auto-hébergées — ✅ en place

- **Toute la Tunisie** (161 Mo, zoom 0–15, 211 257 tuiles) tirée du build Protomaps du 2026-10-12 : `docker compose --profile tasks run --rm pmtiles extract https://build.protomaps.com/20261012.pmtiles /tiles/tunisie.pmtiles --bbox=7.5,30.2,11.7,37.6 --maxzoom=15` (sous Git Bash : préfixer par `MSYS_NO_PATHCONV=1`). L'app lit `/tiles/tunisie.pmtiles` par défaut (`TILES_URL`). L'ancien extrait Grand Tunis (12 Mo) reste disponible pour les essais.
- Styles générés par `mobile/tool/mapstyle` (`@protomaps/basemaps`) : libellés FR ou AR, palette Thniya, police Readex Pro rendue par Flutter (lettres arabes liées).

- Un seul fichier `.pmtiles` de la Tunisie (extrait à partir d'un build Protomaps / OpenMapTiles), servi **en statique par nginx** (requêtes HTTP `Range`).
- Coût : un fichier sur le disque du VPS, pas de serveur de tuiles à maintenir.
- Côté Flutter : `flutter_map` + couche vectorielle compatible PMTiles (ex. `vector_map_tiles` + `vector_map_tiles_pmtiles`) → spike S7.
- Style : un style clair et sobre, avec les libellés en `name:fr` ou `name:ar` selon la langue de l'app.

### Solution de repli

Si le spike S7 échoue (performances, rendu de l'arabe) : fournisseur de tuiles raster avec offre gratuite (MapTiler, Stadia…) le temps du MVP, clé dans `--dart-define`.

### Mise à jour

- Fond de carte : régénéré tous les 3 à 6 mois (il change peu).
- Sans lien avec la reconstruction du graphe OTP.

## Critères d'acceptation

- [x] « hammam lif », « Hammam-Lif » et « حمام الأنف » trouvent la gare (arrêts), puis la ville et ses rues (Photon).
- [x] Une adresse ou un lieu OSM (« Hôpital Charles Nicolle », « جامع الزيتونة ») est trouvé et sert de destination.
- [ ] La recherche répond en moins de 300 ms en local.
- [ ] La carte s'affiche depuis notre propre nginx, sans appel à `tile.openstreetmap.org`.
- [ ] Les libellés de la carte apparaissent en arabe quand l'app est en arabe, et sont correctement liés (lettres attachées).
