package tn.thniya.api.stops;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import com.fasterxml.jackson.annotation.JsonInclude;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import tn.thniya.api.common.ApiException;
import tn.thniya.api.common.Geo;
import tn.thniya.api.common.I18n;
import tn.thniya.api.common.Lang;
import tn.thniya.api.meta.AppMeta;
import tn.thniya.api.meta.MetaService;
import tn.thniya.api.meta.StopIndex;
import tn.thniya.api.otp.Otp;
import tn.thniya.api.otp.OtpClient;
import tn.thniya.api.stops.DepartureBoard.BoardRow;
import tn.thniya.api.view.Fares;
import tn.thniya.api.view.Views;
import tn.thniya.api.view.Views.AlertView;
import tn.thniya.api.view.Views.Departure;
import tn.thniya.api.view.Views.LineRef;
import tn.thniya.api.view.Views.StopRef;

/** Arrêts : carte, à proximité, fiche arrêt (specs/06-api-backend.md §4, §4.3). */
@RestController
@RequestMapping("/api/v1")
@Validated
public class StopsController {

	private static final double WALK_SPEED = 1.3;

	public record MapStop(String id, String kind, String name, double lat, double lon, List<String> modes,
			List<String> lines) {
	}

	public record NearbyStop(StopRef stop, int distanceM, int walkMin, List<String> modes, List<BoardRow> lines) {
	}

	public record NearbyResponse(List<NearbyStop> stops) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record HubMember(StopRef stop, int walkMin) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record LouageDestination(LineRef line, String destination, String bay, Views.Price price,
			Departure departure, AppMeta.ServiceHours serviceHours) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record StopDetail(String id, String kind, String name, String area, double lat, double lon,
			List<String> modes, List<LineRef> lines, List<HubMember> hub, List<AlertView> alerts, List<BoardRow> board,
			List<LouageDestination> louageDestinations, String confidence) {
	}

	private final MetaService meta;

	private final OtpClient otp;

	private final DepartureBoard boards;

	private final Views views;

	private final java.time.Clock clock;

	private final Fares fares;

	private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

	public StopsController(MetaService meta, OtpClient otp, DepartureBoard boards, Views views, Fares fares,
			java.time.Clock clock) {
		this.fares = fares;
		this.meta = meta;
		this.otp = otp;
		this.boards = boards;
		this.views = views;
		this.clock = clock;
	}

	/** Zoom à partir duquel la carte montre aussi les simples arrêts (bus, arrêts d'autocar en ville). */
	static final double STOPS_ZOOM = 14;

	/** Sans zoom fourni : emprise plus large que ≈ 0,06° de longitude (zoom 14 sur un téléphone) = vue large. */
	static final double WIDE_BBOX_DEG = 0.06;

	static final int MAX_MAP_STOPS = 500;

	/**
	 * Arrêts visibles sur la carte : léger, sans départs (bbox = ouest,sud,est,nord). Vue large (zoom &lt; 14) : seules
	 * les gares et stations (train, métro, TGM, louages, gares routières, pôles de bus). Toujours les plus importantes
	 * d'abord, puis les plus proches du centre, dans la limite de 500.
	 */
	@GetMapping("/stops/in-bbox")
	public List<MapStop> inBbox(@RequestParam String bbox, @RequestParam(required = false) Double zoom, Lang lang) {
		String[] p = bbox.split(",");
		if (p.length != 4) {
			throw new IllegalArgumentException("bbox attendu : ouest,sud,est,nord");
		}
		double w = Double.parseDouble(p[0]), s = Double.parseDouble(p[1]);
		double e = Double.parseDouble(p[2]), n = Double.parseDouble(p[3]);
		boolean wide = zoom != null ? zoom < STOPS_ZOOM : e - w > WIDE_BBOX_DEG;
		double cLat = (s + n) / 2, cLon = (w + e) / 2;
		return meta.index().inBbox(w, s, e, n).stream()
			.filter(x -> isBoardable(x.stop()))
			.map(x -> new Ranked(x, modes(x.stop())))
			.filter(r -> !wide || r.rank() < 2)
			.sorted(Comparator.comparingInt(Ranked::rank)
				.thenComparingDouble(r -> Geo.distanceM(cLat, cLon, r.entry().stop().lat(), r.entry().stop().lon()))
				.thenComparing(r -> r.entry().id()))
			.limit(MAX_MAP_STOPS)
			.map(r -> new MapStop(r.entry().id(), r.entry().stop().kind(), I18n.of(r.entry().stop().name(), lang),
					r.entry().stop().lat(), r.entry().stop().lon(), r.modes(), r.entry().stop().lines()))
			.toList();
	}

	/** Importance sur la carte : 0 rail (train, métro, TGM), 1 autre gare ou station, 2 simple arrêt. */
	static int mapRank(String kind, List<String> modes) {
		if (modes.contains("TRAIN") || modes.contains("METRO")) {
			return 0;
		}
		return "stop".equals(kind) || "hail_point".equals(kind) ? 2 : 1;
	}

	private record Ranked(StopIndex.Entry entry, List<String> modes) {

		int rank() {
			return mapRank(entry.stop().kind(), modes);
		}

	}

	/** À proximité : arrêts à distance de marche, avec les prochains départs par ligne. */
	@GetMapping("/nearby")
	public NearbyResponse nearby(@RequestParam double lat, @RequestParam double lon,
			@RequestParam(defaultValue = "800") @Min(100) @Max(3000) int radius,
			@RequestParam(required = false) String mode, Lang lang) {
		Otp.NearbyData data = otp.stopsNearby(Map.of("lat", lat, "lon", lon, "radius", radius), lang);
		List<Otp.StopAtDistance> found = data.stopsByRadius() == null ? List.of()
				: data.stopsByRadius().edges().stream().map(Otp.StopEdge::node).toList();

		List<Otp.StopAtDistance> selected = new ArrayList<>();
		for (Otp.StopAtDistance s : found) {
			AppMeta.Stop stop = meta.stopOrNull(MetaService.localId(s.stop().gtfsId()));
			if (stop == null || !isBoardable(stop) || (mode != null && !modes(stop).contains(mode))) {
				continue;
			}
			selected.add(s);
		}
		selected.sort(Comparator.comparingInt(Otp.StopAtDistance::distance));
		List<Future<NearbyStop>> futures = selected.stream().limit(8).map(s -> executor.submit(() -> {
			String id = MetaService.localId(s.stop().gtfsId());
			AppMeta.Stop stop = meta.stop(id);
			return new NearbyStop(views.stop(id, lang), s.distance(), walkMinutes(s.distance()), modes(stop),
					boards.board(id, 2, 3, null, null, lang));
		})).toList();
		List<NearbyStop> out = new ArrayList<>();
		for (Future<NearbyStop> f : futures) {
			try {
				out.add(f.get());
			}
			catch (Exception ex) {
				throw new ApiException(ApiException.Code.OTP_UNAVAILABLE, "Départs indisponibles", ex);
			}
		}
		return new NearbyResponse(out);
	}

	/** Fiche arrêt / station : tableau des départs, destinations de louage, pôle d'échange, alertes. */
	@GetMapping("/stops/{id}")
	public StopDetail stop(@PathVariable String id, Lang lang) {
		AppMeta.Stop stop = meta.stop(id);
		List<LineRef> lines = stop.lines().stream().map(l -> views.line(l, lang)).toList();
		List<BoardRow> board = boards.board(id, 3, 24, null, null, lang);

		// Louages au départ d'ici : une entrée par destination réellement desservie depuis cette station
		// (seulement les modes qui partent quand ils sont pleins ; les bus et métros sont dans le tableau des départs)
		List<LouageDestination> louages = new ArrayList<>();
		for (String lineId : stop.lines()) {
			AppMeta.Line line = meta.lineOrNull(lineId);
			AppMeta.Mode mode = line == null ? null : meta.current().modes().get(line.mode());
			if (mode == null || !mode.departsWhenFull() || line.diagram() == null) {
				continue;
			}
			var day = meta.day(line.network(), java.time.LocalDate.now(clock));
			String key = day == null ? null : day.period() + ":" + day.dayType();
			for (AppMeta.Direction d : line.directions()) {
				List<AppMeta.DiagramStop> diagram = line.diagram().getOrDefault(d.id(), List.of());
				boolean servesHere = diagram.stream().anyMatch(x -> x.stop().equals(id));
				if (!servesHere || diagram.getLast().stop().equals(id)) {
					continue; // ce sens ne part pas d'ici (on y arrive)
				}
				String destination = I18n.of(d.headsign(), lang);
				LineRef ref = views.line(lineId, lang);
				// pastille du louage = sa destination, comme dans les itinéraires
				ref = new LineRef(ref.id(), ref.mode(), destination, ref.name(), ref.color(), ref.textColor(),
						ref.status(), ref.estimated());
				louages.add(new LouageDestination(ref, destination, stop.platformCode(),
						fares.price(lineId, id, diagram.getLast().stop()), boards.frequencyNow(line, lineId),
						line.serviceHours() == null || key == null ? null : line.serviceHours().get(key)));
			}
		}

		List<HubMember> hub = new ArrayList<>();
		if (stop.hub() != null) {
			AppMeta.Hub h = meta.current().hubs().get(stop.hub());
			if (h != null) {
				for (String member : h.members()) {
					if (member.equals(id)) {
						continue;
					}
					AppMeta.Stop other = meta.stopOrNull(member);
					if (other != null) {
						double d = Geo.distanceM(stop.lat(), stop.lon(), other.lat(), other.lon()) * 1.3;
						hub.add(new HubMember(views.stop(member, lang), walkMinutes((int) d)));
					}
				}
			}
		}
		var now = java.time.LocalDateTime.now(clock);
		var networks = new LinkedHashSet<String>();
		stop.lines().forEach(l -> {
			var line = meta.lineOrNull(l);
			if (line != null) {
				networks.add(line.network());
			}
		});
		List<AlertView> alerts = new ArrayList<>(views.alerts(now, null, id, null, lang));
		stop.lines().forEach(l -> views.alerts(now, l, null, null, lang).stream()
			.filter(a -> alerts.stream().noneMatch(x -> x.id().equals(a.id()))).forEach(alerts::add));

		return new StopDetail(id, stop.kind(), I18n.of(stop.name(), lang), I18n.of(stop.area(), lang), stop.lat(),
				stop.lon(), modes(stop), lines, hub.isEmpty() ? null : hub, alerts, board,
				louages.isEmpty() ? null : louages, stop.confidence());
	}

	private List<String> modes(AppMeta.Stop stop) {
		return stop.lines().stream().map(meta::lineOrNull).filter(java.util.Objects::nonNull).map(AppMeta.Line::mode)
			.distinct().toList();
	}

	private static boolean isBoardable(AppMeta.Stop s) {
		return !"entrance".equals(s.kind()) && !"platform".equals(s.kind()) && !"louage_bay".equals(s.kind());
	}

	static int walkMinutes(int meters) {
		return Math.max(1, (int) Math.round(meters / WALK_SPEED / 60.0));
	}

}
