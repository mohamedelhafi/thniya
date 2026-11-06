#!/bin/sh
# Certificats HTTPS de développement (specs/03-gateway-securite.md §2).
# Crée une autorité locale (ca.crt) puis un certificat serveur pour les noms et IP utiles en local.
# Usage (depuis infra/) : docker run --rm -v "$PWD/nginx:/w" -e LAN_IP=192.168.1.20 alpine:3.22 sh /w/make-dev-certs.sh
set -eu
apk add --no-cache openssl >/dev/null
cd /w
mkdir -p certs
cd certs

if [ ! -f ca.key ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -sha256 \
    -keyout ca.key -out ca.crt -subj "/CN=Thniya Dev CA" >/dev/null 2>&1
  echo "Autorité locale créée : certs/ca.crt"
fi

SAN="DNS:thniya.localhost,DNS:localhost,IP:127.0.0.1,IP:10.0.2.2"
if [ -n "${LAN_IP:-}" ]; then SAN="$SAN,IP:$LAN_IP"; fi

openssl req -newkey rsa:2048 -nodes -keyout server.key -out server.csr -subj "/CN=thniya.localhost" >/dev/null 2>&1
printf "subjectAltName=%s\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n" "$SAN" > ext.cnf
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 397 -sha256 \
  -extfile ext.cnf -out server.crt >/dev/null 2>&1
rm -f server.csr ext.cnf
chmod 644 server.crt ca.crt server.key
echo "Certificat serveur : $SAN"
