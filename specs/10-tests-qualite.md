# 10 — Tests et qualité

> Statut : Brouillon · Mise à jour : 2026-10-13

## 1. Ce qu'on teste, où

| Couche | Type | Outil | Quand |
|---|---|---|---|
| Générateur GTFS | Unitaires (règles de génération, erreurs de saisie) | pytest | À chaque modification du générateur |
| GTFS produit | Validation de format | gtfs-validator (MobilityData) | À chaque `build` |
| Spring | Unitaires (enrichissement, tri, prix, langue) | JUnit 5 | À chaque commit |
| Spring ↔ OTP | Contrat avec un OTP simulé | WireMock + réponses OTP enregistrées | À chaque commit |
| Chaîne complète | **Trajets de référence** contre le vrai OTP | JUnit (profil `it`) ou script | Après chaque reconstruction du graphe |
| Flutter | Widgets (FR + AR), formatage | `flutter_test` | À chaque commit |
| Terrain | Trajets réels faits avec l'app | Porteur du projet, sur le couloir | Avant chaque publication |

## 2. Trajets de référence (« golden trips »)

C'est le filet de sécurité principal : la donnée change souvent, et une erreur de saisie peut casser un itinéraire sans faire planter quoi que ce soit.

Fichier `data/golden-trips.yaml` :

```yaml
- id: HL-TUNIS-MATIN
  description: "Hammam Lif → Tunis Ville, lundi 7h30 : le train doit être proposé en premier"
  from: { lat: 0.0, lon: 0.0 }       # à renseigner
  to:   { lat: 0.0, lon: 0.0 }
  departAt: "lundi 07:30"            # résolu vers le prochain lundi couvert par les données
  expect:
    first_itinerary_modes_include: [TRAIN]
    max_duration_min: 60

- id: HL-TUNIS-APREM-LOUAGE
  description: "L'après-midi, le louage doit apparaître parmi les options"
  from: { lat: 0.0, lon: 0.0 }
  to:   { lat: 0.0, lon: 0.0 }
  departAt: "mardi 14:00"
  expect:
    any_itinerary_modes_include: [LOUAGE]

- id: HORS-ZONE-MARCHE
  description: "Zone sans GTFS : itinéraire à pied uniquement, pas d'erreur"
  from: { lat: 0.0, lon: 0.0 }
  to:   { lat: 0.0, lon: 0.0 }
  departAt: "mercredi 10:00"
  expect:
    coverage: WALK_ONLY

- id: HL-TUNIS-RAMADAN
  description: "Un jour de Ramadan, la grille Ramadan du train est utilisée"
  from: { stop: TRN-HAMMAMLIF }
  to:   { stop: TRN-TUNISVILLE }
  departAt: { period: RAMADAN, day_type: OUVRABLE, time: "16:00" }   # première date de ce régime dans la fenêtre
  expect:
    any_itinerary_modes_include: [TRAIN]
    trip_id_contains: ":RAMADAN:"

- id: LOUAGE-PAS-DE-SERVICE-FTOUR
  description: "Pendant le ftour, aucun louage n'est proposé"
  from: { stop: LOU-HAMMAMLIF-Q-TUNIS }
  to:   { stop: LOU-TUNIS-… }
  departAt: { period: RAMADAN, day_type: OUVRABLE, band: FTOUR }
  expect:
    no_itinerary_modes_include: [LOUAGE]
```

- `departAt` accepte une date fixe, un jour de la semaine (« lundi 07:30 ») ou un **régime** (`period` + `day_type` + heure ou tranche) : le lanceur choisit la première date correspondante dans la fenêtre de données.
- Assertions disponibles : `first_itinerary_modes_include`, `any_itinerary_modes_include`, `no_itinerary_modes_include`, `max_duration_min`, `coverage`, `trip_id_contains`, `uses_line`, `max_transfers`, `price_millimes`.

Règle : **chaque nouvelle ligne ajoutée aux données ajoute au moins un trajet de référence**, et chaque période spéciale (été, Ramadan) en a au moins un.

### Trajets de bout en bout (réponse de l'API)

Un cas peut porter `api_expect` au lieu d'`expect` : il interroge alors l'API (`POST /api/v1/itineraries`) et vérifie
ce que voit l'usager — sections présentes, enchaînements de lignes proposés, durée maximale, prix connus :

| Cas | Attendu |
|---|---|
| `BOUMHEL-LAC-MULTIMODAL` (mercredi 08:00) | louage → M6 → bus B1 **et** louage → train A → M6 → bus B1, ≤ 120 min, sections Suggestions + Train, prix connus |
| `HAMMAMLIF-PLAGE-MARSA` (mercredi 08:00) | train A → M6 → TGM **et** louage → M6 → TGM, ≤ 140 min, sections Suggestions + Louage, prix connus |

| `NUIT-PREMIERS-DEPARTS` (mercredi 00:05) | mention `FIRST_DEPARTURES`, train A → bus B1 proposé |

État au 2026-10-14 : **9 cas sur 9 réussis**. Tests Flutter : liens partageables, politique de relance.

### Base de saisie

`citydata db-check` : la génération depuis la base doit produire un `gtfs.zip` identique à l'octet et le même
`app-meta.json` que depuis `data/src` ([04d](04d-base-de-saisie.md)).

### Charge

Script de charge (requêtes d'itinéraires toutes différentes, donc sans cache) : 52 recherches/s, p50 293 ms,
p95 706 ms, 0 échec, à 16 requêtes simultanées sur le poste de développement.

## 2 bis. Tests du générateur et du calendrier

- Jeux de données miniatures dans `data/scripts/tests/fixtures/` (un réseau fictif, 3 arrêts, 2 lignes).
- Cas obligatoires : grille avec `|` et heures > 24:00, héritage `inherits/remove/add/shift`, repli de type de jour puis de période, `no_service`, jour férié en semaine, chevauchement Ramadan/été, perturbation `NO_SERVICE`, tranches avec trou (doit échouer), nom arabe manquant (doit échouer).
- Test de non-régression : la sortie de `build` sur les fixtures est comparée à une sortie de référence versionnée.

## 2 ter. Vérifier l'app en mode debug

La version web compilée (`--profile`) désactive les assertions de Flutter : une erreur de mise en page peut y passer
inaperçue et vider un écran sur téléphone (cas réel, 2026-10-14 : `LayoutBuilder` dans un `IntrinsicHeight`).
Toute modification d'interface se vérifie aussi **en mode debug sur l'émulateur Android** :
`flutter run -d emulator-5554 --dart-define=API_BASE_URL=http://10.0.2.2:8090`, journal sans exception.
Pas d'`IntrinsicHeight` autour d'un contenu animé (`AnimatedSize`) : son estimation de hauteur diverge pendant
l'animation et produit des bandes jaunes et noires de débordement (schéma de ligne, frise d'un trajet). Un rail ou un
fond dessiné sur toute la hauteur d'une rangée se place dans un `Stack` avec `PositionedDirectional(top: 0, bottom: 0)`.
Les « Cancelled » du journal debug (tuiles annulées pendant un déplacement de carte) sont normaux.

## 3. Qualité du code

- Spring : formatage automatique (Spotless), `./mvnw verify` doit passer.
- Flutter : `flutter analyze` sans avertissement, `dart format`.
- Python : `ruff`.
- Plus tard : intégration continue (GitHub Actions) qui lance tout cela + `build` + validation.

## Critères d'acceptation

- [ ] Au moins 3 trajets de référence dès la fin du lot 2.
- [ ] Une commande unique lance tous les trajets de référence et affiche un rapport clair (réussi / échoué + raison).
