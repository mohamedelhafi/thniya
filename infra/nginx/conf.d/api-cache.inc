# Cache des lectures de l'API (specs/03-gateway-securite.md §6) : durée fixée par l'API (Cache-Control),
# clé = méthode + URL + langue. Les POST (itinéraires) ne sont jamais mis en cache.
proxy_cache apicache;
proxy_cache_methods GET HEAD;
proxy_cache_key "$request_method|$request_uri|$lang_key";
proxy_cache_lock on;                    # une seule requête monte vers l'API pour une même clé
proxy_cache_lock_timeout 5s;
proxy_cache_background_update on;       # sert l'ancienne réponse pendant le rafraîchissement
proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
proxy_cache_revalidate on;              # rafraîchit avec If-None-Match (304 de l'API, ETag)
