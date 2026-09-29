"""将 Dart 调用迁移到生成的 FRB 2 API；不保留 FRB 1 适配器。"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]


def replace(path, old, new, count=1):
    file = ROOT / path
    text = file.read_text()
    if text.count(old) != count:
        raise ValueError(f'Anchor drift in {path}: {old!r}')
    file.write_text(text.replace(old, new))


def main():
    generated = (ROOT / 'flutter/lib/generated/frb_generated.dart').read_text()
    api = re.search(r'abstract class RustLibApi extends BaseApi \{([\s\S]*?)\n\}', generated)
    if api is None:
        raise ValueError('Generated RustLibApi declaration missing')
    names = sorted(set(re.findall(r'\b(crateFlutterFfi\w+)\s*\(', api[1])))
    if len(names) < 100:
        raise ValueError(f'Unexpectedly small generated API: {len(names)}')
    mapping = {name[len('crateFlutterFfi'):][0].lower() + name[len('crateFlutterFfi')+1:]: name for name in names}
    receiver = re.compile(r'\b(bind|_ffiBind|ffiBind|rustdeskImpl)(\s*\.\s*)(' + '|'.join(re.escape(n) for n in sorted(mapping, key=len, reverse=True)) + r')\b')
    changed = {}
    for file in (ROOT / 'flutter/lib').rglob('*.dart'):
        if 'generated' in file.relative_to(ROOT / 'flutter/lib').parts:
            continue
        before = file.read_text()
        after, count = receiver.subn(lambda m: m[1] + m[2] + mapping[m[3]], before)
        if after != before:
            file.write_text(after)
            changed[str(file.relative_to(ROOT))] = count
    replace('flutter/lib/models/platform_model.dart', "import 'package:flutter_hbb/generated_bridge.dart'", "import 'package:flutter_hbb/generated/frb_generated.dart'")
    replace('flutter/lib/models/platform_model.dart', 'RustdeskImpl get bind', 'RustLibApi get bind')
    replace('flutter/lib/models/model.dart', "import 'package:flutter_hbb/generated_bridge.dart'", "import 'package:flutter_hbb/generated/flutter_ffi.dart'")
    path = 'flutter/lib/models/native_model.dart'
    replace(path, "import '../generated_bridge.dart';", "import '../generated/frb_generated.dart';\nimport 'package:flutter_rust_bridge/flutter_rust_bridge_for_generated_io.dart' show ExternalLibrary;")
    replace(path, 'DynamicLibrary _openLinuxCoreLib()', 'ExternalLibrary _openLinuxCoreLib()')
    file = ROOT / path
    text = file.read_text().replace('DynamicLibrary.open(', 'ExternalLibrary.open(')
    text = text.replace('DynamicLibrary.process()', 'ExternalLibrary.process(iKnowHowToUseIt: true)')
    text = text.replace('dylib.lookupFunction', 'dylib.ffiDynamicLibrary.lookupFunction')
    text = text.replace('_ffiBind = RustdeskImpl(dylib);', 'await RustLib.init(externalLibrary: dylib);\n      _ffiBind = RustLib.instance.api;')
    text = text.replace('RustdeskImpl', 'RustLibApi')
    file.write_text(text)
    path = 'flutter/lib/web/bridge.dart'
    file = ROOT / path
    text = file.read_text().replace('class RustdeskImpl {', 'class RustLibApi {')
    # 只改方法声明/tear-off 接口，不改 JS 方法名、事件名或传输字段。
    declarations = re.compile(r'^(  (?:Future<[^\n]+?>|Stream<[^\n]+?>|[A-Za-z][\w<>?, ]*)\s+)(' + '|'.join(re.escape(n) for n in sorted(mapping, key=len, reverse=True)) + r')(\s*\()', re.M)
    text = declarations.sub(lambda m: m[1] + mapping[m[2]] + m[3], text)
    file.write_text(text)
    file = ROOT / 'flutter/lib/models/web_model.dart'
    file.write_text(file.read_text().replace('RustdeskImpl', 'RustLibApi'))
    report = ROOT / 'tools/.reports/dart-api-migration.json'
    report.write_text(json.dumps({'mapping': mapping, 'callsites': changed}, indent=2) + '\n')
    print(f'Migrated {sum(changed.values())} API references in {len(changed)} files; {len(mapping)} generated API methods.')


if __name__ == '__main__':
    main()
