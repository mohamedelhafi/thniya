import 'package:flutter_test/flutter_test.dart';
import 'package:thniya/features/results/results_screen.dart';

void main() {
  test('lien partageable : départ, arrivée, heure de départ', () {
    final a = ResultsArgs.fromUri(Uri.parse(
        '/results?from=36.72442,10.30105,Boumhel&to=36.83509,10.23884,Les%20Berges%20du%20Lac&depart=2026-10-14T08:00'))!;
    expect(a.from.name, 'Boumhel');
    expect(a.to.name, 'Les Berges du Lac');
    expect(a.to.lat, closeTo(36.83509, 1e-9));
    expect(a.timeMode, 'DEPART_AT');
    expect(a.at, DateTime(2026, 10, 14, 8));
  });

  test("lien partageable : « arriver avant » et nom contenant une virgule", () {
    final a = ResultsArgs.fromUri(Uri.parse('/results?from=36.7,10.3,Hammam%20Lif,%20plage&to=36.8,10.3&arrive=2026-10-14T09:30'))!;
    expect(a.from.name, 'Hammam Lif, plage');
    expect(a.timeMode, 'ARRIVE_BY');
  });

  test('lien incomplet : pas de résultats', () {
    expect(ResultsArgs.fromUri(Uri.parse('/results?from=36.7,10.3')), isNull);
    expect(ResultsArgs.fromUri(Uri.parse('/results?from=abc&to=36.8,10.3')), isNull);
  });
}
