import 'native_model.dart' if (dart.library.html) 'web_model.dart';

final platformFFI = PlatformFFI.instance;
final localeName = PlatformFFI.localeName;


String ffiGetByName(String name, [String arg = '']) {
  return PlatformFFI.getByName(name, arg);
}

void ffiSetByName(String name, [String value = '']) {
  PlatformFFI.setByName(name, value);
}
