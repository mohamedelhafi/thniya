import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/models.dart';
import '../../core/state.dart';
import '../../design/components/badges.dart';
import '../../design/components/feedback.dart';
import '../../design/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../home/home_screen.dart';
import '../results/results_screen.dart';

enum SavedSlot { home, work }

class SearchArgs {
  const SearchArgs({this.pickFor, this.from, this.to});
  final SavedSlot? pickFor;
  final Place? from;
  final Place? to;
}

/// Recherche départ / arrivée (specs/07 §5.2) : suggestions dès 2 caractères, anti-rebond 250 ms.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key, required this.args});
  final SearchArgs args;

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

enum _Field { from, to }

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _fromCtrl = TextEditingController();
  final _toCtrl = TextEditingController();
  final _fromFocus = FocusNode();
  final _toFocus = FocusNode();
  Place? _from;
  Place? _to;
  _Field _active = _Field.to;
  List<Place> _results = const [];
  bool _loading = false;
  String? _searched; // dernière requête dont la réponse est arrivée
  Timer? _debounce;
  int _requestId = 0;

  @override
  void initState() {
    super.initState();
    _from = widget.args.from;
    _to = widget.args.to;
    _fromFocus.addListener(() => _fromFocus.hasFocus ? _focus(_Field.from) : null);
    _toFocus.addListener(() => _toFocus.hasFocus ? _focus(_Field.to) : null);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _from ??= myLocationPlace(context, ref.read(locationProvider).position);
      _fromCtrl.text = _from!.name;
      if (_to != null) _toCtrl.text = _to!.name;
      _toFocus.requestFocus();
      setState(() {});
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _fromCtrl.dispose();
    _toCtrl.dispose();
    _fromFocus.dispose();
    _toFocus.dispose();
    super.dispose();
  }

  void _focus(_Field f) => setState(() {
        _active = f;
        _results = const [];
      });

  void _onChanged(String q) {
    _debounce?.cancel();
    if (q.trim().length < 2) {
      setState(() => _results = const []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 250), () async {
      final id = ++_requestId;
      setState(() => _loading = true);
      final pos = ref.read(locationProvider).position;
      try {
        final r = await ref.read(apiProvider).geocode(q.trim(), lat: pos.latitude, lon: pos.longitude);
        if (mounted && id == _requestId) setState(() {
          _results = r;
          _searched = q.trim();
        });
      } catch (_) {
        if (mounted && id == _requestId) setState(() => _results = const []);
      } finally {
        if (mounted && id == _requestId) setState(() => _loading = false);
      }
    });
  }

  void _select(Place p) {
    HapticFeedback.selectionClick();
    final saved = ref.read(savedPlacesProvider.notifier);
    if (widget.args.pickFor != null) {
      widget.args.pickFor == SavedSlot.home ? saved.setHome(p) : saved.setWork(p);
      context.pop();
      return;
    }
    saved.addRecent(p);
    if (_active == _Field.from) {
      _from = p;
      _fromCtrl.text = p.name;
      _toFocus.requestFocus();
    } else {
      _to = p;
      _toCtrl.text = p.name;
    }
    setState(() => _results = const []);
    if (_from != null && _to != null) {
      context.pushReplacement('/results', extra: ResultsArgs(from: _from!, to: _to!));
    }
  }

  void _swap() {
    HapticFeedback.lightImpact();
    setState(() {
      final f = _from;
      _from = _to;
      _to = f;
      _fromCtrl.text = _from?.name ?? '';
      _toCtrl.text = _to?.name ?? '';
    });
    if (_from != null && _to != null) {
      context.pushReplacement('/results', extra: ResultsArgs(from: _from!, to: _to!));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final c = context.colors;
    final saved = ref.watch(savedPlacesProvider);
    final query = (_active == _Field.from ? _fromCtrl : _toCtrl).text.trim();
    final picking = widget.args.pickFor != null;

    return Scaffold(
      backgroundColor: c.surface,
      body: SafeArea(
        child: Column(children: [
          // En-tête : deux champs reliés par une petite frise, bouton d'inversion
          Padding(
            padding: const EdgeInsets.fromLTRB(Space.xs, Space.s, Space.l, Space.m),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              IconButton(
                onPressed: () => context.pop(),
                icon: Icon(context.isRtl ? Symbols.arrow_forward : Symbols.arrow_back),
              ),
              if (!picking)
                Padding(
                  padding: const EdgeInsets.only(top: 18),
                  child: Column(children: [
                    Icon(Symbols.radio_button_checked, size: 14, color: c.brand, fill: 1),
                    for (var i = 0; i < 4; i++)
                      Container(margin: const EdgeInsets.symmetric(vertical: 2), width: 2, height: 4, color: c.divider),
                    Icon(Symbols.location_on, size: 16, color: c.danger, fill: 1),
                  ]),
                ),
              const SizedBox(width: Space.s),
              Expanded(
                child: Column(children: [
                  if (!picking) ...[
                    _Field2(
                      controller: _fromCtrl,
                      focus: _fromFocus,
                      hint: l.from,
                      onChanged: _onChanged,
                    ),
                    const SizedBox(height: Space.s),
                  ],
                  _Field2(controller: _toCtrl, focus: _toFocus, hint: picking ? l.searchHint : l.to, onChanged: _onChanged),
                ]),
              ),
              if (!picking)
                Padding(
                  padding: const EdgeInsets.only(top: 22),
                  child: IconButton(
                    tooltip: l.swap,
                    onPressed: _swap,
                    icon: Icon(Symbols.swap_vert, color: c.textSecondary),
                  ),
                ),
            ]),
          ),
          AnimatedContainer(
            duration: Motion.fast,
            height: 2,
            child: _loading ? LinearProgressIndicator(minHeight: 2, color: c.brand, backgroundColor: c.brandSoft) : null,
          ),
          Divider(color: c.divider),
          Expanded(
            child: ListView(padding: const EdgeInsets.only(bottom: Space.xxl), children: [
              if (query.length < 2) ...[
                if (_active == _Field.from && !picking)
                  _PlaceTile(
                    icon: Symbols.my_location,
                    iconColor: c.brand,
                    title: l.myLocation,
                    onTap: () => _select(myLocationPlace(context, ref.read(locationProvider).position)),
                  ),
                if (!picking && saved.home != null)
                  _PlaceTile(icon: Symbols.home, iconColor: c.brand, title: l.home, subtitle: saved.home!.name,
                      onTap: () => _select(saved.home!)),
                if (!picking && saved.work != null)
                  _PlaceTile(icon: Symbols.work, iconColor: c.brand, title: l.work, subtitle: saved.work!.name,
                      onTap: () => _select(saved.work!)),
                if (saved.recents.isNotEmpty) ...[
                  _SectionTitle(l.recent),
                  for (final p in saved.recents)
                    _PlaceTile(icon: Symbols.history, title: p.name, subtitle: p.area, onTap: () => _select(p)),
                ],
              ] else if (_results.isEmpty && !_loading && _searched == query)
                MessageState(icon: Symbols.search_off, title: l.noResults)
              else if (_results.isEmpty)
                const SizedBox.shrink()
              else ...[
                // Nos arrêts d'abord, puis les adresses et lieux OSM (Photon), chacun sous son titre
                if (_results.any((r) => r.type == 'STOP')) _SectionTitle(l.stopsAndStations),
                for (final p in _results.where((r) => r.type == 'STOP')) _resultTile(c, p, query),
                if (_results.any((r) => r.type != 'STOP')) _SectionTitle(l.addressesAndPlaces),
                for (final p in _results.where((r) => r.type != 'STOP')) _resultTile(c, p, query),
              ],
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _resultTile(ThniyaColors c, Place p, String query) => _PlaceTile(
        icon: p.modes.isEmpty ? Symbols.location_on : modeIconData(p.modes.first),
        iconColor: p.modes.isEmpty ? c.textSecondary : modeColor(context, p.modes.first),
        title: p.name,
        subtitle: p.area,
        trailing: p.distanceM == null ? null : _distance(p.distanceM!),
        badges: p.lines,
        query: query,
        onTap: () => _select(p),
      );

  String _distance(int m) => m < 1000 ? '$m m' : '${(m / 1000).toStringAsFixed(1)} km';
}

class _Field2 extends StatelessWidget {
  const _Field2({required this.controller, required this.focus, required this.hint, required this.onChanged});
  final TextEditingController controller;
  final FocusNode focus;
  final String hint;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) => TextField(
        controller: controller,
        focusNode: focus,
        onChanged: onChanged,
        onTap: () => controller.selection = TextSelection(baseOffset: 0, extentOffset: controller.text.length),
        textInputAction: TextInputAction.search,
        style: context.text.bodyLarge,
        decoration: InputDecoration(
          hintText: hint,
          isDense: true,
          suffixIcon: ListenableBuilder(
            listenable: controller,
            builder: (_, _) => controller.text.isEmpty || !focus.hasFocus
                ? const SizedBox.shrink()
                : IconButton(
                    icon: const Icon(Symbols.close, size: 18),
                    onPressed: () {
                      controller.clear();
                      onChanged('');
                    },
                  ),
          ),
        ),
      );
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(Space.l, Space.l, Space.l, Space.xs),
        child: Text(text.toUpperCase(), style: context.text.labelSmall?.copyWith(letterSpacing: .8)),
      );
}

class _PlaceTile extends StatelessWidget {
  const _PlaceTile({
    required this.icon,
    this.iconColor,
    required this.title,
    this.subtitle,
    this.trailing,
    this.badges = const [],
    this.query,
    required this.onTap,
  });
  final IconData icon;
  final Color? iconColor;
  final String title;
  final String? subtitle;
  final String? trailing;
  final List<LineRef> badges;
  final String? query;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: Space.l, vertical: Space.m),
        child: Row(children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: (iconColor ?? c.textSecondary).withValues(alpha: .12), shape: BoxShape.circle),
            child: Icon(icon, size: 20, color: iconColor ?? c.textSecondary, fill: 1),
          ),
          const SizedBox(width: Space.m),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              _Highlighted(title, query, context.text.titleMedium!),
              if (subtitle != null || badges.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 3),
                  child: Row(children: [
                    if (subtitle != null)
                      Flexible(child: Text(subtitle!, style: context.text.bodySmall, overflow: TextOverflow.ellipsis)),
                    for (final b in badges.take(4)) ...[
                      const SizedBox(width: 6),
                      LineBadge(b, compact: true, showIcon: false),
                    ],
                  ]),
                ),
            ]),
          ),
          if (trailing != null) Text(trailing!, style: context.text.labelSmall),
        ]),
      ),
    );
  }
}

/// Met en gras la partie saisie, comme dans les bonnes listes de suggestions.
class _Highlighted extends StatelessWidget {
  const _Highlighted(this.text, this.query, this.style);
  final String text;
  final String? query;
  final TextStyle style;

  @override
  Widget build(BuildContext context) {
    final q = query?.toLowerCase() ?? '';
    final i = q.isEmpty ? -1 : text.toLowerCase().indexOf(q);
    if (i < 0) return Text(text, style: style);
    final light = style.copyWith(color: context.colors.textSecondary);
    return Text.rich(TextSpan(children: [
      TextSpan(text: text.substring(0, i), style: light),
      TextSpan(text: text.substring(i, i + q.length), style: style),
      TextSpan(text: text.substring(i + q.length), style: light),
    ]));
  }
}
