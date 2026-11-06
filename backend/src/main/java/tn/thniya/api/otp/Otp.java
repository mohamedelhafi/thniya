package tn.thniya.api.otp;

import java.util.List;

/** Réponses de l'API GraphQL d'OTP 2.10, limitées aux champs demandés dans resources/graphql. */
public final class Otp {

	private Otp() {
	}

	public record Response<T>(T data, List<Error> errors) {
	}

	public record Error(String message) {
	}

	// --- plan.graphql ---------------------------------------------------------------------

	public record PlanData(PlanConnection planConnection) {
	}

	public record PlanConnection(List<RoutingError> routingErrors, List<Edge> edges) {
	}

	public record RoutingError(String code, String inputField, String description) {
	}

	public record Edge(Itinerary node) {
	}

	public record Itinerary(String start, String end, Double duration, Integer numberOfTransfers, Double walkDistance,
			List<Leg> legs) {
	}

	public record Leg(String mode, Double distance, Double duration, Boolean transitLeg, String serviceDate,
			String headsign, LegTime start, LegTime end, Place from, Place to, Route route, Trip trip,
			Geometry legGeometry, List<Place> intermediatePlaces, List<Step> steps, List<NextLeg> nextLegs) {

		public boolean isTransit() {
			return Boolean.TRUE.equals(transitLeg);
		}

	}

	public record NextLeg(LegTime start, LegTime end, Trip trip) {
	}

	public record LegTime(String scheduledTime) {
	}

	public record Place(String name, Double lat, Double lon, Stop stop, LegTime arrival) {
	}

	public record Stop(String gtfsId, String name, String platformCode) {
	}

	public record Route(String gtfsId, String shortName, String longName) {
	}

	public record Trip(String gtfsId, String tripShortName, String tripHeadsign) {
	}

	public record Geometry(String points) {
	}

	public record Step(Double distance, String relativeDirection, String absoluteDirection, String streetName,
			Boolean bogusName) {
	}

	// --- stop-departures.graphql ----------------------------------------------------------

	public record StopData(StopNode stop) {
	}

	public record StopNode(String gtfsId, String name, List<StoptimesInPattern> stoptimesForPatterns) {
	}

	public record StoptimesInPattern(PatternRef pattern, List<Stoptime> stoptimes) {
	}

	public record PatternRef(String code, Integer directionId, String headsign, RouteRef route) {
	}

	public record RouteRef(String gtfsId) {
	}

	public record Stoptime(Integer scheduledDeparture, Long serviceDay, String headsign, Trip trip) {
	}

	// --- route-day.graphql ----------------------------------------------------------------

	public record RouteData(RouteNode route) {
	}

	public record RouteNode(String gtfsId, List<PatternNode> patterns) {
	}

	public record PatternNode(String code, Integer directionId, String headsign, List<StopRef> stops,
			List<TripNode> tripsForDate) {
	}

	public record StopRef(String gtfsId) {
	}

	public record TripNode(String gtfsId, String tripShortName, List<TripStoptime> stoptimes) {
	}

	public record TripStoptime(StopRef stop, Integer scheduledDeparture, Integer scheduledArrival) {
	}

	// --- stops-nearby.graphql -------------------------------------------------------------

	public record NearbyData(StopConnection stopsByRadius) {
	}

	public record StopConnection(List<StopEdge> edges) {
	}

	public record StopEdge(StopAtDistance node) {
	}

	public record StopAtDistance(Integer distance, Stop stop) {
	}

}
