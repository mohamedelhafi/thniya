import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show kIsWeb;

import '../extensions.dart';
import 'byte_storage.dart';
import 'cache_stats.dart';

class StorageCache with CacheStats {
  final ByteStorage _storage;
  final Duration _ttl;
  final int _maxSizeInBytes;
  int _putCount = 0;

  StorageCache(this._storage, this._ttl, this._maxSizeInBytes);

  Future<void> remove(String key) async {
    if (kIsWeb) {
      _web.remove(key);
      return;
    }
    await _storage.delete(key);
  }

  Future<Uint8List?> retrieve(String key) async {
    if (kIsWeb) {
      final bytes = _web[key];
      bytes == null ? cacheMiss() : cacheHit();
      return bytes;
    }
    try {
      final bytes = await _storage.read(key);
      if (bytes == null) {
        cacheMiss();
      } else {
        cacheHit();
      }
      return bytes;
    } catch (e) {
      // ignore, file was likely deleted
      return null;
    }
  }

  // Thniya : sur le web, pas de fichiers -> cache mémoire (voir third_party/README.md)
  static final _web = <String, Uint8List>{};

  Future<void> put(String key, Uint8List data) async {
    if (kIsWeb) {
      if (_web.length > 400) _web.remove(_web.keys.first);
      _web[key] = data;
      return;
    }
    if (++_putCount % 20 == 0) {
      await _applyMaxSize(await _storage.storageDirectory());
    }
    await _storage.write(key, data);
  }

  Future<bool> exists(String key) async {
    if (kIsWeb) return _web.containsKey(key);
    final file = await _storage.fileOf(key);
    return file.exists();
  }

  Future<void> applyConstraints() async {
    if (kIsWeb) return;
    final directory = await _storage.storageDirectory();
    if (await directory.exists()) {
      try {
        await _applyMaxAge(directory);
        await _applyMaxSize(directory);
      } catch (e) {
        // ignore, race condition directory may have been deleted
      }
    }
  }

  Future<void> _applyMaxAge(Directory directory) async {
    await directory.list().asyncMap((f) => _expireIfExceedsTtl(f)).toList();
  }

  Future<void> _applyMaxSize(Directory directory) async {
    final entries = await directory
        .list()
        .asyncMap((f) => _toEntry(f))
        .where((e) => e.value.type == FileSystemEntityType.file)
        .toList();
    int size = entries.isEmpty
        ? 0
        : entries.map((e) => e.value.size).reduce((a, b) => a + b);
    if (size > _maxSizeInBytes) {
      final entriesByAccessed = entries
          .sorted((a, b) => a.value.accessed.compareTo(b.value.accessed));
      for (final entry in entriesByAccessed) {
        try {
          await entry.key.delete();
          size -= entry.value.size;
          if (size <= _maxSizeInBytes) {
            break;
          }
        } catch (e) {
          // ignore, race condition file was deleted
        }
      }
    }
  }

  Future<void> _expireIfExceedsTtl(FileSystemEntity entity) async {
    final stat = await entity.stat();
    if (stat.type == FileSystemEntityType.file) {
      final exceeds = _exceedsTtl(stat);
      if (exceeds) {
        await entity.delete();
      }
    }
  }

  bool _exceedsTtl(FileStat stat) {
    final now = DateTime.now();
    final age =
        now.millisecondsSinceEpoch - stat.modified.millisecondsSinceEpoch;
    return (age >= _ttl.inMilliseconds);
  }

  Future<MapEntry<FileSystemEntity, FileStat>> _toEntry(
      FileSystemEntity entity) async {
    return MapEntry(entity, await entity.stat());
  }
}
