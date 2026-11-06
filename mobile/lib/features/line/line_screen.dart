import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import 'package:material_symbols_icons/symbols.dart';

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

final lineProvider = FutureProvider.autoDispose.family<LineDetail, String>(
  (ref, id) => ref.watch(apiProvider).line(id),
);

final timetableProvider = FutureProvider.autoDispose.family<Timetable, (String, String, String?, DateTime)>(
  (ref, k) => ref.watch(apiProvider).timetable(k.$1, direction: k.$2, stop: k.$3, date: k.$4),
);

final lineStopDeparturesProvider = FutureProvider.autoDispose.family<List<BoardRow>, (String, String, String)>(
  (ref, k) => ref.watch(apiProvider).lineStopDepartures(k.$1, k.$2, direction: k.$3, limit: 5),
);

/// Fiche ligne (specs/07 §5.5) : la ligne sur la carte, et dans une feuille le schéma des arrêts et les horaires.
/// Toucher un arrêt (dans le schéma ou sur la carte) le montre sur la carte et déplie ses prochains départs.
class LineScreen extends ConsumerStatefulWidget {
  const LineScreen({super.key, required this.lineId, this.focusStop});
  final String lineId;
  final String? focusStop;

  @override
  ConsumerState<LineScreen> createState() => _LineScreenState();
}

class _LineScreenState extends ConsumerState<LineScreen> with TickerProviderStateMixin {
  static const _min = .3;
  static const _mid = .55;
  static const _max = .94;

  late final _tabs = TabController(length: 2, vsync: this);
  final _map = MapController();
  late final _camera = CameraMotion(this, _map);
  final _sheet = DraggableScrollableController();
  final _sheetSize = ValueNotifier<double>(_mid);
  final _rowKeys = <String, GlobalKey>{};
  int _direction = 0;
  String? _stop; // arrêt des horaires
  String? _selected; // arrêt mis en avant sur la carte et dans le schéma
  DateTime _date = tunisNow();

  @override
  void initState() {
    super.initState();
    _stop = widget.focusStop;
    _selected = widget.focusStop;
    _tabs.addListener(() => setState(() {}));
    _sheet.addListener(() => _sheetSize.value = _sheet.size);
  }

  @override
  void dispose() {
    _tabs.dispose();
    _camera.dispose();
    _sheet.dispose();
    _sheetSize.dispose();
    super.dispose();
  }

  EdgeInsets _visible() {
    final mq = MediaQuery.of(context);
    final sheet = _sheet.isAttached ? _sheet.size : _mid;
    return EdgeInsets.fromLTRB(48, mq.padding.top + 80, 48, mq.size.height * sheet + Space.l);
  }

  List<LatLng> _points(DirectionView dir) => [
    for (final s in dir.stops)
      if (s.lat != null) LatLng(s.lat!, s.lon!),
  ];

  void _fitLine(DirectionView dir) {
    final pts = _points(dir);
    if (pts.length < 2) return;
    _camera.fitPoints(pts, _visible(), maxZoom: 15.5);
  }

  void _select(DiagramStop s) {
    HapticFeedback.selectionClick();
    if (_selected == s.stopId) {
      setState(() => _selected = null);
      return;
    }
    setState(() {
      _selected = s.stopId;
      _stop = s.stopId;
    });
    // la carte reprend de la place pour montrer l'arrêt
    final target = _sheet.isAttached && _sheet.size > .5 ? .45 : null;
    if (target != null) _sheet.animateTo(target, duration: Motion.slow, curve: Motion.enter);
    final mq = MediaQuery.of(context);
    final padding = EdgeInsets.fromLTRB(
      48,
      mq.padding.top + 80,
      48,
      mq.size.height * (target ?? _sheet.size) + Space.l,
    );
    if (s.lat != null) _camera.focusPoint(LatLng(s.lat!, s.lon!), padding, zoom: 15.5);
    // et la ligne de l'arrêt reste visible dans le schéma
    Future.delayed(Motion.slow + const Duration(milliseconds: 50), () {
      final ctx = _rowKeys[s.stopId]?.currentContext;
      if (ctx != null && ctx.mounted) {
        Scrollable.ensureVisible(ctx, duration: Motion.medium, curve: Motion.change, alignment: .15);
      }
    });
  }

  void _onMapMoved(MapCamera camera, bool gesture) {
    if (!gesture) return;
    _camera.stop();
    if (_sheet.isAttached && _sheet.size > _min + .05) {
      _sheet.animateTo(_min, duration: Motion.slow, curve: Motion.enter);
    }
  }

  @override
  Widget build(BuildContext context) {
    final detail = ref.watch(lineProvider(widget.lineId));
    return Scaffold(
      body: detail.when(
        loading: () => const Center(
          child: Padding(padding: EdgeInsets.all(Space.xl), child: SkeletonCard()),
        ),
        error: (e, _) => MessageState.error(context, e, () => ref.invalidate(lineProvider(widget.lineId))),
        data: (d) => _build(context, d),
      ),
    );
  }

  Widget _build(BuildContext context, LineDetail d) {
    final l = L.of(context);
    final c = context.colors;
    final lineColor = hexColor(d.line.color);
    final dir = d.directions[_direction.clamp(0, d.directions.length - 1)];
    final pts = _points(dir);
    final selected = dir.stops.where((s) => s.stopId == _selected).firstOrNull;

    return Stack(
      children: [
        Positioned.fill(
          child: ThniyaMap(
            controller: _map,
            // la carte naît cadrée (arrêt choisi, sinon toute la ligne) : pas de déplacement à l'ouverture
            initialCenter: selected?.lat != null
                ? LatLng(selected!.lat!, selected.lon!)
                : (pts.isNotEmpty ? pts[pts.length ~/ 2] : defaultCenter),
            initialZoom: selected?.lat != null ? 15 : 13,
            initialFit: selected?.lat == null && pts.length > 1
                ? CameraFit.bounds(bounds: LatLngBounds.fromPoints(pts), padding: _visible(), maxZoom: 15.5)
                : null,
            onPositionChanged: _onMapMoved,
            onTap: (_) => setState(() => _selected = null),
            children: [
              PolylineLayer(
                polylines: [
                  if (pts.length > 1) ...[
                    Polyline(points: pts, strokeWidth: 7.5, color: Colors.white),
                    Polyline(points: pts, strokeWidth: 4.5, color: lineColor),
                  ],
                ],
              ),
              MarkerLayer(
                markers: [
                  for (final s in dir.stops)
                    if (s.lat != null && s.stopId != _selected)
                      Marker(
                        point: LatLng(s.lat!, s.lon!),
                        width: 26,
                        height: 26,
                        child: GestureDetector(
                          onTap: () => _select(s),
                          behavior: HitTestBehavior.opaque,
                          child: Center(
                            child: Container(
                              width: s.isTerminus ? 18 : 13,
                              height: s.isTerminus ? 18 : 13,
                              decoration: BoxDecoration(
                                color: Colors.white,
                                shape: BoxShape.circle,
                                border: Border.all(color: lineColor, width: s.isTerminus ? 4 : 3),
                              ),
                            ),
                          ),
                        ),
                      ),
                  if (selected?.lat != null) ...[
                    Marker(
                      point: LatLng(selected!.lat!, selected.lon!),
                      width: 30,
                      height: 30,
                      child: Container(
                        decoration: BoxDecoration(
                          color: lineColor,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 3),
                          boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 6, offset: Offset(0, 2))],
                        ),
                        child: Center(
                          child: ModeIcon(d.line.mode ?? 'BUS', size: 15, color: hexColor(d.line.textColor)),
                        ),
                      ),
                    ),
                    Marker(
                      point: LatLng(selected.lat!, selected.lon!),
                      width: 220,
                      height: 62,
                      alignment: Alignment.topCenter,
                      child: Align(
                        alignment: Alignment.topCenter,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: c.surface,
                            borderRadius: BorderRadius.circular(Radii.badge + 4),
                            boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 8, offset: Offset(0, 2))],
                          ),
                          child: Text(
                            selected.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: context.text.labelMedium?.copyWith(color: c.text),
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),

        // Barre du haut : retour et pastille de la ligne
        Align(
          alignment: Alignment.topCenter,
          child: SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(Space.s),
              child: Row(
                children: [
                  _MapButton(
                    icon: context.isRtl ? Symbols.arrow_forward : Symbols.arrow_back,
                    onTap: () => context.pop(),
                  ),
                  const SizedBox(width: Space.s),
                  Flexible(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 8),
                      decoration: BoxDecoration(
                        color: c.surface,
                        borderRadius: BorderRadius.circular(22),
                        boxShadow: const [BoxShadow(color: Color(0x26000000), blurRadius: 10, offset: Offset(0, 3))],
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          LineBadge(d.line, compact: true),
                          const SizedBox(width: Space.s),
                          Flexible(
                            child: Text(
                              l.towards(dir.headsign),
                              style: context.text.labelLarge,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),

        // Voir toute la ligne, au-dessus de la feuille
        ValueListenableBuilder<double>(
          valueListenable: _sheetSize,
          builder: (context, size, _) => Positioned(
            right: context.isRtl ? null : Space.l,
            left: context.isRtl ? Space.l : null,
            bottom: MediaQuery.sizeOf(context).height * size + Space.m,
            child: AnimatedOpacity(
              duration: Motion.fast,
              opacity: size > .8 ? 0 : 1,
              child: _MapButton(icon: Symbols.route, onTap: () => _fitLine(dir)),
            ),
          ),
        ),

        DraggableScrollableSheet(
          controller: _sheet,
          initialChildSize: _mid,
          minChildSize: _min,
          maxChildSize: _max,
          snap: true,
          snapSizes: const [_min, _mid, _max],
          builder: (context, scroll) => Container(
            decoration: BoxDecoration(
              color: c.background,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(Radii.sheet)),
              boxShadow: const [BoxShadow(color: Color(0x26000000), blurRadius: 24, offset: Offset(0, -4))],
            ),
            child: ListView(
              controller: scroll,
              padding: const EdgeInsets.only(bottom: Space.xxl),
              children: [
                Center(
                  child: Container(
                    margin: const EdgeInsets.only(top: Space.s),
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(color: c.divider, borderRadius: BorderRadius.circular(2)),
                  ),
                ),
                // En-tête aux couleurs de la ligne
                Padding(
                  padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, 0),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(color: lineColor, borderRadius: BorderRadius.circular(Radii.badge)),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            ModeIcon(d.line.mode ?? 'TRAIN', size: 20, color: hexColor(d.line.textColor)),
                            const SizedBox(width: 4),
                            LineCodeText(
                              d.line,
                              style: context.text.titleMedium?.copyWith(color: hexColor(d.line.textColor)),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: Space.m),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(d.line.name, style: context.text.titleLarge),
                            Text(
                              [d.network, if (d.longName != null) d.longName!].join(' · '),
                              style: context.text.bodySmall,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                if (d.period != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, 0),
                    child: PeriodBanner(d.period),
                  ),
                for (final a in d.alerts)
                  Padding(padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, 0), child: AlertBanner(a)),
                // Direction
                Padding(
                  padding: const EdgeInsets.fromLTRB(Space.l, Space.l, Space.l, Space.s),
                  child: SegmentedButton<int>(
                    showSelectedIcon: false,
                    segments: [
                      for (var i = 0; i < d.directions.length; i++)
                        ButtonSegment(
                          value: i,
                          label: Text(l.towards(d.directions[i].headsign), overflow: TextOverflow.ellipsis),
                          icon: Icon(context.isRtl ? Symbols.arrow_back : Symbols.arrow_forward, size: 16),
                        ),
                    ],
                    selected: {_direction},
                    onSelectionChanged: (s) {
                      HapticFeedback.selectionClick();
                      setState(() => _direction = s.first);
                      _fitLine(d.directions[s.first]);
                    },
                  ),
                ),
                TabBar(
                  controller: _tabs,
                  indicatorColor: lineColor,
                  indicatorWeight: 3,
                  labelColor: c.text,
                  unselectedLabelColor: c.textSecondary,
                  labelStyle: context.text.labelLarge,
                  dividerColor: c.divider,
                  tabs: [
                    Tab(text: l.stops),
                    Tab(text: l.timetable),
                  ],
                ),
                AnimatedSwitcher(
                  duration: Motion.medium,
                  child: _tabs.index == 0
                      ? _Diagram(
                          key: ValueKey('diagram-$_direction'),
                          line: d,
                          direction: dir,
                          color: lineColor,
                          selected: _selected,
                          rowKeys: _rowKeys,
                          onStopTap: _select,
                        )
                      : _TimetableView(
                          key: ValueKey('timetable-$_direction-$_stop-${_date.day}'),
                          line: d,
                          direction: dir,
                          stopId: _stop ?? dir.stops.first.stopId,
                          date: _date,
                          onDate: (x) => setState(() => _date = x),
                          onStop: (x) => setState(() => _stop = x),
                        ),
                ),
                if (d.verifiedAt != null)
                  Padding(
                    padding: const EdgeInsets.all(Space.l),
                    child: Row(
                      children: [
                        Icon(
                          d.confidence == 'OFFICIEL' ? Symbols.verified : Symbols.info,
                          size: 16,
                          color: c.textTertiary,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            '${d.confidence == 'OFFICIEL' ? l.officialTimes : l.estimatedTimes}'
                            '${d.versions.isEmpty ? '' : ' · ${d.versions.first.id}'}',
                            style: context.text.bodySmall,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _MapButton extends StatelessWidget {
  const _MapButton({required this.icon, required this.onTap});
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
        padding: const EdgeInsets.all(10),
        child: Icon(icon, color: context.colors.text),
      ),
    ),
  );
}

/// Schéma de ligne vertical : un trait de la couleur de la ligne, un point par arrêt, correspondances à droite.
/// L'arrêt choisi se déplie sur place avec ses prochains départs.
class _Diagram extends StatelessWidget {
  const _Diagram({
    super.key,
    required this.line,
    required this.direction,
    required this.color,
    required this.selected,
    required this.rowKeys,
    required this.onStopTap,
  });
  final LineDetail line;
  final DirectionView direction;
  final Color color;
  final String? selected;
  final Map<String, GlobalKey> rowKeys;
  final ValueChanged<DiagramStop> onStopTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final stops = direction.stops;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: Space.l, vertical: Space.s),
      decoration: BoxDecoration(color: c.surface, borderRadius: BorderRadius.circular(Radii.card)),
      padding: const EdgeInsets.symmetric(vertical: Space.m),
      child: Column(
        children: [
          for (var i = 0; i < stops.length; i++)
            KeyedSubtree(
              key: rowKeys.putIfAbsent(stops[i].stopId, GlobalKey.new),
              child: AnimatedContainer(
                duration: Motion.medium,
                color: stops[i].stopId == selected ? color.withValues(alpha: .1) : Colors.transparent,
                child: InkWell(
                  onTap: () => onStopTap(stops[i]),
                  // Le tracé de la ligne est dessiné derrière la rangée, sur toute sa hauteur réelle : pas
                  // d'IntrinsicHeight, dont l'estimation divergeait quand les départs d'un arrêt se dépliaient
                  // (débordement de 8 px, bande jaune et noire en debug).
                  child: Stack(
                    children: [
                      PositionedDirectional(
                        start: 0,
                        top: 0,
                        bottom: 0,
                        width: 56,
                        child: CustomPaint(
                          painter: _RailPainter(
                            color: color,
                            first: i == 0,
                            last: i == stops.length - 1,
                            terminus: stops[i].isTerminus,
                            surface: c.surface,
                            selected: stops[i].stopId == selected,
                          ),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsetsDirectional.only(start: 56),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: Space.m),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          stops[i].name,
                                          style: stops[i].isTerminus
                                              ? context.text.titleMedium
                                              : context.text.bodyLarge,
                                        ),
                                        if (stops[i].area != null && stops[i].area != stops[i].name)
                                          Text(stops[i].area!, style: context.text.bodySmall),
                                      ],
                                    ),
                                  ),
                                  for (final x in stops[i].interchanges.take(3))
                                    Padding(
                                      padding: const EdgeInsetsDirectional.only(end: 6),
                                      child: LineBadge(x, compact: true),
                                    ),
                                  Padding(
                                    padding: const EdgeInsetsDirectional.only(end: Space.m),
                                    child: AnimatedRotation(
                                      turns: stops[i].stopId == selected ? .25 : 0,
                                      duration: Motion.medium,
                                      child: Icon(
                                        context.isRtl ? Symbols.chevron_left : Symbols.chevron_right,
                                        color: c.textTertiary,
                                        size: 20,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              AnimatedSize(
                                duration: Motion.medium,
                                curve: Motion.enter,
                                child: stops[i].stopId != selected
                                    ? const SizedBox(width: double.infinity)
                                    : _StopDepartures(line: line, direction: direction, stop: stops[i]),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _RailPainter extends CustomPainter {
  _RailPainter({
    required this.color,
    required this.first,
    required this.last,
    required this.terminus,
    required this.surface,
    this.selected = false,
  });
  final Color color;
  final bool first;
  final bool last;
  final bool terminus;
  final Color surface;
  final bool selected;

  @override
  void paint(Canvas canvas, Size size) {
    final x = size.width / 2;
    const y = 28.0; // au niveau du nom de l'arrêt, même quand la ligne est dépliée
    final rail = Paint()
      ..color = color
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(x, first ? y : 0), Offset(x, last ? y : size.height), rail);
    final r = selected
        ? 10.0
        : terminus
        ? 9.0
        : 6.5;
    canvas.drawCircle(Offset(x, y), r, Paint()..color = selected ? color : surface);
    canvas.drawCircle(
      Offset(x, y),
      r,
      Paint()
        ..color = selected ? surface : color
        ..style = PaintingStyle.stroke
        ..strokeWidth = selected
            ? 3
            : terminus
            ? 4
            : 3.5,
    );
  }

  @override
  bool shouldRepaint(_RailPainter old) =>
      old.color != color || old.first != first || old.last != last || old.selected != selected;
}

/// Prochains départs de la ligne à l'arrêt choisi, dépliés dans le schéma.
class _StopDepartures extends ConsumerWidget {
  const _StopDepartures({required this.line, required this.direction, required this.stop});
  final LineDetail line;
  final DirectionView direction;
  final DiagramStop stop;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final f = Fmt.of(context);
    final rows = ref.watch(lineStopDeparturesProvider((line.line.id, stop.stopId, direction.id)));
    return Padding(
      padding: const EdgeInsetsDirectional.only(top: Space.s, end: Space.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          rows.when(
            loading: () => const Skeleton(height: 24, width: 200),
            error: (e, _) => Text(l.loadingError, style: context.text.bodySmall),
            data: (r) {
              final deps = r.expand((x) => x.departures).toList();
              final row = r.firstOrNull;
              if (deps.isEmpty) {
                return Text(
                  row?.nextServiceAt != null ? l.nextService(f.time(row!.nextServiceAt!)) : l.noServiceToday,
                  style: context.text.bodyMedium,
                );
              }
              return DepartureLine(deps, max: 4);
            },
          ),
          const SizedBox(height: Space.s),
          TextButton.icon(
            style: TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(0, 36)),
            onPressed: () => context.push('/stop/${stop.stopId}'),
            icon: const Icon(Symbols.signpost, size: 18),
            label: Text(l.seeStop),
          ),
        ],
      ),
    );
  }
}

/// Horaires d'une journée : sélecteur de date et d'arrêt, grille heure | minutes (specs/07 §5.5).
class _TimetableView extends ConsumerWidget {
  const _TimetableView({
    super.key,
    required this.line,
    required this.direction,
    required this.stopId,
    required this.date,
    required this.onDate,
    required this.onStop,
  });
  final LineDetail line;
  final DirectionView direction;
  final String stopId;
  final DateTime date;
  final ValueChanged<DateTime> onDate;
  final ValueChanged<String> onStop;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final c = context.colors;
    final now = tunisNow();
    final today = DateTime(now.year, now.month, now.day);
    DateTime next(int weekday) =>
        today.add(Duration(days: (weekday - today.weekday + 7) % 7 == 0 ? 7 : (weekday - today.weekday + 7) % 7));
    final dates = <(String, DateTime)>[
      (l.today, today),
      (l.tomorrow, today.add(const Duration(days: 1))),
      (l.saturday, next(DateTime.saturday)),
      (l.sunday, next(DateTime.sunday)),
    ];
    final selectedDay = DateTime(date.year, date.month, date.day);
    final tt = ref.watch(timetableProvider((line.line.id, direction.id, stopId, selectedDay)));
    final lineColor = hexColor(line.line.color);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 44,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: Space.l),
            children: [
              for (final (label, d) in dates)
                Padding(
                  padding: const EdgeInsetsDirectional.only(end: Space.s),
                  child: ChoiceChip(label: Text(label), selected: d == selectedDay, onSelected: (_) => onDate(d)),
                ),
              ActionChip(
                avatar: const Icon(Symbols.calendar_month, size: 18),
                label: Text('${selectedDay.day}/${selectedDay.month}'),
                onPressed: () async {
                  final picked = await showDatePicker(
                    context: context,
                    initialDate: selectedDay,
                    firstDate: today,
                    lastDate: today.add(const Duration(days: 120)),
                  );
                  if (picked != null) onDate(picked);
                },
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(Space.l, Space.s, Space.l, 0),
          child: DropdownButtonFormField<String>(
            initialValue: direction.stops.any((s) => s.stopId == stopId) ? stopId : direction.stops.first.stopId,
            isExpanded: true,
            decoration: const InputDecoration(prefixIcon: Icon(Symbols.signpost)),
            items: [
              for (final s in direction.stops.take(direction.stops.length - 1))
                DropdownMenuItem(value: s.stopId, child: Text(s.name)),
            ],
            onChanged: (v) => v == null ? null : onStop(v),
          ),
        ),
        tt.when(
          loading: () => const Padding(padding: EdgeInsets.all(Space.l), child: SkeletonCard()),
          error: (e, _) => MessageState.error(context, e, () => ref.invalidate(timetableProvider)),
          data: (t) => Padding(
            padding: const EdgeInsets.all(Space.l),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (t.period != null) PeriodBanner(t.period),
                if (t.period != null && t.gridPeriod != null && t.gridPeriod != t.period!.id)
                  Padding(
                    padding: const EdgeInsets.only(top: Space.s),
                    child: Text(l.usualTimetableNotice(t.period!.name), style: context.text.bodySmall),
                  ),
                const SizedBox(height: Space.s),
                if (t.firstDeparture != null)
                  Text(
                    '${l.departuresCount(t.count)} · ${l.firstLast(t.firstDeparture!, t.lastDeparture!)}',
                    style: context.text.labelMedium?.copyWith(color: c.textSecondary),
                  ),
                const SizedBox(height: Space.m),
                if (t.kind == 'FREQUENCY')
                  for (final b in t.frequencies)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(Symbols.autorenew, color: c.accent),
                      title: Text('${b.from} – ${b.to}'),
                      trailing: Text(b.headwayMin == null ? '—' : l.everyMinutes(b.headwayMin!)),
                    )
                else
                  Container(
                    decoration: BoxDecoration(color: c.surface, borderRadius: BorderRadius.circular(Radii.card)),
                    child: Column(
                      children: [for (final h in t.hours) _HourRow(hour: h, color: lineColor, date: selectedDay)],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _HourRow extends StatelessWidget {
  const _HourRow({required this.hour, required this.color, required this.date});
  final TimetableHour hour;
  final Color color;
  final DateTime date;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final now = tunisNow();
    final isToday = date.year == now.year && date.month == now.month && date.day == now.day;
    DateTime at(int m) => DateTime(date.year, date.month, date.day).add(Duration(hours: hour.hour, minutes: m));
    final nextIndex = isToday ? hour.minutes.indexWhere((m) => at(m.m).isAfter(now)) : -1;
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: c.divider)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: Space.l, vertical: Space.m),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 40,
            child: Text(
              (hour.hour % 24).toString().padLeft(2, '0'),
              style: context.text.titleMedium?.copyWith(color: color),
            ),
          ),
          Expanded(
            child: Wrap(
              spacing: Space.m,
              runSpacing: 6,
              children: [
                for (var i = 0; i < hour.minutes.length; i++)
                  Builder(
                    builder: (context) {
                      final m = hour.minutes[i];
                      final past = isToday && !at(m.m).isAfter(now);
                      final isNext = i == nextIndex;
                      final firstNext = isNext && (hour.minutes.take(i).every((x) => !at(x.m).isAfter(now)));
                      return Container(
                        padding: firstNext ? const EdgeInsets.symmetric(horizontal: 6, vertical: 1) : EdgeInsets.zero,
                        decoration: firstNext
                            ? BoxDecoration(color: color, borderRadius: BorderRadius.circular(6))
                            : null,
                        child: Text(
                          m.m.toString().padLeft(2, '0'),
                          style: context.text.bodyLarge?.copyWith(
                            color: firstNext
                                ? Colors.white
                                : past
                                ? c.textTertiary
                                : c.text,
                            fontWeight: firstNext ? FontWeight.w600 : null,
                          ),
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
