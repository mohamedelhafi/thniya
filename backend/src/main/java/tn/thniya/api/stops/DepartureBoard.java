package tn.thniya.api.stops;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.stereotype.Component;

import tn.thniya.api.common.I18n;
import tn.thniya.api.common.Lang;
import tn.thniya.api.common.WebConfig;
import tn.thniya.api.meta.AppMeta;
import tn.thniya.api.meta.MetaService;
import tn.thniya.api.otp.Otp;
import tn.thniya.api.otp.OtpClient;
import tn.thniya.api.view.Views;
import tn.thniya.api.view.Views.Departure;
import tn.thniya.api.view.Views.LineRef;

/**
 * Tableau des départs d'un arrêt : regroupe les départs OTP par ligne et direction (les trains omnibus et
 * semi-directs d'une même direction sont fusionnés). Les louages affichent une fréquence, jamais une heure.
 */
@Component
public class DepartureBoard {

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record BoardRow(LineRef line, String direction, String headsign, List<Departure> departures,
			boolean noServiceToday, OffsetDateTime nextServiceAt) {
	}

	private final OtpClient otp;

	private final MetaService meta;

	private final Views views;

	private final Clock clock;

	public DepartureBoard(OtpClient otp, MetaService meta, Views views, Clock clock) {
		this.otp = otp;
		this.meta = meta;
		this.views = views;
		this.clock = clock;
	}

	/** Départs dans les prochaines heures, n par ligne et direction. */
	public List<BoardRow> board(String stopId, int perRow, int hours, String onlyLine, String onlyDirection, Lang lang) {
		AppMeta.Stop stop = meta.stop(stopId);
		long now = Instant.now(clock).getEpochSecond();
		Otp.StopData data = otp.stopDepartures(Map.of("id", MetaService.otpId(stopId), "start", now,
				"range", hours * 3600, "n", perRow * 3), lang);
		LocalDate today = LocalDate.now(clock);

		Map<String, List<Departure>> grouped = new LinkedHashMap<>();
		Map<String, String[]> keyInfo = new LinkedHashMap<>();
		if (data.stop() != null && data.stop().stoptimesForPatterns() != null) {
			for (Otp.StoptimesInPattern p : data.stop().stoptimesForPatterns()) {
				String lineId = MetaService.localId(p.pattern().route().gtfsId());
				AppMeta.Line line = meta.lineOrNull(lineId);
				if (line == null || (onlyLine != null && !onlyLine.equals(lineId))) {
					continue;
				}
				String direction = directionId(line, p.pattern().directionId());
				if (onlyDirection != null && !onlyDirection.equals(direction)) {
					continue;
				}
				String key = lineId + "|" + direction;
				keyInfo.putIfAbsent(key, new String[] { lineId, direction });
				for (Otp.Stoptime st : p.stoptimes()) {
					OffsetDateTime at = Instant.ofEpochSecond(st.serviceDay() + st.scheduledDeparture())
						.atZone(WebConfig.TUNIS).toOffsetDateTime();
					grouped.computeIfAbsent(key, k -> new ArrayList<>())
						.add(Departure.scheduled(at, st.trip() == null ? null : st.trip().tripShortName()));
				}
			}
		}

		List<BoardRow> rows = new ArrayList<>();
		// Lignes qui desservent l'arrêt mais sans départ dans la fenêtre : on le dit clairement
		for (String lineId : stop.lines()) {
			AppMeta.Line line = meta.lineOrNull(lineId);
			if (line == null || (onlyLine != null && !onlyLine.equals(lineId))) {
				continue;
			}
			for (AppMeta.Direction d : line.directions()) {
				if (onlyDirection != null && !onlyDirection.equals(d.id())) {
					continue;
				}
				if (!servesInDirection(line, d.id(), stopId)) {
					continue;
				}
				String key = lineId + "|" + d.id();
				keyInfo.putIfAbsent(key, new String[] { lineId, d.id() });
			}
		}

		for (var e : keyInfo.entrySet()) {
			String lineId = e.getValue()[0];
			String direction = e.getValue()[1];
			AppMeta.Line line = meta.line(lineId);
			String headsign = line.directions().stream().filter(d -> d.id().equals(direction)).findFirst()
				.map(d -> I18n.of(d.headsign(), lang)).orElse(null);
			if (isFrequency(line)) {
				rows.add(new BoardRow(views.line(lineId, lang), direction, headsign,
						List.of(frequencyNow(line, lineId)), false, null));
				continue;
			}
			List<Departure> deps = grouped.getOrDefault(e.getKey(), List.of()).stream()
				.sorted(Comparator.comparing(Departure::time)).distinct().limit(perRow).toList();
			OffsetDateTime first = deps.isEmpty() ? null : deps.getFirst().time();
			boolean noneToday = first == null || !first.atZoneSameInstant(WebConfig.TUNIS).toLocalDate().equals(today);
			rows.add(new BoardRow(views.line(lineId, lang), direction, headsign,
					noneToday ? List.of() : deps.stream()
						.filter(dep -> dep.time().atZoneSameInstant(WebConfig.TUNIS).toLocalDate().equals(today)).toList(),
					noneToday, noneToday ? first : null));
		}
		return rows;
	}

	public boolean isFrequency(AppMeta.Line line) {
		AppMeta.Mode mode = meta.current().modes().get(line.mode());
		return "frequency".equals(line.scheduleKind()) || (mode != null && !mode.showsExactTimes());
	}

	/** Fréquence de la tranche horaire en cours pour une ligne à fréquence (louage). */
	public Departure frequencyNow(AppMeta.Line line, String lineId) {
		OffsetDateTime now = OffsetDateTime.now(clock);
		AppMeta.Day day = meta.day(line.network(), now.toLocalDate());
		List<AppMeta.FrequencyBand> bands = bandsFor(line, day);
		int minutes = now.getHour() * 60 + now.getMinute();
		for (AppMeta.FrequencyBand b : bands) {
			if (toMinutes(b.from()) <= minutes && minutes < toMinutes(b.to())) {
				return Departure.frequency(b.headwayMin(), b.from(), b.to());
			}
		}
		return Departure.frequency(null, null, null);
	}

	public List<AppMeta.FrequencyBand> bandsFor(AppMeta.Line line, AppMeta.Day day) {
		if (line.frequencies() == null || line.frequencies().isEmpty()) {
			return List.of();
		}
		if (day != null) {
			var exact = line.frequencies().get(day.period() + ":" + day.dayType());
			if (exact != null) {
				return exact;
			}
			var normal = line.frequencies().get("NORMAL:" + day.dayType());
			if (normal != null) {
				return normal;
			}
		}
		return line.frequencies().values().iterator().next();
	}

	static int toMinutes(String hhmm) {
		String[] p = hhmm.split(":");
		return Integer.parseInt(p[0]) * 60 + Integer.parseInt(p[1]);
	}

	/** directionId GTFS (0/1) = position de la direction dans la ligne (specs/04c §3). */
	static String directionId(AppMeta.Line line, Integer gtfsDirection) {
		int i = gtfsDirection == null ? 0 : gtfsDirection;
		return i < line.directions().size() ? line.directions().get(i).id() : line.directions().getFirst().id();
	}

	private static boolean servesInDirection(AppMeta.Line line, String direction, String stopId) {
		var diagram = line.diagram() == null ? null : line.diagram().get(direction);
		if (diagram == null) {
			return true;
		}
		for (int i = 0; i < diagram.size() - 1; i++) { // le terminus d'arrivée n'a pas de départ
			if (diagram.get(i).stop().equals(stopId)) {
				return true;
			}
		}
		return false;
	}

}
