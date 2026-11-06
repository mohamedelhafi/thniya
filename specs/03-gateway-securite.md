# 03 — Gateway et sécurité (nginx)

> Statut : Brouillon · Mise à jour : 2026-10-13 · Décision : [ADR-001](adr/ADR-001-gateway-nginx.md)

## 1. Routage

| Chemin | Cible | Remarque |
|---|---|---|
| `/api/` | `api:8080` | Toute l'API publique |
| `/tiles/` | fichiers statiques `.pmtiles` | Requêtes `Range` autorisées, cache long |
| `/healthz` | réponse nginx directe `200` | Pour le healthcheck et la supervision |
| tout le reste | `404` | OTP, Photon et Actuator ne sont **jamais** routés |

`/api/actuator/*` est bloqué au niveau nginx (`403`) ; Actuator n'est accessible que depuis le réseau interne.

## 2. HTTPS

### Local

- Certificats générés avec **mkcert** pour : `citymapper.localhost`, `localhost`, `127.0.0.1` et **l'IP LAN du PC** (pour tester sur un vrai téléphone).
- Fichiers dans `infra/nginx/certs/` (ignoré par git).
- Émulateur Android : l'hôte est `10.0.2.2` → inclure cette IP dans le certificat ou passer par l'IP LAN.
- Téléphone réel : installer l'autorité racine mkcert sur le téléphone ; en build **debug** uniquement, l'app Android fait confiance aux autorités utilisateur (`network_security_config.xml` du flavor debug).

### VPS

- **Let's Encrypt** via certbot (challenge HTTP-01, renouvellement automatique).
- Port 80 : uniquement `/.well-known/acme-challenge/` + redirection 301 vers HTTPS.

### Paramètres TLS

- TLS 1.2 et 1.3 uniquement ; suites par défaut de nginx moderne.
- HSTS (`max-age=31536000`) **en prod uniquement** (en local, cela polluerait le navigateur).
- HTTP/2 activé.

## 3. Limite de requêtes

Zones `limit_req` par adresse IP (`$binary_remote_addr`) :

| Zone | Chemins | Débit | Burst | Pourquoi |
|---|---|---|---|---|
| `itin` | `/api/v1/itineraries` | 30 req/min | 10 | Calcul coûteux côté OTP |
| `geo` | `/api/v1/geocode`, `/api/v1/reverse` | 5 req/s | 15 | Autocomplétion pendant la frappe |
| `api` | autres `/api/` | 10 req/s | 30 | Lignes, arrêts, départs |
| `tiles` | `/tiles/` | 60 req/s | 200 | Une carte charge des dizaines de tuiles d'un coup |

- `limit_req_status 429` + corps JSON `{"type":"about:blank","title":"Too Many Requests","status":429}`.
- `limit_conn` : 20 connexions simultanées par IP.

> **Attention CGNAT :** en Tunisie, beaucoup d'abonnés mobiles partagent la même IP publique. Des limites trop strictes bloqueraient des utilisateurs innocents. On démarre large, on surveille les `429` dans les logs, et on ajoutera plus tard une clé par installation (`X-Install-Id`) si nécessaire.

## 4. CORS

- **Une app mobile native n'est pas concernée par CORS** : c'est une règle des navigateurs uniquement.
- CORS ne sert que si l'on ajoute un client web (Flutter web, page d'admin, site vitrine qui appelle l'API).
- **Décision : CORS géré dans Spring** (un seul endroit, configurable par profil). nginx ne touche pas aux en-têtes CORS pour éviter les doublons.
  - Profil `local` : `http://localhost:*` autorisé.
  - Profil `prod` : liste vide par défaut, à remplir si un client web apparaît.

## 5. En-têtes et durcissement

- `server_tokens off;`
- `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`.
- `client_max_body_size 16k` (l'API ne reçoit que de petits JSON).
- Timeouts : `proxy_read_timeout 15s` vers l'API (OTP doit répondre bien avant).
- `gzip on` pour `application/json` (les itinéraires avec tracés sont volumineux).
- Transmission `X-Request-Id` (généré par nginx si absent) → repris dans les logs Spring.
- Logs d'accès en JSON : IP, chemin, statut, `request_time`, `upstream_response_time`, `request_id`.

## 6. Cache des lectures

- `proxy_cache_path /var/cache/nginx/api` (zone `apicache`, 256 Mo) ; inclus dans les blocs `/api/` par
  `conf.d/api-cache.inc`.
- Durée : celle de l'API (`Cache-Control`, [06](06-api-backend.md) §5) ; les `POST` (itinéraires) et les erreurs
  (`no-store`) ne sont jamais mis en cache.
- Clé : méthode + URL + **langue** (`$lang_key`, déduite d'`Accept-Language` comme côté Spring : `ar…` → `ar`,
  `fr…` → `fr`).
- `proxy_cache_lock` : une seule requête monte vers l'API pour une même clé (pas d'avalanche à l'expiration) ;
  `proxy_cache_use_stale updating error timeout` + `background_update` : la réponse précédente est servie pendant le
  rafraîchissement ou si l'API tombe ; `proxy_cache_revalidate` : rafraîchissement par `If-None-Match` (304).
- En-tête `X-Cache` (`HIT`, `MISS`, `STALE`…) pour le diagnostic.

## Critères d'acceptation

- [ ] `https://citymapper.localhost/healthz` répond 200 avec un certificat reconnu par le navigateur.
- [ ] `curl` en boucle sur `/api/v1/itineraries` reçoit des `429` après le burst.
- [ ] `/api/actuator/health` → 403 ; ni OTP ni Photon ne sont joignables via nginx.
- [ ] Un téléphone Android en debug atteint l'API en HTTPS sur le réseau local.
- [ ] La même configuration nginx fonctionne sur le VPS en ne changeant que les certificats et `server_name`.

## Questions ouvertes

- Clé d'application (`X-App-Key`) : peu utile contre un attaquant (elle est dans l'APK), mais filtre les robots basiques. À décider au lot 7.
