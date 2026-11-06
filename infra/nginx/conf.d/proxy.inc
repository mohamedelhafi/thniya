proxy_pass http://api;
proxy_http_version 1.1;
proxy_set_header Connection "";
# Hôte complet (avec le port) : sinon Spring prend une requête de même origine pour du cross-origin (CORS 403)
proxy_set_header Host $http_host;
proxy_set_header X-Forwarded-Host $http_host;
proxy_set_header X-Forwarded-Port $server_port;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Request-Id $req_id;
proxy_set_header Accept-Language $http_accept_language;
proxy_connect_timeout 3s;
proxy_read_timeout 15s;
