package tn.thniya.api.common;

import java.util.List;
import java.util.regex.Pattern;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.filter.ShallowEtagHeaderFilter;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Cache HTTP des lectures (specs/06-api-backend.md §5) : la passerelle nginx et les téléphones gardent les réponses
 * le temps indiqué, l'ETag évite de renvoyer un corps inchangé (304). Les données ne changent qu'à la publication ;
 * les départs, eux, vieillissent vite.
 */
@Configuration
public class HttpCaching implements WebMvcConfigurer {

	private record Rule(Pattern path, int maxAgeSeconds) {
	}

	private static final List<Rule> RULES = List.of(
			new Rule(Pattern.compile("^/api/v1/lines/[^/]+/departures$"), 15),
			new Rule(Pattern.compile("^/api/v1/(meta|lines|lines/geometry)$"), 300),
			new Rule(Pattern.compile("^/api/v1/lines/[^/]+(/timetable)?$"), 300),
			new Rule(Pattern.compile("^/api/v1/stops/in-bbox$"), 120),
			new Rule(Pattern.compile("^/api/v1/(geocode|reverse)$"), 300),
			new Rule(Pattern.compile("^/api/v1/alerts$"), 60),
			new Rule(Pattern.compile("^/api/v1/(nearby|stops/[^/]+)$"), 15));

	static int maxAge(String path) {
		for (Rule r : RULES) {
			if (r.path().matcher(path).matches()) {
				return r.maxAgeSeconds();
			}
		}
		return 0;
	}

	@Override
	public void addInterceptors(InterceptorRegistry registry) {
		registry.addInterceptor(new HandlerInterceptor() {
			@Override
			public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
				if ("GET".equals(request.getMethod())) {
					int seconds = maxAge(request.getRequestURI());
					response.setHeader("Cache-Control", seconds > 0 ? "public, max-age=" + seconds : "no-store");
					response.setHeader("Vary", "Accept-Language");
				}
				return true;
			}
		}).addPathPatterns("/api/v1/**");
	}

	/** ETag calculé sur le corps : le client renvoie If-None-Match et reçoit 304 sans corps si rien n'a changé. */
	@Bean
	FilterRegistrationBean<ShallowEtagHeaderFilter> etagFilter() {
		var bean = new FilterRegistrationBean<>(new ShallowEtagHeaderFilter());
		bean.addUrlPatterns("/api/v1/*");
		bean.setName("etagFilter");
		return bean;
	}

}
