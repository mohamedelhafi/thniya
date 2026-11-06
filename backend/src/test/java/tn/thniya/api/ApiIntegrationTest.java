package tn.thniya.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.InputStream;
import java.time.Clock;
import java.time.OffsetDateTime;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JavaType;
import tools.jackson.databind.json.JsonMapper;

import tn.thniya.api.common.Lang;
import tn.thniya.api.geocode.PhotonClient;
import tn.thniya.api.otp.Otp;
import tn.thniya.api.otp.OtpClient;

/**
 * Tests de l'API sur les vraies données (app-meta.json figé) et de vraies réponses OTP enregistrées.
 * Horloge figée au jeudi 15/10/2026 07:30, jour férié (fête de l'Évacuation) : horaires du dimanche.
 */
@SpringBootTest(properties = { "app.meta-path=src/test/resources/app-meta.json",
		"app.feedback-path=target/feedback-test" })
class ApiIntegrationTest {

	@TestConfiguration
	static class FixedClock {

		@Bean
		@Primary
		Clock testClock() {
			return Clock.fixed(OffsetDateTime.parse("2026-10-15T07:30:00+01:00").toInstant(),
					java.time.ZoneId.of("Africa/Tunis"));
		}

	}

	private static final JsonMapper JSON = JsonMapper.builder()
		.disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
		.build();

	@Autowired
	WebApplicationContext context;

	@MockitoBean
	OtpClient otp;

	/** Photon simulé : liste vide par défaut (recherche d'arrêts seule), comme quand le service est absent. */
	@MockitoBean
	PhotonClient photon;

	MockMvc mvc;

	@BeforeEach
	void setUp() {
		mvc = MockMvcBuilders.webAppContextSetup(context).build();
		when(otp.plan(anyMap(), eq(Lang.FR))).thenReturn(fixture("plan-hl-tunis-fr.json", Otp.PlanData.class));
		when(otp.plan(anyMap(), eq(Lang.AR))).thenReturn(fixture("plan-hl-tunis-ar.json", Otp.PlanData.class));
		when(otp.stopDepartures(anyMap(), any())).thenReturn(fixture("stop-departures-hammamlif.json", Otp.StopData.class));
		when(otp.routeDay(anyMap(), any())).thenReturn(fixture("route-day-20261014.json", Otp.RouteData.class));
	}

	static <T> T fixture(String name, Class<T> type) {
		try (InputStream in = ApiIntegrationTest.class.getResourceAsStream("/otp/" + name)) {
			JavaType t = JSON.getTypeFactory().constructParametricType(Otp.Response.class, type);
			Otp.Response<T> response = JSON.readValue(in, t);
			return response.data();
		}
		catch (Exception e) {
			throw new IllegalStateException(e);
		}
	}

	private static final String TRIP = """
			{"from":{"lat":36.7290,"lon":10.3370,"label":"Hammam Lif centre"},
			 "to":{"lat":36.7957,"lon":10.1810,"label":"Place Barcelone"},
			 "time":{"mode":"DEPART_AT","at":"2026-10-14T07:30:00+01:00"}}""";

	@Test
	void itinerariesAreGroupedInSectionsAndEnriched() throws Exception {
		mvc.perform(post("/api/v1/itineraries").contentType(MediaType.APPLICATION_JSON).content(TRIP))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.sections[0].key").value("SUGGESTED"))
			.andExpect(jsonPath("$.sections[0].title").value("Suggestions"))
			// réseau de test : train seul, la section « Train » répéterait les suggestions, elle est masquée
			.andExpect(jsonPath("$.sections.length()").value(1))
			.andExpect(jsonPath("$.coverage").value("PARTIAL"))
			.andExpect(jsonPath("$.period.id").value("NORMAL"))
			.andExpect(jsonPath("$.itineraries.*.legs[1].mode").value(org.hamcrest.Matchers.everyItem(
					org.hamcrest.Matchers.is("TRAIN"))))
			.andExpect(jsonPath("$.itineraries.*.legs[1].line.publicCode").value(org.hamcrest.Matchers.hasItem("BS")))
			.andExpect(jsonPath("$.itineraries.*.legs[0].from.name")
				.value(org.hamcrest.Matchers.hasItem("Hammam Lif centre")))
			.andExpect(jsonPath("$.itineraries.*.nextDepartures[0].trip").value(org.hamcrest.Matchers.hasItem("134")))
			.andExpect(jsonPath("$.itineraries.*.price.millimes").value(org.hamcrest.Matchers.everyItem(
					org.hamcrest.Matchers.nullValue())));
	}

	@Test
	void arabicRequestReturnsArabicNames() throws Exception {
		mvc.perform(post("/api/v1/itineraries").header("Accept-Language", "ar-TN,ar;q=0.9")
			.contentType(MediaType.APPLICATION_JSON).content(TRIP))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.sections[0].title").value("اقتراحات"))
			.andExpect(jsonPath("$.itineraries.*.legs[1].from.name").value(org.hamcrest.Matchers.hasItem("حمام الأنف")))
			.andExpect(jsonPath("$.itineraries.*.legs[1].line.name").value(org.hamcrest.Matchers.hasItem("الضاحية الجنوبية")));
	}

	@Test
	void stopBoardOnHolidayShowsSundayTrains() throws Exception {
		mvc.perform(get("/api/v1/stops/TRN-HAMMAMLIF"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.name").value("Hammam Lif"))
			.andExpect(jsonPath("$.board.length()").value(2))
			.andExpect(jsonPath("$.board[?(@.direction=='NORD')].departures[0].trip").value("136"));
	}

	@Test
	void lineDetailHasDiagramAndDayCodes() throws Exception {
		mvc.perform(get("/api/v1/lines/SNCFT-BS"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.directions[0].stops.length()").value(18))
			.andExpect(jsonPath("$.directions[0].stops[0].isTerminus").value(true))
			.andExpect(jsonPath("$.dayCodes.B").value("Dimanches et fêtes seulement"))
			.andExpect(jsonPath("$.period.dayType").value("DIMANCHE"));
	}

	@Test
	void timetableGroupsDeparturesByHour() throws Exception {
		mvc.perform(get("/api/v1/lines/SNCFT-BS/timetable").param("direction", "NORD").param("stop", "TRN-HAMMAMLIF")
			.param("date", "2026-10-14"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.kind").value("SCHEDULED"))
			.andExpect(jsonPath("$.count").value(48))
			.andExpect(jsonPath("$.firstDeparture").value("04:50"))
			.andExpect(jsonPath("$.hours[0].hour").value(4));
	}

	@Test
	void geocodeFindsStopsByAliasAndArabic() throws Exception {
		mvc.perform(get("/api/v1/geocode").param("q", "hammem lif"))
			.andExpect(jsonPath("$.results[0].id").value("TRN-HAMMAMLIF"));
		mvc.perform(get("/api/v1/geocode").param("q", "حمّام الأنف"))
			.andExpect(jsonPath("$.results[0].id").value("TRN-HAMMAMLIF"));
		mvc.perform(get("/api/v1/geocode").param("q", "borj sedria"))
			.andExpect(jsonPath("$.results[0].id").value("TRN-BORJCEDRIA"));
	}

	@Test
	void geocodeAddsAddressesAfterStopsWithoutTransitDuplicates() throws Exception {
		var hospital = new PhotonClient.Feature(new PhotonClient.Geometry(java.util.List.of(10.3301, 36.7262)),
				new PhotonClient.Properties("Hôpital régional", "Avenue de la République", null, null, "Hammam Plage",
						"Hammam-Lif", null, "N", 1L, "amenity", "hospital", "house"));
		var sameHospitalAgain = new PhotonClient.Feature(new PhotonClient.Geometry(java.util.List.of(10.3303, 36.7263)),
				new PhotonClient.Properties("Hôpital régional", null, null, null, null, "Hammam-Lif", null, "W", 2L,
						"amenity", "hospital", "house"));
		// arrêt OSM à côté de notre gare TRN-HAMMAMLIF : déjà proposé par notre réseau, donc écarté
		var osmStation = new PhotonClient.Feature(new PhotonClient.Geometry(java.util.List.of(10.3346, 36.7295)),
				new PhotonClient.Properties("Hammam Lif", null, null, null, null, "Hammam-Lif", null, "N", 3L,
						"railway", "station", "house"));
		var street = new PhotonClient.Feature(new PhotonClient.Geometry(java.util.List.of(10.3360, 36.7300)),
				new PhotonClient.Properties(null, "Rue de Hammam Lif", "12", null, null, "Hammam-Lif", null, "N", 4L,
						"place", "house", "house"));
		when(photon.search(eq("hammam lif"), any(), any(), anyInt(), eq(Lang.FR)))
			.thenReturn(java.util.List.of(osmStation, hospital, sameHospitalAgain, street));
		mvc.perform(get("/api/v1/geocode").param("q", "hammam lif").param("limit", "6"))
			.andExpect(jsonPath("$.results[0].type").value("STOP"))
			.andExpect(jsonPath("$.results[0].id").value("TRN-HAMMAMLIF"))
			.andExpect(jsonPath("$.results[?(@.type == 'PLACE')].name")
				.value(org.hamcrest.Matchers.contains("Hôpital régional", "12 Rue de Hammam Lif")))
			.andExpect(jsonPath("$.results[?(@.name == 'Hôpital régional')].area")
				.value(org.hamcrest.Matchers.contains("Avenue de la République, Hammam Plage")));
	}

	@Test
	void mapStopsAreSortedByDistanceToTheCentreNotByIdentifier() throws Exception {
		// centré sur Hammam Lif : la gare la plus proche du centre d'abord (avant : tri alphabétique, TRN-BIRELBEY)
		mvc.perform(get("/api/v1/stops/in-bbox").param("bbox", "10.30,36.70,10.37,36.76").param("zoom", "11"))
			.andExpect(jsonPath("$[0].id").value("TRN-HAMMAMLIF"));
	}

	@Test
	void errorsUseProblemDetailWithStableCodeAndTranslatedTitle() throws Exception {
		mvc.perform(get("/api/v1/lines/INCONNUE").header("Accept-Language", "ar"))
			.andExpect(status().isNotFound())
			.andExpect(jsonPath("$.code").value("NOT_FOUND"))
			.andExpect(jsonPath("$.title").value("غير موجود"));
		mvc.perform(post("/api/v1/itineraries").contentType(MediaType.APPLICATION_JSON)
			.content("{\"from\":{\"lat\":99,\"lon\":10}}"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
	}

	@Test
	void metaExposesTodaysPeriodAndCoverage() throws Exception {
		mvc.perform(get("/api/v1/meta"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.today.SNCFT.dayType").value("DIMANCHE"))
			.andExpect(jsonPath("$.today.SNCFT.holidays[0]").value("Fête de l'évacuation"))
			.andExpect(jsonPath("$.coverage[0].level").value("partial"));
	}

	@Test
	void langHeaderParsing() {
		assertThat(Lang.fromHeader("ar-TN,ar;q=0.9,fr;q=0.8")).isEqualTo(Lang.AR);
		assertThat(Lang.fromHeader("fr-FR")).isEqualTo(Lang.FR);
		assertThat(Lang.fromHeader("en-US")).isEqualTo(Lang.FR);
		assertThat(Lang.fromHeader(null)).isEqualTo(Lang.FR);
	}

}
