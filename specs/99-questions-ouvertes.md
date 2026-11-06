# 99 — Questions ouvertes et spikes

> Statut : Brouillon · Mise à jour : 2026-10-13

## Spikes techniques

| # | Question | Lot | Statut | Résultat reporté dans |
|---|---|---|---|---|
| S1 | Restitution des voyages `frequencies` (exact_times=0) par `planConnection` | 2 | À faire | [05-otp.md](05-otp.md) |
| S2 | Exploitabilité des tarifs GTFS v1 dans OTP 2.x | 2 | À faire | [05-otp.md](05-otp.md) |
| S3 | Prise en compte de `translations.txt` (noms arabes) | 2 | ✅ Fait | [05-otp.md](05-otp.md), [08](08-i18n-fr-ar.md) |
| S4 | Durées des louages au changement de tranche horaire | 2 | À faire | [05-otp.md](05-otp.md), [04](04-donnees-modele.md) |
| S5 | `route_type` des louages : 3 (bus) ou 1501 (taxi collectif) | 2 | À faire | [04-donnees-modele.md](04-donnees-modele.md) |
| S6 | Photon : source de l'index Tunisie, qualité de la recherche en arabe | 4 | ✅ Fait (2026-10-14) : export GraphHopper Afrique du Nord filtré sur `tn`, recherche arabe correcte | [09](09-geocodage-tuiles.md) |
| S7 | PMTiles dans flutter_map : performances et rendu des libellés arabes | 5 | Web OK (mode vecteur). À valider sur téléphone (mode raster, libellés) | [09](09-geocodage-tuiles.md), [ADR-004](adr/ADR-004-tuiles-pmtiles.md) |
| S8 | Mémoire et durée du build OTP : Grand Tunis puis Tunisie | 1, 7 | Grand Tunis fait | [02](02-infra-docker.md), [11](11-deploiement-vps.md) |
| S9 | `continuous_pickup` / `continuous_drop_off` (louage hélé en route) : pris en compte par OTP ? | 2 | À faire | [04](04-donnees-modele.md) §8 |
| S10 | Sections façon Citymapper : 5 à 7 requêtes OTP en parallèle tiennent-elles < 1,5 s p95 ? | 3 | À faire | [06](06-api-backend.md) §4.1 |
| S11 | « Autres départs » d'un segment : filtrer OTP sur les mêmes lignes à partir d'une heure donnée | 3 | À faire | [06](06-api-backend.md) §4.2 |
| S12 | Calcul de l'heure du maghrib par date pour les tranches de Ramadan (option V1.1) | 6 | À faire | [04b](04b-calendriers-regimes.md) §5 |

## Questions métier et données

| Question | Pour qui | Bloquant pour |
|---|---|---|
| ~~Liste exacte des gares et horaires de la banlieue sud~~ → ✅ affiche officielle hiver 2026-2027 + OSM (2026-10-13) | — | — |
| Stations de louage du couloir, destinations, prix actuels (station Moncef Bey repérée dans OSM) | Porteur du projet (terrain) | Spikes S1, S4, S5, S9 |
| Lignes Transtu qui desservent le couloir | Porteur du projet (terrain) | Lot 6 |
| Dates des horaires d'été et de Ramadan pour l'année en cours | Porteur du projet | Lot 6 |
| Horaires SNCFT des périodes été et Ramadan (affiches des années précédentes ?) — la grille hiver 2026-2027 est saisie | Porteur du projet | Lot 6 |
| Tarifs officiels de la banlieue sud (non trouvés en ligne) | Porteur du projet | Lot 3 |
| Les 5 temps de parcours inhabituels de l'affiche hiver 2026-2027 (trains 123, 142, 175, 220) : réels ou coquilles ? | Porteur du projet (terrain) | Lot 6 |
| Liste officielle des jours fériés et quelles lignes roulent ces jours-là | Porteur du projet | Lot 6 |
| Les louages s'arrêtent-ils vraiment pendant le ftour ? Horaires de soirée en Ramadan ? | Porteur du projet (terrain) | Lot 6 |
| Nom de l'app, couleur de marque, police | Porteur du projet | Lot 5 |
| Icône de l'app et icône louage : designer ou fait maison ? | Porteur du projet | Lot 5 |
| Hébergeur VPS et nom de domaine | Porteur du projet | Lot 7 |

## Ajouts du 2026-10-13 (base de saisie, réseau de test)

| Question | Qui décide | Impact |
|---|---|---|
| Accepter la licence Directus et désigner le propriétaire du projet (demandé au premier lancement du back-office) | Porteur du projet | Sinon : back-office maison (ADR-007, option 2), sans toucher au schéma |
| Données officielles Transtu (métro, TGM, bus) : grilles, fréquences, tarifs | Porteur du projet / Transtu | Aujourd'hui estimées (positions OSM réelles, horaires de test) : l'app affiche « Horaires estimés » |
| Louages : stations réelles (Bab Alioua, Moncef Bey…), destinations par station, prix | Relevé terrain | Stations seulement (103, sans ligne) : les lignes de test ont été supprimées le 2026-10-14 |
| Accès au back-office sur le VPS : VPN, liste d'IP ou SSO | Porteur du projet | Ne jamais l'exposer publiquement |

