package tn.thniya.api.itinerary;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import tn.thniya.api.common.Lang;
import tn.thniya.api.common.WebConfig;
import tn.thniya.api.itinerary.ItineraryModels.IntermediateStop;
import tn.thniya.api.itinerary.ItineraryModels.ItineraryRequest;
import tn.thniya.api.itinerary.ItineraryModels.ItineraryView;
import tn.thniya.api.itinerary.ItineraryModels.LegView;
import tn.thniya.api.itinerary.ItineraryModels.StepView;
import tn.thniya.api.itinerary.ItineraryModels.SummaryPart;
import tn.thniya.api.meta.AppMeta;
import tn.thniya.api.meta.MetaService;
import tn.thniya.api.otp.Otp;
import tn.thniya.api.otp.TripIds;
import tn.thniya.api.view.Fares;
import tn.thniya.api.view.Views;
import tn.thniya.api.view.Views.AlertView;
import tn.thniya.api.view.Views.Departure;
import tn.thniya.api.view.Views.LineRef;
import tn.thniya.api.view.Views.Price;
import tn.thniya.api.view.Views.StopRef;

/**
 * Traduit un itinéraire OTP en vue Thniya : mode réel (louage), départs, prix, alertes, langue.
 * Règles : specs/06-api-backend.md §4.1 « Règles d'enrichissement ».
 */
@Component
public class ItineraryMapper {

	private final MetaService meta;

	private final Views views;

	private final Fares fares;

	public ItineraryMapper(MetaService meta, Views views, Fares fares) {
		this.meta = meta;
		this.views = views;
		this.fares = fares;
	}

	public ItineraryView toView(Otp.Itinerary it, ItineraryRequest request, Lang lang) {
		List<LegView> legs = new ArrayList<>();
		for (int i = 0; i < it.legs().size(); i++) {
			Otp.Leg leg = it.legs().get(i);
			boolean first = i == 0;
			boolean last = i == it.legs().size() - 1;
			legs.add(leg.isTransit() ? transit(leg, lang) : walk(leg, request, first, last, lang));
		}

		int walkMin = legs.stream().filter(l -> "WALK".equals(l.type())).mapToInt(LegView::durationMin).sum();
		List<LegView> transits = legs.stream().filter(l -> "TRANSIT".equals(l.type())).toList();
		Map<String, AlertView> alerts = new LinkedHashMap<>();
		transits.forEach(l -> l.alerts().forEach(a -> alerts.putIfAbsent(a.id(), a)));
		List<Departure> next = transits.isEmpty() ? List.of()
				: transits.getFirst().departures() != null ? transits.getFirst().departures()
						: List.of(transits.getFirst().departure());

		OffsetDateTime start = OffsetDateTime.parse(it.start());
		OffsetDateTime end = OffsetDateTime.parse(it.end());
		return new ItineraryView(null, start, end, minutes(java.time.Duration.between(start, end).toSeconds()),
				walkMin, it.numberOfTransfers() == null ? Math.max(0, transits.size() - 1) : it.numberOfTransfers(),
				totalPrice(transits), summary(legs), next, List.copyOf(alerts.values()), bounds(it), legs);
	}

	private LegView walk(Otp.Leg leg, ItineraryRequest request, boolean first, boolean last, Lang lang) {
		StopRef from = place(leg.from(), lang, first ? label(request.from(), lang) : null);
		StopRef to = place(leg.to(), lang, last ? label(request.to(), lang) : null);
		List<StepView> steps = leg.steps() == null ? List.of() : leg.steps().stream()
			.filter(s -> s.distance() != null && s.distance() >= 5)
			.map(s -> new StepView(
					Instructions.step(s.relativeDirection(), s.streetName(), Boolean.TRUE.equals(s.bogusName()), lang),
					s.relativeDirection(), Boolean.TRUE.equals(s.bogusName()) ? null : s.streetName(),
					(int) Math.round(s.distance())))
			.toList();
		return new LegView("WALK", "WALK", null, null, from, to, time(leg.start()), time(leg.end()),
				Math.max(1, minutes(leg.duration())), leg.distance() == null ? null : (int) Math.round(leg.distance()),
				steps, null, null, null, null, false, false, null, List.of(),
				leg.legGeometry() == null ? null : leg.legGeometry().points());
	}

	private LegView transit(Otp.Leg leg, Lang lang) {
		String lineId = MetaService.localId(leg.route() == null ? null : leg.route().gtfsId());
		AppMeta.Line line = meta.lineOrNull(lineId);
		AppMeta.Mode mode = line == null ? null : meta.current().modes().get(line.mode());
		boolean frequency = (mode != null && !mode.showsExactTimes())
				|| (line != null && "frequency".equals(line.scheduleKind()));
		LineRef lineRef = views.line(lineId, lang); // remplacée pour un louage, voir plus bas
		String modeId = line == null ? leg.mode() : line.mode();

		StopRef from = place(leg.from(), lang, null);
		StopRef to = place(leg.to(), lang, null);
		OffsetDateTime departAt = time(leg.start());
		List<AlertView> alerts = views.alerts(departAt.atZoneSameInstant(WebConfig.TUNIS).toLocalDateTime(), lineId,
				from.id(), line == null ? null : line.network(), lang);
		List<IntermediateStop> intermediate = leg.intermediatePlaces() == null ? List.of()
				: leg.intermediatePlaces().stream()
					.map(p -> {
						String sid = p.stop() == null ? null : MetaService.localId(p.stop().gtfsId());
						StopRef ref = views.stop(sid, lang, p.name(), p.lat(), p.lon());
						return new IntermediateStop(sid, ref.name(), frequency ? null : time(p.arrival()), ref.lat(),
								ref.lon());
					})
					.toList();
		String headsign = leg.headsign() != null ? leg.headsign()
				: leg.trip() == null ? null : leg.trip().tripHeadsign();
		if (mode != null && mode.departsWhenFull() && headsign != null) {
			// Louage : la pastille porte la destination du sens emprunté, dans la langue de l'usager
			// (« Bab Alioua » / « باب عليوة »), comme la pancarte derrière le pare-brise
			lineRef = new LineRef(lineRef.id(), lineRef.mode(), headsign, lineRef.name(), lineRef.color(),
					lineRef.textColor(), lineRef.status(), lineRef.estimated());
		}
		Price price = fares.price(lineId, from.id(), to.id());
		String polyline = leg.legGeometry() == null ? null : leg.legGeometry().points();

		if (frequency) {
			TripIds ids = TripIds.parse(leg.trip() == null ? null : leg.trip().gtfsId(), true);
			AppMeta.FrequencyBand band = band(line, ids);
			Integer headway = band == null ? null : band.headwayMin();
			Departure departure = Departure.frequency(headway, band == null ? null : band.from(),
					band == null ? null : band.to());
			return new LegView("TRANSIT", modeId, lineRef, headsign, from, to, null, null,
					Math.max(1, minutes(leg.duration())), null, null, intermediate, null, departure,
					headway == null ? null : Math.max(1, headway / 2), true,
					mode != null && mode.departsWhenFull(), price, alerts, polyline);
		}

		List<Departure> departures = new ArrayList<>();
		departures.add(Departure.scheduled(departAt, leg.trip() == null ? null : leg.trip().tripShortName()));
		if (leg.nextLegs() != null) {
			leg.nextLegs().forEach(n -> departures.add(Departure.scheduled(time(n.start()),
					n.trip() == null ? null : n.trip().tripShortName())));
		}
		return new LegView("TRANSIT", modeId, lineRef, headsign, from, to, departAt, time(leg.end()),
				Math.max(1, minutes(leg.duration())), null, null, intermediate, departures, null, null, false, false,
				price, alerts, polyline);
	}

	private AppMeta.FrequencyBand band(AppMeta.Line line, TripIds ids) {
		if (line == null || line.frequencies() == null || ids == null) {
			return null;
		}
		List<AppMeta.FrequencyBand> bands = line.frequencies().get(ids.period() + ":" + ids.dayType());
		if (bands == null) {
			return null;
		}
		return bands.stream().filter(b -> b.band().equals(ids.band())).findFirst().orElse(null);
	}

	private StopRef place(Otp.Place p, Lang lang, String overrideName) {
		if (p.stop() != null) {
			String sid = MetaService.localId(p.stop().gtfsId());
			return views.stop(sid, lang, p.stop().name(), p.lat(), p.lon());
		}
		return new StopRef(null, overrideName != null ? overrideName : p.name(), null, p.lat(), p.lon(), null);
	}

	private static String label(ItineraryModels.Point point, Lang lang) {
		if (point.label() != null && !point.label().isBlank()) {
			return point.label();
		}
		return lang == Lang.AR ? "النقطة المحددة" : "Point choisi";
	}

	private static List<SummaryPart> summary(List<LegView> legs) {
		List<SummaryPart> parts = new ArrayList<>();
		for (LegView l : legs) {
			if ("WALK".equals(l.type())) {
				if (l.durationMin() >= 1 || legs.size() == 1) {
					parts.add(new SummaryPart("WALK", l.durationMin(), null, null));
				}
			}
			else {
				parts.add(new SummaryPart(l.mode(), null, l.line(), "LOUAGE".equals(l.mode()) ? l.to().name() : null));
			}
		}
		return parts;
	}

	private static Price totalPrice(List<LegView> transits) {
		if (transits.isEmpty()) {
			return new Price(0, "TND", false);
		}
		int sum = 0;
		boolean estimated = false;
		for (LegView l : transits) {
			if (l.price() == null || l.price().millimes() == null) {
				return Price.UNKNOWN;
			}
			sum += l.price().millimes();
			estimated |= l.price().estimated();
		}
		return new Price(sum, "TND", estimated);
	}

	private static double[][] bounds(Otp.Itinerary it) {
		double minLat = 90, minLon = 180, maxLat = -90, maxLon = -180;
		for (Otp.Leg l : it.legs()) {
			for (Otp.Place p : List.of(l.from(), l.to())) {
				if (p.lat() == null || p.lon() == null) {
					continue;
				}
				minLat = Math.min(minLat, p.lat());
				maxLat = Math.max(maxLat, p.lat());
				minLon = Math.min(minLon, p.lon());
				maxLon = Math.max(maxLon, p.lon());
			}
		}
		return new double[][] { { minLon, minLat }, { maxLon, maxLat } };
	}

	private static OffsetDateTime time(Otp.LegTime t) {
		return t == null || t.scheduledTime() == null ? null : OffsetDateTime.parse(t.scheduledTime());
	}

	private static int minutes(Number seconds) {
		return seconds == null ? 0 : (int) Math.round(seconds.doubleValue() / 60.0);
	}

}
