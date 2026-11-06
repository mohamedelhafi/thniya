# Photon : recherche d'adresses et de lieux OSM (https://github.com/komoot/photon), specs/09-geocodage-tuiles.md
# Index de la Tunisie construit par infra/scripts/photon-import.sh depuis l'export GraphHopper (Afrique du Nord).
FROM eclipse-temurin:21.0.12_8-jre-noble

ARG PHOTON_VERSION=1.3.0
ARG PHOTON_SHA256=a89707c0045e4807b2a1180e132e68e108d998709f48b6c94b98a6e281f571a5

# zstd : lecture de l'export compressé (.jsonl.zst) à l'import
RUN apt-get update \
 && apt-get install -y --no-install-recommends zstd \
 && rm -rf /var/lib/apt/lists/*

ADD https://github.com/komoot/photon/releases/download/${PHOTON_VERSION}/photon-${PHOTON_VERSION}.jar /opt/photon.jar
RUN echo "${PHOTON_SHA256}  /opt/photon.jar" | sha256sum -c -

COPY entrypoint.sh /usr/local/bin/photon
RUN chmod +x /usr/local/bin/photon

WORKDIR /photon
EXPOSE 2322
ENTRYPOINT ["/usr/local/bin/photon"]
CMD ["serve", "-listen-ip", "0.0.0.0", "-data-dir", "/photon"]
