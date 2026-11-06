package tn.thniya.api.meta;

import java.util.List;
import java.util.Map;

import tn.thniya.api.common.I18n;

/** Contrat app-meta.json produit par le générateur de données (specs/04c-generation-gtfs.md §4). */
public record AppMeta(
		String dataVersion,
		String generatedAt,
		Window window,
		Map<String, Mode> modes,
		Map<String, Network> networks,
		Map<String, Line> lines,
		Map<String, Stop> stops,
		Map<String, Hub> hubs,
		Map<String, Fare> fares,
		Map<String, Period> periods,
		Map<String, Map<String, Day>> calendar,
		List<Alert> alerts,
		List<Coverage> coverage) {

	public record Window(String from, String to) {
	}

	public record Mode(I18n name, String icon, String color, boolean showsExactTimes, boolean departsWhenFull,
			Integer seats) {
	}

	public record Network(I18n name, I18n longName, String url, String phone) {
	}

	public record Line(String network, String mode, String publicCode, I18n name, I18n longName, String color,
			String textColor, String status, String scheduleKind, List<Direction> directions,
			Map<String, List<DiagramStop>> diagram, Map<String, I18n> notes, Map<String, DayCode> dayCodes,
			String fare, String confidence, String verifiedAt, List<TimetableVersion> timetableVersions,
			Map<String, List<FrequencyBand>> frequencies, Map<String, ServiceHours> serviceHours) {
	}

	public record Direction(String id, I18n headsign) {
	}

	public record DiagramStop(String stop, int branch, boolean isTerminus, List<String> interchanges) {
	}

	public record DayCode(List<String> days, I18n label) {
	}

	public record TimetableVersion(String id, String validFrom, String validTo, String source, int corrections) {
	}

	public record FrequencyBand(String band, String from, String to, Integer headwayMin) {
	}

	public record ServiceHours(String first, String last) {
	}

	public record Stop(String kind, I18n name, List<String> aliases, I18n area, double lat, double lon,
			String parent, String hub, List<String> lines, String platformCode, String code, String confidence) {
	}

	public record Hub(I18n name, List<String> members, List<String> aliases) {
	}

	/**
	 * Tarif plein en millimes, version en vigueur au début de la fenêtre. flat : prix unique ; od_pairs : prix
	 * par couple « départ|arrivée ».
	 */
	public record Fare(String model, String currency, boolean estimated, String validFrom, Integer flat,
			Map<String, Integer> pairs) {
	}

	public record Period(I18n name, boolean showBanner) {
	}

	public record Day(String period, String dayType, List<Holiday> holidays) {
	}

	public record Holiday(String id, I18n name, boolean estimated) {
	}

	public record Alert(String id, String effect, String severity, Scope scope, List<ActivePeriod> activePeriods,
			I18n title, I18n body, String url) {
	}

	public record Scope(List<String> lines, List<String> stops, List<String> networks) {
	}

	public record ActivePeriod(String from, String to) {
	}

	public record Coverage(String id, I18n name, String level, List<String> modes, List<List<Double>> polygon) {
	}

}
