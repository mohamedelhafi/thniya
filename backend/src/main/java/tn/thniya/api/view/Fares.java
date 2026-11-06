package tn.thniya.api.view;

import java.util.Map;
import java.util.Objects;

import org.springframework.stereotype.Component;

import tn.thniya.api.meta.AppMeta;
import tn.thniya.api.meta.MetaService;
import tn.thniya.api.view.Views.Price;

/**
 * Prix d'un trajet sur une ligne, à partir des tarifs d'app-meta.json (specs/04-donnees-modele.md « Tarifs »).
 * Jamais de prix inventé : sans tarif saisi, le prix reste inconnu.
 */
@Component
public class Fares {

	private final MetaService meta;

	public Fares(MetaService meta) {
		this.meta = meta;
	}

	public Price price(String lineId, String fromStop, String toStop) {
		AppMeta m = meta.current();
		AppMeta.Line line = meta.lineOrNull(lineId);
		if (line == null || line.fare() == null || m.fares() == null) {
			return Price.UNKNOWN;
		}
		AppMeta.Fare fare = m.fares().get(line.fare());
		if (fare == null) {
			return Price.UNKNOWN;
		}
		boolean estimated = fare.estimated() || "ESTIMATION".equals(line.confidence());
		return switch (fare.model()) {
			case "flat" -> fare.flat() == null ? Price.UNKNOWN : new Price(fare.flat(), fare.currency(), estimated);
			case "od_pairs" -> pair(fare, fromStop, toStop, estimated);
			default -> Price.UNKNOWN;
		};
	}

	/**
	 * Couple exact (ou via les gares parentes) ; sinon, pour une montée ou descente en route (louage hélé), le prix
	 * du trajet complet le plus cher de la ligne, signalé comme estimé : c'est ce que le chauffeur demande en général.
	 */
	private Price pair(AppMeta.Fare fare, String from, String to, boolean estimated) {
		Map<String, Integer> pairs = fare.pairs();
		if (pairs == null || pairs.isEmpty()) {
			return Price.UNKNOWN;
		}
		for (String a : new String[] { from, parent(from) }) {
			for (String b : new String[] { to, parent(to) }) {
				Integer p = a == null || b == null ? null : pairs.get(a + "|" + b);
				if (p != null) {
					return new Price(p, fare.currency(), estimated);
				}
			}
		}
		int max = pairs.values().stream().filter(Objects::nonNull).mapToInt(Integer::intValue).max().orElse(-1);
		return max < 0 ? Price.UNKNOWN : new Price(max, fare.currency(), true);
	}

	private String parent(String stopId) {
		AppMeta.Stop s = meta.stopOrNull(stopId);
		return s == null ? null : s.parent();
	}

}
