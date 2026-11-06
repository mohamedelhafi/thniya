import 'package:flutter_test/flutter_test.dart';
import 'package:thniya/core/api.dart';

void main() {
  test("« aucun itinéraire » n'est jamais relancé : le message s'affiche tout de suite", () {
    expect(retryPolicy(0, ApiError(ApiErrorKind.noRoute)), isNull);
    expect(retryPolicy(0, ApiError(ApiErrorKind.notFound)), isNull);
    expect(retryPolicy(0, ApiError(ApiErrorKind.tooManyRequests)), isNull);
    expect(retryPolicy(0, StateError('bug')), isNull);
  });

  test('panne passagère : 2 relances au plus', () {
    expect(retryPolicy(0, ApiError(ApiErrorKind.offline)), isNotNull);
    expect(retryPolicy(1, ApiError(ApiErrorKind.unavailable)), isNotNull);
    expect(retryPolicy(2, ApiError(ApiErrorKind.offline)), isNull);
  });
}
