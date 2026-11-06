import 'package:flutter/material.dart';
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
import '../../map/thniya_map.dart';
import '../home/home_screen.dart';
import '../results/results_screen.dart';

final stopProvider = FutureProvider.autoDispose.family<StopDetail, String>((ref, id) => ref.watch(apiProvider).stop(id));

/// Fiche arrêt / station (specs/07 §5.6) : tableau des départs par ligne et direction.
class StopScreen extends ConsumerWidget {
  const StopScreen({super.key, required this.stopId});
  final String stopId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final stop = ref.watch(stopProvider(stopId));
    ref.watch(clockProvider); // rafraîchit les comptes à rebours
    return Scaffold(
      body: stop.when(
        loading: () => const Center(child: Padding(padding: EdgeInsets.all(Space.xl), child: SkeletonCard())),
        error: (e, _) => MessageState.error(context, e, () => ref.invalidate(stopProvider(stopId))),
        data: (s) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(stopProvider(stopId)),
          child: _StopBody(stop: s),
        ),
      ),
    );
  }
}

class _StopBody extends ConsumerWidget {
  const _StopBody({required this.stop});
  final StopDetail stop;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final f = Fmt.of(context);
    final c = context.colors;
    final mode = stop.modes.isEmpty ? 'BUS' : stop.modes.first;
    final color = modeColor(context, mode);
    final point = LatLng(stop.lat, stop.lon);

    return CustomScrollView(slivers: [
      SliverAppBar(
        pinned: true,
        expandedHeight: 220,
        backgroundColor: c.surface,
        surfaceTintColor: Colors.transparent,
        leading: Padding(
          padding: const EdgeInsets.all(6),
          child: CircleAvatar(
            backgroundColor: c.surface,
            child: IconButton(
              icon: Icon(context.isRtl ? Symbols.arrow_forward : Symbols.arrow_back, color: c.text),
              onPressed: () => context.pop(),
            ),
          ),
        ),
        flexibleSpace: FlexibleSpaceBar(
          background: IgnorePointer(
            child: ThniyaMap(
              controller: MapController(),
              initialCenter: point,
              initialZoom: 16,
              children: [
                MarkerLayer(markers: [
                  Marker(
                    point: point,
                    width: 40,
                    height: 40,
                    child: Container(
                      decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, border: Border.all(color: color, width: 3),
                          boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 6)]),
                      child: Center(child: ModeIcon(mode, size: 22, color: color)),
                    ),
                  ),
                ]),
              ],
            ),
          ),
        ),
      ),
      SliverToBoxAdapter(
        child: Container(
          color: c.surface,
          padding: const EdgeInsets.fromLTRB(Space.l, Space.l, Space.l, Space.l),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(stop.name, style: context.text.headlineSmall),
            if (stop.area != null) Text(stop.area!, style: context.text.bodyMedium?.copyWith(color: c.textSecondary)),
            const SizedBox(height: Space.m),
            Wrap(spacing: 6, runSpacing: 6, children: [for (final x in stop.lines) LineBadge(x, compact: true)]),
            const SizedBox(height: Space.l),
            FilledButton.icon(
              onPressed: () {
                final loc = ref.read(locationProvider).position;
                context.push('/results',
                    extra: ResultsArgs(
                      from: myLocationPlace(context, loc),
                      to: Place(type: 'STOP', id: stop.id, name: stop.name, lat: stop.lat, lon: stop.lon),
                    ));
              },
              icon: const Icon(Symbols.directions),
              label: Text(l.routeHere),
            ),
          ]),
        ),
      ),
      for (final a in stop.alerts)
        SliverPadding(padding: const EdgeInsets.fromLTRB(Space.l, Space.m, Space.l, 0), sliver: SliverToBoxAdapter(child: AlertBanner(a))),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(Space.l, Space.xl, Space.l, Space.s),
        sliver: SliverToBoxAdapter(child: Text(l.nextDepartures, style: context.text.titleLarge)),
      ),
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: Space.l),
        sliver: SliverList.separated(
          itemCount: stop.board.length,
          separatorBuilder: (_, _) => const SizedBox(height: Space.s),
          itemBuilder: (context, i) {
            final row = stop.board[i];
            return Material(
              color: c.surface,
              borderRadius: BorderRadius.circular(Radii.card),
              child: InkWell(
                borderRadius: BorderRadius.circular(Radii.card),
                onTap: () => context.push('/line/${row.line.id}?stop=${stop.id}'),
                child: Padding(
                  padding: const EdgeInsets.all(Space.l),
                  child: Row(children: [
                    LineBadge(row.line),
                    const SizedBox(width: Space.m),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(l.towards(row.headsign ?? ''), style: context.text.titleSmall),
                        const SizedBox(height: 4),
                        if (row.noServiceToday)
                          Text(
                            row.nextServiceAt == null ? l.noServiceToday : '${l.noServiceToday} · ${l.nextService(f.time(row.nextServiceAt!))}',
                            style: context.text.bodySmall,
                          )
                        else
                          DepartureLine(row.departures),
                      ]),
                    ),
                    Icon(context.isRtl ? Symbols.chevron_left : Symbols.chevron_right, color: c.textTertiary),
                  ]),
                ),
              ),
            );
          },
        ),
      ),
      if (stop.louageDestinations.isNotEmpty) ...[
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(Space.l, Space.xl, Space.l, Space.s),
          sliver: SliverToBoxAdapter(child: Text(l.louagesFromHere, style: context.text.titleLarge)),
        ),
        SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: Space.l),
          sliver: SliverList.separated(
            itemCount: stop.louageDestinations.length,
            separatorBuilder: (_, _) => const SizedBox(height: Space.s),
            itemBuilder: (context, i) {
              final d = stop.louageDestinations[i];
              return Container(
                padding: const EdgeInsets.all(Space.l),
                decoration: BoxDecoration(color: context.colors.surface, borderRadius: BorderRadius.circular(Radii.card)),
                child: Row(children: [
                  LineBadge(d.line),
                  const SizedBox(width: Space.m),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      DepartureLine([d.departure]),
                      Text(l.departsWhenFull, style: context.text.bodySmall),
                    ]),
                  ),
                  Text(f.price(d.price), style: context.text.titleSmall),
                ]),
              );
            },
          ),
        ),
      ],
      const SliverToBoxAdapter(child: SizedBox(height: Space.xxl)),
    ]);
  }
}
