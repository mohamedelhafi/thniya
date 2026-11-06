package tn.thniya.api.itinerary;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.OffsetDateTime;
import java.util.List;

import org.junit.jupiter.api.Test;

import tn.thniya.api.itinerary.ItineraryModels.ItineraryView;
import tn.thniya.api.itinerary.ItineraryModels.LegView;

/** Classement et répartition en sections des itinéraires (specs/06-api-backend.md §4.1). */
class ItineraryRankingTest {

	private static final OffsetDateTime T0 = OffsetDateTime.parse("2026-10-14T08:00:00+01:00");

	private static LegView leg(String mode, int minutes) {
		return new LegView("TRANSIT", mode, null, null, null, null, null, null, minutes, null, null, null, null, null,
				null, false, false, null, List.of(), null);
	}

	private static ItineraryView trip(int arriveAfter, int walk, int transfers, LegView... legs) {
		return new ItineraryView("x", T0, T0.plusMinutes(arriveAfter), arriveAfter, walk, transfers, null, null, null,
				null, null, List.of(legs));
	}

	@Test
	void longWalkIsPenalisedMoreThanOneTransfer() {
		ItineraryView walking = trip(106, 35, 1, leg("LOUAGE", 36), leg("BUS", 23));
		ItineraryView metro = trip(106, 19, 2, leg("LOUAGE", 36), leg("METRO", 9), leg("BUS", 25));
		assertThat(ItineraryService.cost(metro, T0, false)).isLessThan(ItineraryService.cost(walking, T0, false));
	}

	@Test
	void shortMetroHopDoesNotPutTripInMetroSection() {
		ItineraryView v = trip(115, 20, 2, leg("TRAIN", 36), leg("METRO", 5), leg("TRAIN", 36));
		assertThat(ItineraryService.usesSignificantly(v, "TRAIN")).isTrue();
		assertThat(ItineraryService.usesSignificantly(v, "METRO")).isFalse();
		assertThat(ItineraryService.mainMode(v)).isEqualTo("TRAIN");
	}

	@Test
	void feederLouageAndTrainBothCount() {
		ItineraryView v = trip(128, 38, 2, leg("LOUAGE", 34), leg("METRO", 9), leg("TRAIN", 36));
		assertThat(ItineraryService.usesSignificantly(v, "LOUAGE")).isTrue();
		assertThat(ItineraryService.usesSignificantly(v, "TRAIN")).isTrue();
	}

}
