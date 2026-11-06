import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/models.dart';
import '../core/state.dart';
import '../design/theme.dart';
import '../features/home/home_screen.dart';
import '../features/line/line_screen.dart';
import '../features/lines/lines_screen.dart';
import '../features/results/results_screen.dart';
import '../features/search/search_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/stop/stop_screen.dart';
import '../features/trip/trip_screen.dart';
import '../l10n/app_localizations.dart';

/// Transition douce et rapide entre écrans (specs/13 §6) : fondu + léger glissement.
CustomTransitionPage<void> _page(GoRouterState state, Widget child) => CustomTransitionPage(
      key: state.pageKey,
      child: child,
      transitionDuration: const Duration(milliseconds: 280),
      reverseTransitionDuration: const Duration(milliseconds: 220),
      transitionsBuilder: (context, animation, secondary, child) {
        final curved = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
        return FadeTransition(
          opacity: curved,
          child: SlideTransition(
            position: Tween(begin: const Offset(0, 0.04), end: Offset.zero).animate(curved),
            child: child,
          ),
        );
      },
    );

final routerProvider = Provider<GoRouter>((ref) => GoRouter(
      routes: [
        GoRoute(path: '/', pageBuilder: (c, s) => _page(s, const HomeScreen())),
        GoRoute(
          path: '/search',
          pageBuilder: (c, s) => _page(s, SearchScreen(args: s.extra as SearchArgs? ?? const SearchArgs())),
        ),
        GoRoute(
          path: '/results',
          redirect: (c, s) => s.extra == null && ResultsArgs.fromUri(s.uri) == null ? '/' : null,
          pageBuilder: (c, s) =>
              _page(s, ResultsScreen(args: s.extra as ResultsArgs? ?? ResultsArgs.fromUri(s.uri)!)),
        ),
        GoRoute(path: '/trip', pageBuilder: (c, s) => _page(s, TripScreen(itinerary: s.extra! as Itinerary))),
        GoRoute(
          path: '/line/:id',
          pageBuilder: (c, s) => _page(s, LineScreen(lineId: s.pathParameters['id']!, focusStop: s.uri.queryParameters['stop'])),
        ),
        GoRoute(path: '/stop/:id', pageBuilder: (c, s) => _page(s, StopScreen(stopId: s.pathParameters['id']!))),
        GoRoute(path: '/lines', pageBuilder: (c, s) => _page(s, const LinesScreen())),
        GoRoute(path: '/settings', pageBuilder: (c, s) => _page(s, const SettingsScreen())),
      ],
    ));

class ThniyaApp extends ConsumerWidget {
  const ThniyaApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locale = ref.watch(localeProvider);
    return MaterialApp.router(
      title: 'Thniya',
      debugShowCheckedModeBanner: false,
      // Glisser au doigt, à la souris et au pavé tactile : feuilles, cartes d'étape et listes (version web incluse)
      scrollBehavior: const MaterialScrollBehavior().copyWith(dragDevices: PointerDeviceKind.values.toSet()),
      routerConfig: ref.watch(routerProvider),
      locale: locale,
      supportedLocales: L.supportedLocales,
      localizationsDelegates: const [
        L.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: ref.watch(themeModeProvider),
    );
  }
}
