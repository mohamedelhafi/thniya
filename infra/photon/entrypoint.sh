#!/bin/sh
# Lance Photon. Sans index (avant le premier infra/scripts/photon-import.sh), le service attend au lieu de redémarrer
# en boucle ; l'API, elle, continue de chercher dans les arrêts.
if [ "$1" = "serve" ] && [ ! -d /photon/photon_data ]; then
  echo "Index Photon absent : lancer infra/scripts/photon-import.sh" >&2
  exec sleep infinity
fi
exec java -jar /opt/photon.jar "$@"
