package tn.thniya.api.common;

/** Texte bilingue tel qu'il vient de app-meta.json. */
public record I18n(String fr, String ar) {

	/** Texte dans la langue demandée, le français à défaut : jamais de champ vide. */
	public String in(Lang lang) {
		if (lang == Lang.AR && ar != null && !ar.isBlank()) {
			return ar;
		}
		return fr;
	}

	public static String of(I18n value, Lang lang) {
		return value == null ? null : value.in(lang);
	}

}
