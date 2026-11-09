# Découvrir le projet

## Thniya en une phrase

Thniya (ثنية, « le chemin ») répond à la question : **« Comment aller d'ici à là-bas en transport en commun, en combien
de temps et pour combien ? »**, partout en Tunisie, en français et en arabe.

## Ce que l'utilisateur voit

1. Il tape une destination : « La Marsa ».
2. L'app propose plusieurs trajets, par exemple : 1 min à pied → métro **M6** → 5 min à pied → **TGM**, 1 h 20,
   environ 1,300 DT.
3. Il ouvre un trajet : la carte montre chaque étape, avec les arrêts où monter et descendre.

Autres écrans : les arrêts **à proximité** avec leurs prochains passages, la liste de **toutes les lignes**, la fiche
d'une ligne, les réglages (langue, thème).

## Pourquoi c'est difficile

La technique est connue : les grandes villes du monde utilisent les mêmes logiciels. **La difficulté, c'est la
donnée.** En Tunisie, il n'existe pas de fichier officiel à jour qui décrit tout le réseau. Le projet rassemble donc
les informations de plusieurs sources (sites des opérateurs, données ouvertes du ministère, OpenStreetMap, relevés de
terrain) et les décrit dans des fichiers texte simples.

C'est pour ça qu'**une donnée vérifiée sur le terrain est souvent plus utile qu'une ligne de code.**

## Ce qui existe aujourd'hui

| Réseau | Exemples | État des horaires |
|---|---|---|
| SNCFT (trains) | Banlieue Sud, Tunis – Sousse | Publiés par l'opérateur |
| SNTRI (cars) | Tunis – Kairouan | Publiés par l'opérateur |
| Transtu | Métro M1 à M6, TGM, bus | **Estimés** (fréquence officielle + distance) |
| Louages | 103 stations | **Pas encore de lignes** |
| Taxi jamaï | — | **Pas encore de lignes** ; le mode est prêt dans l'app |

## Le vocabulaire en 2 minutes

| Mot | Signification | Exemple |
|---|---|---|
| **Arrêt** (lieu) | Un endroit où l'on monte ou descend | Gare de Hammam Lif |
| **Réseau** | Un opérateur et ses règles de calendrier | Transtu, SNCFT, Louages |
| **Ligne** | Un service avec un nom et un code | Métro M6, Banlieue Sud |
| **Direction** | Le sens d'une ligne | « vers Tunis Ville » |
| **Parcours** (*pattern*) | La liste ordonnée des arrêts d'un sens | Erriadh → … → Tunis Ville |
| **Grille horaire** | Des heures de passage fixes, arrêt par arrêt | Train de 07:20 à Hammam Lif |
| **Fréquence** | « Un départ toutes les N minutes », sans heure fixe | Louage toutes les 10 min en pointe |
| **Tranche horaire** | Une partie de la journée qui a sa propre fréquence | Pointe du matin, 06:00 – 09:00 |
| **Période** | Une saison qui change les horaires | Normale, été, Ramadan |
| **Type de jour** | Ouvrable, samedi, dimanche (et jours fériés) | — |
| **Provenance** | D'où vient une donnée, et quand elle a été vérifiée | « Affiche SNCFT hiver 2026-2027 » |
| **Louage** | Taxi collectif interurbain, part quand il est plein | Bab Alioua → Hammam Lif |
| **Taxi jamaï** | Taxi collectif urbain, trajet fixe (en général jaune) | Ariana → Passage |
| **GTFS** | Format mondial des données de transport (fichiers CSV) | `routes.txt`, `stops.txt` |
| **OTP** | OpenTripPlanner : le logiciel qui calcule les itinéraires | — |
| **Photon** | Le moteur de recherche d'adresses | « Rue de Marseille » |
| **PMTiles** | Le fichier qui contient le fond de carte | `tunisie.pmtiles` |

## Les choix importants

- **Pas de Google Maps.** La carte, le calcul d'itinéraires et la recherche d'adresses sont des logiciels libres que
  le projet héberge lui-même. Pas de dépendance, pas de facture, et le droit d'utiliser les données.
- **Les données sont des fichiers texte** (YAML et CSV) dans `data/src`. Faciles à lire, à corriger et à relire dans
  une pull request.
- **Honnêteté sur les données.** Chaque donnée dit d'où elle vient. Si un horaire est estimé, l'app le dit.
- **Français et arabe dès le départ**, y compris l'affichage de droite à gauche.

Suite : [Installer et lancer](02-installer-et-lancer.md) ou [Architecture](03-architecture.md).
