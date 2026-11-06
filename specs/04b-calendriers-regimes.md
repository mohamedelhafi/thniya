# 04b — Calendriers et régimes horaires

> Statut : Brouillon · Mise à jour : 2026-10-13 · Décision : [ADR-006](adr/ADR-006-regimes-horaires.md)

## 1. Le problème

En Tunisie, un même train ne circule pas aux mêmes heures selon :

- le **jour de la semaine** (semaine, samedi, dimanche) ;
- les **jours fériés** civils et religieux ;
- la **période** : horaires d'hiver, d'été (séance unique de juillet-août), Ramadan, Aïd ;
- des **événements ponctuels** : grève, travaux, fête nationale…

De plus, les dates religieuses **bougent chaque année** et ne sont **confirmées qu'au dernier moment** (observation de la lune). Le modèle doit gérer tout cela sans ressaisir les horaires.

## 2. Vocabulaire

| Terme | Définition | Exemple |
|---|---|---|
| **Événement** | Date ou plage de dates d'une année donnée | Ramadan 2027, Aïd el-Fitr 2027, été 2027, 20 mars |
| **Période** | Saison horaire, définie à partir d'événements | `NORMAL`, `ETE`, `RAMADAN`, `AID` |
| **Type de jour** | Catégorie de jour dans la semaine | `OUVRABLE`, `SAMEDI`, `DIMANCHE` |
| **Régime** | Couple période × type de jour | `RAMADAN / SAMEDI` |
| **Tranche horaire** | Plage nommée dans une journée, propre à un régime | `POINTE_MATIN` = 06:00–09:00 en `NORMAL / OUVRABLE` |
| **Jour de service** | Journée d'exploitation ; peut dépasser minuit | Un départ à `25:10` appartient à la veille |

## 3. Années et événements (`calendar/years/<année>.yaml`)

Un fichier par année, mis à jour au fil de l'eau.

```yaml
# calendar/years/2027.yaml
year: 2027
events:
  # --- Fêtes civiles (dates fixes, liste officielle à vérifier chaque année)
  - { id: NOUVEL_AN,       date: 2027-01-01, kind: holiday, name: { fr: "Jour de l'an", ar: "رأس السنة الميلادية" } }
  - { id: INDEPENDANCE,    date: 2027-03-20, kind: holiday, name: { fr: "Fête de l'indépendance", ar: "عيد الاستقلال" } }
  # … compléter depuis la liste officielle des jours fériés

  # --- Événements religieux (dates mobiles)
  - id: RAMADAN
    kind: period_event
    from: 2027-02-08
    to: 2027-03-09
    status: estimated            # estimated | confirmed
    name: { fr: "Ramadan", ar: "رمضان" }
  - id: AID_FITR
    kind: holiday
    from: 2027-03-10
    to: 2027-03-11
    status: estimated
    name: { fr: "Aïd el-Fitr", ar: "عيد الفطر" }
  - id: AID_ADHA
    kind: holiday
    from: 2027-05-16
    to: 2027-05-17
    status: estimated
    name: { fr: "Aïd el-Adha", ar: "عيد الأضحى" }

  # --- Saisons
  - { id: ETE, kind: period_event, from: 2027-07-01, to: 2027-08-31, status: confirmed,
      name: { fr: "Horaires d'été", ar: "التوقيت الصيفي" } }
  - { id: VACANCES_SCOLAIRES_ETE, kind: period_event, from: 2027-06-30, to: 2027-09-14, status: estimated }

  # --- Ponctuel
  - { id: MARATHON_TUNIS, kind: special, date: 2027-11-xx, status: estimated }
```

> Les dates ci-dessus sont des **exemples** à vérifier, pas des données de référence.

Règles :

- Un événement `estimated` qui tombe dans les **30 prochains jours** déclenche un avertissement dans le rapport de qualité : « confirmer la date de l'Aïd ».
- Quand une date est confirmée, on change `status: confirmed` (et la date si besoin) puis on relance la génération.

## 4. Périodes (`calendar/periods.yaml`)

Les périodes sont définies **une fois**, à partir des événements, pour toutes les années.

```yaml
- id: NORMAL
  name: { fr: "Horaires normaux", ar: "التوقيت العادي" }
  default: true                       # s'applique quand aucune autre période n'est active
  show_banner: false

- id: ETE
  name: { fr: "Horaires d'été", ar: "التوقيت الصيفي" }
  from_event: ETE
  show_banner: true                   # bandeau dans l'app : « Horaires d'été en vigueur »

- id: RAMADAN
  name: { fr: "Horaires de Ramadan", ar: "توقيت رمضان" }
  from_event: RAMADAN
  show_banner: true

- id: AID
  name: { fr: "Horaires de l'Aïd", ar: "توقيت العيد" }
  from_events: [AID_FITR, AID_ADHA]
  extend: { before_days: 1, after_days: 0 }   # la veille de l'Aïd compte aussi (option)
  show_banner: true
```

Chaque **réseau** choisit les périodes qu'il utilise et leur **priorité** (voir [04](04-donnees-modele.md) §6). Si deux périodes se chevauchent (Ramadan pendant l'été, à partir des années 2030), la plus prioritaire l'emporte. On peut aussi créer une période combinée `RAMADAN_ETE` avec `from_events_all: [RAMADAN, ETE]` et une priorité plus haute.

## 5. Tranches horaires (`calendar/time-bands.yaml`)

Les tranches dépendent du régime : la pointe du soir n'est pas la même en Ramadan.

```yaml
- applies_to: { periods: [NORMAL], day_types: [OUVRABLE, SAMEDI] }
  bands:
    - { id: POINTE_MATIN, from: "06:00", to: "09:00" }
    - { id: JOURNEE,      from: "09:00", to: "16:00" }
    - { id: POINTE_SOIR,  from: "16:00", to: "19:00" }
    - { id: SOIREE,       from: "19:00", to: "24:00" }

- applies_to: { periods: [ETE], day_types: [OUVRABLE] }   # séance unique : la pointe arrive plus tôt
  bands:
    - { id: POINTE_MATIN, from: "06:00", to: "08:30" }
    - { id: POINTE_SOIR,  from: "13:00", to: "15:30" }
    - { id: JOURNEE,      from: "08:30", to: "13:00" }
    - { id: SOIREE,       from: "15:30", to: "24:00" }

- applies_to: { periods: [RAMADAN], day_types: [OUVRABLE, SAMEDI] }
  bands:
    - { id: MATIN,        from: "06:30", to: "14:00" }
    - { id: AVANT_FTOUR,  from: "14:00", to: "@maghrib-00:15" }
    - { id: FTOUR,        from: "@maghrib-00:15", to: "@maghrib+01:00" }
    - { id: SOIREE,       from: "@maghrib+01:00", to: "26:00" }

- applies_to: { periods: [NORMAL, ETE, RAMADAN, AID], day_types: [DIMANCHE] }
  bands:
    - { id: TOUTE_LA_JOURNEE, from: "00:00", to: "26:00" }
```

- Les tranches d'un régime doivent **couvrir sans trou ni chevauchement** la plage de service (contrôle bloquant).
- `@maghrib` : heure du coucher du soleil à Tunis, **calculée par le générateur pour chaque date** (elle avance d'environ 1 minute par jour pendant le Ramadan). Le générateur produit alors des voyages jour par jour pour ces tranches. → Option avancée, à activer en V1.1 ; en V1 on peut écrire des heures fixes.
- Les lignes à fréquence référencent ces identifiants (`POINTE_MATIN`, `AVANT_FTOUR`…).

## 6. Résolution : quel régime pour une date donnée ?

Pour chaque réseau `N` et chaque date `d` de la fenêtre de génération :

```
1. Type de jour
   si d est un jour férié (événement kind=holiday) → N.holiday_day_type
   sinon → N.day_type_scheme[jour de la semaine de d]

2. Période
   parmi N.periods (dans l'ordre de priorité), la première active à la date d
   sinon → la période par défaut (NORMAL)

3. Régime = (période, type de jour)

4. Pour chaque ligne L du réseau :
   chercher les horaires de L pour ce régime
   si absents → appliquer les replis (ligne, sinon réseau) :
       d'abord sur le type de jour (DIMANCHE → SAMEDI → OUVRABLE…)
       puis sur la période (AID → RAMADAN → NORMAL…)
   si la ligne déclare explicitement « pas de service » pour ce régime → aucun voyage
   chaque repli utilisé est consigné dans le rapport

5. Appliquer les perturbations NO_SERVICE / STOP_CLOSED actives à la date d
```

Déclarer explicitement l'absence de service (sinon le repli s'appliquerait) :

```yaml
schedule:
  no_service:
    - { periods: [AID], day_types: [OUVRABLE, SAMEDI, DIMANCHE] }
```

## 7. Prévisualisation (`calendar-preview`)

Outil indispensable pour vérifier la configuration avant de publier :

```bash
docker compose --profile tasks run --rm tools calendar-preview --network SNCFT --from 2027-02-01 --days 45
```

```
date        jour  événements             période   type jour  SNCFT-BS-A           LOU-HL-TUNIS
2027-02-07  dim   —                      NORMAL    DIMANCHE   NORMAL/DIMANCHE      NORMAL/DIMANCHE
2027-02-08  lun   RAMADAN (estimé)       RAMADAN   OUVRABLE   RAMADAN/OUVRABLE     RAMADAN/OUVRABLE
2027-02-13  sam   RAMADAN (estimé)       RAMADAN   SAMEDI     ↪ RAMADAN/OUVRABLE   RAMADAN/SAMEDI
…
2027-03-10  mer   AID_FITR (estimé)      AID       DIMANCHE   ↪ RAMADAN/DIMANCHE   ✕ pas de service
```

`↪` = repli utilisé, `✕` = pas de service déclaré.

## 8. Fenêtre de génération

- Par défaut : de **J-7 à J+120**.
- Régénération **hebdomadaire** sur le VPS (tâche planifiée) pour faire glisser la fenêtre et intégrer les dates confirmées.
- Le GTFS ne contient que des **dates explicites** (`calendar_dates.txt`), un `service_id` par régime et par réseau : pas de `calendar.txt` à règles, donc aucune ambiguïté ([ADR-006](adr/ADR-006-regimes-horaires.md)).

## 9. Affichage dans l'app

- `app-meta.json` contient, pour chaque date de la fenêtre et chaque réseau, la période active.
- Bandeau sur l'écran Ligne et Résultats si `show_banner: true` : « Horaires de Ramadan en vigueur ».
- Écran Horaires : sélecteur « Aujourd'hui · Samedi · Dimanche · autre date » qui montre la bonne grille pour la date choisie.

## Critères d'acceptation

- [ ] Changer la date de début du Ramadan dans `years/2027.yaml` et regénérer suffit à basculer tous les réseaux concernés.
- [ ] `calendar-preview` affiche le régime et les replis de chaque ligne jour par jour.
- [ ] Un jour férié en semaine utilise le type de jour défini par le réseau (`holiday_day_type`).
- [ ] Un départ à `25:10` en Ramadan apparaît bien le soir du bon jour dans l'app.
- [ ] Le rapport avertit d'un événement « estimé » dans les 30 prochains jours.
- [ ] Les tranches qui se chevauchent ou laissent un trou font échouer la génération.

## Questions ouvertes

- Heures du `@maghrib` : calcul astronomique dans le générateur (bibliothèque Python) ou table officielle saisie ? → calcul, puis comparaison avec une table publiée.
- Les vacances scolaires changent-elles vraiment les horaires de bus Transtu ? À vérifier sur le terrain avant de créer une période `VACANCES_SCOLAIRES`.
