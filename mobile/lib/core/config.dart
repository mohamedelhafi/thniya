/// Configuration injectée au build : `--dart-define=API_BASE_URL=https://…` (specs/07 §7).
/// Vide = même origine (app web servie par nginx en développement).
class AppConfig {
  static const apiBase = String.fromEnvironment('API_BASE_URL', defaultValue: '');
  static const tilesPath = String.fromEnvironment('TILES_URL', defaultValue: '/tiles/tunisie.pmtiles');

  static String get tilesUrl {
    if (tilesPath.startsWith('http')) return tilesPath;
    if (apiBase.isNotEmpty) return '$apiBase$tilesPath';
    return Uri.base.resolve(tilesPath).toString();
  }
}
