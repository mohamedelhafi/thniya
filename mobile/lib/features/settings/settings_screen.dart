import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/state.dart';
import '../../design/tokens.dart';
import '../../l10n/app_localizations.dart';

/// Réglages (specs/07 §5.10) : langue, thème, à propos des données.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final c = context.colors;
    final locale = ref.watch(localeProvider);
    final mode = ref.watch(themeModeProvider);
    final meta = ref.watch(metaProvider).value;

    Widget card(List<Widget> children) => Container(
          margin: const EdgeInsets.fromLTRB(Space.l, 0, Space.l, Space.l),
          decoration: BoxDecoration(color: c.surface, borderRadius: BorderRadius.circular(Radii.card)),
          child: Column(children: children),
        );

    return Scaffold(
      appBar: AppBar(title: Text(l.settings)),
      body: ListView(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(Space.l, Space.l, Space.l, Space.s),
          child: Text(l.language, style: context.text.titleMedium),
        ),
        card([
          for (final (code, label) in [('fr', 'Français'), ('ar', 'العربية')])
            RadioListTile<String>(
              value: code,
              groupValue: locale.languageCode,
              title: Text(label, style: context.text.bodyLarge),
              onChanged: (v) {
                HapticFeedback.selectionClick();
                ref.read(localeProvider.notifier).set(Locale(v!));
              },
            ),
        ]),
        Padding(
          padding: const EdgeInsets.fromLTRB(Space.l, Space.s, Space.l, Space.s),
          child: Text(l.theme, style: context.text.titleMedium),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(Space.l, 0, Space.l, Space.l),
          child: SegmentedButton<ThemeMode>(
            showSelectedIcon: false,
            segments: [
              ButtonSegment(value: ThemeMode.system, label: Text(l.themeSystem), icon: const Icon(Symbols.contrast)),
              ButtonSegment(value: ThemeMode.light, label: Text(l.themeLight), icon: const Icon(Symbols.light_mode)),
              ButtonSegment(value: ThemeMode.dark, label: Text(l.themeDark), icon: const Icon(Symbols.dark_mode)),
            ],
            selected: {mode},
            onSelectionChanged: (s) => ref.read(themeModeProvider.notifier).set(s.first),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(Space.l, Space.s, Space.l, Space.s),
          child: Text(l.aboutData, style: context.text.titleMedium),
        ),
        card([
          ListTile(
            leading: Icon(Symbols.database, color: c.brand),
            title: Text(l.dataVersion(meta?.dataVersion ?? '…')),
          ),
          ListTile(
            leading: Icon(Symbols.verified, color: c.brand),
            title: Text(l.dataSources, style: context.text.bodyMedium),
          ),
        ]),
        Center(
          child: Padding(
            padding: const EdgeInsets.all(Space.xl),
            child: Column(children: [
              Text(l.appName, style: context.text.headlineSmall?.copyWith(color: c.brand)),
              Text('Thniya · ثنية', style: context.text.bodySmall),
            ]),
          ),
        ),
      ]),
    );
  }
}
