# ADR-006 — Modèle de régimes horaires et dates explicites

> Statut : Proposé · Date : 2026-10-13

## Contexte

Les horaires tunisiens changent selon la période (normal, été, Ramadan, Aïd), le type de jour et les fériés, dont une partie est mobile et confirmée tardivement. Il faut pouvoir tout configurer sans ressaisir les horaires, et prévoir sans ambiguïté ce qui circule un jour donné.

## Options envisagées

1. **`calendar.txt` GTFS à règles** (jours de semaine + plage de dates) + exceptions : compact, mais les chevauchements (Ramadan pendant l'été, Aïd un samedi…) deviennent vite illisibles et difficiles à vérifier.
2. **Saisir les dates de chaque grille à la main** : simple à comprendre, ingérable dans la durée.
3. **Régimes calculés** : événements par année → périodes avec priorités par réseau → type de jour → régime (période × type de jour), avec des replis configurables ; le générateur écrit **une liste de dates explicite** par régime (`calendar_dates.txt` seul).

## Décision

**Option 3.** Les horaires sont rattachés à un régime ; les dates sont calculées par le générateur et vérifiables avec `calendar-preview`.

## Conséquences

- Confirmer une date (début du Ramadan) = modifier une ligne dans `calendar/years/<année>.yaml` puis regénérer.
- Le GTFS a une fenêtre glissante (J-7 à J+120) et doit être **régénéré chaque semaine**.
- Les grilles horaires sont rangées par `PERIODE/TYPE_JOUR/DIRECTION`, avec héritage pour éviter les doublons.
- L'identifiant d'un voyage contient sa période, son type de jour et sa tranche : Spring peut l'interpréter sans autre source.
