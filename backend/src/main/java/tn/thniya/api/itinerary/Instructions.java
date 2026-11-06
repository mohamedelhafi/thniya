package tn.thniya.api.itinerary;

import java.util.Map;

import tn.thniya.api.common.Lang;

/** Consignes de marche courtes et à l'impératif (specs/13-design-ux.md §8), en français et en arabe. */
final class Instructions {

	private Instructions() {
	}

	private static final Map<String, String[]> VERBS = Map.ofEntries(
			Map.entry("DEPART", new String[] { "Partez", "انطلق" }),
			Map.entry("CONTINUE", new String[] { "Continuez", "واصل" }),
			Map.entry("LEFT", new String[] { "Tournez à gauche", "انعطف يسارا" }),
			Map.entry("SLIGHTLY_LEFT", new String[] { "Serrez à gauche", "انعطف قليلا إلى اليسار" }),
			Map.entry("HARD_LEFT", new String[] { "Tournez franchement à gauche", "انعطف بحدة إلى اليسار" }),
			Map.entry("RIGHT", new String[] { "Tournez à droite", "انعطف يمينا" }),
			Map.entry("SLIGHTLY_RIGHT", new String[] { "Serrez à droite", "انعطف قليلا إلى اليمين" }),
			Map.entry("HARD_RIGHT", new String[] { "Tournez franchement à droite", "انعطف بحدة إلى اليمين" }),
			Map.entry("UTURN_LEFT", new String[] { "Faites demi-tour", "استدر للخلف" }),
			Map.entry("UTURN_RIGHT", new String[] { "Faites demi-tour", "استدر للخلف" }),
			Map.entry("CIRCLE_CLOCKWISE", new String[] { "Prenez le rond-point", "خذ المفترق الدائري" }),
			Map.entry("CIRCLE_COUNTERCLOCKWISE", new String[] { "Prenez le rond-point", "خذ المفترق الدائري" }),
			Map.entry("ELEVATOR", new String[] { "Prenez l'ascenseur", "خذ المصعد" }),
			Map.entry("ENTER_STATION", new String[] { "Entrez dans la gare", "ادخل المحطة" }),
			Map.entry("EXIT_STATION", new String[] { "Sortez de la gare", "اخرج من المحطة" }),
			Map.entry("FOLLOW_SIGNS", new String[] { "Suivez les panneaux", "اتبع اللافتات" }));

	static String step(String relativeDirection, String street, boolean bogusName, Lang lang) {
		String[] verb = VERBS.getOrDefault(relativeDirection == null ? "CONTINUE" : relativeDirection,
				VERBS.get("CONTINUE"));
		String text = lang == Lang.AR ? verb[1] : verb[0];
		if (street != null && !street.isBlank() && !bogusName) {
			text += lang == Lang.AR ? " في " + street : " sur " + street;
		}
		return text;
	}

}
