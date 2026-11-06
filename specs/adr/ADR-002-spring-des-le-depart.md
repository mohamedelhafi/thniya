# ADR-002 — Backend Spring dès le MVP

> Statut : Proposé · Date : 2026-10-13 · **Modifie le PRD** (§8.1 « pas de backend au début »)

## Contexte

Le PRD prévoyait que l'app Flutter interroge OTP directement en phase 1, Spring n'arrivant qu'avec les comptes. L'analyse a montré plusieurs besoins dès la V1 qu'OTP ne couvre pas bien seul :

- présenter les louages par fréquence et non par heure fixe ;
- prix fiables (support partiel des tarifs GTFS dans OTP) ;
- noms en arabe ;
- recherche combinée (Photon + arrêts GTFS) ;
- ne pas exposer OTP sur Internet (API GraphQL riche, requêtes coûteuses possibles) ;
- cache.

## Options envisagées

1. **Flutter → OTP directement** (PRD) : moins de code au début, mais toute la logique tunisienne part dans l'app (mise à jour lente via les stores) et OTP est exposé.
2. **Flutter → Spring → OTP dès le départ** : une couche de plus, mais l'API mobile est stable et maîtrisée, et la logique métier se corrige côté serveur sans republier l'app.

## Décision

**Option 2.** Spring est présent dès le lot 3, **sans base de données** jusqu'au lot 8.

## Conséquences

- L'app ne connaît jamais OTP ; elle ne parle qu'à `/api/v1`.
- Changer de moteur ou de version d'OTP n'impacte pas l'app.
- Environ 2 semaines de développement en plus avant l'app, compensées par une app plus simple.
- Le PRD §8, §12 et §16 sont à mettre à jour pour refléter cette décision.
