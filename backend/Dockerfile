# --- Construction -------------------------------------------------------------------------
FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN chmod +x mvnw && ./mvnw -q -B dependency:go-offline
COPY src src
RUN ./mvnw -q -B package -DskipTests && cp target/thniya-api-*.jar /app.jar

# --- Exécution ----------------------------------------------------------------------------
FROM eclipse-temurin:21-jre
RUN useradd --system --uid 10001 thniya
USER thniya
COPY --from=build /app.jar /app/app.jar
EXPOSE 8080
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75"
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s \
  CMD ["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/8080 && printf 'GET /actuator/health HTTP/1.0\\r\\n\\r\\n' >&3 && grep -q UP <&3"]
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
