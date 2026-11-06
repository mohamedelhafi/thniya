package tn.thniya.api.meta;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

import org.junit.jupiter.api.Test;

import tn.thniya.api.common.I18n;

/** Index spatial et textuel des arrêts (specs/06-api-backend.md §5). */
class StopIndexTest {

	private static AppMeta.Stop stop(String fr, String ar, double lat, double lon, String... aliases) {
		return new AppMeta.Stop("stop", new I18n(fr, ar), List.of(aliases), null, lat, lon, null, null, List.of(),
				null, null, "OSM");
	}

	private static StopIndex sample() {
		Map<String, AppMeta.Stop> stops = new LinkedHashMap<>();
		stops.put("TRN-HAMMAMLIF", stop("Hammam-Lif", "حمّام الأنف", 36.7290, 10.3370, "hammem lif"));
		stops.put("TRN-TUNISVILLE", stop("Tunis Ville", "تونس", 36.79565, 10.18085, "barcelone"));
		stops.put("MET-BARCELONE", stop("Place de Barcelone", "ساحة برشلونة", 36.7963, 10.1812));
		stops.put("LOU-BOUMHEL", stop("Boumhel", "بومهل", 36.7252, 10.3006, "bou mhel"));
		return new StopIndex(stops);
	}

	@Test
	void searchIgnoresAccentsPunctuationAndSpaces() {
		StopIndex index = sample();
		assertThat(index.search("hammam lif", null, null, 5)).extracting(h -> h.entry().id())
			.containsExactly("TRN-HAMMAMLIF");
		assertThat(index.search("حمام", null, null, 5)).extracting(h -> h.entry().id())
			.containsExactly("TRN-HAMMAMLIF");
		assertThat(index.search("bou mh", null, null, 5)).extracting(h -> h.entry().id())
			.containsExactly("LOU-BOUMHEL");
	}

	@Test
	void exactAliasRanksBeforePartialName() {
		StopIndex index = sample();
		// « barcelone » est un alias exact de la gare (95) et un mot du nom de la station de métro (60)
		var hits = index.search("barcelone", 36.7963, 10.1812, 5);
		assertThat(hits).extracting(h -> h.entry().id()).containsExactly("TRN-TUNISVILLE", "MET-BARCELONE");
		// à score égal, la plus proche d'abord
		assertThat(index.search("place de b", 36.7963, 10.1812, 5)).extracting(h -> h.entry().id())
			.containsExactly("MET-BARCELONE");
	}

	@Test
	void spatialQueries() {
		StopIndex index = sample();
		assertThat(index.inBbox(10.17, 36.79, 10.19, 36.80)).extracting(StopIndex.Entry::id)
			.containsExactlyInAnyOrder("TRN-TUNISVILLE", "MET-BARCELONE");
		assertThat(index.nearest(36.7955, 10.1806, 150).entry().id()).isEqualTo("TRN-TUNISVILLE");
		assertThat(index.nearest(36.76, 10.25, 150)).isNull();
		assertThat(index.within(36.7960, 10.1810, 200)).hasSize(2);
	}

	@Test
	void scalesToAHundredThousandStops() {
		Random r = new Random(42);
		String[] words = { "hammam", "bab", "cite", "ennour", "jardins", "lac", "marsa", "rades", "ezzahra", "ariana" };
		Map<String, AppMeta.Stop> stops = new LinkedHashMap<>();
		for (int i = 0; i < 100_000; i++) {
			String name = words[r.nextInt(words.length)] + " " + words[r.nextInt(words.length)] + " " + i;
			stops.put("S" + i, stop(name, null, 33 + r.nextDouble() * 4, 8 + r.nextDouble() * 3));
		}
		long t0 = System.nanoTime();
		StopIndex index = new StopIndex(stops);
		long buildMs = (System.nanoTime() - t0) / 1_000_000;

		t0 = System.nanoTime();
		for (int i = 0; i < 200; i++) {
			index.search("lac mar", 36.8, 10.2, 10);
			index.within(36.8, 10.2, 800);
		}
		double perQueryMs = (System.nanoTime() - t0) / 1e6 / 400;
		assertThat(buildMs).isLessThan(5_000);
		assertThat(perQueryMs).isLessThan(20);
	}

}
