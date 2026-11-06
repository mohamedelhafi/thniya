import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_fr.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of L
/// returned by `L.of(context)`.
///
/// Applications need to include `L.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: L.localizationsDelegates,
///   supportedLocales: L.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the L.supportedLocales
/// property.
abstract class L {
  L(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static L of(BuildContext context) {
    return Localizations.of<L>(context, L)!;
  }

  static const LocalizationsDelegate<L> delegate = _LDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('fr'),
  ];

  /// No description provided for @appName.
  ///
  /// In fr, this message translates to:
  /// **'Thniya'**
  String get appName;

  /// No description provided for @whereTo.
  ///
  /// In fr, this message translates to:
  /// **'Où allez-vous ?'**
  String get whereTo;

  /// No description provided for @home.
  ///
  /// In fr, this message translates to:
  /// **'Maison'**
  String get home;

  /// No description provided for @work.
  ///
  /// In fr, this message translates to:
  /// **'Travail'**
  String get work;

  /// No description provided for @setHome.
  ///
  /// In fr, this message translates to:
  /// **'Définir'**
  String get setHome;

  /// No description provided for @lines.
  ///
  /// In fr, this message translates to:
  /// **'Lignes'**
  String get lines;

  /// No description provided for @nearby.
  ///
  /// In fr, this message translates to:
  /// **'À proximité'**
  String get nearby;

  /// No description provided for @all.
  ///
  /// In fr, this message translates to:
  /// **'Tout'**
  String get all;

  /// No description provided for @myLocation.
  ///
  /// In fr, this message translates to:
  /// **'Ma position'**
  String get myLocation;

  /// No description provided for @from.
  ///
  /// In fr, this message translates to:
  /// **'Départ'**
  String get from;

  /// No description provided for @to.
  ///
  /// In fr, this message translates to:
  /// **'Arrivée'**
  String get to;

  /// No description provided for @searchHint.
  ///
  /// In fr, this message translates to:
  /// **'Gare, arrêt, adresse, lieu…'**
  String get searchHint;

  /// No description provided for @stopsAndStations.
  ///
  /// In fr, this message translates to:
  /// **'Arrêts et stations'**
  String get stopsAndStations;

  /// No description provided for @addressesAndPlaces.
  ///
  /// In fr, this message translates to:
  /// **'Adresses et lieux'**
  String get addressesAndPlaces;

  /// No description provided for @recent.
  ///
  /// In fr, this message translates to:
  /// **'Récents'**
  String get recent;

  /// No description provided for @chooseOnMap.
  ///
  /// In fr, this message translates to:
  /// **'Choisir sur la carte'**
  String get chooseOnMap;

  /// No description provided for @leaveNow.
  ///
  /// In fr, this message translates to:
  /// **'Partir maintenant'**
  String get leaveNow;

  /// No description provided for @departAt.
  ///
  /// In fr, this message translates to:
  /// **'Partir à {time}'**
  String departAt(String time);

  /// No description provided for @arriveBy.
  ///
  /// In fr, this message translates to:
  /// **'Arriver avant {time}'**
  String arriveBy(String time);

  /// No description provided for @minutesShort.
  ///
  /// In fr, this message translates to:
  /// **'{n} min'**
  String minutesShort(int n);

  /// No description provided for @hoursMinutes.
  ///
  /// In fr, this message translates to:
  /// **'{h} h {m}'**
  String hoursMinutes(int h, String m);

  /// No description provided for @inMinutes.
  ///
  /// In fr, this message translates to:
  /// **'dans {n} min'**
  String inMinutes(int n);

  /// No description provided for @now.
  ///
  /// In fr, this message translates to:
  /// **'maintenant'**
  String get now;

  /// No description provided for @arrival.
  ///
  /// In fr, this message translates to:
  /// **'Arrivée {time}'**
  String arrival(String time);

  /// No description provided for @walkMinutes.
  ///
  /// In fr, this message translates to:
  /// **'{n} min à pied'**
  String walkMinutes(int n);

  /// No description provided for @priceUnknown.
  ///
  /// In fr, this message translates to:
  /// **'Prix inconnu'**
  String get priceUnknown;

  /// No description provided for @price.
  ///
  /// In fr, this message translates to:
  /// **'{amount} DT'**
  String price(String amount);

  /// No description provided for @everyMinutes.
  ///
  /// In fr, this message translates to:
  /// **'~toutes les {n} min'**
  String everyMinutes(int n);

  /// No description provided for @departsWhenFull.
  ///
  /// In fr, this message translates to:
  /// **'Part quand il est plein'**
  String get departsWhenFull;

  /// No description provided for @transfers.
  ///
  /// In fr, this message translates to:
  /// **'{n, plural, =0{Direct} =1{1 correspondance} other{{n} correspondances}}'**
  String transfers(int n);

  /// No description provided for @stopsCount.
  ///
  /// In fr, this message translates to:
  /// **'{n, plural, =0{Sans arrêt} =1{1 arrêt} other{{n} arrêts}}'**
  String stopsCount(int n);

  /// No description provided for @walkTo.
  ///
  /// In fr, this message translates to:
  /// **'Marchez jusqu\'à {place}'**
  String walkTo(String place);

  /// No description provided for @walkDistance.
  ///
  /// In fr, this message translates to:
  /// **'{min} min · {meters} m'**
  String walkDistance(int min, int meters);

  /// No description provided for @towards.
  ///
  /// In fr, this message translates to:
  /// **'vers {place}'**
  String towards(String place);

  /// No description provided for @getOffAt.
  ///
  /// In fr, this message translates to:
  /// **'Descendez à {place}'**
  String getOffAt(String place);

  /// No description provided for @board.
  ///
  /// In fr, this message translates to:
  /// **'Montez'**
  String get board;

  /// No description provided for @otherDepartures.
  ///
  /// In fr, this message translates to:
  /// **'Autres départs'**
  String get otherDepartures;

  /// No description provided for @arriveAt.
  ///
  /// In fr, this message translates to:
  /// **'Arrivée à {place}'**
  String arriveAt(String place);

  /// No description provided for @save.
  ///
  /// In fr, this message translates to:
  /// **'Enregistrer'**
  String get save;

  /// No description provided for @share.
  ///
  /// In fr, this message translates to:
  /// **'Partager'**
  String get share;

  /// No description provided for @reportProblem.
  ///
  /// In fr, this message translates to:
  /// **'Signaler'**
  String get reportProblem;

  /// No description provided for @noTransitHere.
  ///
  /// In fr, this message translates to:
  /// **'Pas encore de transports ici'**
  String get noTransitHere;

  /// No description provided for @noTransitHereBody.
  ///
  /// In fr, this message translates to:
  /// **'Thniya couvre pour l\'instant la banlieue sud de Tunis. Voici l\'itinéraire à pied.'**
  String get noTransitHereBody;

  /// No description provided for @loadingError.
  ///
  /// In fr, this message translates to:
  /// **'Impossible de charger'**
  String get loadingError;

  /// No description provided for @retry.
  ///
  /// In fr, this message translates to:
  /// **'Réessayer'**
  String get retry;

  /// No description provided for @offline.
  ///
  /// In fr, this message translates to:
  /// **'Pas de connexion'**
  String get offline;

  /// No description provided for @tooManyRequests.
  ///
  /// In fr, this message translates to:
  /// **'Trop de demandes, réessayez dans un instant'**
  String get tooManyRequests;

  /// No description provided for @serviceUnavailable.
  ///
  /// In fr, this message translates to:
  /// **'Service momentanément indisponible'**
  String get serviceUnavailable;

  /// No description provided for @noRoute.
  ///
  /// In fr, this message translates to:
  /// **'Aucun itinéraire trouvé'**
  String get noRoute;

  /// No description provided for @direction.
  ///
  /// In fr, this message translates to:
  /// **'Direction'**
  String get direction;

  /// No description provided for @stops.
  ///
  /// In fr, this message translates to:
  /// **'Arrêts'**
  String get stops;

  /// No description provided for @timetable.
  ///
  /// In fr, this message translates to:
  /// **'Horaires'**
  String get timetable;

  /// No description provided for @today.
  ///
  /// In fr, this message translates to:
  /// **'Aujourd\'hui'**
  String get today;

  /// No description provided for @tomorrow.
  ///
  /// In fr, this message translates to:
  /// **'Demain'**
  String get tomorrow;

  /// No description provided for @saturday.
  ///
  /// In fr, this message translates to:
  /// **'Samedi'**
  String get saturday;

  /// No description provided for @sunday.
  ///
  /// In fr, this message translates to:
  /// **'Dimanche'**
  String get sunday;

  /// No description provided for @departuresCount.
  ///
  /// In fr, this message translates to:
  /// **'{n} départs'**
  String departuresCount(int n);

  /// No description provided for @firstLast.
  ///
  /// In fr, this message translates to:
  /// **'Premier {first} · Dernier {last}'**
  String firstLast(String first, String last);

  /// No description provided for @noServiceToday.
  ///
  /// In fr, this message translates to:
  /// **'Pas de départ aujourd\'hui'**
  String get noServiceToday;

  /// No description provided for @nextService.
  ///
  /// In fr, this message translates to:
  /// **'Prochain : {when}'**
  String nextService(String when);

  /// No description provided for @nextDepartures.
  ///
  /// In fr, this message translates to:
  /// **'Prochains départs'**
  String get nextDepartures;

  /// No description provided for @usualTimetableNotice.
  ///
  /// In fr, this message translates to:
  /// **'Horaires de {period} non publiés : horaires habituels affichés'**
  String usualTimetableNotice(String period);

  /// No description provided for @settings.
  ///
  /// In fr, this message translates to:
  /// **'Réglages'**
  String get settings;

  /// No description provided for @language.
  ///
  /// In fr, this message translates to:
  /// **'Langue'**
  String get language;

  /// No description provided for @theme.
  ///
  /// In fr, this message translates to:
  /// **'Thème'**
  String get theme;

  /// No description provided for @themeSystem.
  ///
  /// In fr, this message translates to:
  /// **'Système'**
  String get themeSystem;

  /// No description provided for @themeLight.
  ///
  /// In fr, this message translates to:
  /// **'Clair'**
  String get themeLight;

  /// No description provided for @themeDark.
  ///
  /// In fr, this message translates to:
  /// **'Sombre'**
  String get themeDark;

  /// No description provided for @aboutData.
  ///
  /// In fr, this message translates to:
  /// **'À propos des données'**
  String get aboutData;

  /// No description provided for @dataVersion.
  ///
  /// In fr, this message translates to:
  /// **'Version des données : {v}'**
  String dataVersion(String v);

  /// No description provided for @dataSources.
  ///
  /// In fr, this message translates to:
  /// **'Sources : data.transport.tn (Transtu, SNTRI, ministère du Transport), sites de la SNCFT, de la Transtu et de la SNTRI, OpenStreetMap (ODbL), Protomaps. Les horaires Transtu sont estimés. Application indépendante et non officielle : en cas de doute, vérifiez auprès de l\'opérateur.'**
  String get dataSources;

  /// No description provided for @officialTimes.
  ///
  /// In fr, this message translates to:
  /// **'Horaires officiels'**
  String get officialTimes;

  /// No description provided for @estimatedTimes.
  ///
  /// In fr, this message translates to:
  /// **'Horaires estimés'**
  String get estimatedTimes;

  /// No description provided for @suggestions.
  ///
  /// In fr, this message translates to:
  /// **'Suggestions'**
  String get suggestions;

  /// No description provided for @seeLine.
  ///
  /// In fr, this message translates to:
  /// **'Voir la ligne'**
  String get seeLine;

  /// No description provided for @seeStop.
  ///
  /// In fr, this message translates to:
  /// **'Voir l\'arrêt'**
  String get seeStop;

  /// No description provided for @allLines.
  ///
  /// In fr, this message translates to:
  /// **'Toutes les lignes'**
  String get allLines;

  /// No description provided for @noNearby.
  ///
  /// In fr, this message translates to:
  /// **'Aucun arrêt à distance de marche'**
  String get noNearby;

  /// No description provided for @locating.
  ///
  /// In fr, this message translates to:
  /// **'Recherche de votre position…'**
  String get locating;

  /// No description provided for @goHome.
  ///
  /// In fr, this message translates to:
  /// **'Rentrer'**
  String get goHome;

  /// No description provided for @holiday.
  ///
  /// In fr, this message translates to:
  /// **'Jour férié : {name}'**
  String holiday(String name);

  /// No description provided for @feedbackSent.
  ///
  /// In fr, this message translates to:
  /// **'Merci ! Votre signalement a été envoyé.'**
  String get feedbackSent;

  /// No description provided for @feedbackPrompt.
  ///
  /// In fr, this message translates to:
  /// **'Qu\'est-ce qui ne va pas ?'**
  String get feedbackPrompt;

  /// No description provided for @send.
  ///
  /// In fr, this message translates to:
  /// **'Envoyer'**
  String get send;

  /// No description provided for @cancel.
  ///
  /// In fr, this message translates to:
  /// **'Annuler'**
  String get cancel;

  /// No description provided for @swap.
  ///
  /// In fr, this message translates to:
  /// **'Inverser'**
  String get swap;

  /// No description provided for @earlier.
  ///
  /// In fr, this message translates to:
  /// **'Plus tôt'**
  String get earlier;

  /// No description provided for @later.
  ///
  /// In fr, this message translates to:
  /// **'Plus tard'**
  String get later;

  /// No description provided for @walk.
  ///
  /// In fr, this message translates to:
  /// **'Marche'**
  String get walk;

  /// No description provided for @change.
  ///
  /// In fr, this message translates to:
  /// **'Changement'**
  String get change;

  /// No description provided for @routeHere.
  ///
  /// In fr, this message translates to:
  /// **'Itinéraire vers ici'**
  String get routeHere;

  /// No description provided for @platform.
  ///
  /// In fr, this message translates to:
  /// **'Voie {code}'**
  String platform(String code);

  /// No description provided for @minUnit.
  ///
  /// In fr, this message translates to:
  /// **'min'**
  String get minUnit;

  /// No description provided for @hourUnit.
  ///
  /// In fr, this message translates to:
  /// **'h'**
  String get hourUnit;

  /// No description provided for @noResults.
  ///
  /// In fr, this message translates to:
  /// **'Aucun résultat'**
  String get noResults;

  /// No description provided for @boardAt.
  ///
  /// In fr, this message translates to:
  /// **'Montez à {place}'**
  String boardAt(String place);

  /// No description provided for @stepOf.
  ///
  /// In fr, this message translates to:
  /// **'Étape {n} sur {total}'**
  String stepOf(int n, int total);

  /// No description provided for @overview.
  ///
  /// In fr, this message translates to:
  /// **'Vue d\'ensemble'**
  String get overview;

  /// No description provided for @tapLegHint.
  ///
  /// In fr, this message translates to:
  /// **'Touchez une étape pour la voir sur la carte'**
  String get tapLegHint;

  /// No description provided for @boarding.
  ///
  /// In fr, this message translates to:
  /// **'Montée'**
  String get boarding;

  /// No description provided for @alighting.
  ///
  /// In fr, this message translates to:
  /// **'Descente'**
  String get alighting;

  /// No description provided for @routeFromHere.
  ///
  /// In fr, this message translates to:
  /// **'Partir d\'ici'**
  String get routeFromHere;

  /// No description provided for @pointOnMap.
  ///
  /// In fr, this message translates to:
  /// **'Point sur la carte'**
  String get pointOnMap;

  /// No description provided for @details.
  ///
  /// In fr, this message translates to:
  /// **'Détails'**
  String get details;

  /// No description provided for @showList.
  ///
  /// In fr, this message translates to:
  /// **'Liste'**
  String get showList;

  /// No description provided for @youArrive.
  ///
  /// In fr, this message translates to:
  /// **'Vous êtes arrivé'**
  String get youArrive;

  /// No description provided for @departures.
  ///
  /// In fr, this message translates to:
  /// **'Départs'**
  String get departures;

  /// No description provided for @goThere.
  ///
  /// In fr, this message translates to:
  /// **'Y aller'**
  String get goThere;

  /// No description provided for @nearStop.
  ///
  /// In fr, this message translates to:
  /// **'Près de {name} · {min} min à pied'**
  String nearStop(String name, int min);

  /// No description provided for @noRouteBody.
  ///
  /// In fr, this message translates to:
  /// **'Essayez une autre heure, ou un départ plus proche d\'une gare ou d\'un arrêt.'**
  String get noRouteBody;

  /// No description provided for @noServiceNow.
  ///
  /// In fr, this message translates to:
  /// **'Plus de transport à cette heure-ci.'**
  String get noServiceNow;

  /// No description provided for @firstDeparturesFrom.
  ///
  /// In fr, this message translates to:
  /// **'Plus de transport à cette heure-ci : voici les premiers départs, dès {time}.'**
  String firstDeparturesFrom(String time);

  /// No description provided for @previousStep.
  ///
  /// In fr, this message translates to:
  /// **'Étape précédente'**
  String get previousStep;

  /// No description provided for @nextStep.
  ///
  /// In fr, this message translates to:
  /// **'Étape suivante'**
  String get nextStep;

  /// No description provided for @louagesFromHere.
  ///
  /// In fr, this message translates to:
  /// **'Louages au départ d\'ici'**
  String get louagesFromHere;
}

class _LDelegate extends LocalizationsDelegate<L> {
  const _LDelegate();

  @override
  Future<L> load(Locale locale) {
    return SynchronousFuture<L>(lookupL(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'fr'].contains(locale.languageCode);

  @override
  bool shouldReload(_LDelegate old) => false;
}

L lookupL(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return LAr();
    case 'fr':
      return LFr();
  }

  throw FlutterError(
    'L.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
