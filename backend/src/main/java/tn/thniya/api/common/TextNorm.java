package tn.thniya.api.common;

import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Normalisation pour la recherche : « Hammam-Lif », « hammem lif » et « حمّام الأنف » doivent se rapprocher.
 * Latin : minuscules, sans accents, sans ponctuation. Arabe : sans voyelles brèves ni tatweel, alef/ya/ta marbuta
 * unifiés.
 */
public final class TextNorm {

	private static final Pattern MARKS = Pattern.compile("\\p{M}+");

	private static final Pattern ARABIC_DIACRITICS = Pattern.compile("[\\u064B-\\u065F\\u0670\\u0640]");

	private static final Pattern NON_WORD = Pattern.compile("[^\\p{L}\\p{N}]+");

	private TextNorm() {
	}

	public static String normalize(String text) {
		if (text == null) {
			return "";
		}
		String s = ARABIC_DIACRITICS.matcher(text).replaceAll("");
		s = s.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ى', 'ي').replace('ة', 'ه');
		s = MARKS.matcher(Normalizer.normalize(s, Normalizer.Form.NFD)).replaceAll("");
		s = NON_WORD.matcher(s.toLowerCase(Locale.ROOT)).replaceAll(" ").trim();
		return s;
	}

	/**
	 * Score de correspondance : 100 = identique, 80 = commence par, 60 = un mot commence par, 40 = contient, 0 = non.
	 */
	public static int score(String query, String candidate) {
		return scoreNormalized(normalize(query), normalize(candidate));
	}

	/** Comme {@link #score} pour des textes déjà normalisés (index pré-calculé). */
	public static int scoreNormalized(String q, String c) {
		if (q.isEmpty() || c.isEmpty()) {
			return 0;
		}
		if (c.equals(q)) {
			return 100;
		}
		if (c.startsWith(q)) {
			return 80;
		}
		if (c.replace(" ", "").startsWith(q.replace(" ", ""))) {
			return 75;
		}
		for (String word : c.split(" ")) {
			if (word.startsWith(q)) {
				return 60;
			}
		}
		return c.contains(q) ? 40 : 0;
	}

}
