package tn.thniya.api.meta;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.locationtech.jts.geom.Envelope;
import org.locationtech.jts.index.strtree.STRtree;

import tn.thniya.api.common.Geo;
import tn.thniya.api.common.TextNorm;

/**
 * Index des arrêts construit une fois par version des données (specs/06-api-backend.md §5 « Performances ») :
 * <ul>
 * <li>index spatial STRtree (JTS) pour la carte, « à proximité » et le géocodage inverse ;</li>
 * <li>noms normalisés pré-calculés et index de trigrammes pour l'autocomplétion.</li>
 * </ul>
 * Immuable : partagé sans verrou entre toutes les requêtes. Coût mesuré : quelques millisecondes pour 100 000
 * arrêts au chargement, requêtes en microsecondes.
 */
public final class StopIndex {

	/** Un arrêt indexé, avec ses textes normalisés (nom français, arabe, alias). */
	public record Entry(String id, AppMeta.Stop stop, String fr, String ar, List<String> aliases) {
	}

	/** Résultat d'une recherche : arrêt, score de pertinence (0-100) et distance éventuelle en mètres. */
	public record Hit(Entry entry, int score, double distanceM) {
	}

	private static final double METERS_PER_DEGREE = 111_320;

	private final STRtree tree = new STRtree();

	private final List<Entry> entries;

	/** Trigramme → positions dans entries (requêtes de 3 caractères et plus). */
	private final Map<String, int[]> trigrams;

	/** Préfixe de 1 ou 2 caractères d'un mot → positions (requêtes courtes). */
	private final Map<String, int[]> shortPrefixes;

	public StopIndex(Map<String, AppMeta.Stop> stops) {
		this.entries = new ArrayList<>(stops.size());
		Map<String, List<Integer>> tri = new HashMap<>();
		Map<String, List<Integer>> pre = new HashMap<>();
		for (var e : stops.entrySet()) {
			AppMeta.Stop s = e.getValue();
			Entry entry = new Entry(e.getKey(), s, TextNorm.normalize(s.name() == null ? null : s.name().fr()),
					TextNorm.normalize(s.name() == null ? null : s.name().ar()),
					s.aliases() == null ? List.of() : s.aliases().stream().map(TextNorm::normalize).toList());
			int pos = entries.size();
			entries.add(entry);
			tree.insert(new Envelope(s.lon(), s.lon(), s.lat(), s.lat()), entry);
			Set<String> texts = new LinkedHashSet<>(entry.aliases());
			texts.add(entry.fr());
			texts.add(entry.ar());
			for (String text : texts) {
				for (int i = 0; i + 3 <= text.length(); i++) {
					tri.computeIfAbsent(text.substring(i, i + 3), k -> new ArrayList<>()).add(pos);
				}
				for (String word : text.split(" ")) {
					for (int n = 1; n <= Math.min(2, word.length()); n++) {
						pre.computeIfAbsent(word.substring(0, n), k -> new ArrayList<>()).add(pos);
					}
				}
			}
		}
		tree.build();
		this.trigrams = compact(tri);
		this.shortPrefixes = compact(pre);
	}

	private static Map<String, int[]> compact(Map<String, List<Integer>> postings) {
		Map<String, int[]> out = new HashMap<>(postings.size() * 2);
		postings.forEach((k, v) -> out.put(k, v.stream().mapToInt(Integer::intValue).distinct().toArray()));
		return out;
	}

	public int size() {
		return entries.size();
	}

	// --- Spatial -----------------------------------------------------------------------------

	/** Arrêts dans un rectangle (ouest, sud, est, nord). */
	@SuppressWarnings("unchecked")
	public List<Entry> inBbox(double west, double south, double east, double north) {
		return (List<Entry>) tree.query(new Envelope(west, east, south, north));
	}

	/** Arrêts à moins de radiusM mètres, du plus proche au plus loin. */
	public List<Hit> within(double lat, double lon, double radiusM) {
		double dLat = radiusM / METERS_PER_DEGREE;
		double dLon = radiusM / (METERS_PER_DEGREE * Math.cos(Math.toRadians(lat)));
		List<Hit> hits = new ArrayList<>();
		for (Entry e : inBbox(lon - dLon, lat - dLat, lon + dLon, lat + dLat)) {
			double d = Geo.distanceM(lat, lon, e.stop().lat(), e.stop().lon());
			if (d <= radiusM) {
				hits.add(new Hit(e, 0, d));
			}
		}
		hits.sort(Comparator.comparingDouble(Hit::distanceM));
		return hits;
	}

	/** Arrêt le plus proche à moins de maxM mètres, ou null (rayon élargi par paliers). */
	public Hit nearest(double lat, double lon, double maxM) {
		for (double r = Math.min(200, maxM); ; r = Math.min(r * 4, maxM)) {
			List<Hit> hits = within(lat, lon, r);
			if (!hits.isEmpty()) {
				return hits.getFirst();
			}
			if (r >= maxM) {
				return null;
			}
		}
	}

	// --- Texte -------------------------------------------------------------------------------

	/**
	 * Arrêts dont le nom ou un alias correspond à la requête (déjà classés : pertinence puis distance). Les alias
	 * comptent un peu moins que le nom officiel.
	 */
	public List<Hit> search(String query, Double lat, Double lon, int limit) {
		String q = TextNorm.normalize(query);
		if (q.isEmpty()) {
			return List.of();
		}
		int[] candidates = candidates(q);
		List<Hit> hits = new ArrayList<>();
		for (int pos : candidates) {
			Entry e = entries.get(pos);
			int best = Math.max(TextNorm.scoreNormalized(q, e.fr()), TextNorm.scoreNormalized(q, e.ar()));
			for (String alias : e.aliases()) {
				best = Math.max(best, TextNorm.scoreNormalized(q, alias) - 5);
			}
			if (best > 0) {
				double d = lat == null || lon == null ? 0 : Geo.distanceM(lat, lon, e.stop().lat(), e.stop().lon());
				hits.add(new Hit(e, best, d));
			}
		}
		hits.sort(Comparator.comparingInt(Hit::score).reversed().thenComparingDouble(Hit::distanceM));
		return hits.size() > limit ? hits.subList(0, limit) : hits;
	}

	/** Sur-ensemble des arrêts pouvant correspondre : intersection des listes de trigrammes de la requête. */
	private int[] candidates(String q) {
		if (q.length() < 3) {
			return shortPrefixes.getOrDefault(q.split(" ")[0], new int[0]);
		}
		int[] result = null;
		for (int i = 0; i + 3 <= q.length(); i++) {
			String gram = q.substring(i, i + 3);
			if (gram.indexOf(' ') >= 0) {
				continue; // « hammam lif » doit aussi trouver « hammamlif »
			}
			int[] posting = trigrams.get(gram);
			if (posting == null) {
				return new int[0];
			}
			result = result == null ? posting : intersect(result, posting);
			if (result.length == 0) {
				break;
			}
		}
		if (result != null) {
			return result;
		}
		String first = q.split(" ")[0];
		return shortPrefixes.getOrDefault(first.substring(0, Math.min(2, first.length())), new int[0]);
	}

	private static int[] intersect(int[] a, int[] b) {
		int[] out = new int[Math.min(a.length, b.length)];
		int i = 0, j = 0, n = 0;
		while (i < a.length && j < b.length) {
			if (a[i] == b[j]) {
				out[n++] = a[i];
				i++;
				j++;
			}
			else if (a[i] < b[j]) {
				i++;
			}
			else {
				j++;
			}
		}
		return Arrays.copyOf(out, n);
	}

}
