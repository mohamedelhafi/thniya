# ADR-005 — Flutter : Riverpod, go_router, dio

> Statut : Proposé · Date : 2026-10-13

## Contexte

L'app a peu d'écrans mais beaucoup d'états asynchrones : position, autocomplétion, itinéraires, comptes à rebours, langue. Il faut une base testable et standard.

## Options envisagées

1. **Riverpod** : gestion d'état asynchrone native (`AsyncValue`), injection facile pour les tests, très répandu.
2. **Bloc** : très structuré, plus verbeux pour une petite app.
3. **Provider / setState** : trop limité pour les flux asynchrones croisés.

## Décision

**Riverpod** (avec génération de code), **go_router** pour la navigation, **dio** pour HTTP, **freezed** pour les modèles.

## Conséquences

- Organisation par fonctionnalité (voir [07-app-flutter.md](../07-app-flutter.md)).
- Si le porteur du projet maîtrise déjà mieux Bloc, cette décision peut être inversée **avant** le lot 5 sans autre impact.
