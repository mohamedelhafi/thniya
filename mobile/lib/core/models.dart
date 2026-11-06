// Modèles de l'API /api/v1 (specs/06-api-backend.md). Lecture JSON écrite à la main, sans génération de code.

import 'package:collection/collection.dart';
import 'package:latlong2/latlong.dart';

typedef Json = Map<String, dynamic>;

List<T> _list<T>(dynamic v, T Function(Json) f) =>
    v == null ? <T>[] : (v as List).map((e) => f(e as Json)).toList();

DateTime? _time(dynamic v) => v == null ? null : toTunis(DateTime.parse(v as String));

/// Les horaires sont ceux de Tunis (UTC+1, sans heure d'été) quel que soit le réglage du téléphone.
const tunisOffset = Duration(hours: 1);

/// Heure « murale » de Tunis, sans fuseau : comparable avec [tunisNow].
DateTime toTunis(DateTime t) {
  final u = t.toUtc().add(tunisOffset);
  return DateTime(u.year, u.month, u.day, u.hour, u.minute, u.second);
}

DateTime tunisNow() => toTunis(DateTime.now());

/// « 2026-10-14T07:30:00+01:00 » à partir d'une heure murale de Tunis.
String tunisIso(DateTime wall) {
  String two(int n) => n.toString().padLeft(2, '0');
  return '${wall.year}-${two(wall.month)}-${two(wall.day)}T${two(wall.hour)}:${two(wall.minute)}:00+01:00';
}

class LineRef {
  LineRef({required this.id, this.mode, required this.publicCode, required this.name, required this.color,
      required this.textColor, this.status, this.estimated = false});
  final String id;
  final String? mode;
  final String publicCode;
  final String name;
  final String color;
  final String textColor;
  final String? status;

  /// Horaires ou durées estimés (pas encore de source officielle) : l'app l'indique.
  final bool estimated;

  factory LineRef.fromJson(Json j) => LineRef(
      id: j['id'], mode: j['mode'], publicCode: j['publicCode'] ?? '', name: j['name'] ?? '',
      color: j['color'] ?? '#555555', textColor: j['textColor'] ?? '#FFFFFF', status: j['status'],
      estimated: j['estimated'] ?? false);
}

class StopRef {
  StopRef({this.id, required this.name, this.area, this.lat, this.lon, this.platform});
  final String? id;
  final String name;
  final String? area;
  final double? lat;
  final double? lon;
  final String? platform;

  factory StopRef.fromJson(Json j) => StopRef(
      id: j['id'], name: j['name'] ?? '', area: j['area'], lat: (j['lat'] as num?)?.toDouble(),
      lon: (j['lon'] as num?)?.toDouble(), platform: j['platform']);
}

class Departure {
  Departure({required this.type, this.time, this.trip, this.headwayMin, this.from, this.to, this.estimated = false});
  final String type; // SCHEDULED | FREQUENCY
  final DateTime? time;
  final String? trip;
  final int? headwayMin;
  final String? from;
  final String? to;
  final bool estimated;

  bool get isFrequency => type == 'FREQUENCY';

  factory Departure.fromJson(Json j) => Departure(
      type: j['type'], time: _time(j['time']), trip: j['trip'], headwayMin: j['headwayMin'], from: j['from'],
      to: j['to'], estimated: j['estimated'] ?? false);
}

class Price {
  Price({this.millimes, this.currency = 'TND', this.estimated = false});
  final int? millimes;
  final String currency;
  final bool estimated;

  bool get known => millimes != null;

  factory Price.fromJson(Json? j) =>
      j == null ? Price() : Price(millimes: j['millimes'], currency: j['currency'] ?? 'TND', estimated: j['estimated'] ?? false);
}

class AlertView {
  AlertView({required this.id, required this.effect, required this.severity, required this.title, this.body, this.url});
  final String id;
  final String effect;
  final String severity;
  final String title;
  final String? body;
  final String? url;

  factory AlertView.fromJson(Json j) => AlertView(
      id: j['id'], effect: j['effect'], severity: j['severity'], title: j['title'] ?? '', body: j['body'], url: j['url']);
}

class PeriodView {
  PeriodView({required this.id, required this.name, required this.banner, this.dayType, this.holidays = const []});
  final String id;
  final String name;
  final bool banner;
  final String? dayType;
  final List<String> holidays;

  factory PeriodView.fromJson(Json j) => PeriodView(
      id: j['id'], name: j['name'] ?? '', banner: j['banner'] ?? false, dayType: j['dayType'],
      holidays: (j['holidays'] as List?)?.cast<String>() ?? const []);

  static PeriodView? maybe(dynamic j) => j == null ? null : PeriodView.fromJson(j as Json);
}

// --- Itinéraires ---------------------------------------------------------------------------

class ItinerariesResponse {
  ItinerariesResponse({required this.dataVersion, required this.coverage, this.notice, this.period,
      required this.sections, required this.itineraries});
  final String dataVersion;
  final String coverage;

  /// FIRST_DEPARTURES : plus rien ne circule à l'heure demandée, ce sont les premiers départs (nuit).
  final String? notice;
  final PeriodView? period;
  final List<Section> sections;
  final Map<String, Itinerary> itineraries;

  factory ItinerariesResponse.fromJson(Json j) => ItinerariesResponse(
      dataVersion: j['dataVersion'], coverage: j['coverage'], notice: j['notice'], period: PeriodView.maybe(j['period']),
      sections: _list(j['sections'], Section.fromJson),
      itineraries: (j['itineraries'] as Json).map((k, v) => MapEntry(k, Itinerary.fromJson(v as Json))));
}

class Section {
  Section({required this.key, required this.title, required this.itineraryIds});
  final String key;
  final String title;
  final List<String> itineraryIds;

  factory Section.fromJson(Json j) =>
      Section(key: j['key'], title: j['title'], itineraryIds: (j['itineraryIds'] as List).cast<String>());
}

class Itinerary {
  Itinerary({required this.id, required this.departAt, required this.arriveAt, required this.durationMin,
      required this.walkMin, required this.transfers, required this.price, required this.summary,
      required this.nextDepartures, required this.alerts, required this.legs, this.bounds});
  final String id;
  final DateTime departAt;
  final DateTime arriveAt;
  final int durationMin;
  final int walkMin;
  final int transfers;
  final Price price;
  final List<SummaryPart> summary;
  final List<Departure> nextDepartures;
  final List<AlertView> alerts;
  final List<Leg> legs;
  final List<List<double>>? bounds;

  Leg? get firstTransit => legs.where((l) => l.isTransit).firstOrNull;

  factory Itinerary.fromJson(Json j) => Itinerary(
      id: j['id'], departAt: _time(j['departAt'])!, arriveAt: _time(j['arriveAt'])!, durationMin: j['durationMin'],
      walkMin: j['walkMin'], transfers: j['transfers'], price: Price.fromJson(j['price']),
      summary: _list(j['summary'], SummaryPart.fromJson), nextDepartures: _list(j['nextDepartures'], Departure.fromJson),
      alerts: _list(j['alerts'], AlertView.fromJson), legs: _list(j['legs'], Leg.fromJson),
      bounds: (j['bounds'] as List?)?.map((p) => (p as List).map((x) => (x as num).toDouble()).toList()).toList());
}

class SummaryPart {
  SummaryPart({required this.mode, this.minutes, this.line, this.destination});
  final String mode;
  final int? minutes;
  final LineRef? line;
  final String? destination;

  factory SummaryPart.fromJson(Json j) => SummaryPart(
      mode: j['mode'], minutes: j['minutes'], line: j['line'] == null ? null : LineRef.fromJson(j['line']),
      destination: j['destination']);
}

class Leg {
  Leg({required this.type, required this.mode, this.line, this.headsign, this.from, this.to, this.departAt,
      this.arriveAt, required this.durationMin, this.distanceM, this.steps = const [], this.intermediateStops = const [],
      this.departures, this.departure, this.waitMin, this.durationEstimated = false, this.departsWhenFull = false,
      required this.price, this.alerts = const [], this.polyline});
  final String type; // WALK | TRANSIT
  final String mode;
  final LineRef? line;
  final String? headsign;
  final StopRef? from;
  final StopRef? to;
  final DateTime? departAt;
  final DateTime? arriveAt;
  final int durationMin;
  final int? distanceM;
  final List<Step> steps;
  final List<IntermediateStop> intermediateStops;
  final List<Departure>? departures;
  final Departure? departure;
  final int? waitMin;
  final bool durationEstimated;
  final bool departsWhenFull;
  final Price price;
  final List<AlertView> alerts;
  final String? polyline;

  bool get isTransit => type == 'TRANSIT';
  bool get isWalk => type == 'WALK';

  factory Leg.fromJson(Json j) => Leg(
      type: j['type'], mode: j['mode'] ?? j['type'], line: j['line'] == null ? null : LineRef.fromJson(j['line']),
      headsign: j['headsign'], from: j['from'] == null ? null : StopRef.fromJson(j['from']),
      to: j['to'] == null ? null : StopRef.fromJson(j['to']), departAt: _time(j['departAt']),
      arriveAt: _time(j['arriveAt']), durationMin: j['durationMin'] ?? 0, distanceM: j['distanceM'],
      steps: _list(j['steps'], Step.fromJson), intermediateStops: _list(j['intermediateStops'], IntermediateStop.fromJson),
      departures: j['departures'] == null ? null : _list(j['departures'], Departure.fromJson),
      departure: j['departure'] == null ? null : Departure.fromJson(j['departure']), waitMin: j['waitMin'],
      durationEstimated: j['durationEstimated'] ?? false, departsWhenFull: j['departsWhenFull'] ?? false,
      price: Price.fromJson(j['price']), alerts: _list(j['alerts'], AlertView.fromJson), polyline: j['polyline']);
}

class Step {
  Step({required this.instruction, this.street, required this.distanceM});
  final String instruction;
  final String? street;
  final int distanceM;

  factory Step.fromJson(Json j) => Step(instruction: j['instruction'], street: j['street'], distanceM: j['distanceM']);
}

class IntermediateStop {
  IntermediateStop({this.stopId, required this.name, this.time, this.lat, this.lon});
  final String? stopId;
  final String name;
  final DateTime? time;
  final double? lat;
  final double? lon;

  factory IntermediateStop.fromJson(Json j) => IntermediateStop(
      stopId: j['stopId'], name: j['name'] ?? '', time: _time(j['time']),
      lat: (j['lat'] as num?)?.toDouble(), lon: (j['lon'] as num?)?.toDouble());
}

// --- Arrêts --------------------------------------------------------------------------------

class BoardRow {
  BoardRow({required this.line, required this.direction, this.headsign, required this.departures,
      required this.noServiceToday, this.nextServiceAt});
  final LineRef line;
  final String direction;
  final String? headsign;
  final List<Departure> departures;
  final bool noServiceToday;
  final DateTime? nextServiceAt;

  factory BoardRow.fromJson(Json j) => BoardRow(
      line: LineRef.fromJson(j['line']), direction: j['direction'], headsign: j['headsign'],
      departures: _list(j['departures'], Departure.fromJson), noServiceToday: j['noServiceToday'] ?? false,
      nextServiceAt: _time(j['nextServiceAt']));
}

class NearbyStop {
  NearbyStop({required this.stop, required this.distanceM, required this.walkMin, required this.modes, required this.lines});
  final StopRef stop;
  final int distanceM;
  final int walkMin;
  final List<String> modes;
  final List<BoardRow> lines;

  factory NearbyStop.fromJson(Json j) => NearbyStop(
      stop: StopRef.fromJson(j['stop']), distanceM: j['distanceM'], walkMin: j['walkMin'],
      modes: (j['modes'] as List).cast<String>(), lines: _list(j['lines'], BoardRow.fromJson));
}

class MapStop {
  MapStop({required this.id, required this.kind, required this.name, required this.lat, required this.lon,
      required this.modes, this.lines = const []});
  final String id;
  final String kind;
  final String name;
  final double lat;
  final double lon;
  final List<String> modes;

  /// Identifiants des lignes qui desservent l'arrêt (tracées quand on le touche).
  final List<String> lines;

  factory MapStop.fromJson(Json j) => MapStop(
      id: j['id'], kind: j['kind'], name: j['name'], lat: (j['lat'] as num).toDouble(),
      lon: (j['lon'] as num).toDouble(), modes: (j['modes'] as List).cast<String>(),
      lines: (j['lines'] as List? ?? const []).cast<String>());
}

class LouageDestination {
  LouageDestination({required this.line, this.destination, this.bay, required this.price, required this.departure});
  final LineRef line;
  final String? destination;
  final String? bay;
  final Price price;
  final Departure departure;

  factory LouageDestination.fromJson(Json j) => LouageDestination(
      line: LineRef.fromJson(j['line']), destination: j['destination'], bay: j['bay'],
      price: Price.fromJson(j['price']), departure: Departure.fromJson(j['departure']));
}

class StopDetail {
  StopDetail({required this.id, required this.kind, required this.name, this.area, required this.lat, required this.lon,
      required this.modes, required this.lines, required this.alerts, required this.board,
      this.louageDestinations = const [], this.confidence});
  final String id;
  final String kind;
  final String name;
  final String? area;
  final double lat;
  final double lon;
  final List<String> modes;
  final List<LineRef> lines;
  final List<AlertView> alerts;
  final List<BoardRow> board;
  final List<LouageDestination> louageDestinations;
  final String? confidence;

  factory StopDetail.fromJson(Json j) => StopDetail(
      id: j['id'], kind: j['kind'], name: j['name'], area: j['area'], lat: (j['lat'] as num).toDouble(),
      lon: (j['lon'] as num).toDouble(), modes: (j['modes'] as List).cast<String>(),
      lines: _list(j['lines'], LineRef.fromJson), alerts: _list(j['alerts'], AlertView.fromJson),
      board: _list(j['board'], BoardRow.fromJson), louageDestinations: _list(j['louageDestinations'], LouageDestination.fromJson),
      confidence: j['confidence']);
}

// --- Lignes --------------------------------------------------------------------------------

class LineSummary {
  LineSummary({required this.line, required this.network, required this.termini, required this.alerts});
  final LineRef line;
  final String network;
  final List<String> termini;
  final int alerts;

  factory LineSummary.fromJson(Json j) => LineSummary(
      line: LineRef.fromJson(j['line']), network: j['network'] ?? '', termini: (j['termini'] as List).cast<String>(),
      alerts: j['alerts'] ?? 0);
}

class DiagramStop {
  DiagramStop({required this.stopId, required this.name, this.area, required this.isTerminus, required this.interchanges,
      this.lat, this.lon});
  final String stopId;
  final String name;
  final String? area;
  final bool isTerminus;
  final List<LineRef> interchanges;
  final double? lat;
  final double? lon;

  factory DiagramStop.fromJson(Json j) => DiagramStop(
      stopId: j['stopId'], name: j['name'], area: j['area'], isTerminus: j['isTerminus'] ?? false,
      interchanges: _list(j['interchanges'], LineRef.fromJson),
      lat: (j['lat'] as num?)?.toDouble(), lon: (j['lon'] as num?)?.toDouble());
}

class DirectionView {
  DirectionView({required this.id, required this.headsign, required this.stops});
  final String id;
  final String headsign;
  final List<DiagramStop> stops;

  factory DirectionView.fromJson(Json j) =>
      DirectionView(id: j['id'], headsign: j['headsign'], stops: _list(j['stops'], DiagramStop.fromJson));
}

class TimetableVersion {
  TimetableVersion({required this.id, required this.validFrom, required this.validTo, this.source, this.corrections = 0});
  final String id;
  final String validFrom;
  final String validTo;
  final String? source;
  final int corrections;

  factory TimetableVersion.fromJson(Json j) => TimetableVersion(
      id: j['id'], validFrom: j['validFrom'], validTo: j['validTo'], source: j['source'], corrections: j['corrections'] ?? 0);
}

class LineDetail {
  LineDetail({required this.line, this.longName, required this.network, this.period, required this.alerts,
      required this.directions, required this.notes, required this.dayCodes, required this.versions,
      required this.scheduleKind, this.confidence, this.verifiedAt});
  final LineRef line;
  final String? longName;
  final String network;
  final PeriodView? period;
  final List<AlertView> alerts;
  final List<DirectionView> directions;
  final Map<String, String> notes;
  final Map<String, String> dayCodes;
  final List<TimetableVersion> versions;
  final String scheduleKind;
  final String? confidence;
  final String? verifiedAt;

  factory LineDetail.fromJson(Json j) => LineDetail(
      line: LineRef.fromJson(j['line']), longName: j['longName'], network: j['network'] ?? '',
      period: PeriodView.maybe(j['period']), alerts: _list(j['alerts'], AlertView.fromJson),
      directions: _list(j['directions'], DirectionView.fromJson),
      notes: (j['notes'] as Json? ?? {}).cast<String, String>(), dayCodes: (j['dayCodes'] as Json? ?? {}).cast<String, String>(),
      versions: _list(j['timetableVersions'], TimetableVersion.fromJson), scheduleKind: j['scheduleKind'] ?? 'timetable',
      confidence: j['confidence'], verifiedAt: j['verifiedAt']);
}

class FrequencyBand {
  FrequencyBand({required this.band, required this.from, required this.to, this.headwayMin});
  final String band;
  final String from;
  final String to;
  final int? headwayMin;

  factory FrequencyBand.fromJson(Json j) =>
      FrequencyBand(band: j['band'], from: j['from'], to: j['to'], headwayMin: j['headwayMin']);
}

class TimetableMinute {
  TimetableMinute(this.m, this.trip);
  final int m;
  final String? trip;
}

class TimetableHour {
  TimetableHour(this.hour, this.minutes);
  final int hour;
  final List<TimetableMinute> minutes;
}

class Timetable {
  Timetable({required this.date, this.period, this.gridPeriod, required this.direction, this.headsign, this.stop,
      required this.kind, required this.hours, required this.frequencies, this.firstDeparture, this.lastDeparture,
      required this.count});
  final String date;
  final PeriodView? period;
  final String? gridPeriod;
  final String direction;
  final String? headsign;
  final StopRef? stop;
  final String kind;
  final List<TimetableHour> hours;
  final List<FrequencyBand> frequencies;
  final String? firstDeparture;
  final String? lastDeparture;
  final int count;

  factory Timetable.fromJson(Json j) => Timetable(
      date: j['date'], period: PeriodView.maybe(j['period']), gridPeriod: j['gridPeriod'], direction: j['direction'],
      headsign: j['headsign'], stop: j['stop'] == null ? null : StopRef.fromJson(j['stop']), kind: j['kind'],
      hours: ((j['hours'] as List?) ?? const [])
          .map((h) => TimetableHour(h['hour'], ((h['minutes'] as List).map((m) => TimetableMinute(m['m'], m['trip']))).toList()))
          .toList(),
      frequencies: _list(j['frequencies'], FrequencyBand.fromJson), firstDeparture: j['firstDeparture'],
      lastDeparture: j['lastDeparture'], count: j['count'] ?? 0);
}

// --- Recherche & méta ----------------------------------------------------------------------

class Place {
  Place({required this.type, this.id, required this.name, this.area, required this.lat, required this.lon,
      this.modes = const [], this.lines = const [], this.distanceM});
  final String type; // STOP | PLACE | POINT | MY_LOCATION
  final String? id;
  final String name;
  final String? area;
  final double lat;
  final double lon;
  final List<String> modes;
  final List<LineRef> lines;
  final int? distanceM;

  factory Place.fromJson(Json j) => Place(
      type: j['type'], id: j['id'], name: j['name'], area: j['area'], lat: (j['lat'] as num).toDouble(),
      lon: (j['lon'] as num).toDouble(), modes: ((j['modes'] as List?) ?? const []).cast<String>(),
      lines: _list(j['lines'], LineRef.fromJson), distanceM: j['distanceM']);

  Json toJson() => {'type': type, 'id': id, 'name': name, 'area': area, 'lat': lat, 'lon': lon, 'modes': modes};
}

class ModeInfo {
  ModeInfo({required this.name, required this.icon, this.color, required this.showsExactTimes});
  final String name;
  final String icon;
  final String? color;
  final bool showsExactTimes;

  factory ModeInfo.fromJson(Json j) =>
      ModeInfo(name: j['name'], icon: j['icon'], color: j['color'], showsExactTimes: j['showsExactTimes'] ?? true);
}

class MetaInfo {
  MetaInfo({required this.dataVersion, required this.modes, required this.today, required this.lines, required this.stops});
  final String dataVersion;
  final Map<String, ModeInfo> modes;
  final Map<String, PeriodView?> today;
  final int lines;
  final int stops;

  PeriodView? get mainPeriod => today.values.whereType<PeriodView>().firstOrNull;

  factory MetaInfo.fromJson(Json j) => MetaInfo(
      dataVersion: j['dataVersion'],
      modes: (j['modes'] as Json).map((k, v) => MapEntry(k, ModeInfo.fromJson(v as Json))),
      today: (j['today'] as Json).map((k, v) => MapEntry(k, PeriodView.maybe(v))), lines: j['lines'], stops: j['stops']);
}

class LineGeometry {
  LineGeometry({required this.line, required this.points});
  final LineRef line;
  final List<LatLng> points;

  factory LineGeometry.fromJson(Json j) => LineGeometry(
      line: LineRef.fromJson(j['line']),
      points: (j['points'] as List).map((p) => LatLng((p[0] as num).toDouble(), (p[1] as num).toDouble())).toList());
}
