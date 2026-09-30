import 'dart:convert';
import 'dart:io';

import 'package:flutter_hbb/generated/flutter_ffi.dart' as native;
import 'package:flutter_hbb/generated/frb_generated.dart';
import 'package:flutter_rust_bridge/flutter_rust_bridge_for_generated_io.dart'
    show ExternalLibrary;
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    final libraryPath = Platform.environment['VIPER_NATIVE_LIBRARY'];
    if (libraryPath == null || !File(libraryPath).existsSync()) {
      throw StateError('Build the Rust library and set VIPER_NATIVE_LIBRARY.');
    }
    await RustLib.init(externalLibrary: ExternalLibrary.open(libraryPath));
  });

  tearDownAll(RustLib.dispose);

  test('the real synchronous and asynchronous bridge agree on app identity',
      () async {
    final synchronous = native.mainGetAppNameSync();
    final asynchronous = await native.mainGetAppName();
    expect(synchronous, isNotEmpty);
    expect(asynchronous, synchronous);
  });

  test('the real printer bridge returns the platform string synchronously', () {
    final String printers = native.mainGetPrinterNames();
    if (Platform.isWindows) {
      final names = jsonDecode(printers);
      expect(names, isA<List<dynamic>>());
      expect(names as List<dynamic>, everyElement(isA<String>()));
    } else {
      expect(printers, isEmpty);
    }
  });

  test('the real asynchronous bridge returns a native version', () async {
    final version = await native.mainGetVersion();
    expect(version, matches(RegExp(r'^\d+\.\d+\.\d+')));
  });
}
