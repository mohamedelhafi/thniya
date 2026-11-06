import 'package:flutter_test/flutter_test.dart';
import 'package:thniya/core/models.dart';
import 'package:thniya/design/components/badges.dart';

LineRef line(String mode, String code) =>
    LineRef(id: 'X', mode: mode, publicCode: code, name: 'x', color: '#000000', textColor: '#FFFFFF');

void main() {
  test('train : « T » puis la lettre de la ligne en petit', () {
    expect(lineCodeParts(line('TRAIN', 'A')), ('T', 'A'));
    expect(lineCodeParts(line('TRAIN', 'TGM')), ('T', 'GM'));
    expect(lineCodeParts(line('TRAIN', 'T')), ('T', null));
    expect(lineCodePlain(line('TRAIN', 'A')), 'T A');
  });

  test('autres modes : code inchangé', () {
    expect(lineCodeParts(line('METRO', 'M6')), ('M6', null));
    expect(lineCodeParts(line('BUS', 'B1')), ('B1', null));
  });
}
