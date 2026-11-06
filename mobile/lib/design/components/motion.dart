import 'package:flutter/material.dart';

import '../tokens.dart';

/// Apparition en douceur (fondu + léger glissement vers le haut), décalée selon [index] pour une cascade
/// lisible dans les listes (specs/13 §6). Ne rejoue pas l'animation quand le widget est reconstruit.
class Appear extends StatefulWidget {
  const Appear({super.key, required this.child, this.index = 0, this.step = const Duration(milliseconds: 45)});
  final Widget child;
  final int index;
  final Duration step;

  @override
  State<Appear> createState() => _AppearState();
}

class _AppearState extends State<Appear> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: Motion.slow);
  late final _curve = CurvedAnimation(parent: _c, curve: Motion.enter);

  @override
  void initState() {
    super.initState();
    final delay = widget.step * widget.index.clamp(0, 8);
    if (delay == Duration.zero) {
      _c.forward();
    } else {
      Future.delayed(delay, () {
        if (mounted) _c.forward();
      });
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FadeTransition(
    opacity: _curve,
    child: SlideTransition(
      position: Tween(begin: const Offset(0, .08), end: Offset.zero).animate(_curve),
      child: widget.child,
    ),
  );
}
