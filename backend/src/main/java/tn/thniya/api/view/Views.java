package tn.thniya.api.view;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.stereotype.Component;

import tn.thniya.api.common.I18n;
import tn.thniya.api.common.Lang;
import tn.thniya.api.meta.AppMeta;
import tn.thniya.api.meta.MetaService;

/** Objets de réponse partagés par tous les endpoints (specs/06-api-backend.md §3) et leur construction. */
@Component
public class Views {

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record LineRef(String id, String mode, String publicCode, String name, String color, String textColor,
			String status, Boolean estimated) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record StopRef(String id, String name, String area, Double lat, Double lon, String platform) {
	}

	/** Un départ : heure exacte (SCHEDULED) ou intervalle (FREQUENCY, louages). */
	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record Departure(String type, OffsetDateTime time, String trip, Integer headwayMin, String from, String to,
			boolean estimated) {

		public static Departure scheduled(OffsetDateTime time, String trip) {
			return new Departure("SCHEDULED", time, trip, null, null, null, false);
		}

		public static Departure frequency(Integer headwayMin, String from, String to) {
			return new Departure("FREQUENCY", null, null, headwayMin, from, to, true);
		}

	}

	/** Prix en millimes ; millimes = null quand le tarif n'est pas encore connu. */
	public record Price(Integer millimes, String currency, boolean estimated) {

		public static final Price UNKNOWN = new Price(null, "TND", true);

	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record AlertView(String id, String effect, String severity, String title, String body, String url) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record PeriodView(String id, String name, boolean banner, String dayType, List<String> holidays) {
	}

	private final MetaService meta;

	public Views(MetaService meta) {
		this.meta = meta;
	}

	public LineRef line(String lineId, Lang lang) {
		AppMeta.Line l = meta.lineOrNull(lineId);
		if (l == null) {
			return new LineRef(lineId, null, lineId, lineId, "#555555", "#FFFFFF", "unknown", null);
		}
		// estimated : horaires/durées estimés (calculés ou relevé non officiel), l'app affiche « estimé »
		return new LineRef(lineId, l.mode(), l.publicCode(), I18n.of(l.name(), lang), l.color(), l.textColor(),
				l.status(), "ESTIMATION".equals(l.confidence()) ? Boolean.TRUE : null);
	}

	public StopRef stop(String stopId, Lang lang, String fallbackName, Double lat, Double lon) {
		AppMeta.Stop s = meta.stopOrNull(stopId);
		if (s == null) {
			return new StopRef(stopId, fallbackName, null, lat, lon, null);
		}
		return new StopRef(stopId, I18n.of(s.name(), lang), I18n.of(s.area(), lang), s.lat(), s.lon(),
				s.platformCode());
	}

	public StopRef stop(String stopId, Lang lang) {
		return stop(stopId, lang, stopId, null, null);
	}

	public AlertView alert(AppMeta.Alert a, Lang lang) {
		return new AlertView(a.id(), a.effect(), a.severity(), I18n.of(a.title(), lang), I18n.of(a.body(), lang),
				a.url());
	}

	public List<AlertView> alerts(LocalDateTime at, String line, String stop, String network, Lang lang) {
		return meta.alertsAt(at, line, stop, network).stream().map(a -> alert(a, lang)).toList();
	}

	/** Période horaire du jour pour un réseau (bandeau « Horaires de Ramadan »…). */
	public PeriodView period(String network, LocalDate date, Lang lang) {
		AppMeta.Day day = meta.day(network, date);
		if (day == null) {
			return null;
		}
		AppMeta.Period p = meta.current().periods().get(day.period());
		return new PeriodView(day.period(), p == null ? day.period() : I18n.of(p.name(), lang),
				p != null && p.showBanner(), day.dayType(),
				day.holidays().stream().map(h -> I18n.of(h.name(), lang)).toList());
	}

	/** Réseau principal (le premier qui a un calendrier) pour les bandeaux généraux. */
	public String defaultNetwork() {
		return meta.current().calendar().keySet().stream().sorted().findFirst().orElse(null);
	}

}
