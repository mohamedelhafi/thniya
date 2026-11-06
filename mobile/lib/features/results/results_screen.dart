import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/format.dart';
import '../../core/models.dart';
import '../../core/state.dart';
import '../../design/components/badges.dart';
import '../../design/components/departures.dart';
import '../../design/components/feedback.dart';
import '../../design/components/motion.dart';
import '../../design/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../search/search_screen.dart';

class ResultsArgs {
  const ResultsArgs({required this.from, required this.to, this.timeMode = 'NOW', this.at});
  final Place from;
  final Place to;
  final String timeMode; // NOW | DEPART_AT | ARRIVE_BY
  final DateTime? at;

  /// Lien partageable : /results?from=lat,lon,Nom&to=lat,lon,Nom[&depart=2026-10-14T08:00|&arrive=…]
  /// (heure murale de Tunis). Null si le lien est incomplet.
  static ResultsArgs? fromUri(Uri uri) {
    Place? point(String? v) {
      final p = v?.split(',');
      if (p == null || p.length < 2) return null;
      final lat = double.tryParse(p[0]), lon = double.tryParse(p[1]);
      if (lat == null || lon == null) return null;
      return Place(type: 'POINT', name: p.length > 2 ? p.sublist(2).join(',') : '$lat, $lon', lat: lat, lon: lon);
    }

    final from = point(uri.queryParameters['from']), to = point(uri.queryParameters['to']);
    if (from == null || to == null) return null;
    final depart = DateTime.tryParse(uri.queryParameters['depart'] ?? '');
    final arrive = DateTime.tryParse(uri.queryParameters['arrive'] ?? '');
    return ResultsArgs(
      from: from,
      to: to,
      timeMode: arrive != null
          ? 'ARRIVE_BY'
          : depart != null
          ? 'DEPART_AT'
          : 'NOW',
      at: arrive ?? depart,
    );
  }
}

final itinerariesProvider = FutureProvider.autoDispose.family<ItinerariesResponse, ResultsArgs>(
  (ref, a) => ref.watch(apiProvider).itineraries(from: a.from, to: a.to, timeMode: a.timeMode, at: a.at),
);

/// Résultats (specs/07 §5.3) : sections Suggestions / par mode / à pied, cartes de trajet très lisibles.
class ResultsScreen extends ConsumerStatefulWidget {
  const ResultsScreen({super.key, required this.args});
  final ResultsArgs args;

  @override
  ConsumerState<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends ConsumerState<ResultsScreen> {
  late ResultsArgs _args = widget.args;

  Future<void> _pickTime() async {
    final l = L.of(context);
    final now = tunisNow();
    final mode = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final (m, label) in [
              ('NOW', l.leaveNow),
              ('DEPART_AT', l.departAt('…')),
              ('ARRIVE_BY', l.arriveBy('…')),
            ])
              ListTile(
                leading: Icon(
                  m == 'NOW'
                      ? Symbols.bolt
                      : m == 'DEPART_AT'
                      ? Symbols.schedule
                      : Symbols.flag,
                ),
                title: Text(label.replaceAll(' …', '')),
                trailing: _args.timeMode == m ? Icon(Symbols.check, color: context.colors.brand) : null,
                onTap: () => Navigator.pop(context, m),
              ),
          ],
        ),
      ),
    );
    if (mode == null || !mounted) return;
    if (mode == 'NOW') {
      setState(() => _args = ResultsArgs(from: _args.from, to: _args.to));
      return;
    }
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(_args.at ?? now));
    if (time == null || !mounted) return;
    final at = DateTime(now.year, now.month, now.day, time.hour, time.minute);
    setState(() => _args = ResultsArgs(from: _args.from, to: _args.to, timeMode: mode, at: at));
  }

  void _shift(int minutes, ItinerariesResponse r) {
    final all = r.itineraries.values.toList();
    if (all.isEmpty) return;
    final base = minutes > 0
        ? all.map((i) => i.departAt).reduce((a, b) => a.isAfter(b) ? a : b)
        : all.map((i) => i.departAt).reduce((a, b) => a.isBefore(b) ? a : b);
    setState(
      () => _args = ResultsArgs(
        from: _args.from,
        to: _args.to,
        timeMode: 'DEPART_AT',
        at: base.add(Duration(minutes: minutes > 0 ? 1 : -45)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final f = Fmt.of(context);
    final c = context.colors;
    final result = ref.watch(itinerariesProvider(_args));
    final timeLabel = switch (_args.timeMode) {
      'DEPART_AT' => l.departAt(f.time(_args.at!)),
      'ARRIVE_BY' => l.arriveBy(f.time(_args.at!)),
      _ => l.leaveNow,
    };

    return Scaffold(
      body: RefreshIndicator(
        // tirer vers le bas : nouveaux horaires (utile en « partir maintenant »)
        onRefresh: () => ref.refresh(itinerariesProvider(_args).future),
        edgeOffset: 128 + MediaQuery.paddingOf(context).top,
        color: c.brand,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverAppBar(
              pinned: true,
              backgroundColor: c.surface,
              surfaceTintColor: Colors.transparent,
              toolbarHeight: 128,
              automaticallyImplyLeading: false,
              titleSpacing: 0,
              title: _Header(
                from: _args.from,
                to: _args.to,
                timeLabel: timeLabel,
                onBack: () => context.pop(),
                onEdit: () => context.pushReplacement(
                  '/search',
                  extra: SearchArgs(from: _args.from, to: _args.to),
                ),
                onTime: _pickTime,
                onSwap: _swap,
              ),
            ),
            ...result.when(
              loading: () => [
                SliverPadding(
                  padding: const EdgeInsets.all(Space.l),
                  sliver: SliverList.separated(
                    itemCount: 4,
                    separatorBuilder: (_, _) => const SizedBox(height: Space.m),
                    itemBuilder: (_, _) => const SkeletonCard(),
                  ),
                ),
              ],
              error: (e, _) => [
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: MessageState.error(context, e, () => ref.invalidate(itinerariesProvider(_args))),
                ),
              ],
              data: (r) => [
                if (r.coverage == 'WALK_ONLY')
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(Space.l, Space.l, Space.l, 0),
                    sliver: SliverToBoxAdapter(
                      child: MessageState(icon: Symbols.explore_off, title: l.noTransitHere, body: l.noTransitHereBody),
                    ),
                  ),
                if (r.notice == 'FIRST_DEPARTURES')
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, 0),
                sliver: SliverToBoxAdapter(child: _NightNotice(firstDeparture: _firstDeparture(r))),
              ),
            if (r.period != null)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, 0),
                    sliver: SliverToBoxAdapter(child: PeriodBanner(r.period)),
                  ),
                for (final s in r.sections) ...[
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(Space.l, Space.xl, Space.l, Space.s),
                    sliver: SliverToBoxAdapter(child: _SectionHeader(section: s)),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: Space.l),
                    sliver: SliverList.separated(
                      itemCount: s.itineraryIds.length,
                      separatorBuilder: (_, _) => const SizedBox(height: Space.s),
                      itemBuilder: (context, i) {
                        final it = r.itineraries[s.itineraryIds[i]]!;
                        return Appear(
                          key: ValueKey('${r.dataVersion}-${s.key}-${it.id}'),
                          index: r.sections.indexOf(s) * 2 + i,
                          child: _ItineraryCard(
                            itinerary: it,
                            heroTag: '${s.key}-${it.id}',
                            onTap: () {
                              HapticFeedback.selectionClick();
                              context.push('/trip', extra: it);
                            },
                          ),
                        );
                      },
                    ),
                  ),
                ],
                SliverPadding(
                  padding: const EdgeInsets.all(Space.l),
                  sliver: SliverToBoxAdapter(
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        TextButton.icon(
                          onPressed: () => _shift(-1, r),
                          icon: const Icon(Symbols.history),
                          label: Text(l.earlier),
                        ),
                        const SizedBox(width: Space.l),
                        TextButton.icon(
                          onPressed: () => _shift(1, r),
                          icon: const Icon(Symbols.update),
                          label: Text(l.later),
                        ),
                      ],
                    ),
                  ),
                ),
                const SliverToBoxAdapter(child: SizedBox(height: Space.xxl)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// Inverser départ et arrivée : le trajet retour en un geste.
  void _swap() {
    HapticFeedback.selectionClick();
    setState(() => _args = ResultsArgs(from: _args.to, to: _args.from, timeMode: _args.timeMode, at: _args.at));
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.from,
    required this.to,
    required this.timeLabel,
    required this.onBack,
    required this.onEdit,
    required this.onTime,
    required this.onSwap,
  });
  final Place from;
  final Place to;
  final String timeLabel;
  final VoidCallback onBack;
  final VoidCallback onEdit;
  final VoidCallback onTime;
  final VoidCallback onSwap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsetsDirectional.only(end: Space.l),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconButton(onPressed: onBack, icon: Icon(context.isRtl ? Symbols.arrow_forward : Symbols.arrow_back)),
              Expanded(
                child: InkWell(
                  borderRadius: BorderRadius.circular(Radii.chip),
                  onTap: onEdit,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: Space.s),
                    decoration: BoxDecoration(color: c.background, borderRadius: BorderRadius.circular(Radii.chip)),
                    child: AnimatedSwitcher(
                      duration: Motion.medium,
                      transitionBuilder: (child, a) => FadeTransition(opacity: a, child: child),
                      child: Column(
                        key: ValueKey('${from.name}>${to.name}'),
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _EndPoint(icon: Symbols.radio_button_checked, color: c.brand, text: from.name),
                          const SizedBox(height: 6),
                          _EndPoint(icon: Symbols.location_on, color: c.danger, text: to.name),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              IconButton(
                tooltip: L.of(context).swap,
                onPressed: onSwap,
                icon: Icon(Symbols.swap_vert, color: c.textSecondary),
              ),
            ],
          ),
          Padding(
            padding: const EdgeInsetsDirectional.only(start: 48, top: Space.s),
            child: ActionChip(
              avatar: Icon(Symbols.schedule, size: 18, color: c.brand),
              label: Text(timeLabel),
              onPressed: onTime,
            ),
          ),
        ],
      ),
    );
  }
}

class _EndPoint extends StatelessWidget {
  const _EndPoint({required this.icon, required this.color, required this.text});
  final IconData icon;
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Icon(icon, size: 14, color: color, fill: 1),
      const SizedBox(width: Space.s),
      Expanded(
        child: Text(text, style: context.text.titleSmall, overflow: TextOverflow.ellipsis),
      ),
    ],
  );
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.section});
  final Section section;

  @override
  Widget build(BuildContext context) {
    final icon = switch (section.key) {
      'SUGGESTED' => Symbols.auto_awesome,
      'LESS_WALKING' => Symbols.airline_seat_recline_normal,
      'WALK' => Symbols.directions_walk,
      _ => modeIconData(section.key),
    };
    final color = switch (section.key) {
      'SUGGESTED' => context.colors.brand,
      'LESS_WALKING' => context.colors.brand,
      _ => modeColor(context, section.key),
    };
    return Row(
      children: [
        Icon(icon, size: 20, color: color, fill: 1),
        const SizedBox(width: Space.s),
        Text(section.title, style: context.text.titleLarge),
      ],
    );
  }
}

/// Carte de trajet (specs/07 §5.3 et 13 §4 ItineraryCard).
class _ItineraryCard extends StatelessWidget {
  const _ItineraryCard({required this.itinerary, required this.heroTag, required this.onTap});
  final Itinerary itinerary;
  final String heroTag;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final f = Fmt.of(context);
    final c = context.colors;
    final it = itinerary;
    final hours = it.durationMin ~/ 60;
    final minutes = it.durationMin % 60;
    return Hero(
      tag: heroTag,
      child: Material(
        color: c.surface,
        borderRadius: BorderRadius.circular(Radii.card),
        child: InkWell(
          borderRadius: BorderRadius.circular(Radii.card),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(Space.l, Space.l, Space.l, Space.m),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: ModeChain(it.summary)),
                    const SizedBox(width: Space.m),
                    // Durée en grand : l'information la plus importante
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.baseline,
                          textBaseline: TextBaseline.alphabetic,
                          children: [
                            if (hours > 0) ...[
                              Text('$hours', style: context.text.displayMedium),
                              Text(
                                ' ${l.hourUnit} ',
                                style: context.text.labelMedium?.copyWith(color: c.textSecondary),
                              ),
                            ],
                            Text(
                              hours > 0 ? minutes.toString().padLeft(2, '0') : '$minutes',
                              style: context.text.displayMedium,
                            ),
                            if (hours == 0)
                              Text(' ${l.minUnit}', style: context.text.labelMedium?.copyWith(color: c.textSecondary)),
                          ],
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: Space.s),
                Text(
                  [
                    l.arrival(f.time(it.arriveAt)),
                    if (it.walkMin > 0) l.walkMinutes(it.walkMin),
                    f.price(it.price),
                    if (it.summary.any((p) => p.line?.estimated ?? false)) l.estimatedTimes,
                  ].join('  ·  '),
                  style: context.text.bodySmall,
                ),
                if (it.nextDepartures.isNotEmpty || it.alerts.isNotEmpty) ...[
                  const SizedBox(height: Space.m),
                  Divider(color: c.divider),
                  const SizedBox(height: Space.s),
                  Row(
                    children: [
                      if (it.firstTransit?.line != null) ...[
                        Text(it.firstTransit!.from?.name ?? '', style: context.text.labelSmall),
                        const Spacer(),
                      ],
                      DepartureLine(it.nextDepartures),
                    ],
                  ),
                  for (final a in it.alerts)
                    Padding(
                      padding: const EdgeInsets.only(top: Space.s),
                      child: AlertBanner(a),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

DateTime? _firstDeparture(ItinerariesResponse r) {
  final all = r.itineraries.values.map((i) => i.departAt).toList()..sort();
  return all.isEmpty ? null : all.first;
}

/// La nuit : plus rien ne circule, voici les premiers départs (comme Citymapper, plutôt qu'« aucun itinéraire »).
class _NightNotice extends StatelessWidget {
  const _NightNotice({required this.firstDeparture});
  final DateTime? firstDeparture;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l = L.of(context);
    return Container(
      padding: const EdgeInsets.all(Space.m),
      decoration: BoxDecoration(color: c.brandSoft, borderRadius: BorderRadius.circular(Radii.card)),
      child: Row(children: [
        Icon(Symbols.bedtime, color: c.brand, fill: 1),
        const SizedBox(width: Space.m),
        Expanded(
          child: Text(
            firstDeparture == null
                ? l.noServiceNow
                : l.firstDeparturesFrom(Fmt.of(context).time(firstDeparture!)),
            style: context.text.bodyMedium?.copyWith(color: c.text),
          ),
        ),
      ]),
    );
  }
}
