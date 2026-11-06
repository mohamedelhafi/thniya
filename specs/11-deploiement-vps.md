# 11 — Déploiement sur VPS (plus tard)

> Statut : Brouillon · Mise à jour : 2026-10-13 · À détailler au lot 7

## 1. Dimensionnement de départ

| Ressource | Valeur | Justification |
|---|---|---|
| RAM | 8 Go minimum (16 Go confortable) | OTP Tunisie entière + Spring + Photon + nginx ; le build du graphe est le pic |
| CPU | 4 vCPU | Build du graphe, requêtes OTP |
| Disque | 80 Go SSD | OSM, graphe, index Photon, PMTiles, images Docker, sauvegardes |
| OS | Ubuntu LTS ou Debian stable | |

Spike S8 fait (2026-10-14) : OTP Tunisie entière = build 31 s avec `-Xmx4g`, graphe 126 Mo, ≈ 1,1 Go en service ; fond de carte national 161 Mo. 8 Go de RAM suffisent.

## 2. Ce qui change par rapport au local

- `compose.prod.yml` : aucun port de débogage, réseau `internal: true`, `restart: unless-stopped`, limites mémoire par service.
- Certificats Let's Encrypt (certbot) au lieu de mkcert ; HSTS activé.
- Profil Spring `prod` : OpenAPI désactivé ou protégé, CORS vide par défaut, logs JSON.
- OSM et fond de carte : Tunisie entière (déjà le cas en local depuis le 2026-10-14).

## 3. Checklist serveur

- [ ] Utilisateur non-root, connexion SSH par clé uniquement, root désactivé.
- [ ] Pare-feu : 22, 80, 443 seulement.
- [ ] fail2ban (SSH).
- [ ] Mises à jour de sécurité automatiques.
- [ ] Docker + plugin Compose.
- [ ] Sauvegardes : `data/src` (aussi dans git), PostgreSQL au lot 8 (dump quotidien hors du serveur).
- [ ] Supervision minimale : sonde externe sur `/healthz` + alerte (ex. Uptime Kuma ou service gratuit).
- [ ] Rotation des logs Docker (`max-size`, `max-file`).

## 4. Mise à jour des données en production

1. En local : modifier `data/src`, `build`, validation, trajets de référence → commit.
2. Sur le VPS : `git pull`, `build`, `otp-build` (graphe écrit dans un nouveau dossier), puis bascule et redémarrage de `otp` et `api`.
3. Vérifier `/api/v1/meta` → nouvelle `dataVersion`.

## 5. Publication sur les stores

- **Google Play :** les nouveaux comptes développeur personnels doivent faire un **test fermé avec au moins 12 testeurs pendant 14 jours** avant de pouvoir publier en production → recruter les testeurs tôt.
- **App Store :** TestFlight, justification de la localisation, politique de confidentialité publique (même sans compte).
- Une page web de politique de confidentialité est obligatoire pour les deux stores.

## Questions ouvertes

- Hébergeur (Hetzner, OVH, hébergeur tunisien pour la latence ?) → comparer prix et latence depuis la Tunisie.
- Nom de domaine.
