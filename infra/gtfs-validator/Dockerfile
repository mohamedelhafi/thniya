# Validateur GTFS officiel de MobilityData (https://github.com/MobilityData/gtfs-validator)
FROM eclipse-temurin:21-jre

ARG VALIDATOR_VERSION=8.0.1
ADD https://github.com/MobilityData/gtfs-validator/releases/download/v${VALIDATOR_VERSION}/gtfs-validator-${VALIDATOR_VERSION}-cli.jar /opt/gtfs-validator.jar

ENTRYPOINT ["java", "-jar", "/opt/gtfs-validator.jar"]
CMD ["--input", "/data/build/gtfs.zip", "--output_base", "/data/build/validation", "--country_code", "tn"]
