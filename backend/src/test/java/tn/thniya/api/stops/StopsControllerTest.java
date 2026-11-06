package tn.thniya.api.stops;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;

/** Importance des arrêts sur la carte d'accueil : en vue large, seuls les rangs 0 et 1 sont affichés. */
class StopsControllerTest {

	@Test
	void railStationsComeFirstThenOtherStationsThenPlainStops() {
		assertThat(StopsController.mapRank("station", List.of("TRAIN"))).isZero();
		assertThat(StopsController.mapRank("station", List.of("METRO", "BUS"))).isZero();
		assertThat(StopsController.mapRank("stop", List.of("METRO"))).isZero();
		assertThat(StopsController.mapRank("louage_station", List.of())).isEqualTo(1);
		assertThat(StopsController.mapRank("station", List.of("BUS"))).isEqualTo(1);   // pôle de bus, gare routière
		assertThat(StopsController.mapRank("stop", List.of("BUS"))).isEqualTo(2);      // simple arrêt de bus
		assertThat(StopsController.mapRank("hail_point", List.of("LOUAGE"))).isEqualTo(2);
	}

}
