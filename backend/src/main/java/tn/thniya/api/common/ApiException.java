package tn.thniya.api.common;

import org.springframework.http.HttpStatus;

/** Erreur métier avec un code stable (non traduit) et un titre traduit. Voir specs/06-api-backend.md §3. */
public class ApiException extends RuntimeException {

	public enum Code {

		VALIDATION_ERROR(HttpStatus.BAD_REQUEST, "Requête invalide", "طلب غير صالح"),
		NOT_FOUND(HttpStatus.NOT_FOUND, "Introuvable", "غير موجود"),
		OUT_OF_AREA(HttpStatus.UNPROCESSABLE_CONTENT, "Hors de la zone couverte", "خارج المنطقة المغطاة"),
		NO_ROUTE(HttpStatus.NOT_FOUND, "Aucun itinéraire trouvé", "لم يتم العثور على أي مسار"),
		OTP_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "Service momentanément indisponible", "الخدمة غير متوفرة حاليا"),
		META_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "Données en cours de chargement", "جاري تحميل البيانات");

		final HttpStatus status;
		final String titleFr;
		final String titleAr;

		Code(HttpStatus status, String titleFr, String titleAr) {
			this.status = status;
			this.titleFr = titleFr;
			this.titleAr = titleAr;
		}

		public String title(Lang lang) {
			return lang == Lang.AR ? titleAr : titleFr;
		}

	}

	private final Code code;

	public ApiException(Code code, String detail) {
		super(detail);
		this.code = code;
	}

	public ApiException(Code code, String detail, Throwable cause) {
		super(detail, cause);
		this.code = code;
	}

	public Code code() {
		return code;
	}

}
