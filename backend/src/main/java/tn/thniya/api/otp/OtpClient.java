package tn.thniya.api.otp;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import tn.thniya.api.common.ApiException;
import tn.thniya.api.common.AppProperties;
import tn.thniya.api.common.Lang;

/**
 * Appels à l'API GraphQL d'OTP. Les requêtes vivent dans resources/graphql/*.graphql (jamais concaténées),
 * les variables sont passées séparément. Voir specs/05-otp.md §3.
 */
@Component
public class OtpClient {

	private final RestClient http;

	private final Map<String, String> queries = new ConcurrentHashMap<>();

	/**
	 * Cloison étanche : au plus N requêtes simultanées vers OTP. Au-delà, on attend un peu puis on répond « service
	 * chargé » plutôt que d'écrouler OTP (un calcul d'itinéraire = jusqu'à 10 requêtes OTP en parallèle).
	 */
	private final Semaphore permits;

	private final Duration queueTimeout;

	public OtpClient(RestClient.Builder builder, AppProperties props) {
		// Client HTTP du JDK : réserve de connexions persistantes sans plafond bas, adaptée aux threads virtuels
		HttpClient client = HttpClient.newBuilder()
			.version(HttpClient.Version.HTTP_1_1)
			.connectTimeout(props.otpTimeout())
			.build();
		var factory = new JdkClientHttpRequestFactory(client);
		factory.setReadTimeout(props.otpTimeout());
		this.http = builder.baseUrl(props.otpBaseUrl() + "/otp/gtfs/v1").requestFactory(factory).build();
		this.permits = new Semaphore(props.otpMaxConcurrent(), true);
		this.queueTimeout = props.otpQueueTimeout();
	}

	public Otp.PlanData plan(Map<String, Object> variables, Lang lang) {
		return execute("plan", variables, lang, new ParameterizedTypeReference<>() {
		});
	}

	public Otp.StopData stopDepartures(Map<String, Object> variables, Lang lang) {
		return execute("stop-departures", variables, lang, new ParameterizedTypeReference<>() {
		});
	}

	public Otp.RouteData routeDay(Map<String, Object> variables, Lang lang) {
		return execute("route-day", variables, lang, new ParameterizedTypeReference<>() {
		});
	}

	public Otp.NearbyData stopsNearby(Map<String, Object> variables, Lang lang) {
		return execute("stops-nearby", variables, lang, new ParameterizedTypeReference<>() {
		});
	}

	private <T> T execute(String name, Map<String, Object> variables, Lang lang,
			ParameterizedTypeReference<Otp.Response<T>> type) {
		Otp.Response<T> response;
		try {
			if (!permits.tryAcquire(queueTimeout.toMillis(), TimeUnit.MILLISECONDS)) {
				throw new ApiException(ApiException.Code.OTP_UNAVAILABLE, "Calculateur d'itinéraires saturé, réessayer");
			}
		}
		catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new ApiException(ApiException.Code.OTP_UNAVAILABLE, "Interrompu");
		}
		try {
			response = http.post()
				.contentType(MediaType.APPLICATION_JSON)
				.header("Accept-Language", lang.code())
				.body(Map.of("query", query(name), "variables", variables))
				.retrieve()
				.body(type);
		}
		catch (RestClientException e) {
			throw new ApiException(ApiException.Code.OTP_UNAVAILABLE, "OTP ne répond pas (" + name + ")", e);
		}
		finally {
			permits.release();
		}
		if (response == null || response.data() == null) {
			String detail = response != null && response.errors() != null && !response.errors().isEmpty()
					? response.errors().getFirst().message() : "réponse vide";
			throw new ApiException(ApiException.Code.OTP_UNAVAILABLE, "Erreur OTP (" + name + ") : " + detail);
		}
		return response.data();
	}

	private String query(String name) {
		return queries.computeIfAbsent(name, n -> {
			try {
				return new ClassPathResource("graphql/" + n + ".graphql").getContentAsString(StandardCharsets.UTF_8);
			}
			catch (IOException e) {
				throw new UncheckedIOException(e);
			}
		});
	}

}
