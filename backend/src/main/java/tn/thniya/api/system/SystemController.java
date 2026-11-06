package tn.thniya.api.system;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonInclude;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import tools.jackson.databind.json.JsonMapper;

import tn.thniya.api.common.AppProperties;
import tn.thniya.api.common.I18n;
import tn.thniya.api.common.Lang;
import tn.thniya.api.geocode.AddressSearch;
import tn.thniya.api.meta.AppMeta;
import tn.thniya.api.meta.MetaService;
import tn.thniya.api.view.Views;
import tn.thniya.api.view.Views.AlertView;
import tn.thniya.api.view.Views.LineRef;
import tn.thniya.api.view.Views.PeriodView;

/** Méta, recherche (arrêts, puis adresses et lieux Photon), alertes, signalements. */
@RestController
@RequestMapping("/api/v1")
public class SystemController {

	public record ModeView(String name, String icon, String color, boolean showsExactTimes, boolean departsWhenFull) {
	}

	public record CoverageView(String id, String name, String level, List<String> modes, List<List<Double>> polygon) {
	}

	public record MetaView(String dataVersion, String generatedAt, AppMeta.Window window, Map<String, ModeView> modes,
			Map<String, String> networks, Map<String, PeriodView> today, List<CoverageView> coverage, int lines,
			int stops) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record Place(String type, String id, String name, String area, double lat, double lon, List<String> modes,
			List<LineRef> lines, Integer distanceM) {
	}

	public record GeocodeResponse(List<Place> results) {
	}

	public record AlertEntry(AlertView alert, List<LineRef> lines, List<String> stops, String from, String to,
			boolean activeNow) {
	}

	public record Feedback(@NotNull String type, @Size(max = 2000) String text, Map<String, Object> context,
			String appVersion) {
	}

	private final MetaService meta;

	private final Views views;

	private final AppProperties props;

	private final java.time.Clock clock;

	private final AddressSearch addressSearch;

	private final JsonMapper json = JsonMapper.builder().build();

	public SystemController(MetaService meta, Views views, AppProperties props, java.time.Clock clock,
			AddressSearch addressSearch) {
		this.meta = meta;
		this.addressSearch = addressSearch;
		this.views = views;
		this.props = props;
		this.clock = clock;
	}

	@GetMapping("/meta")
	public MetaView meta(Lang lang) {
		AppMeta m = meta.current();
		Map<String, ModeView> modes = new LinkedHashMap<>();
		m.modes().forEach((id, mode) -> modes.put(id, new ModeView(I18n.of(mode.name(), lang), mode.icon(),
				mode.color(), mode.showsExactTimes(), mode.departsWhenFull())));
		Map<String, String> networks = new LinkedHashMap<>();
		m.networks().forEach((id, n) -> networks.put(id, I18n.of(n.name(), lang)));
		Map<String, PeriodView> today = new LinkedHashMap<>();
		m.calendar().keySet().forEach(n -> today.put(n, views.period(n, LocalDate.now(clock), lang)));
		return new MetaView(m.dataVersion(), m.generatedAt(), m.window(), modes, networks, today,
				m.coverage().stream().map(c -> new CoverageView(c.id(), I18n.of(c.name(), lang), c.level(), c.modes(),
						c.polygon())).toList(),
				m.lines().size(), m.stops().size());
	}

	/**
	 * Autocomplétion : d'abord nos arrêts (noms FR/AR + alias, derja) classés par pertinence puis proximité, ensuite les
	 * adresses et lieux OSM (Photon). Les adresses gardent au moins la moitié des places quand il y en a.
	 */
	@GetMapping("/geocode")
	public GeocodeResponse geocode(@RequestParam String q, @RequestParam(required = false) Double lat,
			@RequestParam(required = false) Double lon, @RequestParam(defaultValue = "10") int limit, Lang lang) {
		int max = Math.max(1, Math.min(limit, 20));
		List<AddressSearch.Address> addresses = addressSearch.search(q, lat, lon, max, lang, meta.index());
		List<Place> stops = meta.index().search(q, lat, lon, 200).stream()
			.filter(x -> !"entrance".equals(x.entry().stop().kind()) && !"platform".equals(x.entry().stop().kind()))
			.limit(max)
			.map(x -> {
				AppMeta.Stop s = x.entry().stop();
				return new Place("STOP", x.entry().id(), I18n.of(s.name(), lang), I18n.of(s.area(), lang), s.lat(),
						s.lon(),
						s.lines().stream().map(meta::lineOrNull).filter(java.util.Objects::nonNull)
							.map(AppMeta.Line::mode).distinct().toList(),
						s.lines().stream().map(l -> views.line(l, lang)).toList(),
						lat == null ? null : (int) Math.round(x.distanceM()));
			})
			.toList();
		int addressSlots = Math.min(addresses.size(), Math.max(max / 2, max - stops.size()));
		List<Place> results = new ArrayList<>(stops.subList(0, Math.min(stops.size(), max - addressSlots)));
		addresses.stream()
			.limit(addressSlots)
			.forEach(a -> results.add(new Place("PLACE", a.id(), a.name(), a.area(), a.lat(), a.lon(), null, null,
					a.distanceM())));
		return new GeocodeResponse(results);
	}

	/** Nom du lieu sous un point : l'arrêt le plus proche à moins de 150 m, sinon « Point sur la carte ». */
	@GetMapping("/reverse")
	public Place reverse(@RequestParam double lat, @RequestParam double lon, Lang lang) {
		var nearest = meta.index().nearest(lat, lon, 150);
		if (nearest != null) {
			var s = nearest.entry().stop();
			return new Place("STOP", nearest.entry().id(), I18n.of(s.name(), lang), I18n.of(s.area(), lang), s.lat(),
					s.lon(), null, null, (int) Math.round(nearest.distanceM()));
		}
		return new Place("POINT", null, lang == Lang.AR ? "نقطة على الخريطة" : "Point sur la carte", null, lat, lon,
				null, null, null);
	}

	/** État du réseau : alertes actives et à venir. */
	@GetMapping("/alerts")
	public List<AlertEntry> alerts(@RequestParam(required = false) String line,
			@RequestParam(required = false) String stop, @RequestParam(required = false) String network, Lang lang) {
		LocalDateTime now = LocalDateTime.now(clock);
		List<AlertEntry> out = new ArrayList<>();
		for (AppMeta.Alert a : meta.current().alerts()) {
			var scope = a.scope();
			if (line != null && (scope.lines() == null || !scope.lines().contains(line))) {
				continue;
			}
			if (stop != null && (scope.stops() == null || !scope.stops().contains(stop))) {
				continue;
			}
			if (network != null && (scope.networks() == null || !scope.networks().contains(network))) {
				continue;
			}
			var upcoming = a.activePeriods().stream().filter(p -> !LocalDateTime.parse(p.to()).isBefore(now))
				.min(Comparator.comparing(AppMeta.ActivePeriod::from));
			if (upcoming.isEmpty()) {
				continue;
			}
			var p = upcoming.get();
			boolean active = !LocalDateTime.parse(p.from()).isAfter(now);
			out.add(new AlertEntry(views.alert(a, lang),
					scope.lines() == null ? List.of() : scope.lines().stream().map(l -> views.line(l, lang)).toList(),
					scope.stops() == null ? List.of() : scope.stops(), p.from(), p.to(), active));
		}
		return out;
	}

	/** Signaler une erreur de données. Jusqu'au lot 8 : fichier JSONL (specs/06 §7). */
	@PostMapping("/feedback")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public void feedback(@Valid @RequestBody Feedback feedback, Lang lang) throws IOException {
		Path dir = Path.of(props.feedbackPath());
		Files.createDirectories(dir);
		Map<String, Object> entry = new LinkedHashMap<>();
		entry.put("receivedAt", OffsetDateTime.now(clock).toString());
		entry.put("lang", lang.code());
		entry.put("dataVersion", meta.current().dataVersion());
		entry.put("type", feedback.type());
		entry.put("text", feedback.text());
		entry.put("context", feedback.context());
		entry.put("appVersion", feedback.appVersion());
		Files.writeString(dir.resolve("feedback-" + LocalDate.now(clock) + ".jsonl"),
				json.writeValueAsString(entry) + "\n", StandardCharsets.UTF_8, StandardOpenOption.CREATE,
				StandardOpenOption.APPEND);
	}

}
