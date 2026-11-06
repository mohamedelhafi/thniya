import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import 'package:material_symbols_icons/symbols.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/format.dart';
import '../../core/models.dart';
import '../../core/state.dart';
import '../../design/components/badges.dart';
import '../../design/components/departures.dart';
import '../../design/components/feedback.dart';
import '../../design/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../../map/camera_motion.dart';
import '../../map/thniya_map.dart';

/// Fiche trajet (specs/07 §5.4). Deux modes :
/// - **vue d'ensemble** : carte du trajet + frise des étapes dans une feuille ;
/// - **étape** (on touche une étape dans la frise ou son tracé sur la carte) : la feuille s'efface, la carte prend
///   l'écran et vole jusqu'à l'étape, les autres étapes s'estompent ; des cartes d'étape se font glisser pour passer
///   à la suivante. Retour : bouton « Vue d'ensemble », glisser la carte d'étape vers le haut, ou retour arrière.
class TripScreen extends ConsumerStatefulWidget {
  const TripScreen({super.key, required this.itinerary});
  final Itinerary itinerary;

  @override
  ConsumerState<TripScreen> createState() => _TripScreenState();
}

class _TripScreenState extends ConsumerState<TripScreen> with TickerProviderStateMixin {
  static const _peek = .24;
  static const _half = .5;
  static const _full = .94;
  static const _cardHeight = 236.0;
  static const _navHeight = 40.0;

  late Itinerary _it = widget.itinerary;
  final _map = MapController();
  late final _camera = CameraMotion(this, _map);
  final _sheet = DraggableScrollableController();
  final _sheetSize = ValueNotifier<double>(_half);
  final _hit = ValueNotifier<LayerHitResult<int>?>(null);
  PageController? _pages;
  bool _pagingByCode = false;
  int? _focus; // étape mise en avant (null : vue d'ensemble) ; legs.length = carte d'arrivée
  int? _lastFocus; // surlignée dans la frise au retour
  bool _updating = false;

  @override
  void initState() {
    super.initState();
    _sheet.addListener(() => _sheetSize.value = _sheet.size);
  }

  @override
  void dispose() {
    _camera.dispose();
    _sheet.dispose();
    _sheetSize.dispose();
    _hit.dispose();
    _pages?.dispose();
    super.dispose();
  }

  // --- Étapes ------------------------------------------------------------------------------

  /// Une marche d'une minute pour rejoindre le quai n'est pas une « étape » pour l'usager.
  static bool _trivial(Leg l) => l.isWalk && l.durationMin <= 2 && (l.distanceM ?? 0) <= 200;

  /// Étapes présentées en cartes (indices dans legs) ; la dernière, legs.length, est l'arrivée.
  List<int> get _steps => [
    for (var i = 0; i < _it.legs.length; i++)
      if (!_trivial(_it.legs[i])) i,
    _it.legs.length,
  ];

  int _pageOf(int legIndex) {
    final steps = _steps;
    final p = steps.indexWhere((x) => x >= legIndex);
    return p < 0 ? steps.length - 1 : p;
  }

  // --- Géométrie --------------------------------------------------------------------------

  List<LatLng> _pointsOf(Leg leg) {
    final pts = decodeLine(leg.polyline);
    if (pts.isNotEmpty) return pts;
    return [
      if (leg.from?.lat != null) LatLng(leg.from!.lat!, leg.from!.lon!),
      if (leg.to?.lat != null) LatLng(leg.to!.lat!, leg.to!.lon!),
    ];
  }

  /// Partie de l'écran réellement visible : sous la barre du haut, au-dessus de la feuille ou des cartes d'étape.
  EdgeInsets _visible() {
    final mq = MediaQuery.of(context);
    // en mode étape, place pour l'étiquette « Montée · … » au-dessus de l'arrêt le plus haut
    final top = mq.padding.top + 76 + (_focus != null ? 44 : 0);
    final bottom = _focus != null
        ? _cardHeight + mq.padding.bottom + Space.xl + _navHeight + Space.s
        : mq.size.height * (_sheet.isAttached ? _sheet.size : _half) + Space.l;
    // en mode étape, les étiquettes centrées sur les arrêts débordent d'environ 80 px de chaque côté
    final side = _focus != null ? 84.0 : 40.0;
    // en vue d'ensemble, le bouton « tout le trajet » occupe le bord (droit, ou gauche en arabe)
    final button = _focus == null ? 72.0 : side;
    final rtl = Directionality.of(context) == TextDirection.rtl;
    return EdgeInsets.fromLTRB(rtl ? button : side, top, rtl ? side : button, bottom);
  }

  List<LatLng> get _allPoints => _it.legs.expand(_pointsOf).toList();

  void _fitAll() {
    final pts = _allPoints;
    if (pts.length < 2) return;
    _camera.fitPoints(pts, _visible(), maxZoom: 16);
  }

  void _fitFocus() {
    final i = _focus;
    if (i == null) return;
    if (i >= _it.legs.length) {
      final to = _it.legs.last.to;
      if (to?.lat != null) _camera.focusPoint(LatLng(to!.lat!, to.lon!), _visible(), zoom: 16.5);
      return;
    }
    // Une marche très courte se lit mieux un peu dézoomée
    _camera.fitPoints(_pointsOf(_it.legs[i]), _visible(), maxZoom: _it.legs[i].isWalk ? 17 : 16.5);
  }

  // --- Mode étape ----------------------------------------------------------------------------

  void _focusOn(int legIndex) {
    final page = _pageOf(legIndex);
    final index = _steps[page];
    if (index == _focus) return;
    HapticFeedback.selectionClick();
    final entering = _focus == null;
    setState(() {
      _focus = index;
      _lastFocus = index;
    });
    if (entering) {
      _pages?.dispose();
      _pages = PageController(initialPage: page, viewportFraction: .9);
    } else if (_pages?.hasClients ?? false) {
      _pagingByCode = true;
      _pages!
          .animateToPage(page, duration: Motion.slow, curve: Motion.change)
          .whenComplete(() => _pagingByCode = false);
    }
    _fitFocus();
  }

  /// Étape précédente (-1) ou suivante (+1) : boutons sous la carte et flèches du clavier.
  void _step(int delta) {
    final i = _focus;
    if (i == null) return;
    final steps = _steps;
    final page = _pageOf(i) + delta;
    if (page < 0 || page >= steps.length) return;
    _focusOn(steps[page]);
  }

  void _onPageChanged(int page) {
    final index = _steps[page];
    if (_pagingByCode || index == _focus) return;
    HapticFeedback.selectionClick();
    setState(() {
      _focus = index;
      _lastFocus = index;
    });
    _fitFocus();
  }

  void _exitFocus() {
    if (_focus == null) return;
    HapticFeedback.lightImpact();
    setState(() => _focus = null);
    WidgetsBinding.instance.addPostFrameCallback((_) => _fitAll());
  }

  void _onMapMoved(MapCamera camera, bool gesture) {
    if (!gesture) return;
    _camera.stop(); // l'usager reprend la main
    // La carte prend la place quand on l'explore : la feuille descend
    if (_focus == null && _sheet.isAttached && _sheet.size > _peek + .05) {
      _sheet.animateTo(_peek, duration: Motion.slow, curve: Motion.enter);
    }
  }

  // --- Actions -------------------------------------------------------------------------------

  Future<void> _chooseDeparture(int legIndex, Departure d) async {
    final leg = _it.legs[legIndex];
    if (d.time == null || (leg.departAt != null && leg.departAt!.isAtSameMomentAs(d.time!))) return;
    HapticFeedback.selectionClick();
    setState(() => _updating = true);
    try {
      final next = await ref.read(apiProvider).otherDeparture(_it.id, legIndex, d.time!);
      if (mounted) setState(() => _it = next);
    } catch (_) {
      // On garde l'itinéraire affiché : le choix d'un autre départ est un confort.
    } finally {
      if (mounted) setState(() => _updating = false);
    }
  }

  void _share() {
    final f = Fmt.of(context);
    final lines = <String>[
      '${_it.legs.first.from?.name ?? ''} → ${_it.legs.last.to?.name ?? ''}',
      '${f.time(_it.departAt)} – ${f.time(_it.arriveAt)} (${f.duration(_it.durationMin)})',
      for (final leg in _it.legs.where((l) => l.isTransit))
        '${leg.line == null ? '' : lineCodePlain(leg.line!)} ${leg.from?.name ?? ''} → ${leg.to?.name ?? ''}'
            '${leg.departAt != null ? ' ${f.time(leg.departAt!)}' : ''}',
      '— Thniya',
    ];
    SharePlus.instance.share(ShareParams(text: lines.join('\n')));
  }

  Future<void> _report() async {
    final l = L.of(context);
    final ctrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l.feedbackPrompt),
        content: TextField(controller: ctrl, maxLines: 4, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l.cancel)),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(l.send)),
        ],
      ),
    );
    if (ok != true || ctrl.text.trim().isEmpty || !mounted) return;
    try {
      await ref.read(apiProvider).feedback('OTHER', ctrl.text.trim(), {
        'itinerary': _it.id,
        'lines': _it.legs.map((x) => x.line?.id).whereType<String>().toList(),
      });
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l.feedbackSent)));
    } catch (_) {}
  }

  // --- Carte ---------------------------------------------------------------------------------

  Color _legColor(Leg leg) {
    final c = context.colors;
    return leg.isWalk ? c.walk : (leg.line == null ? c.brand : hexColor(leg.line!.color));
  }

  List<Polyline<int>> _polylines() {
    final c = context.colors;
    final out = <Polyline<int>>[];
    final order = List.generate(_it.legs.length, (i) => i);
    if (_focus != null && _focus! < _it.legs.length) {
      order
        ..remove(_focus)
        ..add(_focus!); // l'étape mise en avant est dessinée par-dessus
    }
    for (final i in order) {
      final leg = _it.legs[i];
      final pts = _pointsOf(leg);
      if (pts.length < 2) continue;
      final dim = _focus != null && _focus != i;
      final strong = _focus == i;
      final alpha = dim ? .3 : 1.0;
      if (leg.isWalk) {
        out.add(
          Polyline(
            points: pts,
            strokeWidth: strong ? 5 : 4,
            color: c.walk.withValues(alpha: alpha),
            pattern: StrokePattern.dotted(spacingFactor: 2),
            hitValue: i,
          ),
        );
      } else {
        out.add(
          Polyline(
            points: pts,
            strokeWidth: strong ? 9 : 7,
            color: Colors.white.withValues(alpha: dim ? .5 : 1),
            hitValue: i,
          ),
        );
        out.add(
          Polyline(
            points: pts,
            strokeWidth: strong ? 6 : 4.5,
            color: _legColor(leg).withValues(alpha: alpha),
            hitValue: i,
          ),
        );
      }
    }
    return out;
  }

  List<Marker> _markers() {
    final c = context.colors;
    final l = L.of(context);
    final markers = <Marker>[];
    final focusLeg = _focus != null && _focus! < _it.legs.length ? _it.legs[_focus!] : null;

    // Arrêts de montée et de descente de tout le trajet (estompés hors de l'étape mise en avant)
    for (var i = 0; i < _it.legs.length; i++) {
      final leg = _it.legs[i];
      if (!leg.isTransit || leg == focusLeg) continue;
      for (final s in [leg.from, leg.to]) {
        if (s?.lat == null) continue;
        markers.add(
          Marker(
            point: LatLng(s!.lat!, s.lon!),
            width: 16,
            height: 16,
            child: Opacity(
              opacity: focusLeg == null ? 1 : .45,
              child: _StopDot(color: _legColor(leg), size: 16),
            ),
          ),
        );
      }
    }

    if (focusLeg != null) {
      final color = _legColor(focusLeg);
      // Arrêts intermédiaires : petits points sur le tracé
      for (final s in focusLeg.intermediateStops) {
        if (s.lat == null) continue;
        markers.add(
          Marker(
            point: LatLng(s.lat!, s.lon!),
            width: 11,
            height: 11,
            child: _StopDot(color: color, size: 11, border: 2.5),
          ),
        );
      }
      final from = focusLeg.from, to = focusLeg.to;
      if (from?.lat != null) {
        markers.addAll(
          _labelledStop(
            point: LatLng(from!.lat!, from.lon!),
            color: color,
            mode: focusLeg.isWalk ? 'WALK' : focusLeg.mode,
            caption: focusLeg.isWalk ? null : l.boarding,
            name: from.name,
            onTap: focusLeg.isTransit && from.id != null ? () => context.push('/stop/${from.id}') : null,
          ),
        );
      }
      if (to?.lat != null) {
        markers.addAll(
          _labelledStop(
            point: LatLng(to!.lat!, to.lon!),
            color: color,
            mode: focusLeg.isWalk ? null : focusLeg.mode,
            caption: focusLeg.isWalk ? null : l.alighting,
            name: to.name,
            onTap: focusLeg.isTransit && to.id != null ? () => context.push('/stop/${to.id}') : null,
          ),
        );
      }
    }

    // Départ et destination
    final first = _it.legs.first.from;
    if (first?.lat != null && (focusLeg == null || focusLeg != _it.legs.first)) {
      markers.add(
        Marker(
          point: LatLng(first!.lat!, first.lon!),
          width: 22,
          height: 22,
          child: Container(
            decoration: BoxDecoration(
              color: c.brand,
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 3.5),
              boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 6, offset: Offset(0, 2))],
            ),
          ),
        ),
      );
    }
    final last = _it.legs.last.to;
    if (last?.lat != null) {
      markers.add(
        Marker(
          point: LatLng(last!.lat!, last.lon!),
          width: 38,
          height: 38,
          alignment: Alignment.topCenter,
          child: Icon(Symbols.location_on, size: 38, color: c.danger, fill: 1),
        ),
      );
    }
    return markers;
  }

  /// Arrêt mis en avant : pastille du mode + étiquette « Montée · Bab Alioua » au-dessus.
  List<Marker> _labelledStop({
    required LatLng point,
    required Color color,
    required String? mode,
    required String? caption,
    required String name,
    VoidCallback? onTap,
  }) {
    final c = context.colors;
    return [
      Marker(
        point: point,
        width: mode == null ? 18 : 30,
        height: mode == null ? 18 : 30,
        child: mode == null
            ? _StopDot(color: color, size: 18)
            : Container(
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 3),
                  boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 6, offset: Offset(0, 2))],
                ),
                child: Center(child: ModeIcon(mode, size: 15, color: Colors.white)),
              ),
      ),
      Marker(
        point: point,
        // boîte large centrée sur l'arrêt : l'étiquette s'y décale pour rester dans l'écran
        width: MediaQuery.sizeOf(context).width * 2,
        height: 64,
        alignment: Alignment.topCenter,
        child: _EdgeAwareLabel(
          point: point,
          child: GestureDetector(
            onTap: onTap,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: c.surface,
                borderRadius: BorderRadius.circular(Radii.badge + 4),
                boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 8, offset: Offset(0, 2))],
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (caption != null) ...[
                    Text(
                      caption,
                      style: context.text.labelSmall?.copyWith(color: color, fontWeight: FontWeight.w700),
                    ),
                    Text(' · ', style: context.text.labelSmall),
                  ],
                  Flexible(
                    child: Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: context.text.labelMedium?.copyWith(color: c.text),
                    ),
                  ),
                  if (onTap != null)
                    Icon(context.isRtl ? Symbols.chevron_left : Symbols.chevron_right, size: 16, color: c.textTertiary),
                ],
              ),
            ),
          ),
        ),
      ),
    ];
  }

  // --- Écran ---------------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final first = _it.legs.first;
    final start = first.from?.lat != null ? LatLng(first.from!.lat!, first.from!.lon!) : defaultCenter;
    final focused = _focus != null;
    final bottomInset = MediaQuery.paddingOf(context).bottom;

    return CallbackShortcuts(
      bindings: {
        SingleActivator(context.isRtl ? LogicalKeyboardKey.arrowRight : LogicalKeyboardKey.arrowLeft): () => _step(-1),
        SingleActivator(context.isRtl ? LogicalKeyboardKey.arrowLeft : LogicalKeyboardKey.arrowRight): () => _step(1),
        const SingleActivator(LogicalKeyboardKey.escape): _exitFocus,
      },
      child: Focus(
        autofocus: true,
        child: PopScope(
          canPop: !focused,
          onPopInvokedWithResult: (didPop, _) {
            if (!didPop) _exitFocus();
          },
          child: Scaffold(
            body: Stack(
              children: [
                Positioned.fill(
                  child: ThniyaMap(
                    controller: _map,
                    initialCenter: start,
                    initialZoom: 13,
                    // la carte naît cadrée sur tout le trajet : pas de déplacement à l'ouverture
                    initialFit: _allPoints.length > 1
                        ? CameraFit.bounds(bounds: LatLngBounds.fromPoints(_allPoints), padding: _visible(), maxZoom: 16)
                        : null,
                    onPositionChanged: _onMapMoved,
                    children: [
                      MouseRegion(
                        hitTestBehavior: HitTestBehavior.deferToChild,
                        cursor: SystemMouseCursors.click,
                        child: GestureDetector(
                          onTap: () {
                            final hit = _hit.value;
                            if (hit != null && hit.hitValues.isNotEmpty) _focusOn(hit.hitValues.first);
                          },
                          child: PolylineLayer<int>(hitNotifier: _hit, minimumHitbox: 18, polylines: _polylines()),
                        ),
                      ),
                      MarkerLayer(markers: _markers()),
                    ],
                  ),
                ),

                // Barre du haut : retour, étape en cours, vue d'ensemble
                Align(
                  alignment: Alignment.topCenter,
                  child: SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.all(Space.s),
                      child: SizedBox(
                        height: 48,
                        child: Row(
                          children: [
                            _CircleButton(
                              icon: context.isRtl ? Symbols.arrow_forward : Symbols.arrow_back,
                              onTap: () => focused ? _exitFocus() : context.pop(),
                            ),
                            const SizedBox(width: Space.s),
                            Expanded(
                              child: AnimatedSwitcher(
                                duration: Motion.medium,
                                transitionBuilder: (child, a) => FadeTransition(
                                  opacity: a,
                                  child: SlideTransition(
                                    position: Tween(begin: const Offset(0, -.4), end: Offset.zero).animate(a),
                                    child: child,
                                  ),
                                ),
                                child: !focused
                                    ? const SizedBox(key: ValueKey('none'))
                                    : Align(
                                        key: const ValueKey('step'),
                                        alignment: AlignmentDirectional.centerStart,
                                        child: _StepPill(
                                          text: l.stepOf(_pageOf(_focus!) + 1, _steps.length),
                                          leg: _focus! < _it.legs.length ? _it.legs[_focus!] : null,
                                        ),
                                      ),
                              ),
                            ),
                            AnimatedScale(
                              scale: focused ? 1 : 0,
                              duration: Motion.medium,
                              curve: Motion.enter,
                              child: _CircleButton(icon: Symbols.zoom_out_map, onTap: _exitFocus, tooltip: l.overview),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),

                // Bouton « tout le trajet », juste au-dessus de la feuille
                ValueListenableBuilder<double>(
                  valueListenable: _sheetSize,
                  builder: (context, size, _) => Positioned(
                    right: context.isRtl ? null : Space.l,
                    left: context.isRtl ? Space.l : null,
                    bottom: MediaQuery.sizeOf(context).height * size + Space.m,
                    child: AnimatedOpacity(
                      duration: Motion.fast,
                      opacity: focused || size > .8 ? 0 : 1,
                      child: IgnorePointer(
                        ignoring: focused || size > .8,
                        child: _CircleButton(icon: Symbols.route, onTap: () => _fitAll(), tooltip: l.overview),
                      ),
                    ),
                  ),
                ),

                // Feuille : la frise des étapes (s'efface en mode étape)
                AnimatedSlide(
                  offset: focused ? const Offset(0, 1) : Offset.zero,
                  duration: Motion.slow,
                  curve: Motion.change,
                  child: IgnorePointer(
                    ignoring: focused,
                    child: DraggableScrollableSheet(
                      controller: _sheet,
                      initialChildSize: _half,
                      minChildSize: _peek,
                      maxChildSize: _full,
                      snap: true,
                      snapSizes: const [_peek, _half, _full],
                      builder: (context, scroll) => _sheetBody(scroll),
                    ),
                  ),
                ),

                // Étape précédente / suivante, juste au-dessus des cartes (annonce l'étape voisine)
                Positioned(
                  left: Space.m,
                  right: Space.m,
                  bottom: bottomInset + Space.m + _cardHeight + Space.s,
                  height: _navHeight,
                  child: AnimatedOpacity(
                    opacity: focused ? 1 : 0,
                    duration: Motion.medium,
                    child: IgnorePointer(ignoring: !focused, child: _stepNav()),
                  ),
                ),

                // Cartes d'étape : glisser pour passer d'une étape à l'autre
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: bottomInset + Space.m,
                  height: _cardHeight,
                  child: AnimatedSlide(
                    offset: focused ? Offset.zero : const Offset(0, 1.4),
                    duration: Motion.slow,
                    curve: Motion.change,
                    child: AnimatedOpacity(
                      opacity: focused ? 1 : 0,
                      duration: Motion.medium,
                      child: IgnorePointer(
                        ignoring: !focused,
                        child: _pages == null
                            ? const SizedBox.shrink()
                            : GestureDetector(
                                // glisser vers le haut : retour à la liste
                                onVerticalDragEnd: (d) {
                                  if ((d.primaryVelocity ?? 0) < -250) _exitFocus();
                                },
                                child: PageView.builder(
                                  controller: _pages,
                                  itemCount: _steps.length,
                                  onPageChanged: _onPageChanged,
                                  itemBuilder: (context, page) {
                                    final i = _steps[page];
                                    return Padding(
                                      padding: const EdgeInsets.symmetric(horizontal: 6),
                                      child: i < _it.legs.length
                                          ? _LegCard(
                                              leg: _it.legs[i],
                                              color: _legColor(_it.legs[i]),
                                              onDeparture: (d) => _chooseDeparture(i, d),
                                              onList: _exitFocus,
                                            )
                                          : _ArrivalCard(
                                              name: _it.legs.last.to?.name ?? '',
                                              time: _it.arriveAt,
                                              onList: _exitFocus,
                                            ),
                                    );
                                  },
                                ),
                              ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _stepNav() {
    final i = _focus;
    if (i == null) return const SizedBox.shrink();
    final steps = _steps;
    final page = _pageOf(i);
    final l = L.of(context);
    Widget button(int delta) {
      final target = page + delta;
      final visible = target >= 0 && target < steps.length;
      final leg = visible && steps[target] < _it.legs.length ? _it.legs[steps[target]] : null;
      final label = !visible
          ? ''
          : leg == null
          ? l.youArrive
          : leg.isWalk
          ? l.minutesShort(leg.durationMin)
          : '';
      return AnimatedScale(
        scale: visible ? 1 : 0,
        duration: Motion.fast,
        child: _StepNavButton(
          previous: delta < 0,
          mode: leg == null ? null : (leg.isWalk ? 'WALK' : leg.mode),
          line: leg?.line,
          color: leg == null ? null : _legColor(leg),
          label: label,
          tooltip: delta < 0 ? l.previousStep : l.nextStep,
          onTap: visible ? () => _step(delta) : null,
        ),
      );
    }

    return Row(children: [button(-1), const Spacer(), button(1)]);
  }

  Widget _sheetBody(ScrollController scroll) {
    final c = context.colors;
    final l = L.of(context);
    final f = Fmt.of(context);
    final last = _it.legs.last.to;
    return Container(
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(Radii.sheet)),
        boxShadow: const [BoxShadow(color: Color(0x26000000), blurRadius: 24, offset: Offset(0, -4))],
      ),
      child: ListView(
        controller: scroll,
        padding: EdgeInsets.zero,
        children: [
          Center(
            child: Container(
              margin: const EdgeInsets.only(top: Space.s),
              width: 40,
              height: 4,
              decoration: BoxDecoration(color: c.divider, borderRadius: BorderRadius.circular(2)),
            ),
          ),
          // Résumé
          Padding(
            padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, Space.s),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(f.duration(_it.durationMin), style: context.text.displayLarge),
                const SizedBox(width: Space.m),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${f.time(_it.departAt)} → ${f.time(_it.arriveAt)}', style: context.text.titleMedium),
                        Text('${l.transfers(_it.transfers)} · ${f.price(_it.price)}', style: context.text.bodySmall),
                      ],
                    ),
                  ),
                ),
                if (_updating)
                  SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: c.brand)),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: Space.l),
            child: ModeChain(_it.summary),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(Space.l, Space.s, Space.l, 0),
            child: Row(
              children: [
                Icon(Symbols.touch_app, size: 14, color: c.textTertiary),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(l.tapLegHint, style: context.text.labelSmall?.copyWith(color: c.textTertiary)),
                ),
              ],
            ),
          ),
          for (final a in _it.alerts)
            Padding(padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, 0), child: AlertBanner(a)),
          const SizedBox(height: Space.m),
          Divider(color: c.divider),
          // Frise
          AnimatedSwitcher(
            duration: Motion.medium,
            child: Column(
              key: ValueKey(_it.id),
              children: [
                for (var i = 0; i < _it.legs.length; i++)
                  _LegTile(
                    leg: _it.legs[i],
                    isFirst: i == 0,
                    highlighted: i == _lastFocus,
                    onTap: () => _focusOn(i),
                    onDeparture: (d) => _chooseDeparture(i, d),
                  ),
                _ArrivalTile(name: last?.name ?? '', time: _it.arriveAt, onTap: () => _focusOn(_it.legs.length)),
              ],
            ),
          ),
          Divider(color: c.divider),
          Padding(
            padding: const EdgeInsets.all(Space.l),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _Action(icon: Symbols.ios_share, label: l.share, onTap: _share),
                _Action(icon: Symbols.flag, label: l.reportProblem, onTap: _report),
              ],
            ),
          ),
          SizedBox(height: MediaQuery.paddingOf(context).bottom + Space.l),
        ],
      ),
    );
  }
}

// --- Éléments de carte ---------------------------------------------------------------------

/// Étiquette posée au-dessus d'un arrêt, centrée sur lui, mais décalée si besoin pour ne jamais sortir de l'écran.
class _EdgeAwareLabel extends StatelessWidget {
  const _EdgeAwareLabel({required this.point, required this.child});
  final LatLng point;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final camera = MapCamera.of(context); // reconstruit à chaque mouvement de la carte
    return CustomSingleChildLayout(
      delegate: _ClampToScreen(x: camera.latLngToScreenPoint(point).x, screen: camera.nonRotatedSize.x),
      child: child,
    );
  }
}

class _ClampToScreen extends SingleChildLayoutDelegate {
  _ClampToScreen({required this.x, required this.screen});
  final double x; // position de l'arrêt à l'écran
  final double screen; // largeur de l'écran

  static const _margin = 8.0;

  @override
  BoxConstraints getConstraintsForChild(BoxConstraints constraints) =>
      BoxConstraints(maxWidth: (screen - 2 * _margin).clamp(0, 260), maxHeight: constraints.maxHeight);

  @override
  Offset getPositionForChild(Size size, Size child) {
    final center = size.width / 2; // l'arrêt est au centre de la boîte
    final minLeft = center - x + _margin; // bord gauche de l'écran
    final maxLeft = center - x + screen - child.width - _margin; // bord droit
    final left = (center - child.width / 2).clamp(minLeft, maxLeft < minLeft ? minLeft : maxLeft);
    return Offset(left, 0);
  }

  @override
  bool shouldRelayout(_ClampToScreen old) => old.x != x || old.screen != screen;
}

class _StopDot extends StatelessWidget {
  const _StopDot({required this.color, required this.size, this.border = 3.5});
  final Color color;
  final double size;
  final double border;

  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      color: Colors.white,
      shape: BoxShape.circle,
      border: Border.all(color: color, width: border),
    ),
  );
}

/// Bouton « ‹ Train A » / « Bus B1 › » : passe à l'étape voisine en disant laquelle.
class _StepNavButton extends StatelessWidget {
  const _StepNavButton({
    required this.previous,
    required this.mode,
    required this.color,
    required this.label,
    this.line,
    required this.tooltip,
    required this.onTap,
  });
  final bool previous;
  final String? mode;
  final Color? color;
  final String label;
  final LineRef? line;
  final String tooltip;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final rtl = context.isRtl;
    final chevron = Icon(previous == rtl ? Symbols.chevron_right : Symbols.chevron_left, size: 22, color: c.text);
    final content = <Widget>[
      if (previous) chevron,
      if (mode != null)
        ModeIcon(mode!, size: 16, color: color ?? c.textSecondary)
      else
        Icon(Symbols.location_on, size: 16, color: c.danger, fill: 1),
      const SizedBox(width: 4),
      ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 110),
        child: line != null
            ? LineCodeText(line!, style: context.text.labelLarge)
            : Text(label, style: context.text.labelLarge, maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
      if (!previous) chevron,
    ];
    return Tooltip(
      message: tooltip,
      child: Material(
        color: c.surface,
        borderRadius: BorderRadius.circular(20),
        elevation: 3,
        shadowColor: Colors.black26,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: onTap,
          child: Padding(
            padding: EdgeInsetsDirectional.fromSTEB(previous ? 6 : 12, 0, previous ? 12 : 6, 0),
            child: SizedBox(
              height: 40,
              child: Row(mainAxisSize: MainAxisSize.min, children: content),
            ),
          ),
        ),
      ),
    );
  }
}

class _StepPill extends StatelessWidget {
  const _StepPill({required this.text, required this.leg});
  final String text;
  final Leg? leg;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 9),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(22),
        boxShadow: const [BoxShadow(color: Color(0x26000000), blurRadius: 10, offset: Offset(0, 3))],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          ModeIcon(leg?.mode ?? 'WALK', size: 18, color: c.textSecondary),
          const SizedBox(width: 6),
          Text(text, style: context.text.labelLarge),
        ],
      ),
    );
  }
}

// --- Cartes d'étape (mode étape) -----------------------------------------------------------

class _CardFrame extends StatelessWidget {
  const _CardFrame({required this.color, required this.child, required this.onList});
  final Color color;
  final Widget child;
  final VoidCallback onList;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    // L'ombre est portée par le conteneur extérieur, sous le fond : peinte à l'intérieur, elle grisait la carte
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(Radii.card),
        boxShadow: const [BoxShadow(color: Color(0x2E000000), blurRadius: 18, offset: Offset(0, 6))],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(Radii.card),
        child: Container(
          decoration: BoxDecoration(
            color: c.surface,
            border: BorderDirectional(start: BorderSide(color: color, width: 5)),
          ),
          child: Stack(
            fit: StackFit.expand,
            children: [
              Padding(padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, Space.m), child: child),
              // Poignée : rappelle qu'on peut remonter à la liste
              PositionedDirectional(
                top: 6,
                end: 6,
                child: IconButton(
                  visualDensity: VisualDensity.compact,
                  tooltip: L.of(context).showList,
                  onPressed: onList,
                  icon: Icon(Symbols.format_list_bulleted, size: 20, color: c.textTertiary),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LegCard extends StatelessWidget {
  const _LegCard({required this.leg, required this.color, required this.onDeparture, required this.onList});
  final Leg leg;
  final Color color;
  final ValueChanged<Departure> onDeparture;
  final VoidCallback onList;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l = L.of(context);
    final f = Fmt.of(context);

    if (leg.isWalk) {
      return _CardFrame(
        color: c.walk,
        onList: onList,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                ModeIcon('WALK', size: 22, color: c.textSecondary),
                const SizedBox(width: Space.s),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsetsDirectional.only(end: 36),
                    child: Text(
                      l.walkTo(leg.to?.name ?? ''),
                      style: context.text.titleMedium,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(l.walkDistance(leg.durationMin, leg.distanceM ?? 0), style: context.text.bodySmall),
            const SizedBox(height: Space.s),
            Expanded(
              child: ListView(
                padding: EdgeInsets.zero,
                children: [
                  for (final s in leg.steps)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Row(
                        children: [
                          Icon(Symbols.turn_right, size: 16, color: c.textTertiary),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(s.instruction, style: context.text.bodySmall?.copyWith(color: c.text)),
                          ),
                          Text('${s.distanceM} m', style: context.text.labelSmall),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    final dep = leg.departure;
    return _CardFrame(
      color: color,
      onList: onList,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsetsDirectional.only(end: 36),
            child: Row(
              children: [
                if (leg.line != null) LineBadge(leg.line!),
                const SizedBox(width: Space.s),
                Expanded(
                  child: Text(
                    leg.line != null && leg.line!.publicCode == leg.headsign
                        ? leg.line!.name
                        : l.towards(leg.headsign ?? leg.to?.name ?? ''),
                    style: context.text.bodyMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: Space.m),
          _CardStop(
            color: color,
            label: l.boardAt(leg.from?.name ?? ''),
            trailing: leg.departAt != null ? f.time(leg.departAt!) : null,
          ),
          _CardRail(
            color: color,
            text:
                '${l.stopsCount(leg.intermediateStops.length + 1)} · '
                '${leg.durationEstimated ? '~' : ''}${f.duration(leg.durationMin)}'
                '${leg.price.known ? ' · ${f.price(leg.price)}' : ''}',
          ),
          _CardStop(
            color: color,
            label: l.getOffAt(leg.to?.name ?? ''),
            trailing: leg.arriveAt != null ? f.time(leg.arriveAt!) : null,
          ),
          const Spacer(),
          if (dep != null && dep.isFrequency)
            Row(
              children: [
                DepartureLine([dep]),
                if (leg.departsWhenFull) ...[
                  const SizedBox(width: Space.s),
                  Flexible(
                    child: Text(
                      '· ${l.departsWhenFull}',
                      style: context.text.bodySmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ],
            )
          else if (leg.departures != null && leg.departures!.length > 1)
            DepartureChips(
              departures: leg.departures!,
              selected: leg.departAt,
              onSelected: onDeparture,
              scrollable: true,
            ),
        ],
      ),
    );
  }
}

class _CardStop extends StatelessWidget {
  const _CardStop({required this.color, required this.label, this.trailing});
  final Color color;
  final String label;
  final String? trailing;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      SizedBox(
        width: 18,
        child: Center(child: _StopDot(color: color, size: 14, border: 3)),
      ),
      const SizedBox(width: Space.s),
      Expanded(
        child: Text(label, style: context.text.titleSmall, maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
      if (trailing != null) Text(trailing!, style: context.text.titleSmall),
    ],
  );
}

class _CardRail extends StatelessWidget {
  const _CardRail({required this.color, required this.text});
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 30,
    child: Row(
      children: [
        SizedBox(
          width: 18,
          child: Center(
            child: Container(
              width: 4,
              decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2)),
            ),
          ),
        ),
        const SizedBox(width: Space.s),
        Expanded(
          child: Text(
            text,
            style: context.text.labelMedium?.copyWith(color: context.colors.textSecondary),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    ),
  );
}

class _ArrivalCard extends StatelessWidget {
  const _ArrivalCard({required this.name, required this.time, required this.onList});
  final String name;
  final DateTime time;
  final VoidCallback onList;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l = L.of(context);
    return _CardFrame(
      color: c.danger,
      onList: onList,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Symbols.location_on, color: c.danger, fill: 1, size: 34),
          const SizedBox(height: Space.s),
          Text(l.youArrive, style: context.text.labelLarge?.copyWith(color: c.textSecondary)),
          Text(name, style: context.text.headlineSmall, maxLines: 2, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 4),
          Text(Fmt.of(context).time(time), style: context.text.titleMedium),
        ],
      ),
    );
  }
}

// --- Frise (vue d'ensemble) ----------------------------------------------------------------

/// Une étape de la frise : rail vertical à gauche (couleur de la ligne, pointillés pour la marche).
class _LegTile extends StatefulWidget {
  const _LegTile({
    required this.leg,
    required this.isFirst,
    required this.highlighted,
    required this.onTap,
    required this.onDeparture,
  });
  final Leg leg;
  final bool isFirst;
  final bool highlighted;
  final VoidCallback onTap;
  final ValueChanged<Departure> onDeparture;

  @override
  State<_LegTile> createState() => _LegTileState();
}

class _LegTileState extends State<_LegTile> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final leg = widget.leg;
    final c = context.colors;
    final l = L.of(context);
    final f = Fmt.of(context);
    final color = leg.isWalk ? c.walk : (leg.line == null ? c.brand : hexColor(leg.line!.color));

    Widget body;
    if (leg.isWalk) {
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.isFirst) Text(leg.from?.name ?? '', style: context.text.titleMedium) else const SizedBox.shrink(),
          Padding(
            padding: EdgeInsets.only(top: widget.isFirst ? Space.s : 0),
            child: Row(
              children: [
                ModeIcon('WALK', size: 18, color: c.textSecondary),
                const SizedBox(width: 6),
                Expanded(child: Text(l.walkTo(leg.to?.name ?? ''), style: context.text.bodyMedium)),
              ],
            ),
          ),
          Text(l.walkDistance(leg.durationMin, leg.distanceM ?? 0), style: context.text.bodySmall),
          if (leg.steps.isNotEmpty)
            TextButton(
              style: TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(0, 32)),
              onPressed: () => setState(() => _expanded = !_expanded),
              child: Icon(_expanded ? Symbols.expand_less : Symbols.expand_more, color: c.textTertiary),
            ),
          AnimatedSize(
            duration: Motion.medium,
            curve: Motion.enter,
            child: !_expanded
                ? const SizedBox(width: double.infinity)
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final s in leg.steps)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(
                            children: [
                              Icon(Symbols.turn_right, size: 16, color: c.textTertiary),
                              const SizedBox(width: 6),
                              Expanded(child: Text(s.instruction, style: context.text.bodySmall)),
                              Text('${s.distanceM} m', style: context.text.labelSmall),
                            ],
                          ),
                        ),
                    ],
                  ),
          ),
        ],
      );
    } else {
      final dep = leg.departure;
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(leg.from?.name ?? '', style: context.text.titleMedium)),
              if (leg.departAt != null)
                Text(f.time(leg.departAt!), style: context.text.titleMedium?.copyWith(color: c.textSecondary)),
            ],
          ),
          if (leg.from?.platform != null) Text(l.platform(leg.from!.platform!), style: context.text.bodySmall),
          const SizedBox(height: Space.s),
          Row(
            children: [
              if (leg.line != null) LineBadge(leg.line!),
              const SizedBox(width: Space.s),
              Expanded(
                // louage : la pastille dit déjà la destination, on donne le nom de la ligne
                child: Text(
                  leg.line != null && leg.line!.publicCode == leg.headsign
                      ? leg.line!.name
                      : l.towards(leg.headsign ?? leg.to?.name ?? ''),
                  style: context.text.bodyMedium,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (leg.price.known)
                Text(f.price(leg.price), style: context.text.labelMedium?.copyWith(color: c.textSecondary)),
            ],
          ),
          if (leg.line?.estimated ?? false)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(
                children: [
                  Icon(Symbols.info, size: 14, color: c.textTertiary),
                  const SizedBox(width: 4),
                  Text(l.estimatedTimes, style: context.text.labelSmall?.copyWith(color: c.textTertiary)),
                ],
              ),
            ),
          const SizedBox(height: Space.s),
          if (dep != null && dep.isFrequency) ...[
            DepartureLine([dep]),
            if (leg.departsWhenFull)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(l.departsWhenFull, style: context.text.bodySmall),
              ),
          ] else if (leg.departures != null && leg.departures!.length > 1) ...[
            Text(l.otherDepartures, style: context.text.labelSmall),
            const SizedBox(height: 6),
            DepartureChips(departures: leg.departures!, selected: leg.departAt, onSelected: widget.onDeparture),
          ],
          const SizedBox(height: Space.s),
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Text(
                    '${l.stopsCount(leg.intermediateStops.length + 1)} · ${leg.durationEstimated ? '~' : ''}${f.duration(leg.durationMin)}',
                    style: context.text.labelMedium?.copyWith(color: c.textSecondary),
                  ),
                  Icon(_expanded ? Symbols.expand_less : Symbols.expand_more, size: 18, color: c.textTertiary),
                ],
              ),
            ),
          ),
          AnimatedSize(
            duration: Motion.medium,
            curve: Motion.enter,
            child: !_expanded
                ? const SizedBox(width: double.infinity)
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final s in leg.intermediateStops)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 3),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(s.name, style: context.text.bodySmall?.copyWith(color: c.text)),
                              ),
                              if (s.time != null) Text(f.time(s.time!), style: context.text.labelSmall),
                            ],
                          ),
                        ),
                    ],
                  ),
          ),
          const SizedBox(height: Space.s),
          Text(l.getOffAt(leg.to?.name ?? ''), style: context.text.titleSmall),
          if (leg.arriveAt != null) Text(f.time(leg.arriveAt!), style: context.text.bodySmall),
        ],
      );
    }

    return AnimatedContainer(
      duration: Motion.slow,
      color: widget.highlighted ? color.withValues(alpha: .08) : Colors.transparent,
      child: InkWell(
        onTap: widget.onTap,
        // Le rail est placé derrière l'étape, sur toute sa hauteur réelle : pas d'IntrinsicHeight, dont
        // l'estimation divergeait pendant le repli animé des arrêts intermédiaires (bande jaune et noire en debug).
        child: Stack(
          children: [
            PositionedDirectional(
              start: 0,
              top: 0,
              bottom: 0,
              width: 56,
              child: Column(
                children: [
                  const SizedBox(height: Space.l),
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(color: leg.isWalk ? c.background : color, shape: BoxShape.circle),
                    child: Center(
                      child: ModeIcon(
                        leg.mode,
                        size: 16,
                        color: leg.isWalk ? c.textSecondary : hexColor(leg.line?.textColor ?? '#FFFFFF'),
                      ),
                    ),
                  ),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: leg.isWalk
                          ? _DottedRail(color: c.walk)
                          : Container(
                              width: 6,
                              decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
                            ),
                    ),
                  ),
                ],
              ),
            ),
            // Indice : l'étape se montre sur la carte
            PositionedDirectional(
              top: Space.l,
              end: Space.m,
              child: Icon(Symbols.map, size: 18, color: c.textTertiary),
            ),
            SizedBox(
              width: double.infinity,
              child: Padding(
                // Début : le rail (56) ; fin : l'icône de carte (18) et ses marges
                padding: const EdgeInsetsDirectional.fromSTEB(56, Space.l, Space.s + 18 + Space.m, Space.m),
                child: body,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Rail en pointillés d'une étape à pied, dessiné (CustomPaint) sur toute la hauteur de l'étape.
class _DottedRail extends StatelessWidget {
  const _DottedRail({required this.color});
  final Color color;

  @override
  Widget build(BuildContext context) =>
      CustomPaint(painter: _DotsPainter(color), child: const SizedBox(width: 4, height: double.infinity));
}

class _DotsPainter extends CustomPainter {
  _DotsPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final n = (size.height / 9).floor().clamp(1, 200);
    final step = size.height / n;
    final paint = Paint()..color = color;
    for (var i = 0; i < n; i++) {
      canvas.drawCircle(Offset(size.width / 2, step * (i + .5)), 2, paint);
    }
  }

  @override
  bool shouldRepaint(_DotsPainter old) => old.color != color;
}

class _ArrivalTile extends StatelessWidget {
  const _ArrivalTile({required this.name, required this.time, required this.onTap});
  final String name;
  final DateTime time;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: Space.m),
        child: Row(
          children: [
            SizedBox(width: 56, child: Icon(Symbols.location_on, color: c.danger, fill: 1, size: 28)),
            Expanded(child: Text(name, style: context.text.titleMedium)),
            Padding(
              padding: const EdgeInsetsDirectional.only(end: Space.l),
              child: Text(Fmt.of(context).time(time), style: context.text.titleMedium),
            ),
          ],
        ),
      ),
    );
  }
}

class _Action extends StatelessWidget {
  const _Action({required this.icon, required this.label, required this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => InkWell(
    borderRadius: BorderRadius.circular(Radii.chip),
    onTap: onTap,
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: Space.l, vertical: Space.s),
      child: Column(
        children: [
          Icon(icon, color: context.colors.brand),
          const SizedBox(height: 4),
          Text(label, style: context.text.labelMedium),
        ],
      ),
    ),
  );
}

class _CircleButton extends StatelessWidget {
  const _CircleButton({required this.icon, required this.onTap, this.tooltip});
  final IconData icon;
  final VoidCallback onTap;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final button = Material(
      color: context.colors.surface,
      shape: const CircleBorder(),
      elevation: 3,
      shadowColor: Colors.black26,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Icon(icon, color: context.colors.text),
        ),
      ),
    );
    return tooltip == null ? button : Tooltip(message: tooltip!, child: button);
  }
}
