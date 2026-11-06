package tn.thniya.api.common;

import java.util.List;

public final class Geo {

	private Geo() {
	}

	/** Distance à vol d'oiseau en mètres. */
	public static double distanceM(double lat1, double lon1, double lat2, double lon2) {
		double r = 6_371_000;
		double dLat = Math.toRadians(lat2 - lat1);
		double dLon = Math.toRadians(lon2 - lon1);
		double h = Math.pow(Math.sin(dLat / 2), 2)
				+ Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) * Math.pow(Math.sin(dLon / 2), 2);
		return 2 * r * Math.asin(Math.sqrt(h));
	}

	/** Point dans un polygone [[lon, lat], …]. */
	public static boolean contains(List<List<Double>> polygon, double lon, double lat) {
		boolean inside = false;
		for (int i = 0, j = polygon.size() - 1; i < polygon.size(); j = i++) {
			double xi = polygon.get(i).get(0), yi = polygon.get(i).get(1);
			double xj = polygon.get(j).get(0), yj = polygon.get(j).get(1);
			if ((yi > lat) != (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) {
				inside = !inside;
			}
		}
		return inside;
	}

}
