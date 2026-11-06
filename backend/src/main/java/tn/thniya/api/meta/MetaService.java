package tn.thniya.api.meta;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.CacheManager;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;

import tn.thniya.api.common.ApiException;
import tn.thniya.api.common.AppProperties;

/**
 * Charge app-meta.json et le recharge quand le fichier change (nouvelle génération des données).
 * Un changement de dataVersion vide tous les caches (specs/06 §5).
 */
@Service
public class MetaService {

	private static final Logger log = LoggerFactory.getLogger(MetaService.class);

	private static final String FEED_PREFIX = "TN:";

	private final AppProperties props;

	private final CacheManager caches;

	private final JsonMapper mapper = JsonMapper.builder()
		.disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
		.build();

	private volatile AppMeta meta;

	private volatile StopIndex index;

	private volatile FileTime loadedAt;

	public MetaService(AppProperties props, CacheManager caches) {
		this.props = props;
		this.caches = caches;
		reloadIfChanged();
	}

	@Scheduled(fixedDelayString = "PT30S", initialDelayString = "PT30S")
	public void reloadIfChanged() {
		try {
			FileTime modified = Files.getLastModifiedTime(Path.of(props.metaPath()));
			if (modified.equals(loadedAt)) {
				return;
			}
			AppMeta fresh = mapper.readValue(Path.of(props.metaPath()).toFile(), AppMeta.class);
			String previous = meta == null ? null : meta.dataVersion();
			long t0 = System.nanoTime();
			StopIndex freshIndex = new StopIndex(fresh.stops());
			// l'index est publié avant les données : un lecteur ne voit jamais des données sans leur index
			index = freshIndex;
			meta = fresh;
			loadedAt = modified;
			if (!Objects.equals(previous, fresh.dataVersion())) {
				caches.getCacheNames().forEach(name -> Objects.requireNonNull(caches.getCache(name)).clear());
				log.info("Données chargées : version {} ({} lignes, {} arrêts, index en {} ms)", fresh.dataVersion(),
						fresh.lines().size(), fresh.stops().size(), (System.nanoTime() - t0) / 1_000_000);
			}
		}
		catch (IOException | RuntimeException e) {
			log.warn("Impossible de lire {} : {}", props.metaPath(), e.getMessage());
		}
	}

	public AppMeta current() {
		AppMeta m = meta;
		if (m == null) {
			throw new ApiException(ApiException.Code.META_UNAVAILABLE, "app-meta.json n'est pas encore chargé");
		}
		return m;
	}

	/** Index spatial et textuel des arrêts de la version courante. */
	public StopIndex index() {
		current();
		return index;
	}

	// --- Accès pratiques -------------------------------------------------------------------

	public AppMeta.Line line(String id) {
		AppMeta.Line line = current().lines().get(id);
		if (line == null) {
			throw new ApiException(ApiException.Code.NOT_FOUND, "Ligne inconnue : " + id);
		}
		return line;
	}

	public AppMeta.Stop stop(String id) {
		AppMeta.Stop stop = current().stops().get(id);
		if (stop == null) {
			throw new ApiException(ApiException.Code.NOT_FOUND, "Arrêt inconnu : " + id);
		}
		return stop;
	}

	public AppMeta.Line lineOrNull(String id) {
		return id == null ? null : current().lines().get(id);
	}

	public AppMeta.Stop stopOrNull(String id) {
		return id == null ? null : current().stops().get(id);
	}

	/** Jour du calendrier d'un réseau (période, type de jour, fériés), ou null hors fenêtre. */
	public AppMeta.Day day(String network, LocalDate date) {
		var byDate = current().calendar().get(network);
		return byDate == null ? null : byDate.get(date.toString());
	}

	/** Alertes actives à un instant donné qui touchent une ligne, un arrêt ou un réseau. */
	public List<AppMeta.Alert> alertsAt(LocalDateTime at, String line, String stop, String network) {
		return current().alerts().stream()
			.filter(a -> a.activePeriods().stream()
				.anyMatch(p -> !at.isBefore(LocalDateTime.parse(p.from())) && !at.isAfter(LocalDateTime.parse(p.to()))))
			.filter(a -> matches(a.scope().lines(), line) || matches(a.scope().stops(), stop)
					|| matches(a.scope().networks(), network))
			.toList();
	}

	private static boolean matches(List<String> ids, String id) {
		return id != null && ids != null && ids.contains(id);
	}

	/** « TN:TRN-HAMMAMLIF » (identifiant OTP) → « TRN-HAMMAMLIF » (identifiant des données). */
	public static String localId(String otpId) {
		if (otpId == null) {
			return null;
		}
		return otpId.startsWith(FEED_PREFIX) ? otpId.substring(FEED_PREFIX.length()) : otpId;
	}

	public static String otpId(String localId) {
		return FEED_PREFIX + localId;
	}

}
