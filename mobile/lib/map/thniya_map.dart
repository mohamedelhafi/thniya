import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_polyline_algorithm/google_polyline_algorithm.dart';
import 'package:latlong2/latlong.dart';
import 'package:path_provider/path_provider.dart';
import 'package:vector_map_tiles/vector_map_tiles.dart';
import 'package:vector_map_tiles_pmtiles/vector_map_tiles_pmtiles.dart';
// ignore: implementation_imports
import 'package:vector_tile_renderer/vector_tile_renderer.dart' as vtr;

import '../core/config.dart';
import '../core/state.dart';
import '../design/tokens.dart';

/// Fond de carte PMTiles auto-hébergé (ADR-004), chargé une seule fois.
final tileProviderProvider =
    FutureProvider<PmTilesVectorTileProvider>((ref) => PmTilesVectorTileProvider.fromSource(AppConfig.tilesUrl));

/// Style de carte Thniya : clair/sombre × libellés FR/AR (assets/map, générés par tool/mapstyle).
final mapThemeProvider = FutureProvider.family<vtr.Theme, (String, Brightness)>((ref, key) async {
  final (lang, brightness) = key;
  final name = 'assets/map/thniya-${brightness == Brightness.dark ? 'dark' : 'light'}-$lang.json';
  final json = jsonDecode(await rootBundle.loadString(name)) as Map<String, dynamic>;
  return vtr.ThemeReader().read(json);
});

/// Carte de base de l'app : fond vectoriel + couches de l'écran (tracés, arrêts, position).
class ThniyaMap extends ConsumerWidget {
  const ThniyaMap({
    super.key,
    required this.controller,
    this.initialCenter = defaultCenter,
    this.initialZoom = 14,
    this.initialFit,
    this.children = const [],
    this.onTap,
    this.onLongPress,
    this.onPositionChanged,
    this.onReady,
    this.bottomPadding = 0,
  });

  final MapController controller;
  final LatLng initialCenter;
  final double initialZoom;

  /// Cadrage initial (prioritaire sur centre et zoom). À préférer à un déplacement dans [onReady] : un déplacement
  /// juste après la création annule les tuiles de la première vue, et le fond de carte de la vue finale n'était
  /// chargé qu'au premier geste de l'utilisateur (fiches ligne et trajet sans fond de carte).
  final CameraFit? initialFit;
  final List<Widget> children;
  final void Function(LatLng)? onTap;
  final void Function(LatLng)? onLongPress;
  final void Function(MapCamera camera, bool hasGesture)? onPositionChanged;

  /// Appelé quand la carte a sa taille : premier cadrage possible.
  final VoidCallback? onReady;
  final double bottomPadding;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(localeProvider).languageCode;
    final brightness = Theme.of(context).brightness;
    final theme = ref.watch(mapThemeProvider((lang, brightness)));
    final tiles = ref.watch(tileProviderProvider);
    final c = context.colors;

    return Container(
      color: brightness == Brightness.dark ? const Color(0xFF161B1F) : const Color(0xFFF5F3EF),
      child: FlutterMap(
        mapController: controller,
        options: MapOptions(
          initialCenter: initialCenter,
          initialZoom: initialZoom,
          initialCameraFit: initialFit,
          minZoom: 9,
          maxZoom: 18,
          backgroundColor: Colors.transparent,
          interactionOptions: const InteractionOptions(flags: InteractiveFlag.all & ~InteractiveFlag.rotate),
          onTap: onTap == null ? null : (_, p) => onTap!(p),
          onLongPress: onLongPress == null ? null : (_, p) => onLongPress!(p),
          onPositionChanged: onPositionChanged,
          onMapReady: onReady,
        ),
        children: [
          if (theme.hasValue && tiles.hasValue)
            VectorTileLayer(
              key: ValueKey('$lang-$brightness'),
              theme: theme.requireValue,
              tileProviders: TileProviders({'protomaps': tiles.requireValue}),
              // Zoom maximal du fichier PMTiles : au-delà, ses tuiles sont agrandies (third_party/README.md).
              maximumZoom: 15,
              // Web : le mode raster (images de tuiles) ne s'affiche pas ; le mode vecteur oui.
              // Mobile : raster, plus fluide (specs/13 §7).
              layerMode: kIsWeb ? VectorTileLayerMode.vector : VectorTileLayerMode.raster,
              // Sur le web, pas d'isolats : rendu dans le fil principal. Sur mobile, isolats pour la fluidité.
              concurrency: kIsWeb ? 0 : 4,
              fileCacheTtl: kIsWeb ? Duration.zero : const Duration(days: 30),
              // Le cache range les tuiles par z/x/y, sans le fichier source ni le style : un dossier par fichier
              // .pmtiles et par style, sinon un nouvel extrait réaffiche les anciennes tuiles et cases vides, et le
              // thème sombre ou l'arabe réaffichent les tuiles du style précédent.
              cacheFolder: kIsWeb ? null : () => _tileCacheFolder('$lang-${brightness.name}'),
            ),
          ...children,
          RichAttributionWidget(
            alignment: AttributionAlignment.bottomLeft,
            showFlutterMapAttribution: false,
            attributions: const [TextSourceAttribution('© OpenStreetMap · Protomaps')],
            popupBackgroundColor: c.surface,
          ),
        ],
      ),
    );
  }
}

/// Dossier du cache de tuiles propre au fond de carte et au style (« tunisie.pmtiles » → …/.vector_map/tunisie/fr-light).
Future<Directory> _tileCacheFolder(String style) async {
  final name = Uri.parse(AppConfig.tilesUrl).pathSegments.last.replaceAll(RegExp(r'\.pmtiles$'), '');
  final safe = name.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_');
  return Directory('${(await getTemporaryDirectory()).path}/.vector_map/$safe/$style');
}

/// Décode un tracé encodé (format polyline de Google, renvoyé par OTP).
List<LatLng> decodeLine(String? encoded) {
  if (encoded == null || encoded.isEmpty) return const [];
  return decodePolyline(encoded).map((p) => LatLng(p[0].toDouble(), p[1].toDouble())).toList();
}

/// Point « vous êtes ici », discret et lisible sur fond clair ou sombre.
class MyLocationMarker extends StatelessWidget {
  const MyLocationMarker({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: c.brand.withValues(alpha: .18),
      ),
      padding: const EdgeInsets.all(6),
      child: Container(
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: c.brand,
          border: Border.all(color: Colors.white, width: 3),
          boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 6, offset: Offset(0, 2))],
        ),
      ),
    );
  }
}
