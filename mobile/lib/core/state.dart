import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'models.dart';

/// Préférences locales (langue, thème, lieux enregistrés, récents) — sans compte (specs/07 §5.9).
final prefsProvider = Provider<SharedPreferences>((ref) => throw UnimplementedError('initialisé dans main'));

// --- Langue et thème -----------------------------------------------------------------------

class LocaleNotifier extends Notifier<Locale> {
  @override
  Locale build() {
    final saved = ref.read(prefsProvider).getString('locale');
    if (saved != null) return Locale(saved);
    final system = WidgetsBinding.instance.platformDispatcher.locale.languageCode;
    return Locale(system == 'ar' ? 'ar' : 'fr');
  }

  void set(Locale locale) {
    ref.read(prefsProvider).setString('locale', locale.languageCode);
    state = locale;
  }
}

final localeProvider = NotifierProvider<LocaleNotifier, Locale>(LocaleNotifier.new);

class ThemeModeNotifier extends Notifier<ThemeMode> {
  @override
  ThemeMode build() => ThemeMode.values.byName(ref.read(prefsProvider).getString('themeMode') ?? 'system');

  void set(ThemeMode mode) {
    ref.read(prefsProvider).setString('themeMode', mode.name);
    state = mode;
  }
}

final themeModeProvider = NotifierProvider<ThemeModeNotifier, ThemeMode>(ThemeModeNotifier.new);

/// Le client API suit la langue : changer de langue recharge tout le contenu traduit.
final apiProvider = Provider<ThniyaApi>((ref) => ThniyaApi(ref.watch(localeProvider).languageCode));

final metaProvider = FutureProvider<MetaInfo>((ref) => ref.watch(apiProvider).meta());

// --- Horloge (comptes à rebours) -----------------------------------------------------------

/// Bat chaque 20 s : les « dans 4 min » se mettent à jour sans recharger les données.
final clockProvider = StreamProvider<DateTime>((ref) async* {
  yield tunisNow();
  yield* Stream.periodic(const Duration(seconds: 20), (_) => tunisNow());
});

// --- Position ------------------------------------------------------------------------------

/// Place Barcelone (gare de Tunis) quand la position n'est pas disponible.
const defaultCenter = LatLng(36.7963, 10.1808);

class LocationState {
  const LocationState(this.position, {this.granted = false, this.loading = false});
  final LatLng position;
  final bool granted;
  final bool loading;
}

class LocationNotifier extends Notifier<LocationState> {
  @override
  LocationState build() {
    Future.microtask(locate);
    return const LocationState(defaultCenter, loading: true);
  }

  Future<void> locate() async {
    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        state = const LocationState(defaultCenter);
        return;
      }
      final p = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 8)));
      state = LocationState(LatLng(p.latitude, p.longitude), granted: true);
    } catch (_) {
      state = const LocationState(defaultCenter);
    }
  }
}

final locationProvider = NotifierProvider<LocationNotifier, LocationState>(LocationNotifier.new);

// --- Lieux enregistrés et récents ----------------------------------------------------------

class SavedPlaces {
  const SavedPlaces({this.home, this.work, this.recents = const []});
  final Place? home;
  final Place? work;
  final List<Place> recents;
}

class SavedPlacesNotifier extends Notifier<SavedPlaces> {
  SharedPreferences get _p => ref.read(prefsProvider);

  Place? _read(String key) {
    final raw = _p.getString(key);
    return raw == null ? null : Place.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  @override
  SavedPlaces build() {
    final recents = (_p.getStringList('recents') ?? [])
        .map((r) => Place.fromJson(jsonDecode(r) as Map<String, dynamic>))
        .toList();
    return SavedPlaces(home: _read('home'), work: _read('work'), recents: recents);
  }

  void setHome(Place p) {
    _p.setString('home', jsonEncode(p.toJson()));
    state = SavedPlaces(home: p, work: state.work, recents: state.recents);
  }

  void setWork(Place p) {
    _p.setString('work', jsonEncode(p.toJson()));
    state = SavedPlaces(home: state.home, work: p, recents: state.recents);
  }

  void addRecent(Place p) {
    if (p.type == 'MY_LOCATION') return;
    final list = [p, ...state.recents.where((r) => r.name != p.name)].take(8).toList();
    _p.setStringList('recents', list.map((r) => jsonEncode(r.toJson())).toList());
    state = SavedPlaces(home: state.home, work: state.work, recents: list);
  }
}

final savedPlacesProvider = NotifierProvider<SavedPlacesNotifier, SavedPlaces>(SavedPlacesNotifier.new);
