// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class LAr extends L {
  LAr([String locale = 'ar']) : super(locale);

  @override
  String get appName => 'ثنية';

  @override
  String get whereTo => 'إلى أين؟';

  @override
  String get home => 'الدار';

  @override
  String get work => 'الخدمة';

  @override
  String get setHome => 'حدّد';

  @override
  String get lines => 'الخطوط';

  @override
  String get nearby => 'بالقرب منك';

  @override
  String get all => 'الكل';

  @override
  String get myLocation => 'موقعي';

  @override
  String get from => 'الانطلاق';

  @override
  String get to => 'الوصول';

  @override
  String get searchHint => 'محطة، موقف، عنوان، مكان…';

  @override
  String get stopsAndStations => 'المحطات والمواقف';

  @override
  String get addressesAndPlaces => 'العناوين والأماكن';

  @override
  String get recent => 'الأخيرة';

  @override
  String get chooseOnMap => 'اختر على الخريطة';

  @override
  String get leaveNow => 'انطلق الآن';

  @override
  String departAt(String time) {
    return 'انطلاق على $time';
  }

  @override
  String arriveBy(String time) {
    return 'وصول قبل $time';
  }

  @override
  String minutesShort(int n) {
    return '$n د';
  }

  @override
  String hoursMinutes(int h, String m) {
    return '$h س $m د';
  }

  @override
  String inMinutes(int n) {
    return 'بعد $n د';
  }

  @override
  String get now => 'الآن';

  @override
  String arrival(String time) {
    return 'الوصول $time';
  }

  @override
  String walkMinutes(int n) {
    return '$n د مشيًا';
  }

  @override
  String get priceUnknown => 'السعر غير معروف';

  @override
  String price(String amount) {
    return '$amount د.ت';
  }

  @override
  String everyMinutes(int n) {
    return 'كل ~$n د تقريبًا';
  }

  @override
  String get departsWhenFull => 'ينطلق عندما يمتلئ';

  @override
  String transfers(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n تغيير',
      many: '$n تغييرًا',
      few: '$n تغييرات',
      two: 'تغييران',
      one: 'تغيير واحد',
      zero: 'مباشر',
    );
    return '$_temp0';
  }

  @override
  String stopsCount(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n محطة',
      many: '$n محطة',
      few: '$n محطات',
      two: 'محطتان',
      one: 'محطة واحدة',
      zero: 'دون توقف',
    );
    return '$_temp0';
  }

  @override
  String walkTo(String place) {
    return 'امشِ إلى $place';
  }

  @override
  String walkDistance(int min, int meters) {
    return '$min د · $meters م';
  }

  @override
  String towards(String place) {
    return 'باتجاه $place';
  }

  @override
  String getOffAt(String place) {
    return 'انزل في $place';
  }

  @override
  String get board => 'اركب';

  @override
  String get otherDepartures => 'انطلاقات أخرى';

  @override
  String arriveAt(String place) {
    return 'الوصول إلى $place';
  }

  @override
  String get save => 'حفظ';

  @override
  String get share => 'مشاركة';

  @override
  String get reportProblem => 'إبلاغ';

  @override
  String get noTransitHere => 'لا توجد وسائل نقل هنا بعد';

  @override
  String get noTransitHereBody =>
      'تغطي ثنية حاليًا الضاحية الجنوبية لتونس. إليك المسار مشيًا.';

  @override
  String get loadingError => 'تعذّر التحميل';

  @override
  String get retry => 'أعد المحاولة';

  @override
  String get offline => 'لا يوجد اتصال';

  @override
  String get tooManyRequests => 'طلبات كثيرة، أعد المحاولة بعد قليل';

  @override
  String get serviceUnavailable => 'الخدمة غير متوفرة حاليًا';

  @override
  String get noRoute => 'لم نجد أي مسار';

  @override
  String get direction => 'الاتجاه';

  @override
  String get stops => 'المحطات';

  @override
  String get timetable => 'التوقيت';

  @override
  String get today => 'اليوم';

  @override
  String get tomorrow => 'غدًا';

  @override
  String get saturday => 'السبت';

  @override
  String get sunday => 'الأحد';

  @override
  String departuresCount(int n) {
    return '$n انطلاقة';
  }

  @override
  String firstLast(String first, String last) {
    return 'الأولى $first · الأخيرة $last';
  }

  @override
  String get noServiceToday => 'لا انطلاقات اليوم';

  @override
  String nextService(String when) {
    return 'القادمة: $when';
  }

  @override
  String get nextDepartures => 'الانطلاقات القادمة';

  @override
  String usualTimetableNotice(String period) {
    return 'توقيت $period لم يُنشر بعد: نعرض التوقيت المعتاد';
  }

  @override
  String get settings => 'الإعدادات';

  @override
  String get language => 'اللغة';

  @override
  String get theme => 'المظهر';

  @override
  String get themeSystem => 'النظام';

  @override
  String get themeLight => 'فاتح';

  @override
  String get themeDark => 'داكن';

  @override
  String get aboutData => 'حول البيانات';

  @override
  String dataVersion(String v) {
    return 'نسخة البيانات: $v';
  }

  @override
  String get dataSources =>
      'المصادر: data.transport.tn (شركة نقل تونس، الشركة الوطنية للنقل بين المدن، وزارة النقل)، مواقع الشركة الوطنية للسكك الحديدية وشركة نقل تونس والشركة الوطنية للنقل بين المدن، OpenStreetMap (ODbL)، Protomaps. أوقات شركة نقل تونس تقديرية. تطبيق مستقل وغير رسمي: عند الشك، يُرجى التحقق لدى الناقل.';

  @override
  String get officialTimes => 'توقيت رسمي';

  @override
  String get estimatedTimes => 'توقيت تقريبي';

  @override
  String get suggestions => 'اقتراحات';

  @override
  String get seeLine => 'عرض الخط';

  @override
  String get seeStop => 'عرض المحطة';

  @override
  String get allLines => 'كل الخطوط';

  @override
  String get noNearby => 'لا توجد محطة قريبة مشيًا';

  @override
  String get locating => 'نبحث عن موقعك…';

  @override
  String get goHome => 'روّح';

  @override
  String holiday(String name) {
    return 'يوم عطلة: $name';
  }

  @override
  String get feedbackSent => 'شكرًا! تم إرسال بلاغك.';

  @override
  String get feedbackPrompt => 'ما المشكلة؟';

  @override
  String get send => 'إرسال';

  @override
  String get cancel => 'إلغاء';

  @override
  String get swap => 'عكس';

  @override
  String get earlier => 'قبل';

  @override
  String get later => 'بعد';

  @override
  String get walk => 'مشي';

  @override
  String get change => 'تغيير';

  @override
  String get routeHere => 'المسار إلى هنا';

  @override
  String platform(String code) {
    return 'السكة $code';
  }

  @override
  String get minUnit => 'د';

  @override
  String get hourUnit => 'س';

  @override
  String get noResults => 'لا توجد نتائج';

  @override
  String boardAt(String place) {
    return 'اركب في $place';
  }

  @override
  String stepOf(int n, int total) {
    return 'المرحلة $n من $total';
  }

  @override
  String get overview => 'نظرة عامة';

  @override
  String get tapLegHint => 'المس مرحلة لرؤيتها على الخريطة';

  @override
  String get boarding => 'الركوب';

  @override
  String get alighting => 'النزول';

  @override
  String get routeFromHere => 'الانطلاق من هنا';

  @override
  String get pointOnMap => 'نقطة على الخريطة';

  @override
  String get details => 'التفاصيل';

  @override
  String get showList => 'القائمة';

  @override
  String get youArrive => 'وصلت';

  @override
  String get departures => 'الانطلاقات';

  @override
  String get goThere => 'اذهب إلى هناك';

  @override
  String nearStop(String name, int min) {
    return 'قرب $name · $min د مشيًا';
  }

  @override
  String get noRouteBody => 'جرّب وقتًا آخر، أو نقطة انطلاق أقرب إلى محطة.';

  @override
  String get noServiceNow => 'لا توجد وسائل نقل في هذا الوقت.';

  @override
  String firstDeparturesFrom(String time) {
    return 'لا توجد وسائل نقل في هذا الوقت: إليك أولى الانطلاقات ابتداءً من $time.';
  }

  @override
  String get previousStep => 'المرحلة السابقة';

  @override
  String get nextStep => 'المرحلة التالية';

  @override
  String get louagesFromHere => 'اللواج من هنا';
}
