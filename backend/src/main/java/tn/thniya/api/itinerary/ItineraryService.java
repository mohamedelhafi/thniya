package tn.thniya.api.itinerary;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Clock;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.stereotype.Service;

import tn.thniya.api.common.ApiException;
import tn.thniya.api.common.AppProperties;
import tn.thniya.api.common.CacheConfig;
import tn.thniya.api.common.Geo;
import tn.thniya.api.common.I18n;
import tn.thniya.api.common.Lang;
import tn.thniya.api.common.WebConfig;
import tn.thniya.api.itinerary.ItineraryModels.DepartureChoice;
import tn.thniya.api.itinerary.ItineraryModels.ItinerariesResponse;
import tn.thniya.api.itinerary.ItineraryModels.ItineraryRequest;
import tn.thniya.api.itinerary.ItineraryModels.ItineraryView;
import tn.thniya.api.itinerary.ItineraryModels.LegView;
import tn.thniya.api.itinerary.ItineraryModels.Section;
import tn.thniya.api.itinerary.ItineraryModels.TimeMode;
import tn.thniya.api.meta.AppMeta;
import tn.thniya.api.meta.MetaService;
import tn.thniya.api.otp.Otp;
import tn.thniya.api.otp.OtpClient;
import tn.thniya.api.view.Views;

/**
 * Itinéraires groupés en sections, comme Citymapper : plusieurs requêtes OTP en parallèle, fusion, dédoublonnage,
 * enrichissement (specs/06-api-backend.md §4.1).
 */
@Service
public class ItineraryService {

	private static final Logger log = LoggerFactory.getLogger(ItineraryService.class);

	/** Mode de nos données → mode OTP. Bus et louages partagent BUS : on les sépare par filtre de lignes. */
	/** Fenêtre de recherche quand plus rien ne circule à l'heure demandée : couvre la nuit jusqu'aux premiers départs. */
	private static final String NIGHT_WINDOW = "PT10H";

	static final Map<String, String> OTP_MODE = Map.of("TRAIN", "RAIL", "METRO", "TRAM", "BUS", "BUS", "LOUAGE",
			"BUS", "TAXI_COLLECTIF", "BUS", "FERRY", "FERRY");

	static final List<String> MODE_ORDER = List.of("TRAIN", "METRO", "BUS", "LOUAGE", "TAXI_COLLECTIF", "FERRY");

	private static final Map<String, String[]> SECTION_TITLES = Map.of(
			"SUGGESTED", new String[] { "Suggestions", "اقتراحات" },
			"LESS_WALKING", new String[] { "Moins de marche", "أقل مشي" },
			"WALK", new String[] { "À pied", "مشيا على الأقدام" });

	record Stored(ItineraryView view, ItineraryRequest request, Lang lang) {
	}

	private record SectionQuery(String key, Map<String, Object> variables) {
	}

	private final OtpClient otp;

	private final MetaService meta;

	private final Views views;

	private final ItineraryMapper mapper;

	private final AppProperties props;

	private final Clock clock;

	private final Cache byId;

	private final Cache results;

	private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

	public ItineraryService(OtpClient otp, MetaService meta, Views views, ItineraryMapper mapper, AppProperties props,
			Clock clock, CacheManager caches) {
		this.otp = otp;
		this.meta = meta;
		this.views = views;
		this.mapper = mapper;
		this.props = props;
		this.clock = clock;
		this.byId = caches.getCache(CacheConfig.ITINERARY_BY_ID);
		this.results = caches.getCache(CacheConfig.ITINERARIES);
	}

	public ItinerariesResponse plan(ItineraryRequest request, Lang lang) {
		String key = cacheKey(request, lang);
		ItinerariesResponse cached = results.get(key, ItinerariesResponse.class);
		if (cached != null) {
			return cached;
		}
		ItinerariesResponse response = compute(request, lang);
		results.put(key, response);
		return response;
	}

	private ItinerariesResponse compute(ItineraryRequest request, Lang lang) {
		AppMeta m = meta.current();
		List<String> modes = allowedModes(request, m);
		OffsetDateTime when = departure(request);
		boolean arriveBy = request.timeOrNow().mode() == TimeMode.ARRIVE_BY;
		List<SectionQuery> queries = queries(request, modes, m, when, arriveBy);

		// Pas d'abandon ici même si tout est vide : la recherche de nuit (1 bis) peut encore trouver les premiers départs
		Map<String, List<Otp.Itinerary>> raw = runInParallel(queries, lang);

		// 1. Toutes les variantes en transport, une seule par suite de lignes (la meilleure)
		Map<String, Candidate> bySignature = new LinkedHashMap<>();
		ItineraryView walkOnly = collect(raw, request, lang, when, arriveBy, bySignature);

		// 1 bis. Plus rien ne circule à cette heure-ci (la nuit) : premiers départs dans les 10 h qui suivent,
		// comme Citymapper, plutôt que « aucun itinéraire »
		String window = null;
		if (bySignature.isEmpty() && !modes.isEmpty()) {
			window = NIGHT_WINDOW;
			SectionQuery first = transitQuery("FIRST_DEPARTURES", modes, Set.of(), m, request, when, arriveBy,
					reluctance(request), 5);
			first.variables().put("searchWindow", window);
			collect(runInParallel(List.of(first), lang), request, lang, when, arriveBy, bySignature);
		}
		final String searchWindow = window;

		// 2. Deuxième passe : on retire tour à tour chaque ligne du meilleur trajet. OTP ne renvoie que les
		// trajets optimaux ; cette passe fait apparaître les vraies alternatives (louage → train au lieu du louage
		// direct, métro au lieu de la marche…), comme les sections de Citymapper.
		Candidate first = bySignature.values().stream().min(Comparator.comparingDouble(Candidate::cost)).orElse(null);
		if (first != null) {
			List<SectionQuery> second = new ArrayList<>();
			first.view().legs().stream()
				.filter(l -> "TRANSIT".equals(l.type()) && l.line() != null)
				.map(l -> l.line().id())
				.distinct()
				.limit(3)
				.forEach(lineId -> {
					SectionQuery q = transitQuery("WITHOUT_LINE_" + lineId, modes, Set.of(lineId), m, request, when,
							arriveBy, reluctance(request), 3);
					if (searchWindow != null) {
						q.variables().put("searchWindow", searchWindow);
					}
					second.add(q);
				});
			if (!second.isEmpty()) {
				collect(runInParallel(second, lang), request, lang, when, arriveBy, bySignature);
			}
		}

		// 3. On écarte les variantes absurdes (beaucoup plus longues que la meilleure)
		List<Candidate> ranked = bySignature.values().stream().sorted(Comparator.comparingDouble(Candidate::cost))
			.toList();
		List<Candidate> kept = new ArrayList<>();
		if (!ranked.isEmpty()) {
			Candidate best = ranked.getFirst();
			double tolerance = Math.max(40, best.view().durationMin() * 0.75);
			ranked.stream().filter(c -> c.cost() <= best.cost() + tolerance).forEach(kept::add);
		}

		// 4. Sections : suggestions, une section par mode principal, moins de marche, à pied
		int max = props.itineraries().maxPerSection();
		Map<String, ItineraryView> all = new LinkedHashMap<>();
		List<Section> sections = new ArrayList<>();
		List<Candidate> suggested = kept.stream().limit(Math.min(3, max)).toList();
		addSection(sections, all, "SUGGESTED", title("SUGGESTED", lang, m), suggested, request, lang);
		Set<String> shown = new HashSet<>(all.keySet());
		for (String mode : MODE_ORDER) {
			List<Candidate> ofMode = kept.stream().filter(c -> usesSignificantly(c.view(), mode)).limit(max).toList();
			// Une section qui ne fait que répéter les suggestions n'apporte rien : on ne l'affiche pas
			if (ofMode.stream().anyMatch(c -> !shown.contains(c.view().id()))) {
				addSection(sections, all, mode, title(mode, lang, m), ofMode, request, lang);
			}
		}
		if (!suggested.isEmpty()) {
			int bestWalk = suggested.getFirst().view().walkMin();
			List<Candidate> lessWalking = kept.stream()
				.filter(c -> c.view().walkMin() <= bestWalk - 4)
				.sorted(Comparator.comparingInt((Candidate c) -> c.view().walkMin())
					.thenComparingDouble(Candidate::cost))
				.limit(2)
				.toList();
			if (lessWalking.stream().allMatch(c -> shown.contains(c.view().id()))) {
				lessWalking = List.of();
			}
			addSection(sections, all, "LESS_WALKING", title("LESS_WALKING", lang, m), lessWalking, request, lang);
		}
		if (walkOnly != null && walkOnly.durationMin() <= 120) {
			addSection(sections, all, "WALK", title("WALK", lang, m),
					List.of(new Candidate(walkOnly, walkOnly.durationMin(), null)), request, lang);
		}
		if (sections.isEmpty()) {
			throw new ApiException(ApiException.Code.NO_ROUTE, "Aucun itinéraire entre ces deux points");
		}

		String coverage = kept.isEmpty() ? "WALK_ONLY" : coverage(request, m);
		String notice = searchWindow != null && !kept.isEmpty() ? "FIRST_DEPARTURES" : null;
		return new ItinerariesResponse(m.dataVersion(), coverage, notice,
				views.period(views.defaultNetwork(), when.atZoneSameInstant(WebConfig.TUNIS).toLocalDate(), lang),
				sections, all);
	}

	/** Ajoute les itinéraires en transport aux candidats ; renvoie l'itinéraire à pied s'il y en a un. */
	private ItineraryView collect(Map<String, List<Otp.Itinerary>> raw, ItineraryRequest request, Lang lang,
			OffsetDateTime when, boolean arriveBy, Map<String, Candidate> bySignature) {
		ItineraryView walkOnly = null;
		for (var entry : raw.entrySet()) {
			for (Otp.Itinerary it : entry.getValue()) {
				ItineraryView view = withId(mapper.toView(it, request, lang), it);
				if (view.legs().stream().noneMatch(l -> "TRANSIT".equals(l.type()))) {
					if (entry.getKey().equals("WALK") && walkOnly == null) {
						walkOnly = view;
					}
					continue;
				}
				Candidate c = new Candidate(view, cost(view, when, arriveBy), mainMode(view));
				bySignature.merge(signature(view), c, (a, b) -> a.cost() <= b.cost() ? a : b);
			}
		}
		return walkOnly;
	}

	/** Un itinéraire candidat, son coût de classement et son mode principal (plus long temps à bord). */
	private record Candidate(ItineraryView view, double cost, String mainMode) {
	}

	private void addSection(List<Section> sections, Map<String, ItineraryView> all, String key, String title,
			List<Candidate> items, ItineraryRequest request, Lang lang) {
		if (items.isEmpty()) {
			return;
		}
		for (Candidate c : items) {
			all.putIfAbsent(c.view().id(), c.view());
			byId.put(c.view().id(), new Stored(c.view(), request, lang));
		}
		sections.add(new Section(key, title, items.stream().map(c -> c.view().id()).toList()));
	}

	/**
	 * Coût de classement, en minutes : heure d'arrivée (ou de départ en « arriver à »), plus une pénalité par
	 * correspondance et par minute de marche au-delà de 8 min. Proche de ce que ressent le voyageur : 25 min de marche
	 * pour gagner 2 min ne sont pas une bonne suggestion.
	 */
	static double cost(ItineraryView v, OffsetDateTime when, boolean arriveBy) {
		double minutes = arriveBy ? Duration.between(v.departAt(), when).toSeconds() / 60.0
				: Duration.between(when, v.arriveAt()).toSeconds() / 60.0;
		return minutes + 5.0 * v.transfers() + Math.max(0, v.walkMin() - 8);
	}

	static String mainMode(ItineraryView v) {
		Map<String, Integer> minutes = new HashMap<>();
		for (LegView l : v.legs()) {
			if ("TRANSIT".equals(l.type())) {
				minutes.merge(l.mode(), l.durationMin(), Integer::sum);
			}
		}
		return minutes.entrySet().stream().max(Map.Entry.comparingByValue()).map(Map.Entry::getKey).orElse(null);
	}

	/**
	 * Un trajet figure dans la section d'un mode s'il l'emprunte vraiment : au moins 8 min et un quart du temps à
	 * bord. Un trajet louage + métro + TGM apparaît donc sous « Louage » et sous « Train », pas sous « Métro » pour
	 * deux stations.
	 */
	static boolean usesSignificantly(ItineraryView v, String mode) {
		int total = 0;
		int ofMode = 0;
		for (LegView l : v.legs()) {
			if ("TRANSIT".equals(l.type())) {
				total += l.durationMin();
				if (mode.equals(l.mode())) {
					ofMode += l.durationMin();
				}
			}
		}
		return ofMode > 0 && (ofMode >= Math.min(8, total) && ofMode * 4 >= total);
	}

	/** Suite des lignes empruntées : deux variantes avec les mêmes lignes ne sont montrées qu'une fois. */
	private static String signature(ItineraryView v) {
		StringBuilder sb = new StringBuilder();
		for (LegView l : v.legs()) {
			if ("TRANSIT".equals(l.type())) {
				sb.append(l.line() == null ? l.mode() : l.line().id()).append('>');
			}
		}
		return sb.toString();
	}

	/** Recalcule l'itinéraire en prenant un autre départ pour le segment index (puces « autres départs »). */
	public ItineraryView alternative(String id, int index, DepartureChoice choice) {
		Stored stored = byId.get(id, Stored.class);
		if (stored == null) {
			throw new ApiException(ApiException.Code.NOT_FOUND, "Itinéraire expiré ou inconnu : " + id);
		}
		List<LegView> legs = stored.view().legs();
		if (index < 0 || index >= legs.size() || !"TRANSIT".equals(legs.get(index).type())
				|| legs.get(index).departAt() == null) {
			throw new ApiException(ApiException.Code.VALIDATION_ERROR, "Segment " + index + " sans horaires");
		}
		LegView leg = legs.get(index);
		Duration offset = Duration.between(stored.view().departAt(), leg.departAt());
		OffsetDateTime start = choice.departAt().minus(offset).minusMinutes(1);

		Map<String, Object> vars = baseVariables(stored.request(), start, false);
		vars.put("first", 5);
		vars.put("modes", Map.of("transitOnly", true,
				"transit", Map.of("transit", List.of(Map.of("mode", OTP_MODE.getOrDefault(leg.mode(), "BUS"))))));
		vars.put("preferences", preferences(stored.request(), List.of(MetaService.otpId(leg.line().id())), 1.0));
		List<Otp.Itinerary> found = edges(otp.plan(vars, stored.lang()));

		ItineraryView best = null;
		for (Otp.Itinerary it : found) {
			ItineraryView v = withId(mapper.toView(it, stored.request(), stored.lang()), it);
			boolean match = v.legs().stream().anyMatch(l -> "TRANSIT".equals(l.type()) && l.line() != null
					&& l.line().id().equals(leg.line().id()) && choice.departAt().isEqual(l.departAt()));
			if (match) {
				best = v;
				break;
			}
			if (best == null) {
				best = v;
			}
		}
		if (best == null) {
			throw new ApiException(ApiException.Code.NO_ROUTE, "Pas d'itinéraire avec ce départ");
		}
		byId.put(best.id(), new Stored(best, stored.request(), stored.lang()));
		return best;
	}

	// --- Construction des requêtes ----------------------------------------------------------

	private List<String> allowedModes(ItineraryRequest request, AppMeta m) {
		Set<String> available = new LinkedHashSet<>();
		m.lines().values().stream().filter(l -> "active".equals(l.status())).forEach(l -> available.add(l.mode()));
		List<String> wanted = request.preferencesOrDefault().modes();
		return MODE_ORDER.stream().filter(available::contains).filter(x -> wanted == null || wanted.contains(x))
			.toList();
	}

	/**
	 * Requêtes OTP de la première passe, lancées en parallèle (specs/06-api-backend.md §4.1) : tous modes, tous
	 * modes sauf un (fait apparaître les alternatives), moins de marche, et à pied.
	 */
	private List<SectionQuery> queries(ItineraryRequest request, List<String> modes, AppMeta m, OffsetDateTime when,
			boolean arriveBy) {
		double reluctance = reluctance(request);
		List<SectionQuery> queries = new ArrayList<>();
		if (!modes.isEmpty()) {
			queries.add(transitQuery("ALL", modes, Set.of(), m, request, when, arriveBy, reluctance, 5));
			if (modes.size() > 1) {
				for (String mode : modes) {
					List<String> others = modes.stream().filter(x -> !x.equals(mode)).toList();
					queries.add(transitQuery("WITHOUT_" + mode, others, Set.of(), m, request, when, arriveBy,
							reluctance, 3));
				}
			}
			queries.add(transitQuery("LESS_WALKING", modes, Set.of(), m, request, when, arriveBy, 6.0, 3));
		}
		Map<String, Object> walk = baseVariables(request, when, arriveBy);
		walk.put("first", 1);
		walk.put("modes", Map.of("directOnly", true, "direct", List.of("WALK")));
		walk.put("preferences",
				Map.of("street", Map.of("walk", Map.of("speed", request.preferencesOrDefault().speed().metersPerSecond))));
		queries.add(new SectionQuery("WALK", walk));
		return queries;
	}

	private static double reluctance(ItineraryRequest request) {
		return request.preferencesOrDefault().lessWalking() ? 4.0 : 2.0;
	}

	private SectionQuery transitQuery(String key, List<String> modes, Set<String> excludedLines, AppMeta m,
			ItineraryRequest request, OffsetDateTime when, boolean arriveBy, double reluctance, int first) {
		List<String> routes = m.lines().entrySet().stream()
			.filter(e -> "active".equals(e.getValue().status()) && modes.contains(e.getValue().mode())
					&& !excludedLines.contains(e.getKey()))
			.map(e -> MetaService.otpId(e.getKey())).sorted().toList();
		List<Map<String, Object>> otpModes = modes.stream().map(OTP_MODE::get).distinct()
			.map(x -> Map.<String, Object>of("mode", x)).toList();
		Map<String, Object> vars = baseVariables(request, when, arriveBy);
		vars.put("first", first);
		vars.put("modes", Map.of("transitOnly", true, "transit", Map.of("transit", otpModes)));
		vars.put("preferences", preferences(request, routes, reluctance));
		return new SectionQuery(key, vars);
	}

	private Map<String, Object> preferences(ItineraryRequest request, List<String> routes, double reluctance) {
		var prefs = request.preferencesOrDefault();
		Map<String, Object> transit = new HashMap<>();
		transit.put("filters", List.of(Map.of("include", List.of(Map.of("routes", routes)))));
		if (prefs.fewerTransfers()) {
			transit.put("transfer", Map.of("cost", 600));
		}
		return Map.of("street", Map.of("walk", Map.of("speed", prefs.speed().metersPerSecond, "reluctance", reluctance)),
				"transit", transit);
	}

	private Map<String, Object> baseVariables(ItineraryRequest request, OffsetDateTime when, boolean arriveBy) {
		Map<String, Object> vars = new HashMap<>();
		vars.put("from", location(request.from()));
		vars.put("to", location(request.to()));
		vars.put("dateTime", Map.of(arriveBy ? "latestArrival" : "earliestDeparture", when.toString()));
		return vars;
	}

	private static Map<String, Object> location(ItineraryModels.Point p) {
		return Map.of("location", Map.of("coordinate", Map.of("latitude", p.lat(), "longitude", p.lon())),
				"label", p.label() == null ? "" : p.label());
	}

	private OffsetDateTime departure(ItineraryRequest request) {
		var time = request.timeOrNow();
		if (time.mode() == TimeMode.NOW || time.at() == null) {
			return OffsetDateTime.now(clock).truncatedTo(ChronoUnit.MINUTES);
		}
		return time.at();
	}

	// --- Exécution -------------------------------------------------------------------------

	private Map<String, List<Otp.Itinerary>> runInParallel(List<SectionQuery> queries, Lang lang) {
		Map<String, Future<Otp.PlanData>> futures = new LinkedHashMap<>();
		for (SectionQuery q : queries) {
			futures.put(q.key(), executor.submit(() -> otp.plan(q.variables(), lang)));
		}
		long deadline = System.nanoTime() + props.itineraries().parallelTimeout().toNanos();
		Map<String, List<Otp.Itinerary>> out = new LinkedHashMap<>();
		ApiException unavailable = null;
		for (var e : futures.entrySet()) {
			try {
				long left = Math.max(0, deadline - System.nanoTime());
				out.put(e.getKey(), edges(e.getValue().get(left, TimeUnit.NANOSECONDS)));
			}
			catch (java.util.concurrent.ExecutionException ex) {
				if (ex.getCause() instanceof ApiException api) {
					unavailable = api;
				}
				log.warn("Section {} en échec : {}", e.getKey(), ex.getCause().getMessage());
				out.put(e.getKey(), List.of());
			}
			catch (java.util.concurrent.TimeoutException ex) {
				e.getValue().cancel(true);
				log.warn("Section {} trop lente, ignorée", e.getKey());
				out.put(e.getKey(), List.of());
			}
			catch (InterruptedException ex) {
				Thread.currentThread().interrupt();
				throw new ApiException(ApiException.Code.OTP_UNAVAILABLE, "Interrompu");
			}
		}
		if (unavailable != null && out.values().stream().allMatch(List::isEmpty)) {
			throw unavailable;
		}
		return out;
	}

	private static List<Otp.Itinerary> edges(Otp.PlanData data) {
		if (data == null || data.planConnection() == null || data.planConnection().edges() == null) {
			return List.of();
		}
		return data.planConnection().edges().stream().map(Otp.Edge::node).toList();
	}

	// --- Utilitaires -----------------------------------------------------------------------

	private String title(String key, Lang lang, AppMeta m) {
		String[] t = SECTION_TITLES.get(key);
		if (t != null) {
			return lang == Lang.AR ? t[1] : t[0];
		}
		AppMeta.Mode mode = m.modes().get(key);
		return mode == null ? key : I18n.of(mode.name(), lang);
	}

	private String coverage(ItineraryRequest request, AppMeta m) {
		for (AppMeta.Coverage c : m.coverage()) {
			boolean from = Geo.contains(c.polygon(), request.from().lon(), request.from().lat());
			boolean to = Geo.contains(c.polygon(), request.to().lon(), request.to().lat());
			if (from && to && "complete".equals(c.level())) {
				return "FULL";
			}
		}
		return "PARTIAL";
	}

	private static ItineraryView withId(ItineraryView v, Otp.Itinerary it) {
		StringBuilder sig = new StringBuilder();
		for (Otp.Leg l : it.legs()) {
			sig.append(l.mode()).append('|')
				.append(l.route() == null ? "" : l.route().gtfsId()).append('|')
				.append(l.trip() == null ? "" : l.trip().gtfsId()).append('|')
				.append(l.start().scheduledTime()).append('|').append(l.end().scheduledTime()).append(';');
		}
		return new ItineraryView(hash(sig.toString()), v.departAt(), v.arriveAt(), v.durationMin(), v.walkMin(),
				v.transfers(), v.price(), v.summary(), v.nextDepartures(), v.alerts(), v.bounds(), v.legs());
	}

	private static String hash(String s) {
		try {
			byte[] d = MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8));
			return Base64.getUrlEncoder().withoutPadding().encodeToString(d).substring(0, 16);
		}
		catch (NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
	}

	private String cacheKey(ItineraryRequest r, Lang lang) {
		var t = r.timeOrNow();
		OffsetDateTime when = departure(r);
		long bucket = when.toEpochSecond() / (t.mode() == TimeMode.NOW ? 60 : 300);
		var p = r.preferencesOrDefault();
		return String.join("|", round(r.from().lat()), round(r.from().lon()), round(r.to().lat()), round(r.to().lon()),
				String.valueOf(t.mode()), String.valueOf(bucket), String.valueOf(p.modes()),
				String.valueOf(p.lessWalking()), String.valueOf(p.fewerTransfers()), String.valueOf(p.speed()),
				lang.name(), meta.current().dataVersion());
	}

	private static String round(double v) {
		return String.valueOf(Math.round(v * 2000) / 2000.0); // ~50 m
	}

}
