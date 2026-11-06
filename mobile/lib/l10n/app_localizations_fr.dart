// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class LFr extends L {
  LFr([String locale = 'fr']) : super(locale);

  @override
  String get appName => 'Thniya';

  @override
  String get whereTo => 'Où allez-vous ?';

  @override
  String get home => 'Maison';

  @override
  String get work => 'Travail';

  @override
  String get setHome => 'Définir';

  @override
  String get lines => 'Lignes';

  @override
  String get nearby => 'À proximité';

  @override
  String get all => 'Tout';

  @override
  String get myLocation => 'Ma position';

  @override
  String get from => 'Départ';

  @override
  String get to => 'Arrivée';

  @override
  String get searchHint => 'Gare, arrêt, adresse, lieu…';

  @override
  String get stopsAndStations => 'Arrêts et stations';

  @override
  String get addressesAndPlaces => 'Adresses et lieux';

  @override
  String get recent => 'Récents';

  @override
  String get chooseOnMap => 'Choisir sur la carte';

  @override
  String get leaveNow => 'Partir maintenant';

  @override
  String departAt(String time) {
    return 'Partir à $time';
  }

  @override
  String arriveBy(String time) {
    return 'Arriver avant $time';
  }

  @override
  String minutesShort(int n) {
    return '$n min';
  }

  @override
  String hoursMinutes(int h, String m) {
    return '$h h $m';
  }

  @override
  String inMinutes(int n) {
    return 'dans $n min';
  }

  @override
  String get now => 'maintenant';

  @override
  String arrival(String time) {
    return 'Arrivée $time';
  }

  @override
  String walkMinutes(int n) {
    return '$n min à pied';
  }

  @override
  String get priceUnknown => 'Prix inconnu';

  @override
  String price(String amount) {
    return '$amount DT';
  }

  @override
  String everyMinutes(int n) {
    return '~toutes les $n min';
  }

  @override
  String get departsWhenFull => 'Part quand il est plein';

  @override
  String transfers(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n correspondances',
      one: '1 correspondance',
      zero: 'Direct',
    );
    return '$_temp0';
  }

  @override
  String stopsCount(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n arrêts',
      one: '1 arrêt',
      zero: 'Sans arrêt',
    );
    return '$_temp0';
  }

  @override
  String walkTo(String place) {
    return 'Marchez jusqu\'à $place';
  }

  @override
  String walkDistance(int min, int meters) {
    return '$min min · $meters m';
  }

  @override
  String towards(String place) {
    return 'vers $place';
  }

  @override
  String getOffAt(String place) {
    return 'Descendez à $place';
  }

  @override
  String get board => 'Montez';

  @override
  String get otherDepartures => 'Autres départs';

  @override
  String arriveAt(String place) {
    return 'Arrivée à $place';
  }

  @override
  String get save => 'Enregistrer';

  @override
  String get share => 'Partager';

  @override
  String get reportProblem => 'Signaler';

  @override
  String get noTransitHere => 'Pas encore de transports ici';

  @override
  String get noTransitHereBody =>
      'Thniya couvre pour l\'instant la banlieue sud de Tunis. Voici l\'itinéraire à pied.';

  @override
  String get loadingError => 'Impossible de charger';

  @override
  String get retry => 'Réessayer';

  @override
  String get offline => 'Pas de connexion';

  @override
  String get tooManyRequests => 'Trop de demandes, réessayez dans un instant';

  @override
  String get serviceUnavailable => 'Service momentanément indisponible';

  @override
  String get noRoute => 'Aucun itinéraire trouvé';

  @override
  String get direction => 'Direction';

  @override
  String get stops => 'Arrêts';

  @override
  String get timetable => 'Horaires';

  @override
  String get today => 'Aujourd\'hui';

  @override
  String get tomorrow => 'Demain';

  @override
  String get saturday => 'Samedi';

  @override
  String get sunday => 'Dimanche';

  @override
  String departuresCount(int n) {
    return '$n départs';
  }

  @override
  String firstLast(String first, String last) {
    return 'Premier $first · Dernier $last';
  }

  @override
  String get noServiceToday => 'Pas de départ aujourd\'hui';

  @override
  String nextService(String when) {
    return 'Prochain : $when';
  }

  @override
  String get nextDepartures => 'Prochains départs';

  @override
  String usualTimetableNotice(String period) {
    return 'Horaires de $period non publiés : horaires habituels affichés';
  }

  @override
  String get settings => 'Réglages';

  @override
  String get language => 'Langue';

  @override
  String get theme => 'Thème';

  @override
  String get themeSystem => 'Système';

  @override
  String get themeLight => 'Clair';

  @override
  String get themeDark => 'Sombre';

  @override
  String get aboutData => 'À propos des données';

  @override
  String dataVersion(String v) {
    return 'Version des données : $v';
  }

  @override
  String get dataSources =>
      'Sources : data.transport.tn (Transtu, SNTRI, ministère du Transport), sites de la SNCFT, de la Transtu et de la SNTRI, OpenStreetMap (ODbL), Protomaps. Les horaires Transtu sont estimés. Application indépendante et non officielle : en cas de doute, vérifiez auprès de l\'opérateur.';

  @override
  String get officialTimes => 'Horaires officiels';

  @override
  String get estimatedTimes => 'Horaires estimés';

  @override
  String get suggestions => 'Suggestions';

  @override
  String get seeLine => 'Voir la ligne';

  @override
  String get seeStop => 'Voir l\'arrêt';

  @override
  String get allLines => 'Toutes les lignes';

  @override
  String get noNearby => 'Aucun arrêt à distance de marche';

  @override
  String get locating => 'Recherche de votre position…';

  @override
  String get goHome => 'Rentrer';

  @override
  String holiday(String name) {
    return 'Jour férié : $name';
  }

  @override
  String get feedbackSent => 'Merci ! Votre signalement a été envoyé.';

  @override
  String get feedbackPrompt => 'Qu\'est-ce qui ne va pas ?';

  @override
  String get send => 'Envoyer';

  @override
  String get cancel => 'Annuler';

  @override
  String get swap => 'Inverser';

  @override
  String get earlier => 'Plus tôt';

  @override
  String get later => 'Plus tard';

  @override
  String get walk => 'Marche';

  @override
  String get change => 'Changement';

  @override
  String get routeHere => 'Itinéraire vers ici';

  @override
  String platform(String code) {
    return 'Voie $code';
  }

  @override
  String get minUnit => 'min';

  @override
  String get hourUnit => 'h';

  @override
  String get noResults => 'Aucun résultat';

  @override
  String boardAt(String place) {
    return 'Montez à $place';
  }

  @override
  String stepOf(int n, int total) {
    return 'Étape $n sur $total';
  }

  @override
  String get overview => 'Vue d\'ensemble';

  @override
  String get tapLegHint => 'Touchez une étape pour la voir sur la carte';

  @override
  String get boarding => 'Montée';

  @override
  String get alighting => 'Descente';

  @override
  String get routeFromHere => 'Partir d\'ici';

  @override
  String get pointOnMap => 'Point sur la carte';

  @override
  String get details => 'Détails';

  @override
  String get showList => 'Liste';

  @override
  String get youArrive => 'Vous êtes arrivé';

  @override
  String get departures => 'Départs';

  @override
  String get goThere => 'Y aller';

  @override
  String nearStop(String name, int min) {
    return 'Près de $name · $min min à pied';
  }

  @override
  String get noRouteBody =>
      'Essayez une autre heure, ou un départ plus proche d\'une gare ou d\'un arrêt.';

  @override
  String get noServiceNow => 'Plus de transport à cette heure-ci.';

  @override
  String firstDeparturesFrom(String time) {
    return 'Plus de transport à cette heure-ci : voici les premiers départs, dès $time.';
  }

  @override
  String get previousStep => 'Étape précédente';

  @override
  String get nextStep => 'Étape suivante';

  @override
  String get louagesFromHere => 'Louages au départ d\'ici';
}
