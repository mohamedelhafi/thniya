package tn.thniya.api.common;

import java.util.Locale;

/** Langues de l'app. Toute réponse est déjà traduite dans la langue demandée (specs/08-i18n-fr-ar.md). */
public enum Lang {

	FR, AR;

	/** « ar-TN,ar;q=0.9,fr;q=0.8 » → AR. Toute autre langue → FR. */
	public static Lang fromHeader(String acceptLanguage) {
		if (acceptLanguage == null || acceptLanguage.isBlank()) {
			return FR;
		}
		for (String part : acceptLanguage.split(",")) {
			String tag = part.split(";")[0].trim().toLowerCase(Locale.ROOT);
			if (tag.startsWith("ar")) {
				return AR;
			}
			if (tag.startsWith("fr")) {
				return FR;
			}
		}
		return FR;
	}

	public String code() {
		return name().toLowerCase(Locale.ROOT);
	}

}
