import 'package:flutter/widgets.dart';

import '../l10n/app_localizations.dart';
import 'models.dart';

/// Formats affichés (specs/08-i18n-fr-ar.md §3) : chiffres occidentaux, heures sur 24 h, prix en dinars.
class Fmt {
  Fmt(this.l);
  final L l;

  static Fmt of(BuildContext context) => Fmt(L.of(context));

  String time(DateTime t) => '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  String duration(int minutes) {
    if (minutes < 60) return l.minutesShort(minutes);
    return l.hoursMinutes(minutes ~/ 60, (minutes % 60).toString().padLeft(2, '0'));
  }

  /// « 1,500 DT » à partir des millimes ; « Prix inconnu » si le tarif n'est pas saisi.
  String price(Price p) {
    if (!p.known) return l.priceUnknown;
    final dinars = p.millimes! ~/ 1000;
    final mill = (p.millimes! % 1000).toString().padLeft(3, '0');
    return '${p.estimated ? '~' : ''}${l.price('$dinars,$mill')}';
  }

  /// « dans 4 min », « maintenant », ou l'heure au-delà d'une heure.
  String countdown(DateTime t, DateTime now) {
    final minutes = t.difference(now).inSeconds / 60;
    if (minutes < 0.75) return l.now;
    if (minutes < 60) return l.inMinutes(minutes.ceil());
    return time(t);
  }

  String departure(Departure d, DateTime now) {
    if (d.isFrequency) return d.headwayMin == null ? l.departsWhenFull : l.everyMinutes(d.headwayMin!);
    return countdown(d.time!, now);
  }
}
