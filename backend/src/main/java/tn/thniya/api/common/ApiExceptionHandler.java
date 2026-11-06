package tn.thniya.api.common;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

/** Toutes les erreurs au format RFC 9457 avec un champ « code » stable. */
@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class ApiExceptionHandler {

	private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

	@ExceptionHandler(ApiException.class)
	ProblemDetail api(ApiException e, HttpServletRequest request, HttpServletResponse response) {
		response.setHeader("Cache-Control", "no-store"); // une erreur ne doit jamais rester en cache
		if (e.code().status.is5xxServerError()) {
			log.warn("{} : {}", e.code(), e.getMessage(), e.getCause());
		}
		return problem(e.code().status, e.code(), e.getMessage(), Lang.fromHeader(request.getHeader("Accept-Language")));
	}

	@ExceptionHandler({ MethodArgumentNotValidException.class, HandlerMethodValidationException.class,
			MissingServletRequestParameterException.class, MethodArgumentTypeMismatchException.class,
			HttpMessageNotReadableException.class, IllegalArgumentException.class })
	ProblemDetail validation(Exception e, HttpServletRequest request, HttpServletResponse response) {
		response.setHeader("Cache-Control", "no-store");
		return problem(HttpStatus.BAD_REQUEST, ApiException.Code.VALIDATION_ERROR, e.getMessage(),
				Lang.fromHeader(request.getHeader("Accept-Language")));
	}

	private static ProblemDetail problem(HttpStatus status, ApiException.Code code, String detail, Lang lang) {
		ProblemDetail pd = ProblemDetail.forStatusAndDetail(status, detail);
		pd.setTitle(code.title(lang));
		pd.setProperty("code", code.name());
		return pd;
	}

}
