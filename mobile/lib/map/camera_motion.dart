import 'dart:math' as math;

import 'package:flutter/widgets.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../design/tokens.dart';

/// Mouvements de caméra animés (specs/13 §6) : la carte « vole » d'un cadrage à l'autre au lieu de sauter.
///
/// Pour un grand déplacement, elle dézoome un peu à mi-course puis rezoome, comme un survol : l'œil garde le fil.
class CameraMotion {
  CameraMotion(this._vsync, this.controller);

  final TickerProvider _vsync;
  final MapController controller;
  AnimationController? _anim;

  bool get isAnimating => _anim?.isAnimating ?? false;

  /// Cadre [points] dans la zone visible, c'est-à-dire l'écran moins [padding] (feuille, barre du haut…).
  void fitPoints(List<LatLng> points, EdgeInsets padding, {double maxZoom = 17, Duration? duration}) {
    if (points.isEmpty) return;
    if (points.length == 1 || _degenerate(points)) {
      focusPoint(points.first, padding, zoom: maxZoom.clamp(0, 16.5), duration: duration);
      return;
    }
    final MapCamera target;
    try {
      target = CameraFit.bounds(
        bounds: LatLngBounds.fromPoints(points),
        padding: padding,
        maxZoom: maxZoom,
      ).fit(controller.camera);
    } catch (_) {
      return; // carte pas encore dimensionnée
    }
    flyTo(target.center, target.zoom, duration: duration);
  }

  /// Centre [point] au milieu de la zone visible (et non de l'écran) au zoom [zoom].
  void focusPoint(LatLng point, EdgeInsets padding, {double zoom = 16, Duration? duration}) {
    final MapCamera cam;
    try {
      cam = controller.camera;
    } catch (_) {
      return;
    }
    // Décalage du centre : la zone visible n'est pas centrée sur l'écran quand une feuille la recouvre
    final atZoom = cam.withPosition(center: point, zoom: zoom);
    final offset = Offset((padding.right - padding.left) / 2, (padding.bottom - padding.top) / 2);
    final projected = atZoom.project(point) + math.Point<double>(offset.dx, offset.dy);
    flyTo(atZoom.unproject(projected), zoom, duration: duration);
  }

  void flyTo(LatLng center, double zoom, {Duration? duration}) {
    final MapCamera start;
    try {
      start = controller.camera;
    } catch (_) {
      return;
    }
    _anim?.dispose();
    // Distance en pixels au zoom de départ : au-delà d'un écran, on dézoome à mi-course
    final a = start.project(start.center), b = start.project(center);
    final pixels = math.sqrt(math.pow(a.x - b.x, 2) + math.pow(a.y - b.y, 2));
    final screen = math.max(start.nonRotatedSize.x, 1);
    final dip = pixels > screen ? math.min(2.0, math.log(pixels / screen) / math.ln2 + .5) : 0.0;
    final ms = duration?.inMilliseconds ?? (Motion.camera.inMilliseconds + (dip * 120).round());

    final anim = _anim = AnimationController(
      vsync: _vsync,
      duration: Duration(milliseconds: ms),
    );
    final curve = CurvedAnimation(parent: anim, curve: Motion.change);
    anim.addListener(() {
      final t = curve.value;
      final lat = start.center.latitude + (center.latitude - start.center.latitude) * t;
      final lon = start.center.longitude + (center.longitude - start.center.longitude) * t;
      final z = start.zoom + (zoom - start.zoom) * t - dip * math.sin(math.pi * t);
      controller.move(LatLng(lat, lon), z);
    });
    anim.forward();
  }

  void stop() => _anim?.stop();

  void dispose() => _anim?.dispose();

  static bool _degenerate(List<LatLng> pts) {
    final f = pts.first;
    return pts.every((p) => (p.latitude - f.latitude).abs() < 1e-5 && (p.longitude - f.longitude).abs() < 1e-5);
  }
}
