package tn.thniya.api.common;

import java.io.IOException;
import java.time.Clock;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.slf4j.MDC;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.MethodParameter;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {

	public static final ZoneId TUNIS = ZoneId.of("Africa/Tunis");

	private final AppProperties props;

	WebConfig(AppProperties props) {
		this.props = props;
	}

	@Bean
	Clock clock() {
		return Clock.system(TUNIS);
	}

	/** CORS : seulement utile pour un client web (une app mobile n'est pas concernée). specs/03 §4. */
	@Override
	public void addCorsMappings(CorsRegistry registry) {
		if (!props.corsAllowedOrigins().isEmpty()) {
			registry.addMapping("/api/**")
				.allowedOriginPatterns(props.corsAllowedOrigins().toArray(String[]::new))
				.allowedMethods("GET", "POST")
				.maxAge(3600);
		}
	}

	/** Permet d'écrire « Lang lang » dans un contrôleur : déduit de l'en-tête Accept-Language. */
	@Override
	public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
		resolvers.add(new HandlerMethodArgumentResolver() {
			@Override
			public boolean supportsParameter(MethodParameter parameter) {
				return parameter.getParameterType() == Lang.class;
			}

			@Override
			public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer mav,
					NativeWebRequest request, WebDataBinderFactory binderFactory) {
				return Lang.fromHeader(request.getHeader("Accept-Language"));
			}
		});
	}

	/** Reprend l'X-Request-Id de nginx (ou en crée un) pour le relier aux logs. */
	@Component
	@Order(Ordered.HIGHEST_PRECEDENCE)
	static class RequestIdFilter extends OncePerRequestFilter {

		@Override
		protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
				throws ServletException, IOException {
			String id = request.getHeader("X-Request-Id");
			if (id == null || id.isBlank() || id.length() > 64) {
				id = UUID.randomUUID().toString();
			}
			MDC.put("requestId", id);
			response.setHeader("X-Request-Id", id);
			try {
				chain.doFilter(request, response);
			}
			finally {
				MDC.remove("requestId");
			}
		}

	}

}
