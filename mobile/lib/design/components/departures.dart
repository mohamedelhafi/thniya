import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/format.dart';
import '../../core/models.dart';
import '../../core/state.dart';
import '../tokens.dart';

/// Prochains départs en ligne : « dans 4 min · 08:02 · 08:25 », ou « ~toutes les 10 min » pour un louage.
/// Se met à jour seul grâce à l'horloge partagée (specs/13 §4 Countdown).
class DepartureLine extends ConsumerWidget {
  const DepartureLine(this.departures, {super.key, this.max = 3, this.emphasizeFirst = true});
  final List<Departure> departures;
  final int max;
  final bool emphasizeFirst;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = ref.watch(clockProvider).value ?? tunisNow();
    final f = Fmt.of(context);
    final c = context.colors;
    if (departures.isEmpty) return const SizedBox.shrink();
    final first = departures.first;
    if (first.isFrequency) {
      return Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(Symbols.autorenew, size: 16, color: c.accent),
        const SizedBox(width: 4),
        Text(f.departure(first, now), style: context.text.labelMedium?.copyWith(color: c.accent)),
      ]);
    }
    final upcoming = departures.where((d) => d.time != null && d.time!.isAfter(now.subtract(const Duration(seconds: 30))));
    final shown = upcoming.take(max).toList();
    if (shown.isEmpty) return const SizedBox.shrink();
    return Row(mainAxisSize: MainAxisSize.min, children: [
      _Pulse(color: c.success),
      const SizedBox(width: 6),
      AnimatedSwitcher(
        duration: Motion.medium,
        transitionBuilder: (child, a) => FadeTransition(
            opacity: a, child: SlideTransition(position: Tween(begin: const Offset(0, .3), end: Offset.zero).animate(a), child: child)),
        child: Text(f.countdown(shown.first.time!, now),
            key: ValueKey(f.countdown(shown.first.time!, now)),
            style: context.text.labelLarge?.copyWith(color: emphasizeFirst ? c.success : c.text)),
      ),
      for (final d in shown.skip(1)) ...[
        Text('  ·  ', style: context.text.labelMedium?.copyWith(color: c.textTertiary)),
        Text(f.time(d.time!), style: context.text.labelMedium?.copyWith(color: c.textSecondary)),
      ],
    ]);
  }
}

/// Petit point vert qui « respire » : indique un départ à venir (horaire théorique, pas du temps réel).
class _Pulse extends StatefulWidget {
  const _Pulse({required this.color});
  final Color color;

  @override
  State<_Pulse> createState() => _PulseState();
}

class _PulseState extends State<_Pulse> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1600))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 10,
        height: 10,
        child: AnimatedBuilder(
          animation: _c,
          builder: (_, _) => Stack(alignment: Alignment.center, children: [
            Container(
              width: 4 + 6 * _c.value,
              height: 4 + 6 * _c.value,
              decoration: BoxDecoration(shape: BoxShape.circle, color: widget.color.withValues(alpha: 0.35 * (1 - _c.value))),
            ),
            Container(width: 6, height: 6, decoration: BoxDecoration(shape: BoxShape.circle, color: widget.color)),
          ]),
        ),
      );
}

/// Puces de départs sélectionnables (fiche trajet : « Autres départs »).
class DepartureChips extends StatelessWidget {
  const DepartureChips(
      {super.key, required this.departures, required this.selected, required this.onSelected, this.scrollable = false});
  final List<Departure> departures;
  final DateTime? selected;
  final ValueChanged<Departure> onSelected;

  /// Une seule rangée qui défile horizontalement (cartes d'étape à hauteur fixe).
  final bool scrollable;

  @override
  Widget build(BuildContext context) {
    final f = Fmt.of(context);
    final c = context.colors;
    final chips = [
      for (final d in departures.where((d) => d.time != null))
        _Chip(
          label: f.time(d.time!),
          sub: d.trip,
          selected: selected != null && d.time!.isAtSameMomentAs(selected!),
          onTap: () => onSelected(d),
          color: c.brand,
        ),
    ];
    if (!scrollable) return Wrap(spacing: Space.s, runSpacing: Space.s, children: chips);
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(children: [
        for (final chip in chips) Padding(padding: const EdgeInsetsDirectional.only(end: Space.s), child: chip),
      ]),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, this.sub, required this.selected, required this.onTap, required this.color});
  final String label;
  final String? sub;
  final bool selected;
  final VoidCallback onTap;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return AnimatedContainer(
      duration: Motion.fast,
      decoration: BoxDecoration(
        color: selected ? color : c.surface,
        borderRadius: BorderRadius.circular(Radii.chip),
        border: Border.all(color: selected ? color : c.divider),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(Radii.chip),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 6),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(label, style: context.text.labelLarge?.copyWith(color: selected ? c.onBrand : c.text)),
            if (sub != null)
              Text(sub!, style: context.text.labelSmall?.copyWith(
                  color: selected ? c.onBrand.withValues(alpha: .8) : c.textTertiary, fontSize: 10)),
          ]),
        ),
      ),
    );
  }
}
