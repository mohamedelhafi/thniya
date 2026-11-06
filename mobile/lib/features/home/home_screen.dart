import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/models.dart';
import '../../core/state.dart';
import '../../design/components/badges.dart';
import '../../design/components/departures.dart';
import '../../design/components/feedback.dart';
import '../../design/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../../map/camera_motion.dart';
import '../../map/thniya_map.dart';
import '../lines/lines_screen.dart';
import '../results/results_screen.dart';
import '../search/search_screen.dart';
import '../stop/stop_screen.dart';

/// Arrêts « à proximité » de la position courante, filtrés par mode (specs/07 §5.1).
final nearbyProvider = FutureProvider.autoDispose.family<List<NearbyStop>, (LatLng, String?)>((ref, key) async {
  final (pos, mode) = key;
  return ref.watch(apiProvider).nearby(pos.latitude, pos.longitude, radius: 1500, mode: mode);
});

final _nearbyModeProvider = StateProvider<String?>((ref) => null);

/// Tracés des lignes (suite de leurs arrêts) pour dessiner le réseau sur la carte.
final networkProvider = FutureProvider<List<LineGeometry>>((ref) => ref.watch(apiProvider).lineGeometry());

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> with TickerProviderStateMixin {
  static const _sheetMin = .14;
  static const _sheetMid = .42;

  final _map = MapController();
  late final _camera = CameraMotion(this, _map);
  final _sheet = DraggableScrollableController();
  // Taille de la feuille sans reconstruire tout l'écran (la carte) à chaque image du glisser
  final _sheetSize = ValueNotifier<double>(_sheetMid);
  List<MapStop> _stops = const [];
  Timer? _debounce;
  _Detail _detail = _Detail.icon;

  // Sélection sur la carte : un arrêt touché, ou un repère posé par appui long
  MapStop? _selStop;
  LatLng? _pin;
  Place? _pinPlace;

  @override
  void initState() {
    super.initState();
    _sheet.addListener(() {
      final rising = _sheet.size > _sheetSize.value;
      _sheetSize.value = _sheet.size;
      // remonter la liste à la main referme l'aperçu : on revient à « à proximité »
      if (rising && _sheet.size > _sheetMin + .08 && (_selStop != null || _pin != null)) _clearSelection();
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _camera.dispose();
    _sheet.dispose();
    _sheetSize.dispose();
    super.dispose();
  }

  /// Zone de carte visible au-dessus de la feuille réduite et de l'aperçu.
  EdgeInsets _visible() {
    final mq = MediaQuery.of(context);
    return EdgeInsets.fromLTRB(40, mq.padding.top + 120, 40, mq.size.height * _sheetMin + 220);
  }

  void _collapseSheet() {
    if (_sheet.isAttached && _sheet.size > _sheetMin + .02) {
      _sheet.animateTo(_sheetMin, duration: Motion.slow, curve: Motion.enter);
    }
  }

  void _selectStop(MapStop s) {
    HapticFeedback.selectionClick();
    setState(() {
      _selStop = s;
      _pin = null;
      _pinPlace = null;
    });
    _collapseSheet();
    _camera.focusPoint(LatLng(s.lat, s.lon), _visible(), zoom: _map.camera.zoom < 15.5 ? 15.5 : _map.camera.zoom);
  }

  Future<void> _dropPin(LatLng p) async {
    HapticFeedback.mediumImpact();
    setState(() {
      _pin = p;
      _selStop = null;
      _pinPlace = null;
    });
    _collapseSheet();
    _camera.focusPoint(p, _visible(), zoom: _map.camera.zoom < 15 ? 15 : _map.camera.zoom);
    try {
      final place = await ref.read(apiProvider).reverse(p.latitude, p.longitude);
      if (mounted && _pin == p) setState(() => _pinPlace = place);
    } catch (_) {}
  }

  /// Arrêt visible le plus proche du repère, pour le situer (« Près de Place de Barcelone · 3 min à pied »).
  (MapStop, int)? _nearestStop(LatLng p) {
    const distance = Distance();
    (MapStop, int)? best;
    for (final s in _stops) {
      final m = distance.as(LengthUnit.Meter, p, LatLng(s.lat, s.lon)).round();
      if (m <= 1500 && (best == null || m < best.$2)) best = (s, m);
    }
    return best;
  }

  void _clearSelection() {
    if (_selStop == null && _pin == null) return;
    setState(() {
      _selStop = null;
      _pin = null;
      _pinPlace = null;
    });
  }

  /// Le repère, sous la forme d'un lieu utilisable pour un itinéraire.
  Place _pinAsPlace(L l) {
    final pin = _pin!;
    final known = _pinPlace;
    if (known != null && known.type == 'STOP') return known;
    return Place(type: 'POINT', name: l.pointOnMap, lat: pin.latitude, lon: pin.longitude);
  }

  void _onCamera(MapCamera camera, bool gesture) {
    if (gesture) {
      _camera.stop(); // l'usager reprend la main
      // explorer la carte lui donne la place : la liste « à proximité » s'abaisse
      if (_selStop == null && _pin == null && _sheet.isAttached && _sheet.size > _sheetMid - .02) {
        _sheet.animateTo(_sheetMin, duration: Motion.slow, curve: Motion.enter);
      }
    }
    final detail = _Detail.forZoom(camera.zoom);
    if (detail != _detail) setState(() => _detail = detail);
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), _loadStops);
  }

  /// Stations de la zone affichée. La caméra est relue au moment de l'appel : au démarrage, la carte n'a pas
  /// encore sa taille et son emprise est un point (l'API répondait alors « aucune station ») — on réessaie.
  Future<void> _loadStops([int attempt = 0]) async {
    if (!mounted) return;
    final LatLngBounds b;
    try {
      b = _map.camera.visibleBounds;
    } catch (_) {
      return;
    }
    if (b.east - b.west < 1e-6 || b.north - b.south < 1e-6) {
      if (attempt < 20) _debounce = Timer(const Duration(milliseconds: 150), () => _loadStops(attempt + 1));
      return;
    }
    try {
      final stops =
          await ref.read(apiProvider).stopsInBbox(b.west, b.south, b.east, b.north, zoom: _map.camera.zoom);
      if (mounted) setState(() => _stops = stops);
    } catch (_) {}
  }

  void _recenter() {
    HapticFeedback.selectionClick();
    final loc = ref.read(locationProvider);
    _camera.flyTo(loc.position, 15.5);
    ref.read(locationProvider.notifier).locate();
  }

  void _goTo(Place? destination) {
    HapticFeedback.selectionClick();
    if (destination == null) {
      context.push('/search', extra: const SearchArgs());
      return;
    }
    final loc = ref.read(locationProvider);
    context.push(
      '/results',
      extra: ResultsArgs(from: myLocationPlace(context, loc.position), to: destination),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final loc = ref.watch(locationProvider);
    final saved = ref.watch(savedPlacesProvider);
    final height = MediaQuery.sizeOf(context).height;
    final mode = ref.watch(_nearbyModeProvider);
    final network = ref.watch(networkProvider).value ?? const [];
    final selectedLines = _selStop?.lines.toSet() ?? const <String>{};

    ref.listen(locationProvider, (prev, next) {
      if (prev?.position != next.position) _camera.flyTo(next.position, 15.5);
    });

    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(
            child: ThniyaMap(
              controller: _map,
              initialCenter: loc.position,
              initialZoom: 15,
              onPositionChanged: _onCamera,
              onTap: (_) => _clearSelection(),
              onLongPress: _dropPin,
              // Stations visibles dès que la carte a sa taille, même si elle ne bouge pas ensuite
              onReady: () => _onCamera(_map.camera, false),
              children: [
                // Pas de réseau dessiné au départ : seulement les lignes de la station touchée, en fondu
                if (selectedLines.isNotEmpty)
                  TweenAnimationBuilder<double>(
                    key: ValueKey('lines-${_selStop!.id}'),
                    tween: Tween(begin: 0, end: 1),
                    duration: Motion.slow,
                    curve: Motion.enter,
                    builder: (context, opacity, child) => Opacity(opacity: opacity, child: child),
                    child: PolylineLayer(
                      polylines: [
                        for (final g in network)
                          if (selectedLines.contains(g.line.id))
                            Polyline(
                              points: g.points,
                              strokeWidth: 3.5,
                              color: hexColor(g.line.color),
                              borderStrokeWidth: 1.5,
                              borderColor: Colors.white.withValues(alpha: .9),
                            ),
                      ],
                    ),
                  ),
                MarkerLayer(
                  markers: [
                    for (final s in _stops.where((s) => mode == null || _modeOf(s) == mode))
                      Marker(
                        point: LatLng(s.lat, s.lon),
                        width: _detail.markerWidth,
                        height: _detail.markerHeight,
                        alignment: _detail == _Detail.labelled
                            ? (context.isRtl ? const Alignment(-.62, 0) : const Alignment(.62, 0))
                            : Alignment.center,
                        child: AnimatedOpacity(
                          // une station est choisie : celles qui ne sont pas sur ses lignes s'effacent
                          opacity: selectedLines.isEmpty || s.lines.any(selectedLines.contains) ? 1 : .3,
                          duration: Motion.medium,
                          child: AnimatedScale(
                            scale: _selStop?.id == s.id ? 1.25 : 1,
                            duration: Motion.fast,
                            child: _StopMarker(stop: s, mode: _modeOf(s), detail: _detail, onTap: () => _selectStop(s)),
                          ),
                        ),
                      ),
                    Marker(point: loc.position, width: 30, height: 30, child: const MyLocationMarker()),
                    if (_pin != null)
                      Marker(
                        point: _pin!,
                        width: 44,
                        height: 44,
                        alignment: Alignment.topCenter,
                        child: TweenAnimationBuilder<double>(
                          // le repère « tombe » sur la carte
                          tween: Tween(begin: -24, end: 0),
                          duration: Motion.medium,
                          curve: Curves.easeOutBack,
                          builder: (context, dy, child) => Transform.translate(offset: Offset(0, dy), child: child),
                          child: Icon(Symbols.location_on, size: 44, color: context.colors.danger, fill: 1),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),

          // Recherche + raccourcis, flottants en haut
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(Space.l, Space.s, Space.l, 0),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _SearchCard(onTap: () => _goTo(null), onSettings: () => context.push('/settings')),
                  const SizedBox(height: Space.s),
                  SizedBox(
                    height: 40,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        _ShortcutChip(
                          icon: Symbols.home,
                          label: saved.home == null ? l.home : l.goHome,
                          sub: saved.home == null ? l.setHome : null,
                          onTap: () => saved.home == null
                              ? context.push('/search', extra: const SearchArgs(pickFor: SavedSlot.home))
                              : _goTo(saved.home),
                        ),
                        _ShortcutChip(
                          icon: Symbols.work,
                          label: l.work,
                          sub: saved.work == null ? l.setHome : null,
                          onTap: () => saved.work == null
                              ? context.push('/search', extra: const SearchArgs(pickFor: SavedSlot.work))
                              : _goTo(saved.work),
                        ),
                        _ShortcutChip(icon: Symbols.route, label: l.lines, onTap: () => context.push('/lines')),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Bouton de recentrage, posé juste au-dessus de la feuille (ou de l'aperçu)
          ValueListenableBuilder<double>(
            valueListenable: _sheetSize,
            builder: (context, size, _) {
              final selecting = _selStop != null || _pin != null;
              return AnimatedPositioned(
                duration: Motion.medium,
                curve: Motion.enter,
                right: context.isRtl ? null : Space.l,
                left: context.isRtl ? Space.l : null,
                bottom: height * size + Space.m + (selecting ? 196 : 0),
                child: AnimatedOpacity(
                  duration: Motion.fast,
                  opacity: size > .8 ? 0 : 1,
                  child: _RoundButton(icon: Symbols.my_location, onTap: _recenter),
                ),
              );
            },
          ),

          DraggableScrollableSheet(
            controller: _sheet,
            initialChildSize: _sheetMid,
            minChildSize: _sheetMin,
            maxChildSize: .92,
            snap: true,
            snapSizes: const [_sheetMin, _sheetMid, .92],
            builder: (context, scroll) => _NearbySheet(scroll: scroll, position: loc.position, locating: loc.loading),
          ),

          // Aperçu de l'arrêt touché ou du repère posé, au-dessus de la feuille réduite
          Positioned(
            left: Space.m,
            right: Space.m,
            bottom: height * _sheetMin + Space.s,
            child: AnimatedSwitcher(
              duration: Motion.medium,
              switchInCurve: Motion.enter,
              switchOutCurve: Curves.easeIn,
              transitionBuilder: (child, a) => FadeTransition(
                opacity: a,
                child: SlideTransition(
                  position: Tween(begin: const Offset(0, .25), end: Offset.zero).animate(a),
                  child: child,
                ),
              ),
              child: _selStop != null
                  ? _StopPreview(
                      key: ValueKey('stop-${_selStop!.id}'),
                      stop: _selStop!,
                      mode: _modeOf(_selStop!),
                      onClose: _clearSelection,
                      onGo: () => context.push(
                        '/results',
                        extra: ResultsArgs(
                          from: myLocationPlace(context, loc.position),
                          to: Place(
                            type: 'STOP',
                            id: _selStop!.id,
                            name: _selStop!.name,
                            lat: _selStop!.lat,
                            lon: _selStop!.lon,
                          ),
                        ),
                      ),
                    )
                  : _pin != null
                  ? _PinPreview(
                      key: ValueKey('pin-$_pin'),
                      place: _pinPlace,
                      nearest: _nearestStop(_pin!),
                      onClose: _clearSelection,
                      onGoHere: () => context.push(
                        '/results',
                        extra: ResultsArgs(from: myLocationPlace(context, loc.position), to: _pinAsPlace(l)),
                      ),
                      onFromHere: () => context.push('/search', extra: SearchArgs(from: _pinAsPlace(l))),
                    )
                  : const SizedBox.shrink(key: ValueKey('none')),
            ),
          ),
        ],
      ),
    );
  }
}

/// Aperçu d'un arrêt touché sur la carte : prochains départs sans quitter la carte (specs/07 §5.1).
class _StopPreview extends ConsumerWidget {
  const _StopPreview({super.key, required this.stop, required this.mode, required this.onClose, required this.onGo});
  final MapStop stop;
  final String mode;
  final VoidCallback onClose;
  final VoidCallback onGo;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final c = context.colors;
    final detail = ref.watch(stopProvider(stop.id));
    final color = modeColor(context, mode);
    return _PreviewFrame(
      onClose: onClose,
      header: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            child: Center(child: ModeIcon(mode, size: 20, color: Colors.white)),
          ),
          const SizedBox(width: Space.m),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(stop.name, style: context.text.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
                if (detail.value?.area != null)
                  Text(
                    detail.value!.area!,
                    style: context.text.bodySmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
        ],
      ),
      body: SizedBox(
        height: 72,
        child: detail.when(
          loading: () => Center(
            child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: c.brand)),
          ),
          error: (_, _) => const SizedBox.shrink(),
          data: (d) => ListView(
            padding: EdgeInsets.zero,
            physics: const ClampingScrollPhysics(),
            children: [
              for (final row in d.board.take(3))
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    children: [
                      LineBadge(row.line, compact: true, showIcon: false),
                      const SizedBox(width: Space.s),
                      Expanded(
                        child: Text(
                          l.towards(row.headsign ?? ''),
                          style: context.text.bodySmall?.copyWith(color: c.text),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (row.noServiceToday)
                        Text(l.noServiceToday, style: context.text.labelSmall)
                      else
                        DepartureLine(row.departures, max: 2),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
      actions: [
        Expanded(
          child: FilledButton.icon(
            onPressed: onGo,
            icon: const Icon(Symbols.directions, size: 18),
            label: Text(l.goThere),
          ),
        ),
        const SizedBox(width: Space.s),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => context.push('/stop/${stop.id}'),
            icon: const Icon(Symbols.schedule, size: 18),
            label: Text(l.departures),
          ),
        ),
      ],
    );
  }
}

/// Aperçu du repère posé par appui long : « Itinéraire vers ici » ou « Partir d'ici ».
class _PinPreview extends StatelessWidget {
  const _PinPreview({
    super.key,
    required this.place,
    required this.nearest,
    required this.onClose,
    required this.onGoHere,
    required this.onFromHere,
  });
  final Place? place;
  final (MapStop, int)? nearest;
  final VoidCallback onClose;
  final VoidCallback onGoHere;
  final VoidCallback onFromHere;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final c = context.colors;
    final stop = place?.type == 'STOP' ? place : null;
    return _PreviewFrame(
      onClose: onClose,
      header: Row(
        children: [
          Icon(Symbols.location_on, color: c.danger, fill: 1, size: 32),
          const SizedBox(width: Space.s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  stop?.name ?? l.pointOnMap,
                  style: context.text.titleMedium,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (stop == null && nearest != null)
                  Text(
                    l.nearStop(nearest!.$1.name, (nearest!.$2 / 80).ceil().clamp(1, 99)),
                    style: context.text.bodySmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
        ],
      ),
      body: const SizedBox(height: Space.s),
      actions: [
        Expanded(
          child: FilledButton.icon(
            onPressed: onGoHere,
            icon: const Icon(Symbols.directions, size: 18),
            label: Text(l.goThere),
          ),
        ),
        const SizedBox(width: Space.s),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: onFromHere,
            icon: const Icon(Symbols.trip_origin, size: 18),
            label: Text(l.routeFromHere),
          ),
        ),
      ],
    );
  }
}

class _PreviewFrame extends StatelessWidget {
  const _PreviewFrame({required this.header, required this.body, required this.actions, required this.onClose});
  final Widget header;
  final Widget body;
  final List<Widget> actions;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return GestureDetector(
      // glisser l'aperçu vers le bas le ferme
      onVerticalDragEnd: (d) {
        if ((d.primaryVelocity ?? 0) > 250) onClose();
      },
      child: Material(
        color: c.surface,
        borderRadius: BorderRadius.circular(Radii.card),
        elevation: 6,
        shadowColor: Colors.black38,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.s, Space.m),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: header),
                  IconButton(
                    onPressed: onClose,
                    visualDensity: VisualDensity.compact,
                    icon: Icon(Symbols.close, size: 20, color: c.textTertiary),
                  ),
                ],
              ),
              const SizedBox(height: Space.s),
              Padding(
                padding: const EdgeInsetsDirectional.only(end: Space.s),
                child: body,
              ),
              Padding(
                padding: const EdgeInsetsDirectional.only(end: Space.s, top: Space.s),
                child: Row(children: actions),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

Place myLocationPlace(BuildContext context, LatLng p) =>
    Place(type: 'MY_LOCATION', name: L.of(context).myLocation, lat: p.latitude, lon: p.longitude);

class _SearchCard extends StatelessWidget {
  const _SearchCard({required this.onTap, required this.onSettings});
  final VoidCallback onTap;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Material(
      color: c.surface,
      elevation: 0,
      borderRadius: BorderRadius.circular(Radii.card),
      shadowColor: Colors.black26,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(Radii.card),
          boxShadow: const [BoxShadow(color: Color(0x1F000000), blurRadius: 18, offset: Offset(0, 6))],
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(Radii.card),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.s, Space.m),
            child: Row(
              children: [
                Icon(Symbols.search, color: c.brand, weight: 600, size: 26),
                const SizedBox(width: Space.m),
                Expanded(
                  child: Text(
                    L.of(context).whereTo,
                    style: context.text.titleMedium?.copyWith(fontSize: 18, color: c.text),
                  ),
                ),
                IconButton(
                  onPressed: onSettings,
                  icon: CircleAvatar(
                    radius: 16,
                    backgroundColor: c.brandSoft,
                    child: Icon(Symbols.tune, size: 18, color: c.brand),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ShortcutChip extends StatelessWidget {
  const _ShortcutChip({required this.icon, required this.label, this.sub, required this.onTap});
  final IconData icon;
  final String label;
  final String? sub;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsetsDirectional.only(end: Space.s),
      child: Material(
        color: c.surface,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: Space.m),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              boxShadow: const [BoxShadow(color: Color(0x14000000), blurRadius: 8, offset: Offset(0, 2))],
            ),
            child: Row(
              children: [
                Icon(icon, size: 18, color: c.brand, fill: 1),
                const SizedBox(width: 6),
                Text(label, style: context.text.labelMedium),
                if (sub != null) ...[
                  const SizedBox(width: 4),
                  Text(sub!, style: context.text.labelSmall?.copyWith(color: c.textTertiary)),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({required this.icon, required this.onTap});
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: context.colors.surface,
    shape: const CircleBorder(),
    elevation: 3,
    shadowColor: Colors.black26,
    child: InkWell(
      customBorder: const CircleBorder(),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Icon(icon, color: context.colors.brand, fill: 1),
      ),
    ),
  );
}

/// Mode affiché pour un arrêt : celui de ses lignes, sinon déduit de son type.
String _modeOf(MapStop s) {
  if (s.modes.isNotEmpty) return s.modes.first;
  return switch (s.kind) {
    'louage_station' || 'louage_bay' || 'hail_point' => 'LOUAGE',
    'station' => 'TRAIN',
    _ => 'BUS',
  };
}

/// Niveau de détail des arrêts selon le zoom : point de loin, icône du mode, puis icône + nom de près.
enum _Detail {
  dot(10, 10),
  small(22, 22),
  icon(30, 30),
  labelled(170, 30);

  const _Detail(this.markerWidth, this.markerHeight);
  final double markerWidth;
  final double markerHeight;

  // Le type (icône du mode) reste lisible dès la vue d'ensemble ; le point seul pour la région entière
  static _Detail forZoom(double zoom) => zoom < 10.5
      ? dot
      : zoom < 13
      ? small
      : zoom < 14.5
      ? icon
      : labelled;
}

class _StopMarker extends StatelessWidget {
  const _StopMarker({required this.stop, required this.mode, required this.detail, required this.onTap});
  final MapStop stop;
  final String mode;
  final _Detail detail;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = modeColor(context, mode);
    final c = context.colors;
    const shadow = [BoxShadow(color: Color(0x33000000), blurRadius: 4, offset: Offset(0, 1))];

    final Widget pin = switch (detail) {
      _Detail.small => Container(
        width: 22,
        height: 22,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 2),
          boxShadow: shadow,
        ),
        child: Center(child: ModeIcon(mode, size: 12, color: Colors.white)),
      ),
      _Detail.dot => Container(
        width: 10,
        height: 10,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 2),
          boxShadow: shadow,
        ),
      ),
      _ => Container(
        width: 30,
        height: 30,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 2.5),
          boxShadow: shadow,
        ),
        child: Center(child: ModeIcon(mode, size: 16, color: Colors.white)),
      ),
    };

    return Semantics(
      button: true,
      label: stop.name,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: detail != _Detail.labelled
            ? pin
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  pin,
                  const SizedBox(width: 4),
                  Flexible(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                      decoration: BoxDecoration(
                        color: c.surface.withValues(alpha: .94),
                        borderRadius: BorderRadius.circular(Radii.badge),
                        boxShadow: shadow,
                      ),
                      child: Text(
                        stop.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: context.text.labelSmall?.copyWith(color: c.text, fontSize: 11.5),
                      ),
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

class _NearbySheet extends ConsumerWidget {
  const _NearbySheet({required this.scroll, required this.position, required this.locating});
  final ScrollController scroll;
  final LatLng position;
  final bool locating;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final c = context.colors;
    final mode = ref.watch(_nearbyModeProvider);
    final nearby = ref.watch(nearbyProvider((position, mode)));
    final meta = ref.watch(metaProvider).value;
    // Seulement les modes qui ont des lignes : pas de filtre « Bus » sans bus
    final withLines = ref.watch(linesProvider).value?.map((x) => x.line.mode).toSet() ?? const <String?>{};
    final modes = (meta?.modes.keys ?? const <String>[]).where(withLines.contains).toList();

    return Container(
      decoration: BoxDecoration(
        color: c.background,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(Radii.sheet)),
        boxShadow: const [BoxShadow(color: Color(0x26000000), blurRadius: 24, offset: Offset(0, -4))],
      ),
      child: CustomScrollView(
        controller: scroll,
        slivers: [
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    margin: const EdgeInsets.only(top: Space.s, bottom: Space.m),
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(color: c.divider, borderRadius: BorderRadius.circular(2)),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: Space.l),
                  child: Row(
                    children: [
                      Text(l.nearby, style: context.text.headlineSmall),
                      const Spacer(),
                      if (locating) ...[
                        SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2, color: c.brand),
                        ),
                        const SizedBox(width: Space.s),
                        Text(l.locating, style: context.text.bodySmall),
                      ],
                    ],
                  ),
                ),
                if (meta?.mainPeriod != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, 0),
                    child: PeriodBanner(meta!.mainPeriod),
                  ),
                const SizedBox(height: Space.m),
                SizedBox(
                  height: 36,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: Space.l),
                    children: [
                      _ModeFilter(
                        label: l.all,
                        selected: mode == null,
                        onTap: () => ref.read(_nearbyModeProvider.notifier).state = null,
                      ),
                      for (final m in modes)
                        _ModeFilter(
                          mode: m,
                          label: meta!.modes[m]!.name,
                          selected: mode == m,
                          onTap: () => ref.read(_nearbyModeProvider.notifier).state = m,
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: Space.m),
              ],
            ),
          ),
          ...nearby.when(
            data: (stops) => stops.isEmpty
                ? [
                    SliverToBoxAdapter(
                      child: MessageState(icon: Symbols.near_me_disabled, title: l.noNearby),
                    ),
                  ]
                : [
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(Space.l, 0, Space.l, Space.xxl),
                      sliver: SliverList.separated(
                        itemCount: stops.length,
                        separatorBuilder: (_, _) => const SizedBox(height: Space.m),
                        itemBuilder: (context, i) => _NearbyCard(stop: stops[i]),
                      ),
                    ),
                  ],
            loading: () => [
              SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: Space.l),
                sliver: SliverList.separated(
                  itemCount: 3,
                  separatorBuilder: (_, _) => const SizedBox(height: Space.m),
                  itemBuilder: (_, _) => const SkeletonCard(),
                ),
              ),
            ],
            error: (e, _) => [
              SliverToBoxAdapter(
                child: MessageState.error(context, e, () => ref.invalidate(nearbyProvider((position, mode)))),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ModeFilter extends StatelessWidget {
  const _ModeFilter({this.mode, required this.label, required this.selected, required this.onTap});
  final String? mode;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsetsDirectional.only(end: Space.s),
      child: AnimatedContainer(
        duration: Motion.fast,
        decoration: BoxDecoration(
          color: selected ? c.text : c.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: selected ? c.text : c.divider),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: () {
            HapticFeedback.selectionClick();
            onTap();
          },
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            child: Row(
              children: [
                if (mode != null) ...[
                  ModeIcon(mode!, size: 16, color: selected ? c.surface : modeColor(context, mode!)),
                  const SizedBox(width: 6),
                ],
                Text(label, style: context.text.labelMedium?.copyWith(color: selected ? c.surface : c.text)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NearbyCard extends StatelessWidget {
  const _NearbyCard({required this.stop});
  final NearbyStop stop;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l = L.of(context);
    final mode = stop.modes.isEmpty ? 'BUS' : stop.modes.first;
    return Material(
      color: c.surface,
      borderRadius: BorderRadius.circular(Radii.card),
      child: InkWell(
        borderRadius: BorderRadius.circular(Radii.card),
        onTap: () => context.push('/stop/${stop.stop.id}'),
        child: Padding(
          padding: const EdgeInsets.all(Space.l),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: modeColor(context, mode).withValues(alpha: .12),
                      shape: BoxShape.circle,
                    ),
                    child: Center(child: ModeIcon(mode, size: 20, color: modeColor(context, mode))),
                  ),
                  const SizedBox(width: Space.m),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(stop.stop.name, style: context.text.titleMedium),
                        if (stop.stop.area != null) Text(stop.stop.area!, style: context.text.bodySmall),
                      ],
                    ),
                  ),
                  Icon(Symbols.directions_walk, size: 16, color: c.textSecondary),
                  Text(l.minutesShort(stop.walkMin), style: context.text.labelMedium?.copyWith(color: c.textSecondary)),
                ],
              ),
              if (stop.lines.isNotEmpty) ...[
                const SizedBox(height: Space.m),
                Divider(color: c.divider),
                for (final row in stop.lines)
                  Padding(
                    padding: const EdgeInsets.only(top: Space.m),
                    child: Row(
                      children: [
                        LineBadge(row.line, compact: true, showIcon: false),
                        const SizedBox(width: Space.s),
                        Expanded(
                          child: Text(
                            l.towards(row.headsign ?? ''),
                            style: context.text.bodyMedium,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (row.noServiceToday)
                          Text(l.noServiceToday, style: context.text.bodySmall)
                        else
                          DepartureLine(row.departures, max: 2),
                      ],
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
