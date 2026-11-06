package tn.thniya.api.geocode;

import java.net.http.HttpClient;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import tn.thniya.api.common.AppProperties;
import tn.thniya.api.common.Lang;

/**
 * Recherche d'adresses et de lieux OpenStreetMap avec Photon (index de la Tunisie, specs/09-geocodage-tuiles.md).
 * Photon est un complément : s'il est absent, lent ou en panne, on renvoie une liste vide et la recherche d'arrêts
 * suffit (jamais d'erreur pour l'usager).
 */
@Component
public class PhotonClient {

	private static final Logger log = LoggerFactory.getLogger(PhotonClient.class);

	/** Tunisie (ouest, sud, est, nord) : rien hors du pays. */
	private static final String TUNISIA_BBOX = "7.5,30.2,11.7,37.6";

	@JsonIgnoreProperties(ignoreUnknown = true)
	public record FeatureCollection(List<Feature> features) {
	}

	@JsonIgnoreProperties(ignoreUnknown = true)
	public record Feature(Geometry geometry, Properties properties) {
	}

	@JsonIgnoreProperties(ignoreUnknown = true)
	public record Geometry(List<Double> coordinates) {
	}

	@JsonIgnoreProperties(ignoreUnknown = true)
	public record Properties(String name, String street, String housenumber, String locality, String district,
			String city, String county, String osm_type, Long osm_id, String osm_key, String osm_value, String type) {
	}

	/** Après une panne, Photon n'est plus interrogé pendant ce délai (pas d'attente ni de journal à chaque frappe). */
	static final Duration BACKOFF = Duration.ofSeconds(30);

	private final RestClient http;

	private final boolean enabled;

	private final Clock clock;

	private volatile Instant pausedUntil = Instant.MIN;

	public PhotonClient(RestClient.Builder builder, AppProperties props, Clock clock) {
		this.clock = clock;
		this.enabled = props.photonBaseUrl() != null && !props.photonBaseUrl().isBlank();
		HttpClient client = HttpClient.newBuilder()
			.version(HttpClient.Version.HTTP_1_1)
			.connectTimeout(props.photonTimeout())
			.build();
		var factory = new JdkClientHttpRequestFactory(client);
		factory.setReadTimeout(props.photonTimeout());
		this.http = builder.baseUrl(enabled ? props.photonBaseUrl() : "http://localhost").requestFactory(factory).build();
	}

	/** Lieux et adresses correspondant à la saisie, biaisés autour de (lat, lon) si connus ; vide si Photon échoue. */
	public List<Feature> search(String query, Double lat, Double lon, int limit, Lang lang) {
		if (!enabled || query == null || query.isBlank() || clock.instant().isBefore(pausedUntil)) {
			return List.of();
		}
		try {
			FeatureCollection fc = http.get()
				.uri(b -> {
					b.path("/api")
						.queryParam("q", "{q}")
						.queryParam("limit", limit)
						.queryParam("lang", lang == Lang.AR ? "ar" : "fr")
						.queryParam("bbox", TUNISIA_BBOX);
					if (lat != null && lon != null) {
						b.queryParam("lat", lat).queryParam("lon", lon);
					}
					return b.build(Map.of("q", query.strip()));
				})
				.retrieve()
				.body(FeatureCollection.class);
			return fc == null || fc.features() == null ? List.of() : fc.features();
		}
		catch (RestClientException e) {
			pausedUntil = clock.instant().plus(BACKOFF);
			log.warn("Photon indisponible, recherche limitée aux arrêts pendant {} s : {}", BACKOFF.toSeconds(),
					e.getMessage());
			return List.of();
		}
	}

}
