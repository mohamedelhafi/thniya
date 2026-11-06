import 'package:flutter/material.dart';

/// Jetons de design Thniya (specs/13-design-ux.md §2). Une seule source pour toutes les couleurs et mesures.
@immutable
class ThniyaColors extends ThemeExtension<ThniyaColors> {
  const ThniyaColors({
    required this.brand,
    required this.brandSoft,
    required this.onBrand,
    required this.accent,
    required this.surface,
    required this.surfaceRaised,
    required this.background,
    required this.text,
    required this.textSecondary,
    required this.textTertiary,
    required this.divider,
    required this.walk,
    required this.success,
    required this.warning,
    required this.danger,
    required this.skeleton,
    required this.mapScrim,
  });

  final Color brand;
  final Color brandSoft;
  final Color onBrand;
  final Color accent;
  final Color surface;
  final Color surfaceRaised;
  final Color background;
  final Color text;
  final Color textSecondary;
  final Color textTertiary;
  final Color divider;
  final Color walk;
  final Color success;
  final Color warning;
  final Color danger;
  final Color skeleton;
  final Color mapScrim;

  /// Bleu-vert « Sidi Bou Saïd » + ocre : notre identité, distincte de Citymapper.
  static const light = ThniyaColors(
    brand: Color(0xFF0E7C86),
    brandSoft: Color(0xFFE2F2F3),
    onBrand: Colors.white,
    accent: Color(0xFFE8A317),
    surface: Colors.white,
    surfaceRaised: Colors.white,
    background: Color(0xFFF3F5F6),
    text: Color(0xFF111417),
    textSecondary: Color(0xFF5C6670),
    textTertiary: Color(0xFF8A949C),
    divider: Color(0xFFE6E9EB),
    walk: Color(0xFF8A949C),
    success: Color(0xFF1F9D55),
    warning: Color(0xFFC9850A),
    danger: Color(0xFFD93636),
    skeleton: Color(0xFFE9EDEF),
    mapScrim: Color(0x14000000),
  );

  static const dark = ThniyaColors(
    brand: Color(0xFF3FB8C2),
    brandSoft: Color(0xFF12343A),
    onBrand: Color(0xFF051416),
    accent: Color(0xFFF2BE4B),
    surface: Color(0xFF161B1F),
    surfaceRaised: Color(0xFF1E252A),
    background: Color(0xFF0B0E10),
    text: Color(0xFFF2F4F5),
    textSecondary: Color(0xFF9AA4AD),
    textTertiary: Color(0xFF6E7880),
    divider: Color(0xFF263038),
    walk: Color(0xFF8A949C),
    success: Color(0xFF4CC285),
    warning: Color(0xFFF2BE4B),
    danger: Color(0xFFF06A6A),
    skeleton: Color(0xFF232B31),
    mapScrim: Color(0x33000000),
  );

  @override
  ThniyaColors copyWith() => this;

  @override
  ThniyaColors lerp(ThemeExtension<ThniyaColors>? other, double t) => t < .5 ? this : (other as ThniyaColors? ?? this);
}

/// Espacements sur une grille de 4.
class Space {
  static const xs = 4.0;
  static const s = 8.0;
  static const m = 12.0;
  static const l = 16.0;
  static const xl = 24.0;
  static const xxl = 32.0;
}

/// Rayons : pastilles 6, cartes 16, feuilles 24.
class Radii {
  static const badge = 6.0;
  static const chip = 10.0;
  static const card = 16.0;
  static const sheet = 24.0;
}

/// Durées d'animation (specs/13 §6).
class Motion {
  static const fast = Duration(milliseconds: 150);
  static const medium = Duration(milliseconds: 250);
  static const slow = Duration(milliseconds: 350);
  static const camera = Duration(milliseconds: 400);
  static const enter = Curves.easeOutCubic;
  static const change = Curves.easeInOutCubic;
}

extension ThniyaContext on BuildContext {
  ThniyaColors get colors => Theme.of(this).extension<ThniyaColors>()!;
  TextTheme get text => Theme.of(this).textTheme;
  bool get isRtl => Directionality.of(this) == TextDirection.rtl;
}

/// « #1565C0 » → Color.
Color hexColor(String hex) {
  final h = hex.replaceFirst('#', '');
  return Color(int.parse(h.length == 6 ? 'FF$h' : h, radix: 16));
}
