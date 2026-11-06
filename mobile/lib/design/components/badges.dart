import 'package:flutter/material.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/models.dart';
import '../tokens.dart';

/// Icônes de mode : un seul jeu, arrondi, même graisse (specs/13 §3).
IconData modeIconData(String mode) => switch (mode) {
      'TRAIN' => Symbols.train,
      'METRO' => Symbols.tram,
      'BUS' => Symbols.directions_bus,
      'LOUAGE' => Symbols.airport_shuttle,
      'TAXI_COLLECTIF' => Symbols.local_taxi,
      'FERRY' => Symbols.directions_boat,
      'WALK' => Symbols.directions_walk,
      _ => Symbols.commute,
    };

Color modeColor(BuildContext context, String mode) => switch (mode) {
      'TRAIN' => const Color(0xFF1565C0),
      'METRO' => const Color(0xFF2E7D32),
      'BUS' => const Color(0xFFC62828),
      'LOUAGE' => context.colors.accent,
      'WALK' => context.colors.walk,
      _ => context.colors.brand,
    };

class ModeIcon extends StatelessWidget {
  const ModeIcon(this.mode, {super.key, this.size = 20, this.color, this.filled = true});
  final String mode;
  final double size;
  final Color? color;
  final bool filled;

  @override
  Widget build(BuildContext context) => Icon(
        modeIconData(mode),
        size: size,
        fill: filled ? 1 : 0,
        weight: 500,
        opticalSize: size,
        color: color ?? context.colors.text,
      );
}

/// Code affiché d'une ligne, en deux parties : le code principal et un complément écrit en petit.
/// Trains : « T » (= train) puis, en petit, la lettre de la ligne pour les distinguer : T + A (banlieue sud),
/// T + GM (TGM). Autres modes : le code tel quel (M6, B1, destination du louage).
(String, String?) lineCodeParts(LineRef line) {
  if (line.mode != 'TRAIN') return (line.publicCode, null);
  final code = line.publicCode.trim();
  final rest = code.toUpperCase().startsWith('T') ? code.substring(1) : code;
  return ('T', rest.isEmpty ? null : rest);
}

/// Code de ligne en texte simple (partage, lecteur d'écran) : « T A », « T GM », « M6 ».
String lineCodePlain(LineRef line) {
  final (main, small) = lineCodeParts(line);
  return small == null ? main : '$main $small';
}

/// Code de ligne avec son complément en petit (T + A).
class LineCodeText extends StatelessWidget {
  const LineCodeText(this.line, {super.key, this.style});
  final LineRef line;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final base = style ?? DefaultTextStyle.of(context).style;
    final (main, small) = lineCodeParts(line);
    if (small == null) return Text(main, style: base, maxLines: 1, overflow: TextOverflow.ellipsis);
    return Text.rich(
      TextSpan(children: [
        TextSpan(text: main),
        TextSpan(text: small, style: base.copyWith(fontSize: (base.fontSize ?? 14) * .68, fontWeight: FontWeight.w600)),
      ]),
      style: base,
      maxLines: 1,
    );
  }
}

/// Pastille de ligne : couleur de la ligne, code public ; variante louage avec destination.
class LineBadge extends StatelessWidget {
  const LineBadge(this.line, {super.key, this.compact = false, this.showIcon = true, this.destination});
  final LineRef line;
  final bool compact;
  final bool showIcon;
  final String? destination;

  @override
  Widget build(BuildContext context) {
    final bg = hexColor(line.color);
    final fg = hexColor(line.textColor);
    final style = (compact ? context.text.labelMedium : context.text.labelLarge)!.copyWith(color: fg, height: 1.1);
    return Semantics(
      label: '${line.name} ${lineCodePlain(line)}',
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: compact ? 6 : 8, vertical: compact ? 3 : 4),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(Radii.badge)),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (showIcon && line.mode != null) ...[
              ModeIcon(line.mode!, size: compact ? 14 : 16, color: fg),
              SizedBox(width: compact ? 3 : 4),
            ],
            LineCodeText(line, style: style),
            if (destination != null) ...[
              SizedBox(width: compact ? 3 : 5),
              Flexible(
                child: Text('→ $destination',
                    style: style.copyWith(fontSize: (style.fontSize ?? 14) - 1), overflow: TextOverflow.ellipsis),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Suite marche → pastilles → … d'un itinéraire, repliée si elle déborde (specs/13 §4).
class ModeChain extends StatelessWidget {
  const ModeChain(this.parts, {super.key, this.compact = false});
  final List<SummaryPart> parts;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final items = <Widget>[];
    for (var i = 0; i < parts.length; i++) {
      final p = parts[i];
      if (i > 0) {
        items.add(Padding(
          padding: const EdgeInsets.symmetric(horizontal: 3),
          child: Icon(context.isRtl ? Symbols.chevron_left : Symbols.chevron_right, size: 16, color: c.textTertiary),
        ));
      }
      if (p.mode == 'WALK') {
        items.add(Row(mainAxisSize: MainAxisSize.min, children: [
          ModeIcon('WALK', size: compact ? 18 : 20, color: c.textSecondary),
          if (p.minutes != null)
            Text('${p.minutes}', style: context.text.labelSmall?.copyWith(color: c.textSecondary, fontSize: 11)),
        ]));
      } else if (p.line != null) {
        // Louage : le code affiché est la ville de destination (« Tunis », « Ezzahra »), comme sur le pare-brise
        items.add(LineBadge(p.line!, compact: compact));
      } else {
        items.add(ModeIcon(p.mode, size: 20));
      }
    }
    return Wrap(crossAxisAlignment: WrapCrossAlignment.center, runSpacing: 6, children: items);
  }
}
