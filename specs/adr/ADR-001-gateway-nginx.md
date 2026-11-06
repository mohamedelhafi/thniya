# ADR-001 — nginx comme passerelle (pas Kong pour l'instant)

> Statut : Proposé · Date : 2026-10-13

## Contexte

Il faut un point d'entrée unique qui assure HTTPS, limite de requêtes, en-têtes de sécurité et routage vers Spring et les tuiles. Deux candidats : nginx et Kong.

## Options envisagées

1. **nginx**
   - + Très léger (quelques dizaines de Mo de RAM) : important car OTP consomme l'essentiel de la mémoire du VPS.
   - + Configuration en fichiers texte versionnés ; identique en local et sur le VPS.
   - + `limit_req`/`limit_conn`, TLS et service de fichiers statiques (tuiles PMTiles avec `Range`) natifs.
   - + Intégration certbot éprouvée.
   - − Pas de gestion de « consommateurs » (clés d'API par client), pas d'interface d'administration.
2. **Kong (mode DB-less)**
   - + Plugins prêts : rate limiting par consommateur, clés d'API, JWT, CORS, métriques.
   - + Utile si l'API devient publique pour des partenaires.
   - − Plus lourd (Kong repose sur nginx/OpenResty, plus son propre runtime).
   - − Une brique de plus à apprendre et à maintenir, pour des besoins que nginx couvre déjà.
   - − Le service des tuiles statiques resterait de toute façon plus simple dans nginx.

## Décision

**nginx.** Les besoins actuels (une app mobile, un seul client, un seul VPS) sont entièrement couverts. CORS est géré dans Spring (voir [03-gateway-securite.md](../03-gateway-securite.md) §4).

## Conséquences

- Configuration dans `infra/nginx/`.
- **À revoir si** : ouverture de l'API à des partenaires tiers, besoin de quotas par client ou par clé, ou plusieurs services backend à exposer. La migration vers Kong reste simple car Kong accepte une configuration déclarative et se place au même endroit dans l'architecture.
