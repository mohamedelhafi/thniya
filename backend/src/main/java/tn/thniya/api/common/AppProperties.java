package tn.thniya.api.common;

import java.time.Duration;
import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("app")
public record AppProperties(
		String otpBaseUrl,
		String photonBaseUrl,
		String metaPath,
		String feedbackPath,
		@DefaultValue("fr") String defaultLanguage,
		@DefaultValue List<String> corsAllowedOrigins,
		@DefaultValue("8s") Duration otpTimeout,
		@DefaultValue("32") int otpMaxConcurrent,
		@DefaultValue("3s") Duration otpQueueTimeout,
		@DefaultValue("2s") Duration photonTimeout,
		@DefaultValue Itineraries itineraries) {

	public record Itineraries(
			@DefaultValue("3") int maxPerSection,
			@DefaultValue("6s") Duration parallelTimeout) {
	}

}
