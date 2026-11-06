package tn.thniya.api.itinerary;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonInclude;

import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;

import tn.thniya.api.view.Views.AlertView;
import tn.thniya.api.view.Views.Departure;
import tn.thniya.api.view.Views.LineRef;
import tn.thniya.api.view.Views.PeriodView;
import tn.thniya.api.view.Views.Price;
import tn.thniya.api.view.Views.StopRef;

/** Contrats de POST /api/v1/itineraries (specs/06-api-backend.md §4.1). */
public final class ItineraryModels {

	private ItineraryModels() {
	}

	// --- Requête --------------------------------------------------------------------------

	public record ItineraryRequest(@NotNull @Valid Point from, @NotNull @Valid Point to, @Valid TimeSpec time,
			@Valid Preferences preferences) {

		public TimeSpec timeOrNow() {
			return time == null ? new TimeSpec(TimeMode.NOW, null) : time;
		}

		public Preferences preferencesOrDefault() {
			return preferences == null ? Preferences.DEFAULT : preferences;
		}

	}

	public record Point(@NotNull @DecimalMin("30") @DecimalMax("38") Double lat,
			@NotNull @DecimalMin("7") @DecimalMax("12") Double lon, String label, String stopId) {
	}

	public enum TimeMode {

		NOW, DEPART_AT, ARRIVE_BY

	}

	public record TimeSpec(TimeMode mode, OffsetDateTime at) {
	}

	public enum WalkSpeed {

		SLOW(1.0), NORMAL(1.3), FAST(1.6);

		final double metersPerSecond;

		WalkSpeed(double metersPerSecond) {
			this.metersPerSecond = metersPerSecond;
		}

	}

	public record Preferences(List<String> modes, boolean lessWalking, boolean fewerTransfers, WalkSpeed walkSpeed) {

		static final Preferences DEFAULT = new Preferences(null, false, false, WalkSpeed.NORMAL);

		WalkSpeed speed() {
			return walkSpeed == null ? WalkSpeed.NORMAL : walkSpeed;
		}

	}

	// --- Réponse --------------------------------------------------------------------------

	/** notice : FIRST_DEPARTURES quand plus rien ne circule à l'heure demandée (nuit) et qu'on montre les premiers départs. */
	public record ItinerariesResponse(String dataVersion, String coverage, String notice, PeriodView period,
			List<Section> sections,
			Map<String, ItineraryView> itineraries) {
	}

	public record Section(String key, String title, List<String> itineraryIds) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record ItineraryView(String id, OffsetDateTime departAt, OffsetDateTime arriveAt, int durationMin,
			int walkMin, int transfers, Price price, List<SummaryPart> summary, List<Departure> nextDepartures,
			List<AlertView> alerts, double[][] bounds, List<LegView> legs) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record SummaryPart(String mode, Integer minutes, LineRef line, String destination) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record LegView(String type, String mode, LineRef line, String headsign, StopRef from, StopRef to,
			OffsetDateTime departAt, OffsetDateTime arriveAt, int durationMin, Integer distanceM, List<StepView> steps,
			List<IntermediateStop> intermediateStops, List<Departure> departures, Departure departure, Integer waitMin,
			boolean durationEstimated, boolean departsWhenFull, Price price, List<AlertView> alerts, String polyline) {
	}

	public record StepView(String instruction, String direction, String street, int distanceM) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record IntermediateStop(String stopId, String name, OffsetDateTime time, Double lat, Double lon) {
	}

	public record DepartureChoice(@NotNull OffsetDateTime departAt) {
	}

}
