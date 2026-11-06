import 'package:flutter/material.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/api.dart';
import '../../core/models.dart';
import '../../l10n/app_localizations.dart';
import '../tokens.dart';

/// Squelette animé à la forme du contenu (jamais de spinner plein écran).
class Skeleton extends StatefulWidget {
  const Skeleton({super.key, this.width, this.height = 14, this.radius = 6});
  final double? width;
  final double height;
  final double radius;

  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final base = context.colors.skeleton;
    return FadeTransition(
      opacity: Tween(begin: 0.55, end: 1.0).animate(CurvedAnimation(parent: _c, curve: Curves.easeInOut)),
      child: Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(color: base, borderRadius: BorderRadius.circular(widget.radius)),
      ),
    );
  }
}

class SkeletonCard extends StatelessWidget {
  const SkeletonCard({super.key});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(Space.l),
        decoration: BoxDecoration(color: context.colors.surface, borderRadius: BorderRadius.circular(Radii.card)),
        child: const Row(
          children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Skeleton(width: 150, height: 22),
                SizedBox(height: Space.m),
                Skeleton(width: 210),
                SizedBox(height: Space.s),
                Skeleton(width: 120),
              ]),
            ),
            Skeleton(width: 48, height: 34),
          ],
        ),
      );
}

/// Bandeau de période (« Horaires de Ramadan ») ou de jour férié.
class PeriodBanner extends StatelessWidget {
  const PeriodBanner(this.period, {super.key});
  final PeriodView? period;

  @override
  Widget build(BuildContext context) {
    final p = period;
    if (p == null || (!p.banner && p.holidays.isEmpty)) return const SizedBox.shrink();
    final l = L.of(context);
    final label = p.holidays.isNotEmpty ? l.holiday(p.holidays.first) : p.name;
    return _Banner(icon: p.holidays.isNotEmpty ? Symbols.celebration : Symbols.schedule, text: label,
        color: context.colors.accent);
  }
}

class AlertBanner extends StatelessWidget {
  const AlertBanner(this.alert, {super.key});
  final AlertView alert;

  @override
  Widget build(BuildContext context) {
    final color = alert.severity == 'severe' ? context.colors.danger : context.colors.warning;
    return _Banner(icon: Symbols.warning, text: alert.title, detail: alert.body, color: color);
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.icon, required this.text, this.detail, required this.color});
  final IconData icon;
  final String text;
  final String? detail;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: Space.s + 2),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(Radii.chip),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, size: 18, color: color, fill: 1),
          const SizedBox(width: Space.s),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(text, style: context.text.labelMedium?.copyWith(color: context.colors.text)),
              if (detail != null) Text(detail!, style: context.text.bodySmall),
            ]),
          ),
        ]),
      );
}

/// Écran vide ou d'erreur : un message, une action.
class MessageState extends StatelessWidget {
  const MessageState({super.key, required this.icon, required this.title, this.body, this.action, this.onAction});
  final IconData icon;
  final String title;
  final String? body;
  final String? action;
  final VoidCallback? onAction;

  factory MessageState.error(BuildContext context, Object error, VoidCallback retry) {
    final l = L.of(context);
    final kind = error is ApiError ? error.kind : ApiErrorKind.other;
    final title = switch (kind) {
      ApiErrorKind.offline => l.offline,
      ApiErrorKind.tooManyRequests => l.tooManyRequests,
      ApiErrorKind.unavailable => l.serviceUnavailable,
      ApiErrorKind.noRoute => l.noRoute,
      _ => l.loadingError,
    };
    return MessageState(
      icon: switch (kind) {
        ApiErrorKind.offline => Symbols.wifi_off,
        ApiErrorKind.noRoute => Symbols.wrong_location,
        _ => Symbols.sentiment_dissatisfied,
      },
      title: title,
      body: kind == ApiErrorKind.noRoute ? l.noRouteBody : null,
      action: kind == ApiErrorKind.noRoute ? null : l.retry,
      onAction: kind == ApiErrorKind.noRoute ? null : retry,
    );
  }

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(Space.xxl),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Container(
              padding: const EdgeInsets.all(Space.l),
              decoration: BoxDecoration(color: context.colors.brandSoft, shape: BoxShape.circle),
              child: Icon(icon, size: 32, color: context.colors.brand),
            ),
            const SizedBox(height: Space.l),
            Text(title, style: context.text.titleMedium, textAlign: TextAlign.center),
            if (body != null) ...[
              const SizedBox(height: Space.s),
              Text(body!, style: context.text.bodyMedium?.copyWith(color: context.colors.textSecondary),
                  textAlign: TextAlign.center),
            ],
            if (action != null) ...[
              const SizedBox(height: Space.l),
              FilledButton(onPressed: onAction, child: Text(action!)),
            ],
          ]),
        ),
      );
}
