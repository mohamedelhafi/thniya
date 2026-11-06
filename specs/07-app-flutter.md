# 07 — App Flutter : fonctionnalités et écrans

> Statut : Brouillon · Mise à jour : 2026-10-13 · Décision : [ADR-005](adr/ADR-005-flutter-riverpod.md) · Design : [13-design-ux.md](13-design-ux.md)

## 1. Ambition

L'app reprend **l'ergonomie, la logique et la fluidité de Citymapper**, adaptées au transport tunisien (louages, horaires de Ramadan, bilingue FR/AR), **sans la fonction « Go »** (guidage en direct).

> On reproduit l'expérience, pas la marque : pas de logo, de nom, d'icônes, d'illustrations ni de couleur de marque de Citymapper. Voir [13](13-design-ux.md) §1.

### Correspondance des fonctionnalités Citymapper

| Fonctionnalité Citymapper | Chez nous | V1 |
|---|---|---|
| Carte d'accueil + « Où allez-vous ? » | Identique | ✅ |
| « Get me home » / « Get me to work » | « Rentrer à la maison » / « Aller au travail » (lieux enregistrés en local) | ✅ |
| À proximité : arrêts et prochains départs par mode | Identique, avec onglet Louage | ✅ |
| Recherche avec récents, favoris, choix sur la carte | Identique + recherche en arabe et en derja | ✅ |
| Partir maintenant / partir à / arriver avant | Identique | ✅ |
| Résultats groupés (suggestions, par mode, marche…) | Identique, avec section Louage | ✅ |
| Fiche trajet : carte + étapes + autres départs | Identique, avec infos louage (quai, prix, « part quand plein ») | ✅ |
| Fiche ligne : schéma, direction, horaires | Identique + grille par régime (Ramadan, été…) | ✅ |
| Fiche arrêt / station : tableau des départs | Identique + destinations d'une station de louages | ✅ |
| État du réseau / perturbations | Alertes saisies dans les données (grève, travaux) | ✅ |
| Favoris (lieux, lignes, arrêts, trajets) | En local, sans compte | ✅ |
| Préférences (modes, moins de marche…) | Identique | ✅ |
| Partager un trajet | Partage texte (+ lien plus tard) | ✅ |
| **Go** : guidage, « descendez au prochain arrêt », partage d'heure d'arrivée | — | ❌ exclu |
| Temps réel des véhicules | — (pas de données) | ❌ |
| Vélos, trottinettes, VTC, taxi | Hors périmètre | ❌ |
| Cartes hors ligne | Plus tard | ❌ |
| Compte utilisateur | Lot 8, optionnel | ❌ |

## 2. Stack

| Besoin | Paquet |
|---|---|
| État et injection | `flutter_riverpod` + `riverpod_generator` |
| Navigation | `go_router` (routes imbriquées, liens profonds prêts) |
| HTTP | `dio` (intercepteurs : langue, `X-Request-Id`, 429/503, nouvelle tentative) |
| Modèles | Lecture JSON écrite à la main (`lib/core/models.dart`) — pas de génération de code en V1 |
| Carte | `flutter_map` 7 + `vector_map_tiles` 8 + `vector_map_tiles_pmtiles` ; styles Thniya générés par `tool/mapstyle` (clair/sombre × FR/AR) |
| Position | `geolocator` |
| Stockage local | `shared_preferences` en V1 (Maison, Travail, récents, langue, thème) ; `drift` quand les favoris grossiront |
| Préférences simples | `shared_preferences` (langue, préférences de trajet) |
| Traductions | `flutter_localizations` + `intl` + ARB (`gen-l10n`) |
| Catalogue de composants | `widgetbook` (voir [13](13-design-ux.md)) |
| Partage | `share_plus` |

## 3. Organisation du code

```
mobile/lib/
├── main.dart
├── app/              # MaterialApp.router, thème, routes, langue
├── design/           # jetons (couleurs, typo, espacements), composants partagés (13 §4)
├── core/             # client API, config, erreurs, formatage, horloge, stockage local
├── l10n/             # app_fr.arb, app_ar.arb
└── features/
    ├── home/         # carte d'accueil, à proximité, raccourcis
    ├── search/       # saisie départ/arrivée, options de départ
    ├── results/      # liste des itinéraires
    ├── trip/         # fiche trajet
    ├── line/         # fiche ligne + horaires
    ├── stop/         # fiche arrêt / station
    ├── lines/        # annuaire des lignes
    ├── alerts/       # état du réseau
    ├── saved/        # favoris, trajets enregistrés
    └── settings/     # langue, préférences, à propos des données
```

Chaque fonctionnalité : `data/` (API, modèles), `application/` (providers), `presentation/` (écrans, widgets).

## 4. Carte de navigation

```
Accueil (carte)
 ├── Recherche ──▶ Résultats ──▶ Fiche trajet ──▶ Fiche ligne / Fiche arrêt
 ├── À proximité ──▶ Fiche arrêt ──▶ Fiche ligne ──▶ Horaires
 ├── Lignes (annuaire) ──▶ Fiche ligne
 ├── État du réseau ──▶ Détail d'une alerte
 ├── Favoris
 └── Réglages
```

Toutes les fiches (trajet, ligne, arrêt) s'ouvrent **par-dessus la carte**, dans une feuille glissante (voir [13](13-design-ux.md) §5).

## 5. Écrans

### 5.1 Accueil

**Contenu**
- Carte plein écran, centrée sur l'utilisateur, avec **toutes les stations typées** et **aucune ligne dessinée au
  départ** (la carte reste lisible ; décision du porteur du projet, 2026-10-14) :
  - zoom < 10,5 : point coloré selon le mode ;
  - zoom 10,5 à 13 : petite pastille de la couleur du mode avec son icône (train, métro, bus, louage) ;
  - zoom 13 à 14,5 : pastille normale ;
  - zoom ≥ 14,5 : pastille + nom de l'arrêt.
- **Toucher une station** dessine en fondu **ses lignes seulement** (trait fin, liseré blanc) et estompe les stations
  qui ne sont pas sur ces lignes ; fermer l'aperçu efface les tracés.
  Couleurs de mode : train bleu, métro vert, bus rouge, louage ocre. Le filtre de mode de la feuille « À proximité » s'applique aussi à la carte.
- Carte de recherche flottante en haut : « Où allez-vous ? ».
- Juste dessous : raccourcis **Maison**, **Travail**, puis les lieux enregistrés (puces défilantes). Maison ou Travail non définis → appui = « Définir ».
- Feuille « À proximité » en bas, à 3 crans (réduite, moitié, plein écran) :
  - onglets par mode : Tout · Train · Métro · Bus · Louage ;
  - pour chaque arrêt proche : nom, distance à pied, lignes (pastilles) avec les 2 prochains départs ou « ~toutes les 10 min » ;
  - les stations de louages listent leurs destinations.
- Bandeau en haut de la feuille s'il y a une perturbation proche ou une période spéciale (« Horaires de Ramadan »).
- Bouton de recentrage sur ma position ; accès Lignes, État du réseau, Favoris, Réglages.

**Gestes (implémentés)**
- **Toucher un arrêt sur la carte** : la carte vole jusqu'à lui (au centre de la zone visible), sa pastille grossit,
  la feuille s'abaisse et un **aperçu** s'ouvre au-dessus : nom, quartier, 3 prochains départs par ligne, boutons
  « Y aller » (itinéraire depuis ma position) et « Départs » (fiche arrêt). On reste sur la carte : on peut toucher
  plusieurs arrêts à la suite.
- **Appui long sur la carte** : un repère « tombe » à cet endroit ; aperçu « Point sur la carte · Près de Place de
  Barcelone · 3 min à pied » (ou le nom de l'arrêt si l'on a appuyé dessus), boutons « Y aller » et « Partir d'ici ».
- Toucher la carte ailleurs, la croix, glisser l'aperçu vers le bas ou remonter la feuille : l'aperçu se ferme.
- **Explorer la carte** (glisser, zoomer) abaisse la feuille « À proximité » : la carte prend la place.
- Recentrage animé (vol) sur ma position.

**Critères**
- [ ] L'accueil est affiché en moins de 2 s au démarrage à froid (téléphone milieu de gamme).
- [ ] Sans permission de localisation : carte centrée sur Tunis, feuille « À proximité » remplacée par une invitation.
- [ ] Les arrêts se rechargent quand la carte bouge (anti-rebond 400 ms), sans clignotement.
- [ ] « Rentrer à la maison » lance directement la recherche Ma position → Maison.

### 5.2 Recherche

**Contenu**
- Deux champs **Départ** (par défaut « Ma position ») et **Arrivée**, bouton de permutation.
- Avant la saisie : Maison, Travail, favoris, recherches récentes, « Choisir sur la carte ».
- Pendant la saisie : résultats groupés **Arrêts et stations** puis **Lieux**, chacun avec icône, nom, zone (commune), distance.
- Sous les champs : **Partir maintenant ▾** → feuille avec Partir maintenant / Partir à / Arriver avant + sélecteur jour et heure.
- **Options ▾** : modes autorisés (Train, Métro, Bus, Louage), « Moins de marche », « Moins de correspondances », vitesse de marche (lente, normale, rapide). Mémorisées.

**Critères**
- [ ] Suggestions dès 2 caractères, anti-rebond 250 ms, réponse affichée < 300 ms en local.
- [ ] « hammem lif », « Hammam-Lif » et « حمام الأنف » trouvent la même gare.
- [ ] Sélection sur la carte : appui long ou carte avec viseur central + nom du lieu en direct.
- [ ] Le clavier ne masque jamais la liste des suggestions.

### 5.3 Résultats

**Contenu**
- En-tête compact : départ → arrivée (modifiable), heure de départ, options.
- Liste de **sections**, comme Citymapper :
  1. **Suggestions** : les 3 meilleurs, tous modes confondus ;
  2. **Train**, **Métro**, **Bus**, **Louage** : meilleurs trajets utilisant principalement ce mode ;
  3. **Moins de marche** ;
  4. **À pied** : durée et distance.
  Sections vides masquées.
- **Carte de trajet** (une par itinéraire) :
  - ligne 1 : chaîne de modes (icône marche + minutes, pastille de ligne colorée, louage avec destination) ;
  - à droite : **durée totale en grand** ;
  - ligne 2 : « Arrivée 08:24 · 1,800 DT · 6 min à pied » ;
  - ligne 3 : prochains départs du premier transport : « dans 4 min · 08:02 · 08:25 », ou « Louage ~toutes les 10 min » ;
  - pastille d'alerte si une perturbation touche le trajet ; « horaires estimés » si la confiance est faible.
- Boutons **Plus tôt** / **Plus tard** en bas de liste.
- Zone non couverte : bandeau « Pas encore de transports ici » + trajet à pied.

**Critères**
- [ ] Le squelette des cartes s'affiche immédiatement ; les vrais résultats en < 1,5 s (p95, local).
- [ ] Les comptes à rebours se mettent à jour chaque minute sans recharger la liste.
- [ ] Tri implicite par section ; aucun doublon d'itinéraire entre Suggestions et les sections de mode n'est affiché deux fois dans la même section.
- [ ] Glisser vers le bas rafraîchit.

### 5.4 Fiche trajet

**Deux modes (implémentés)**

| Mode | Carte | Bas de l'écran | Entrée / sortie |
|---|---|---|---|
| **Vue d'ensemble** | tout le trajet, cadré au-dessus de la feuille | feuille à 3 crans (24 %, 50 %, 94 %) avec le résumé et la frise | à l'ouverture ; bouton « Vue d'ensemble », glisser une carte d'étape vers le haut, ou retour arrière depuis le mode étape |
| **Étape** | ~70 % de l'écran ; la caméra **vole** jusqu'à l'étape ; les autres étapes s'estompent ; montée et descente étiquetées (« Montée · Bab Alioua », « Descente · Tunis Marine », touchables → fiche arrêt), arrêts intermédiaires en points | **cartes d'étape** à faire glisser (la suivante dépasse sur le bord) : « Montez à … / Descendez à … », arrêts, durée, prix, départs sélectionnables ou fréquence | toucher une étape de la frise, ou **toucher son tracé sur la carte** |

- **Boutons précédent / suivant** juste au-dessus des cartes, qui annoncent l'étape voisine (« ‹ 🚆 A »,
  « 🚶 20 min › », « 📍 Vous êtes arrivé ›») ; masqués aux extrémités. Au clavier (web) : flèches ← → (inversées en
  arabe) et Échap pour revenir à la vue d'ensemble.
- Étiquettes « Montée · … / Descente · … » : centrées sur l'arrêt mais **décalées pour rester dans l'écran**.
- Barre du haut en mode étape : « Étape 2 sur 7 » avec l'icône du mode ; les marches de moins de 2 min et 200 m
  (rejoindre le quai) ne sont pas comptées comme des étapes. Dernière carte : « Vous êtes arrivé ».
- Explorer la carte en vue d'ensemble abaisse la feuille ; bouton « tout le trajet » au-dessus de la feuille.
- Au retour à la vue d'ensemble, la dernière étape consultée reste surlignée dans la frise.
- Cadrage : toujours dans la **zone visible** (sous la barre du haut, au-dessus de la feuille ou des cartes, marges
  pour les étiquettes) ; mouvements de caméra animés avec léger dézoom pour les grands déplacements
  (`map/camera_motion.dart`).

**Contenu**
- Carte en haut avec le tracé coloré par segment (couleur de la ligne, pointillés pour la marche), cadrée sur le trajet.
- Feuille glissante avec :
  - **résumé** : durée, heure d'arrivée, prix total, nombre de correspondances ;
  - **frise verticale** (le cœur de l'écran) :
    - **Marche** : « Marcher 5 min (380 m) jusqu'à Gare de Hammam Lif » ; dépliable en indications rue par rue ;
    - **Transport à horaires** : pastille de ligne, direction (« vers Tunis Ville »), voie si connue, **puces des prochains départs** sélectionnables (07:40 · 08:02 · 08:25), « 7 arrêts » dépliable, « Descendre à Radès », durée, prix du segment ;
    - **Louage** : « Station de louages de Hammam Lif, quai Tunis », « Part quand il est plein · ~toutes les 10 min », durée « environ 25 min », prix par place ;
    - **Correspondance** : temps de marche et d'attente entre deux segments ;
  - **arrivée** : heure et nom de la destination ;
  - actions : **Enregistrer**, **Partager**, **Signaler une erreur**.
- Appui sur une pastille de ligne → fiche ligne ; appui sur un arrêt → fiche arrêt.
- Bandeaux d'alerte sur les segments concernés.

**Critères**
- [ ] Choisir un autre départ dans les puces recalcule les étapes suivantes et l'heure d'arrivée (< 1 s).
- [ ] La carte se recadre sur le segment touché dans la frise.
- [ ] Aucune heure exacte n'est affichée pour un louage.
- [ ] Transition fluide depuis la carte de résultat (élément partagé, voir [13](13-design-ux.md) §6).

### 5.5 Fiche ligne

**Mise en page (implémentée)** : la ligne est dessinée sur la carte (tracé de la direction choisie, un point par
arrêt) et la feuille à 3 crans porte l'en-tête, la direction, les onglets Arrêts / Horaires. **Toucher un arrêt**
(dans le schéma ou sur la carte) : la feuille s'abaisse, la carte vole jusqu'à l'arrêt (étiqueté), la ligne du
schéma se déplie sur place avec les prochains départs et « Voir l'arrêt » — plus de fenêtre modale. Changer de
direction recadre la carte ; l'arrêt choisi devient celui de l'onglet Horaires.

**Contenu**
- En-tête aux couleurs de la ligne : pastille, nom, réseau, mode.
- Sélecteur de **direction** (« vers Tunis Ville » / « vers Erriadh »).
- **Schéma de ligne** vertical : trait de la couleur de la ligne, un point par arrêt, branches si besoin, **pastilles de correspondance** (autres lignes) à droite de chaque arrêt.
- Bandeau de période si active (« Horaires de Ramadan ») et alertes de la ligne.
- Appui sur un arrêt → prochains passages de cette ligne à cet arrêt, puis lien vers la fiche arrêt.
- Onglet **Horaires** :
  - sélecteur de date : Aujourd'hui · Demain · Samedi · Dimanche · autre date (la bonne grille est choisie selon le régime de la date) ;
  - sélecteur d'arrêt (par défaut le premier) ;
  - **grille par heure** : une ligne par heure, les minutes à la suite (`07 | 10 25 40 55`) ;
  - renvois de notes (« a : ne circule pas les jours fériés ») ;
  - ligne à fréquence : « 06:00–09:00 : toutes les 10 min environ », premier et dernier départ.
- Bouton **Favori**.

**Critères**
- [ ] Le schéma est lisible jusqu'à 40 arrêts, défilement fluide.
- [ ] Changer de date montre la grille du bon régime (vérifié sur une date de Ramadan).
- [ ] Les départs passés de la journée sont grisés, le prochain est mis en avant.

### 5.6 Fiche arrêt / station

**Contenu**
- Nom, zone, mode, mini-carte, distance à pied.
- **Tableau des départs** groupé par ligne et direction : pastille, direction, 3 prochains départs (« 4 min », « 08:12 », « 08:30 ») ou fréquence.
- **Station de louages** : liste des destinations avec quai, prix, fréquence actuelle, horaires de service.
- Pôle d'échange : les autres stations du pôle et le temps de marche.
- Alertes de l'arrêt ; bouton **Favori** ; « Itinéraire vers ici ».

**Critères**
- [ ] Les départs se mettent à jour chaque minute.
- [ ] Un arrêt sans service aujourd'hui l'indique clairement (« Pas de départ aujourd'hui — prochain : lundi 05:40 »).

### 5.7 Lignes (annuaire)

- Onglets par mode, recherche par numéro ou nom, lignes favorites en tête.
- Chaque ligne : pastille, nom, terminus, état (normal, perturbée, suspendue).

### 5.8 État du réseau

- Liste des alertes actives et à venir, par réseau puis par ligne, avec gravité.
- Lignes sans alerte : « Service normal » (seulement pour les lignes que l'on couvre).

### 5.9 Favoris

- Lieux (Maison, Travail, autres avec icône et nom), arrêts, lignes, trajets enregistrés.
- Stockés en local (`drift`), réordonnables, supprimables par glissement.

### 5.10 Réglages

- Langue (Français / العربية), thème (clair, sombre, système).
- Préférences de trajet par défaut.
- **À propos des données** : version des données, date de mise à jour, sources par réseau, niveau de couverture.
- Signaler un problème, politique de confidentialité, licences (OSM).

## 6. États transverses

| Situation | Comportement |
|---|---|
| Chargement | Squelettes à la forme du contenu, jamais de spinner plein écran |
| Pas de réseau | Bandeau discret + dernier contenu connu (lignes et arrêts en cache local) |
| `429` | « Trop de demandes, réessayez dans un instant » + nouvelle tentative automatique |
| `503` | « Service momentanément indisponible » + bouton Réessayer |
| Données estimées | Libellé « environ » / icône discrète, explication au toucher |
| Ligne suspendue | Pastille barrée + bandeau |

## 7. Configuration et plateformes

- `--dart-define=API_BASE_URL=…`, `TILES_URL=…` ; flavors `dev` et `prod`.
- Android debug : confiance aux autorités utilisateur (certificat mkcert). Jamais en release.
- Localisation « pendant l'utilisation » uniquement, textes d'explication FR/AR.
- Cibles : Android 8+ (API 26), iOS 15+. Test obligatoire sur un Android d'entrée de gamme (3 Go de RAM).

## 8. Développement web et correctifs

- L'app tourne aussi en version web, servie par nginx sur `http://127.0.0.1:8090` (même origine que l'API et les tuiles) : `flutter build web --profile --pwa-strategy=none`.
- Sur le web, la carte utilise `VectorTileLayerMode.vector` ; sur mobile, `raster` (plus fluide).
- Deux dépendances corrigées localement (`mobile/third_party/README.md`) : `executor_lib` (pas d'isolats sur le web) et `vector_map_tiles` (cache mémoire sur le web ; en mode raster, fond de carte conservé au-delà du zoom 15).
- **Heures** : toujours affichées en heure de Tunis (UTC+1), quel que soit le fuseau du téléphone (`toTunis`, `tunisNow`).

## 8 quater. Erreurs, relances et nuit

- **Relances automatiques** (politique `retryPolicy`, passée à `ProviderScope`) : seulement pour les pannes
  passagères (pas de réseau, `503`), 2 fois au plus (0,7 s puis 2,8 s). Une réponse définitive (`NO_ROUTE`, `404`,
  `429`, erreur de requête) s'affiche **tout de suite**. Sans cette règle, Riverpod 3 relance indéfiniment et
  l'écran reste en squelette (bogue constaté le 2026-10-14 sur Borj Cédria → Lac à minuit).
- « Aucun itinéraire » : icône, explication (« Essayez une autre heure, ou un départ plus proche d'une gare »), pas
  de bouton « Réessayer » inutile.
- **La nuit** : bandeau « Plus de transport à cette heure-ci : voici les premiers départs, dès 04:35 » au-dessus des
  résultats (`notice = FIRST_DEPARTURES`).

## 8 ter. Résultats : gestes

- Bouton **⇅** dans l'en-tête : inverse départ et arrivée (le trajet retour en un geste).
- **Tirer vers le bas** : recalcule (nouveaux horaires en « partir maintenant »).
- Cartes de résultat qui apparaissent **en cascade** (fondu + glissement, 45 ms d'écart).
- Glisser au doigt, à la souris et au pavé tactile partout (version web incluse).

## 8 bis. Liens partageables et données estimées

- `/#/results?from=lat,lon,Nom&to=lat,lon,Nom&depart=2026-10-14T08:00` (ou `arrive=`) ouvre directement les
  résultats ; l'heure est l'heure murale de Tunis. Exemples de test :
  - Boumhel → Les Berges du Lac : `from=36.72442,10.30105,Boumhel&to=36.83509,10.23884,Les Berges du Lac`
  - Hammam Lif (plage) → La Marsa : `from=36.7330,10.3400,Hammam Lif plage&to=36.8791,10.3277,La Marsa`
- Ligne estimée (`line.estimated`) : « Horaires estimés » sur la carte de résultat et sur l'étape ; prix précédé de
  « ~ » quand il est estimé ; prix de chaque étape affiché à droite de la pastille.

## 9. Langues

Voir [08-i18n-fr-ar.md](08-i18n-fr-ar.md). Chaque écran est livré et validé **en FR et en AR** dès le premier jour.

## Questions ouvertes

- Nom de l'app et identité (couleur principale, icône) : nécessaire avant le lot 5.
- Liens profonds de partage (`https://<domaine>/trajet/…`) : demandent un domaine et une page web → lot 7.
