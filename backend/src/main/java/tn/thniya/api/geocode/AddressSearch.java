package tn.thniya.api.geocode;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Service;

import tn.thniya.api.common.Geo;
import tn.thniya.api.common.Lang;
import tn.thniya.api.common.TextNorm;
import tn.thniya.api.geocode.PhotonClient.Feature;
import tn.thniya.api.geocode.PhotonClient.Properties;
import tn.thniya.api.meta.StopIndex;

/**
 * Adresses et lieux (Photon) à afficher après les arrêts dans la recherche (specs/09 §1) : noms lisibles, sans les
 * arrêts que notre réseau connaît déjà, sans doublons (même nom à quelques centaines de mètres ou dans le même
 * quartier). On suit l'ordre de pertinence de Photon (biaisé par la position) : le premier de chaque doublon reste.
 */
@Service
public class AddressSearch {

	/** Un arrêt OSM à moins de cette distance d'un de nos arrêts est un doublon : notre arrêt est déjà proposé. */
	static final double TRANSIT_DUPLICATE_M = 150;

	/** Deux résultats de même nom aussi proches = un seul lieu (tronçons d'une même rue, magasin et galerie…). */
	static final double SAME_PLACE_M = 300;

	public record Address(String id, String name, String area, double lat, double lon, Integer distanceM) {
	}

	private final PhotonClient photon;

	public AddressSearch(PhotonClient photon) {
		this.photon = photon;
	}

	public List<Address> search(String query, Double lat, Double lon, int limit, Lang lang, StopIndex stops) {
		List<Address> out = new ArrayList<>();
		List<String[]> keys = new ArrayList<>();   // nom et sous-titre normalisés de chaque résultat gardé
		for (Feature f : photon.search(query, lat, lon, limit + 5, lang)) {
			Properties p = f.properties();
			List<Double> c = f.geometry() == null ? null : f.geometry().coordinates();
			if (p == null || c == null || c.size() < 2) {
				continue;
			}
			double fLat = c.get(1), fLon = c.get(0);
			String name = name(p);
			if (name == null) {
				continue;
			}
			if (isTransitStop(p) && !stops.within(fLat, fLon, TRANSIT_DUPLICATE_M).isEmpty()) {
				continue;
			}
			String norm = TextNorm.normalize(name);
			String area = area(p, name, lang);
			String normArea = TextNorm.normalize(area);
			// même nom tout près, ou même nom dans le même quartier (tronçons d'une même rue) : un seul résultat
			boolean duplicate = false;
			for (int i = 0; i < out.size() && !duplicate; i++) {
				Address a = out.get(i);
				duplicate = keys.get(i)[0].equals(norm) && (Geo.distanceM(a.lat(), a.lon(), fLat, fLon) < SAME_PLACE_M
						|| (!normArea.isEmpty() && keys.get(i)[1].equals(normArea)));
			}
			if (duplicate) {
				continue;
			}
			Integer distance = lat == null || lon == null ? null
					: (int) Math.round(Geo.distanceM(lat, lon, fLat, fLon));
			String id = p.osm_type() == null || p.osm_id() == null ? null : "osm:" + p.osm_type() + p.osm_id();
			out.add(new Address(id, name, area, fLat, fLon, distance));
			keys.add(new String[] { norm, normArea });
			if (out.size() >= limit) {
				break;
			}
		}
		return out;
	}

	/** Nom affiché : le nom du lieu, sinon « rue + numéro ». */
	static String name(Properties p) {
		if (p.name() != null && !p.name().isBlank()) {
			return p.name().strip();
		}
		if (p.street() != null && !p.street().isBlank()) {
			return p.housenumber() == null ? p.street().strip() : p.housenumber().strip() + " " + p.street().strip();
		}
		return null;
	}

	/** Sous-titre : rue (si le nom n'est pas déjà la rue), quartier, ville — deux éléments au plus. */
	static String area(Properties p, String name, Lang lang) {
		List<String> parts = new ArrayList<>();
		Set<String> seen = new HashSet<>();                  // sans répéter un lieu (casse et accents ignorés)
		seen.add(TextNorm.normalize(name));
		if (p.name() != null && p.street() != null) {
			add(parts, seen, p.housenumber() == null ? p.street() : p.housenumber() + " " + p.street());
		}
		for (String s : new String[] { p.district(), p.locality(), p.city(), p.county() }) {
			add(parts, seen, s);
		}
		List<String> kept = parts.subList(0, Math.min(2, parts.size()));
		return kept.isEmpty() ? null : String.join(lang == Lang.AR ? "، " : ", ", kept);
	}

	private static void add(List<String> parts, Set<String> seen, String value) {
		if (value != null && !value.isBlank() && seen.add(TextNorm.normalize(value))) {
			parts.add(value.strip());
		}
	}

	/** Arrêt ou gare dans OSM (notre réseau les connaît mieux, avec leurs lignes). */
	static boolean isTransitStop(Properties p) {
		String key = p.osm_key(), value = p.osm_value();
		return "public_transport".equals(key) || ("highway".equals(key) && "bus_stop".equals(value))
				|| ("railway".equals(key) && Set.of("station", "halt", "tram_stop", "stop").contains(value))
				|| ("amenity".equals(key) && Set.of("bus_station", "taxi").contains(value));
	}

}
