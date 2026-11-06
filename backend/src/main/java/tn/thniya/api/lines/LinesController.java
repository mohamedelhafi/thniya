package tn.thniya.api.lines;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.cache.annotation.Cacheable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import tn.thniya.api.common.ApiException;
import tn.thniya.api.common.CacheConfig;
import tn.thniya.api.common.I18n;
import tn.thniya.api.common.Lang;
import tn.thniya.api.common.TextNorm;
import tn.thniya.api.meta.AppMeta;
import tn.thniya.api.meta.MetaService;
import tn.thniya.api.otp.Otp;
import tn.thniya.api.otp.OtpClient;
import tn.thniya.api.otp.TripIds;
import tn.thniya.api.stops.DepartureBoard;
import tn.thniya.api.stops.DepartureBoard.BoardRow;
import tn.thniya.api.view.Views;
import tn.thniya.api.view.Views.AlertView;
import tn.thniya.api.view.Views.LineRef;
import tn.thniya.api.view.Views.PeriodView;

/** Annuaire des lignes, fiche ligne (schéma), horaires par date (specs/06-api-backend.md §4.4, §4.5). */
@RestController
@RequestMapping("/api/v1/lines")
public class LinesController {

	private static final List<String> MODE_ORDER = List.of("TRAIN", "METRO", "BUS", "LOUAGE", "TAXI_COLLECTIF", "FERRY");

	public record LineSummary(LineRef line, String network, List<String> termini, int alerts) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record DiagramStop(String stopId, String name, String area, boolean isTerminus, List<LineRef> interchanges,
			Double lat, Double lon) {
	}

	public record DirectionView(String id, String headsign, List<DiagramStop> stops) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record LineDetail(LineRef line, String longName, String network, String networkUrl, PeriodView period,
			List<AlertView> alerts, List<DirectionView> directions, Map<String, String> notes,
			Map<String, String> dayCodes, List<AppMeta.TimetableVersion> timetableVersions, String scheduleKind,
			String confidence, String verifiedAt) {
	}

	public record Minute(int m, String trip) {
	}

	public record Hour(int hour, List<Minute> minutes) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record Timetable(String date, PeriodView period, String gridPeriod, String direction, String headsign,
			Views.StopRef stop, String kind, List<Hour> hours, List<AppMeta.FrequencyBand> frequencies,
			String firstDeparture, String lastDeparture, int count) {
	}

	private final MetaService meta;

	private final OtpClient otp;

	private final Views views;

	private final DepartureBoard boards;

	private final java.time.Clock clock;

	public LinesController(MetaService meta, OtpClient otp, Views views, DepartureBoard boards, java.time.Clock clock) {
		this.meta = meta;
		this.otp = otp;
		this.views = views;
		this.boards = boards;
		this.clock = clock;
	}

	@GetMapping
	public List<LineSummary> lines(@RequestParam(required = false) String mode,
			@RequestParam(required = false) String q, Lang lang) {
		LocalDateTime now = LocalDateTime.now(clock);
		return meta.current().lines().entrySet().stream()
			.filter(e -> !"draft".equals(e.getValue().status()))
			.filter(e -> mode == null || mode.equals(e.getValue().mode()))
			.filter(e -> q == null || q.isBlank() || TextNorm.score(q, e.getValue().publicCode()) > 0
					|| TextNorm.score(q, I18n.of(e.getValue().name(), Lang.FR)) > 0
					|| TextNorm.score(q, I18n.of(e.getValue().name(), Lang.AR)) > 0)
			.sorted(Comparator.comparingInt((Map.Entry<String, AppMeta.Line> e) -> MODE_ORDER.indexOf(e.getValue().mode()))
				.thenComparing(e -> e.getValue().publicCode()))
			.map(e -> new LineSummary(views.line(e.getKey(), lang),
					I18n.of(meta.current().networks().get(e.getValue().network()).name(), lang),
					e.getValue().directions().stream().map(d -> I18n.of(d.headsign(), lang)).toList(),
					views.alerts(now, e.getKey(), null, e.getValue().network(), lang).size()))
			.toList();
	}

	public record LineGeometry(LineRef line, List<List<Double>> points) {
	}

	/** Tracé de chaque ligne (suite de ses arrêts, [lat, lon]) pour dessiner le réseau sur la carte d'accueil. */
	@GetMapping("/geometry")
	public List<LineGeometry> geometry(Lang lang) {
		List<LineGeometry> out = new ArrayList<>();
		meta.current().lines().forEach((id, line) -> {
			if (!"active".equals(line.status()) || line.diagram() == null || line.diagram().isEmpty()) {
				return;
			}
			var main = line.diagram().get(line.directions().getFirst().id());
			if (main == null) {
				return;
			}
			List<List<Double>> points = main.stream()
				.map(s -> meta.stopOrNull(s.stop()))
				.filter(java.util.Objects::nonNull)
				.map(s -> List.of(s.lat(), s.lon()))
				.toList();
			out.add(new LineGeometry(views.line(id, lang), points));
		});
		return out;
	}

	@GetMapping("/{id}")
	public LineDetail line(@PathVariable String id, Lang lang) {
		AppMeta.Line line = meta.line(id);
		AppMeta.Network network = meta.current().networks().get(line.network());
		List<DirectionView> directions = new ArrayList<>();
		for (AppMeta.Direction d : line.directions()) {
			List<AppMeta.DiagramStop> diagram = line.diagram() == null ? List.of()
					: line.diagram().getOrDefault(d.id(), List.of());
			directions.add(new DirectionView(d.id(), I18n.of(d.headsign(), lang), diagram.stream().map(s -> {
				AppMeta.Stop stop = meta.stopOrNull(s.stop());
				return new DiagramStop(s.stop(), stop == null ? s.stop() : I18n.of(stop.name(), lang),
						stop == null ? null : I18n.of(stop.area(), lang), s.isTerminus(),
						s.interchanges().stream().map(l -> views.line(l, lang)).toList(), stop == null ? null : stop.lat(),
						stop == null ? null : stop.lon());
			}).toList()));
		}
		Map<String, String> notes = new TreeMap<>();
		if (line.notes() != null) {
			line.notes().forEach((k, v) -> notes.put(k, I18n.of(v, lang)));
		}
		Map<String, String> codes = new TreeMap<>();
		if (line.dayCodes() != null) {
			line.dayCodes().forEach((k, v) -> codes.put(k, I18n.of(v.label(), lang)));
		}
		return new LineDetail(views.line(id, lang), I18n.of(line.longName(), lang),
				network == null ? line.network() : I18n.of(network.name(), lang), network == null ? null : network.url(),
				views.period(line.network(), LocalDate.now(clock), lang),
				views.alerts(LocalDateTime.now(clock), id, null, line.network(), lang), directions, notes, codes,
				line.timetableVersions(), line.scheduleKind(), line.confidence(), line.verifiedAt());
	}

	/** Grille horaire d'une journée à un arrêt : la bonne grille (Ramadan, été…) est choisie selon la date. */
	@GetMapping("/{id}/timetable")
	@Cacheable(cacheNames = CacheConfig.TIMETABLE, key = "#id + '|' + #direction + '|' + #stop + '|' + #date + '|' + #lang")
	public Timetable timetable(@PathVariable String id, @RequestParam(required = false) String direction,
			@RequestParam(required = false) String stop, @RequestParam(required = false) LocalDate date, Lang lang) {
		AppMeta.Line line = meta.line(id);
		LocalDate day = date == null ? LocalDate.now(clock) : date;
		AppMeta.Direction dir = line.directions().stream()
			.filter(d -> direction == null || d.id().equals(direction)).findFirst()
			.orElseThrow(() -> new ApiException(ApiException.Code.NOT_FOUND, "Direction inconnue : " + direction));
		int dirIndex = line.directions().indexOf(dir);
		List<AppMeta.DiagramStop> diagram = line.diagram() == null ? List.of()
				: line.diagram().getOrDefault(dir.id(), List.of());
		String stopId = stop != null ? stop : diagram.isEmpty() ? null : diagram.getFirst().stop();
		PeriodView period = views.period(line.network(), day, lang);

		if (boards.isFrequency(line)) {
			var bands = boards.bandsFor(line, meta.day(line.network(), day));
			return new Timetable(day.toString(), period, null, dir.id(), I18n.of(dir.headsign(), lang),
					views.stop(stopId, lang), "FREQUENCY", null, bands,
					bands.isEmpty() ? null : bands.getFirst().from(), bands.isEmpty() ? null : bands.getLast().to(), 0);
		}

		Otp.RouteData data = otp.routeDay(Map.of("id", MetaService.otpId(id),
				"date", day.format(DateTimeFormatter.BASIC_ISO_DATE)), lang);
		TreeMap<Integer, List<Minute>> byHour = new TreeMap<>();
		String gridPeriod = null;
		List<Integer> all = new ArrayList<>();
		if (data.route() != null) {
			for (Otp.PatternNode p : data.route().patterns()) {
				if (p.directionId() != null && p.directionId() != dirIndex) {
					continue;
				}
				for (Otp.TripNode trip : p.tripsForDate()) {
					for (Otp.TripStoptime st : trip.stoptimes()) {
						if (!MetaService.otpId(stopId).equals(st.stop().gtfsId())) {
							continue;
						}
						int seconds = st.scheduledDeparture();
						all.add(seconds);
						byHour.computeIfAbsent(seconds / 3600, h -> new ArrayList<>())
							.add(new Minute(seconds % 3600 / 60, trip.tripShortName()));
						TripIds ids = TripIds.parse(trip.gtfsId(), false);
						if (ids != null && ids.period() != null) {
							gridPeriod = ids.period();
						}
					}
				}
			}
		}
		List<Hour> hours = byHour.entrySet().stream()
			.map(e -> new Hour(e.getKey(), e.getValue().stream().sorted(Comparator.comparingInt(Minute::m)).toList()))
			.toList();
		all.sort(Integer::compare);
		return new Timetable(day.toString(), period, gridPeriod, dir.id(), I18n.of(dir.headsign(), lang),
				views.stop(stopId, lang), "SCHEDULED", hours, null, all.isEmpty() ? null : hhmm(all.getFirst()),
				all.isEmpty() ? null : hhmm(all.getLast()), all.size());
	}

	/** Prochains passages d'une ligne à un arrêt (appui sur un arrêt dans le schéma de ligne). */
	@GetMapping("/{id}/stops/{stopId}/departures")
	public List<BoardRow> departures(@PathVariable String id, @PathVariable String stopId,
			@RequestParam(required = false) String direction, @RequestParam(defaultValue = "4") int limit, Lang lang) {
		meta.line(id);
		return boards.board(stopId, Math.min(limit, 10), 24, id, direction, lang);
	}

	private static String hhmm(int seconds) {
		return String.format("%02d:%02d", seconds / 3600, seconds % 3600 / 60);
	}

}
