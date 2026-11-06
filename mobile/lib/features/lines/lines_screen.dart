import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/models.dart';
import '../../core/state.dart';
import '../../design/components/badges.dart';
import '../../design/components/feedback.dart';
import '../../design/tokens.dart';
import '../../l10n/app_localizations.dart';

final linesProvider = FutureProvider<List<LineSummary>>((ref) => ref.watch(apiProvider).lines());

/// Annuaire des lignes (specs/07 §5.7), groupées par mode.
class LinesScreen extends ConsumerWidget {
  const LinesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final c = context.colors;
    final lines = ref.watch(linesProvider);
    final meta = ref.watch(metaProvider).value;

    return Scaffold(
      appBar: AppBar(title: Text(l.allLines)),
      body: lines.when(
        loading: () => ListView(padding: const EdgeInsets.all(Space.l), children: const [SkeletonCard()]),
        error: (e, _) => MessageState.error(context, e, () => ref.invalidate(linesProvider)),
        data: (list) {
          final byMode = <String, List<LineSummary>>{};
          for (final x in list) {
            byMode.putIfAbsent(x.line.mode ?? '', () => []).add(x);
          }
          return ListView(padding: const EdgeInsets.only(bottom: Space.xxl), children: [
            for (final entry in byMode.entries) ...[
              Padding(
                padding: const EdgeInsets.fromLTRB(Space.l, Space.xl, Space.l, Space.s),
                child: Row(children: [
                  ModeIcon(entry.key, color: modeColor(context, entry.key)),
                  const SizedBox(width: Space.s),
                  Text(meta?.modes[entry.key]?.name ?? entry.key, style: context.text.titleLarge),
                ]),
              ),
              for (final x in entry.value)
                Padding(
                  padding: const EdgeInsets.fromLTRB(Space.l, 0, Space.l, Space.s),
                  child: Material(
                    color: c.surface,
                    borderRadius: BorderRadius.circular(Radii.card),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(Radii.card),
                      onTap: () => context.push('/line/${x.line.id}'),
                      child: Padding(
                        padding: const EdgeInsets.all(Space.l),
                        child: Row(children: [
                          LineBadge(x.line),
                          const SizedBox(width: Space.m),
                          Expanded(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(x.line.name, style: context.text.titleMedium),
                              Text(x.termini.join('  ⇄  '), style: context.text.bodySmall),
                            ]),
                          ),
                          if (x.alerts > 0) Icon(Symbols.warning, color: c.warning, fill: 1),
                          Icon(context.isRtl ? Symbols.chevron_left : Symbols.chevron_right, color: c.textTertiary),
                        ]),
                      ),
                    ),
                  ),
                ),
            ],
          ]);
        },
      ),
    );
  }
}
