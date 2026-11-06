import 'package:flutter/material.dart';

import 'tokens.dart';

const _font = 'ReadexPro';

/// Readex Pro est une police variable : on règle l'axe « wght » explicitement.
TextStyle _style(double size, double weight, Color color, {double height = 1.25, double spacing = 0}) => TextStyle(
      fontFamily: _font,
      fontSize: size,
      fontWeight: FontWeight.values[((weight / 100).round() - 1).clamp(0, 8)],
      fontVariations: [FontVariation('wght', weight)],
      height: height,
      letterSpacing: spacing,
      color: color,
    );

ThemeData buildTheme(Brightness brightness) {
  final c = brightness == Brightness.light ? ThniyaColors.light : ThniyaColors.dark;

  // Échelle typographique (specs/13 §2) : display 34, carte 26, titre 20, corps 16, libellé 14, note 12.
  final text = TextTheme(
    displayLarge: _style(34, 700, c.text, height: 1.05, spacing: -0.5),
    displayMedium: _style(26, 700, c.text, height: 1.05, spacing: -0.3),
    headlineSmall: _style(22, 650, c.text),
    titleLarge: _style(20, 600, c.text),
    titleMedium: _style(16, 600, c.text),
    titleSmall: _style(14, 600, c.text),
    bodyLarge: _style(16, 400, c.text, height: 1.4),
    bodyMedium: _style(14, 400, c.text, height: 1.4),
    bodySmall: _style(12, 400, c.textSecondary, height: 1.35),
    labelLarge: _style(15, 600, c.text),
    labelMedium: _style(13, 550, c.text),
    labelSmall: _style(11, 550, c.textSecondary, spacing: 0.2),
  );

  final scheme = ColorScheme.fromSeed(
    seedColor: c.brand,
    brightness: brightness,
    primary: c.brand,
    onPrimary: c.onBrand,
    secondary: c.accent,
    surface: c.surface,
    onSurface: c.text,
    error: c.danger,
  );

  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    fontFamily: _font,
    textTheme: text,
    scaffoldBackgroundColor: c.background,
    canvasColor: c.surface,
    dividerColor: c.divider,
    splashFactory: InkSparkle.splashFactory,
    extensions: [c],
    appBarTheme: AppBarTheme(
      backgroundColor: c.surface,
      foregroundColor: c.text,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: text.titleLarge,
    ),
    cardTheme: CardThemeData(
      color: c.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.card)),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: c.surface,
      selectedColor: c.brandSoft,
      side: BorderSide(color: c.divider),
      labelStyle: text.labelMedium,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.chip)),
      padding: const EdgeInsets.symmetric(horizontal: Space.s, vertical: Space.xs),
    ),
    dividerTheme: DividerThemeData(color: c.divider, thickness: 1, space: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: c.background,
      hintStyle: text.bodyLarge?.copyWith(color: c.textTertiary),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(Radii.chip), borderSide: BorderSide.none),
      contentPadding: const EdgeInsets.symmetric(horizontal: Space.l, vertical: Space.m),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: c.brand,
        foregroundColor: c.onBrand,
        textStyle: text.labelLarge,
        minimumSize: const Size(48, 48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.chip)),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        textStyle: WidgetStatePropertyAll(text.labelMedium),
        shape: WidgetStatePropertyAll(RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.chip))),
      ),
    ),
  );
}
