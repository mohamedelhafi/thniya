package tn.thniya.api.otp;

import tn.thniya.api.meta.MetaService;

/**
 * Lecture des identifiants de voyages générés (specs/04c-generation-gtfs.md §3) :
 * grille     LIGNE:VERSION:PERIODE:TYPE_JOUR:NUMERO
 * fréquence  LIGNE:PERIODE:TYPE_JOUR:TRANCHE:PARCOURS
 */
public record TripIds(String line, String version, String period, String dayType, String train, String band,
		String pattern) {

	public static TripIds parse(String otpTripId, boolean frequency) {
		String id = MetaService.localId(otpTripId);
		if (id == null) {
			return null;
		}
		String[] p = id.split(":");
		if (frequency && p.length == 5) {
			return new TripIds(p[0], null, p[1], p[2], null, p[3], p[4]);
		}
		if (!frequency && p.length == 5) {
			return new TripIds(p[0], p[1], p[2], p[3], p[4], null, null);
		}
		return new TripIds(p[0], null, null, null, null, null, null);
	}

}
