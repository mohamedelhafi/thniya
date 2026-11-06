# 13 — Design, interactions et fluidité

> Statut : Brouillon · Mise à jour : 2026-10-13

## 1. Intention

Retrouver ce qui fait Citymapper :

- **la carte au centre**, les informations dans des feuilles qui glissent par-dessus ;
- **une lecture immédiate** : durée en grand, chaîne de modes, pastilles de lignes colorées ;
- **des couleurs franches**, des formes simples, beaucoup d'air ;
- **aucune attente perçue** : squelettes, transitions continues, réponses instantanées au toucher ;
- un ton **direct et un peu complice** dans les textes.

### Ce qu'on ne copie pas

Logo, nom, mascotte, icônes et illustrations de Citymapper, sa couleur de marque et ses textes. Copier l'**identité** exposerait à un rejet des stores (application « imitation ») et à un litige ; copier l'**ergonomie** (dispositions, enchaînements, principes d'interaction) est la pratique normale du secteur. On crée donc notre propre identité, avec une touche tunisienne.

## 2. Identité (proposition à valider)

| Jeton | Clair | Sombre | Usage |
|---|---|---|---|
| `brand` | `#0E7C86` (bleu-vert « Sidi Bou Saïd ») | `#3FB8C2` | Boutons principaux, sélection, ma position |
| `accent` | `#E8A317` (ocre) | `#F2BE4B` | Louages, mises en avant |
| `surface` | `#FFFFFF` | `#14181B` | Feuilles, cartes |
| `background` | `#F3F5F6` | `#0B0E10` | Fond derrière les cartes |
| `textPrimary` | `#111417` | `#F2F4F5` | |
| `textSecondary` | `#5C6670` | `#9AA4AD` | |
| `success` / `warning` / `danger` | `#1F9D55` / `#E8A317` / `#D93636` | variantes claires | Alertes, états |
| `walk` | `#8A949C` | `#8A949C` | Segments à pied (pointillés) |

- **Couleurs des lignes** : viennent des données (`color`, `text_color`). Contraste ≥ 4,5:1 vérifié par le générateur.
- **Couleurs des modes** (quand une ligne n'a pas de couleur) : définies dans `modes.yaml`.

### Typographie

- Une famille qui couvre **le latin et l'arabe** avec le même esprit géométrique et arrondi. Candidates à tester : **Readex Pro**, IBM Plex Sans + IBM Plex Sans Arabic, Noto Sans + Noto Sans Arabic.
- **Chiffres tabulaires** pour toutes les heures et durées (pas de saut quand le compte à rebours change).

| Style | Taille / graisse | Usage |
|---|---|---|
| `display` | 34 / Bold | Durée totale sur la fiche trajet |
| `durationCard` | 26 / Bold | Durée sur une carte de résultat |
| `title` | 20 / SemiBold | Titres d'écran et de feuille |
| `body` | 16 / Regular | Texte courant |
| `label` | 14 / Medium | Pastilles, métadonnées |
| `caption` | 12 / Regular | Notes, sources |

### Espacements et formes

- Grille de 4 : `4, 8, 12, 16, 24, 32`.
- Rayons : pastilles 6, cartes 16, feuilles 24 (coins hauts).
- Ombres très légères ; en mode sombre, on remplace les ombres par des surfaces plus claires.
- Zones tactiles ≥ 48 × 48.

## 3. Iconographie

- Jeu d'icônes **maison** : un trait, coins arrondis, même épaisseur : train, métro, bus, louage (minibus reconnaissable), marche, correspondance, station, alerte, Maison, Travail.
- L'icône de louage est **la signature visuelle** de l'app : elle doit être soignée et reconnaissable.
- Format vectoriel (SVG converti en police d'icônes ou `flutter_svg`), versions remplie et contour.

### Pastilles de ligne : abréviations et icônes

Une pastille = **icône du mode + code court**, sur la couleur de la ligne. Le code doit se lire en un coup d'œil et
correspondre à ce qui est écrit sur le quai ou le véhicule.

| Mode | Icône (Material Symbols) | Code | Exemple |
|---|---|---|---|
| Train (SNCFT, TGM) | `train` | **T** (= train), puis **en petit** la lettre de la ligne pour les distinguer | **T**ᴬ (banlieue sud Tunis – Erriadh), **T**ᴳᴹ (TGM) |
| Métro léger | `tram` | **M** + numéro | M1 … M6 |
| Bus | `directions_bus` | numéro Transtu | 20, 28… (B1 = ligne de test) |
| Louage | `airport_shuttle` | **destination du sens emprunté**, dans la langue de l'usager | Bab Alioua / باب عليوة |
| Marche | `directions_walk` | minutes | 7 |

Le nom complet de la ligne (« Banlieue Sud », « Louage Boumhel ⇄ Bab Alioua ») apparaît dans la fiche trajet et la
fiche ligne, jamais dans la pastille.

Trains (décision du porteur du projet, 2026-10-14) : le « T » suffit à dire « train » ; le complément en petit
(`public_code` de la ligne, sans son « T » initial) ne sert qu'à distinguer deux lignes. Rendu : `LineCodeText`
(`lineCodeParts`), partout où un code de ligne est affiché ; en texte simple (partage, lecteur d'écran) : « T A ».

## 4. Composants (catalogue `widgetbook`)

Chaque composant existe dans le catalogue, en clair et en sombre, en FR et en AR, avec ses tests « golden » (comparaison d'images).

| Composant | Rôle |
|---|---|
| `LineBadge` | Pastille de ligne : couleur, code public, variante compacte ; louage avec destination |
| `ModeIcon` | Icône de mode, tailles 16/20/24 |
| `ModeChain` | Suite marche → pastilles → … avec minutes de marche ; se replie (« +2 ») si trop longue |
| `DurationText` | « 49 min », « 1 h 15 » ; chiffres tabulaires ; « ~ » si estimé |
| `DepartureChips` | Puces de prochains départs, sélectionnables |
| `Countdown` | « dans 4 min » qui se met à jour seul, puis « maintenant » |
| `FrequencyLabel` | « ~toutes les 10 min » |
| `PriceText` | Millimes → « 1,800 DT » / « 1,800 د.ت » |
| `ItineraryCard` | Carte de résultat complète |
| `TimelineLeg` | Segment de la frise : marche, transport, louage, correspondance |
| `StopRow` | Arrêt avec pastilles de lignes et prochains départs |
| `LineDiagram` | Schéma vertical de ligne avec branches et correspondances |
| `TimetableGrid` | Grille heures / minutes |
| `AlertBanner` | Bandeau d'alerte (info, attention, grave) |
| `PeriodBanner` | « Horaires de Ramadan en vigueur » |
| `SearchField`, `PlaceRow` | Recherche et suggestions |
| `MapSheetScaffold` | Carte + feuille glissante à crans (base de tous les écrans principaux) |
| `SkeletonBlock` | Squelette animé |
| `EmptyState` | Écran vide illustré (texte + action) |

## 5. Mise en page : la carte et les feuilles

- **Un seul `MapSheetScaffold`** pour Accueil, Résultats, Fiche trajet, Fiche ligne, Fiche arrêt : la carte reste en place, seules la feuille et les couches de la carte changent. C'est ce qui donne l'impression de continuité.
- Feuille à **3 crans** : réduite (~ 15 %), moitié (~ 50 %), plein écran (~ 92 %).
- La carte **réagit à la feuille** : quand la feuille monte, le cadrage de la carte tient compte de l'espace visible.
- En plein écran, la carte disparaît au profit d'un en-tête compact ; un geste vers le bas la fait revenir.
- **RTL** : la mise en page des feuilles est en miroir, la carte non ([08](08-i18n-fr-ar.md)).

### Gestes et réactions de la carte (implémentés)

| Geste | Où | Réaction |
|---|---|---|
| Toucher une étape (frise) ou son tracé (carte) | Fiche trajet | mode étape : la feuille s'efface, la carte vole jusqu'à l'étape, les autres s'estompent |
| Glisser les cartes d'étape à gauche / à droite, ou boutons « ‹ A » / « TGM › », ou flèches du clavier | Fiche trajet | étape précédente / suivante, la carte suit |
| Glisser une carte d'étape vers le haut, « Vue d'ensemble », retour | Fiche trajet | retour à la frise, tout le trajet recadré |
| Toucher un arrêt | Accueil, fiche ligne | la carte vole jusqu'à l'arrêt, aperçu des départs (accueil) ou ligne du schéma dépliée (fiche ligne) |
| Appui long | Accueil | repère + « Y aller » / « Partir d'ici » |
| Glisser / zoomer la carte | Accueil, trajet, ligne | la feuille s'abaisse (la carte prend la place) ; l'animation de caméra en cours s'arrête |
| ⇅ | Résultats | inverser départ et arrivée |
| Tirer vers le bas | Résultats, fiche arrêt | actualiser |

Règles :
- **Cadrer dans la zone visible**, jamais sur l'écran entier : marges = barre du haut + feuille (ou cartes d'étape)
  + place des étiquettes et des boutons flottants.
- **Animer la caméra** (400 ms, `easeInOutCubic`, petit dézoom à mi-course au-delà d'un écran de distance) ; un
  geste de l'usager l'interrompt aussitôt.
- Retour haptique léger à chaque sélection (étape, arrêt, filtre), plus marqué pour l'appui long.
- La taille de la feuille est suivie sans reconstruire l'écran (pas de saccade de la carte pendant le glisser).

## 6. Mouvement

| Interaction | Animation | Durée |
|---|---|---|
| Changement de cran de la feuille | Ressort, sans rebond excessif | ~ 300 ms |
| Résultat → fiche trajet | Élément partagé : la carte de résultat devient l'en-tête de la fiche ; le tracé se dessine sur la carte | 350 ms |
| Recadrage de la carte | Mouvement de caméra animé (`fitBounds`) | 400 ms |
| Arrivée des résultats | Fondu + léger glissement, décalé de 30 ms par carte | 200 ms |
| Puce de départ sélectionnée | Changement d'état + mise à jour des heures en fondu croisé | 150 ms |
| Compte à rebours | Changement de chiffre en fondu vertical | 200 ms |
| Appui | Retour visuel immédiat (< 100 ms) + **retour haptique léger** sur les sélections importantes |

- Courbes : `easeOutCubic` pour les entrées, `easeInOutCubic` pour les changements d'état.
- **Réduction des animations** respectée (réglage d'accessibilité du système) : on passe en fondus simples.

## 7. Fluidité : budgets de performance

| Mesure | Objectif | Comment on le tient |
|---|---|---|
| Démarrage à froid → carte visible | < 2 s (Android milieu de gamme) | Pas d'appel bloquant au démarrage, dernier état en cache |
| Image | 60 i/s constants (120 sur écrans compatibles) | Profilage en mode `profile`, pas de reconstructions inutiles (Riverpod `select`) |
| Saisie → suggestions | < 300 ms | Anti-rebond 250 ms, cache Spring, requêtes annulées si obsolètes |
| Recherche → premiers résultats | < 1,5 s p95 | Squelettes immédiats, requêtes OTP parallèles côté Spring |
| Résultat → fiche trajet | Instantané | Les données de la fiche sont déjà dans la réponse des résultats |
| Fiche ligne | < 500 ms | Lignes et schémas mis en cache local (`drift`), rafraîchis en arrière-plan |
| Taille de l'app | < 30 Mo | Polices limitées aux graisses utilisées, icônes vectorielles |

Techniques :
- **Préchargement** : à l'ouverture des résultats, précharger les fiches lignes des premiers itinéraires.
- **Annulation** des requêtes devenues inutiles (saisie, déplacement de carte).
- **Optimisme** : afficher ce qu'on sait déjà (nom de la ligne, couleur) avant la réponse complète.
- **Couches carte** : arrêts en une seule couche de marqueurs regroupés, pas un widget par arrêt.
- **Carte en vue large (toute la Tunisie)** : l'API ne renvoie que les gares et stations sous le zoom 14 (les plus
  importantes d'abord, 500 au plus) ; le style ne dessine l'occupation du sol, les zones et les limites administratives
  qu'à partir du zoom 11, les petites routes du zoom 12, les bâtiments du zoom 14 (`tool/mapstyle`) ; le décodage des
  tuiles se fait dans des isolats, y compris en debug. Le cache de tuiles est propre à chaque fichier `.pmtiles` et à chaque style (langue, thème).
- **Cadrage initial** : une carte qui doit montrer une ligne ou un trajet naît cadrée (`ThniyaMap.initialFit`), sans
  déplacement dans `onReady` : un déplacement juste après la création annulait les tuiles de la première vue et le fond
  de carte n'apparaissait qu'au premier geste (fiches ligne et trajet vides).
- **Zoom rapproché** : au-delà du zoom 15 (dernier zoom du fichier PMTiles), les tuiles du zoom 15 sont agrandies
  jusqu'au zoom 18. Corrigé le 2026-10-14 dans `vector_map_tiles` (`mobile/third_party/README.md`) : la couche
  disparaissait au-delà du zoom 15 (arrêt choisi sur une ligne, étape d'un trajet, accueil au niveau de la rue).
- Mesuré le 2026-10-14 (émulateur x86_64, release, cache vidé) : fiche de la banlieue sud et de la ligne 5 (toute la
  Tunisie) avec fond de carte en moins de 10 s sans geste ; réponse au toucher ≈ 0,5 s au premier lancement. En debug,
  les vues larges restent lentes (code non optimisé). Attention : dans `adb logcat`, `app_time_stats max=…` compte
  aussi les pauses sans image (app au repos) ; un gel se vérifie par le temps de réponse à un toucher.
- Rejeté : tuiles de 512 px (`TileOffset.mapbox`) : 4 fois moins de tuiles, mais chaque tuile est dessinée d'un bloc
  dans le fil principal (plus de 5 s → « l'application ne répond pas ») et l'échelle des libellés change.
- Test de référence sur un **Android d'entrée de gamme (3 Go de RAM)** avant chaque version.

## 8. Ton et textes

- Phrases courtes, à l'impératif, sans jargon : « Marchez 5 min jusqu'à… », « Descendez à Radès ».
- Honnêteté sur les estimations : « environ », « part quand il est plein ».
- Une pointe de complicité tunisienne est bienvenue dans les écrans vides et les messages d'erreur (à écrire dans les deux langues, sans traduction littérale).

## 9. Accessibilité

- Contraste AA partout ; tailles de police dynamiques jusqu'à 200 % sans casse.
- Étiquettes de lecteur d'écran sur toutes les pastilles et icônes (« Ligne A, direction Tunis Ville, dans 4 minutes »).
- Information jamais portée par la couleur seule (icône ou texte en plus).

## Critères d'acceptation

- [ ] Tous les composants du §4 sont dans `widgetbook`, en clair/sombre et FR/AR.
- [ ] Tests golden des composants en FR et en AR.
- [ ] Les budgets du §7 sont mesurés et respectés sur un Android d'entrée de gamme.
- [ ] Revue visuelle de chaque écran à côté de l'écran Citymapper équivalent : mêmes principes, identité distincte.

## Questions ouvertes

- Couleur de marque et nom définitifs.
- Police définitive (test de rendu arabe + latin sur les vrais écrans).
- Faire appel à un designer pour l'icône de l'app et l'icône louage ?
