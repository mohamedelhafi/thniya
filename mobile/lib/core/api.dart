import 'package:dio/dio.dart';

import 'config.dart';
import 'models.dart';

/// Erreur lisible pour l'interface (specs/07 §6 : 429, 503, hors ligne…).
class ApiError implements Exception {
  ApiError(this.kind, [this.code, this.message]);
  final ApiErrorKind kind;
  final String? code;
  final String? message;

  @override
  String toString() => 'ApiError($kind, $code, $message)';
}

enum ApiErrorKind { offline, tooManyRequests, unavailable, notFound, noRoute, other }

/// Relances automatiques des données (Riverpod relance par défaut toute erreur, indéfiniment, en laissant l'écran
/// en chargement). Ici : seulement les pannes passagères (pas de réseau, service indisponible), 2 fois au plus ;
/// jamais une réponse définitive comme « aucun itinéraire », qui doit s'afficher tout de suite.
Duration? retryPolicy(int retryCount, Object error) {
  final transient = error is ApiError && (error.kind == ApiErrorKind.offline || error.kind == ApiErrorKind.unavailable);
  if (!transient || retryCount >= 2) return null;
  return Duration(milliseconds: 700 * (retryCount + 1) * (retryCount + 1));
}

/// Client de l'API Thniya. La langue suit celle de l'app (en-tête Accept-Language).
class ThniyaApi {
  ThniyaApi(String languageCode)
      : _dio = Dio(BaseOptions(
          baseUrl: '${AppConfig.apiBase}/api/v1',
          connectTimeout: const Duration(seconds: 8),
          receiveTimeout: const Duration(seconds: 20),
          headers: {'Accept-Language': languageCode},
        ));

  final Dio _dio;

  Future<T> _call<T>(Future<Response<dynamic>> Function() request, T Function(dynamic) parse) async {
    try {
      final res = await request();
      return parse(res.data);
    } on DioException catch (e) {
      throw _map(e);
    }
  }

  ApiError _map(DioException e) {
    final status = e.response?.statusCode;
    final data = e.response?.data;
    final code = data is Map ? data['code'] as String? : null;
    final message = data is Map ? data['title'] as String? : null;
    if (status == null) return ApiError(ApiErrorKind.offline);
    if (status == 429) return ApiError(ApiErrorKind.tooManyRequests, code, message);
    if (status == 503) return ApiError(ApiErrorKind.unavailable, code, message);
    if (code == 'NO_ROUTE') return ApiError(ApiErrorKind.noRoute, code, message);
    if (status == 404) return ApiError(ApiErrorKind.notFound, code, message);
    return ApiError(ApiErrorKind.other, code, message);
  }

  Future<MetaInfo> meta() => _call(() => _dio.get('/meta'), (d) => MetaInfo.fromJson(d));

  Future<List<Place>> geocode(String q, {double? lat, double? lon}) => _call(
      () => _dio.get('/geocode', queryParameters: {'q': q, 'lat': ?lat, 'lon': ?lon, 'limit': 12}),
      (d) => ((d['results'] as List).map((e) => Place.fromJson(e))).toList());

  Future<Place> reverse(double lat, double lon) =>
      _call(() => _dio.get('/reverse', queryParameters: {'lat': lat, 'lon': lon}), (d) => Place.fromJson(d));

  Future<ItinerariesResponse> itineraries({
    required Place from,
    required Place to,
    String timeMode = 'NOW',
    DateTime? at,
    Map<String, dynamic>? preferences,
  }) =>
      _call(
          () => _dio.post('/itineraries', data: {
                'from': {'lat': from.lat, 'lon': from.lon, 'label': from.name, 'stopId': from.id},
                'to': {'lat': to.lat, 'lon': to.lon, 'label': to.name, 'stopId': to.id},
                'time': {'mode': timeMode, if (at != null) 'at': tunisIso(at)},
                'preferences': ?preferences,
              }),
          (d) => ItinerariesResponse.fromJson(d));

  Future<Itinerary> otherDeparture(String itineraryId, int legIndex, DateTime departAt) => _call(
      () => _dio.post('/itineraries/$itineraryId/legs/$legIndex/departures',
          data: {'departAt': tunisIso(departAt)}),
      (d) => Itinerary.fromJson(d));

  Future<List<NearbyStop>> nearby(double lat, double lon, {int radius = 1200, String? mode}) => _call(
      () => _dio.get('/nearby', queryParameters: {'lat': lat, 'lon': lon, 'radius': radius, 'mode': ?mode}),
      (d) => ((d['stops'] as List).map((e) => NearbyStop.fromJson(e))).toList());

  /// Arrêts de la zone affichée ; en vue large (zoom < 14), l'API ne renvoie que les gares et stations.
  Future<List<MapStop>> stopsInBbox(double west, double south, double east, double north, {double? zoom}) => _call(
      () => _dio.get('/stops/in-bbox', queryParameters: {
            'bbox': '$west,$south,$east,$north',
            if (zoom != null) 'zoom': zoom.toStringAsFixed(1),
          }),
      (d) => ((d as List).map((e) => MapStop.fromJson(e))).toList());

  Future<StopDetail> stop(String id) => _call(() => _dio.get('/stops/$id'), (d) => StopDetail.fromJson(d));

  Future<List<LineSummary>> lines({String? mode}) => _call(
      () => _dio.get('/lines', queryParameters: {'mode': ?mode}),
      (d) => ((d as List).map((e) => LineSummary.fromJson(e))).toList());

  Future<List<LineGeometry>> lineGeometry() =>
      _call(() => _dio.get('/lines/geometry'), (d) => ((d as List).map((e) => LineGeometry.fromJson(e))).toList());

  Future<LineDetail> line(String id) => _call(() => _dio.get('/lines/$id'), (d) => LineDetail.fromJson(d));

  Future<Timetable> timetable(String lineId, {required String direction, String? stop, required DateTime date}) => _call(
      () => _dio.get('/lines/$lineId/timetable', queryParameters: {
            'direction': direction,
            'stop': ?stop,
            'date': '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}',
          }),
      (d) => Timetable.fromJson(d));

  Future<List<BoardRow>> lineStopDepartures(String lineId, String stopId, {String? direction, int limit = 4}) => _call(
      () => _dio.get('/lines/$lineId/stops/$stopId/departures', queryParameters: {'direction': ?direction, 'limit': limit}),
      (d) => ((d as List).map((e) => BoardRow.fromJson(e))).toList());

  Future<void> feedback(String type, String text, Map<String, dynamic> context) =>
      _call(() => _dio.post('/feedback', data: {'type': type, 'text': text, 'context': context}), (_) {});
}
