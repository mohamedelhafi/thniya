package tn.thniya.api.common;

import java.time.Duration;

import com.github.benmanes.caffeine.cache.Caffeine;

import org.springframework.cache.CacheManager;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Caches et durées de vie (specs/06-api-backend.md §5). Vidés à chaque nouvelle version des données. */
@Configuration
public class CacheConfig {

	public static final String ITINERARIES = "itineraries";

	public static final String ITINERARY_BY_ID = "itineraryById";

	public static final String TIMETABLE = "timetable";

	public static final String DEPARTURES = "departures";

	public static final String NEARBY = "nearby";

	@Bean
	CacheManager cacheManager() {
		var manager = new CaffeineCacheManager();
		manager.registerCustomCache(ITINERARIES, cache(Duration.ofMinutes(2), 2_000));
		manager.registerCustomCache(ITINERARY_BY_ID, cache(Duration.ofMinutes(30), 20_000));
		manager.registerCustomCache(TIMETABLE, cache(Duration.ofHours(1), 2_000));
		manager.registerCustomCache(DEPARTURES, cache(Duration.ofSeconds(30), 5_000));
		manager.registerCustomCache(NEARBY, cache(Duration.ofSeconds(30), 5_000));
		return manager;
	}

	private static com.github.benmanes.caffeine.cache.Cache<Object, Object> cache(Duration ttl, long max) {
		return Caffeine.newBuilder().expireAfterWrite(ttl).maximumSize(max).build();
	}

}
