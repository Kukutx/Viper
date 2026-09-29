import 'package:flutter_hbb/utils/screenshot_save.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('sends the full selected path to the native screenshot writer', () async {
    final actions = <String>[];
    final result = await saveScreenshotToSelectedPath(
      selectPath: () async => '/tmp/截图 with spaces.png',
      handleAction: (action) async { actions.add(action); return ''; },
    );
    expect(result, isEmpty);
    expect(actions, ['0:/tmp/截图 with spaces.png']);
  });

  test('cancellation explicitly discards the cached screenshot', () async {
    final actions = <String>[];
    await saveScreenshotToSelectedPath(
      selectPath: () async => null,
      handleAction: (action) async { actions.add(action); return ''; },
    );
    expect(actions, ['2']);
  });

  test('a native save error is returned without discarding the cache', () async {
    final actions = <String>[];
    final result = await saveScreenshotToSelectedPath(
      selectPath: () async => '/readonly/image.png',
      handleAction: (action) async { actions.add(action); return 'Permission denied'; },
    );
    expect(result, 'Permission denied');
    expect(actions, ['0:/readonly/image.png']);
  });

  test('a picker failure never consumes the native cache', () async {
    var called = false;
    await expectLater(saveScreenshotToSelectedPath(
      selectPath: () async => throw StateError('Picker failed'),
      handleAction: (_) async { called = true; return ''; },
    ), throwsStateError);
    expect(called, isFalse);
  });

  test('a bridge failure remains observable to the caller', () async {
    await expectLater(saveScreenshotToSelectedPath(
      selectPath: () async => '/tmp/image.png',
      handleAction: (_) async => throw StateError('Bridge failed'),
    ), throwsStateError);
  });
}
