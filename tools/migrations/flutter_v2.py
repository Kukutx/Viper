"""在隔离的 GitHub Actions checkout 中准备 FRB 2 / Flutter 升级候选。"""
from pathlib import Path
import json
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def replace(path, before, after, count=1):
    file = ROOT / path
    text = file.read_text()
    actual = text.count(before)
    if actual != count:
        raise ValueError(f'{path}: expected {count} occurrences, found {actual}: {before!r}')
    file.write_text(text.replace(before, after))


def latest(name):
    request = urllib.request.Request(f'https://pub.dev/api/packages/{name}', headers={'User-Agent': 'Viper-migration/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    version = data['latest']['version']
    if '-' in version:
        raise ValueError(f'{name}: prerelease rejected: {version}')
    return version


def prepare():
    replace('Cargo.toml', 'version = "=1.80"', 'version = "=2.13.0"')
    file = ROOT / 'src/flutter_ffi.rs'
    text = file.read_text()
    pattern = re.compile(r'(^pub fn [^{]*?) -> SyncReturn<([^\n{]+)> \{', re.M)
    text, count = pattern.subn(lambda m: '#[flutter_rust_bridge::frb(sync)]\n' + m[1] + ' -> ' + m[2] + ' {', text)
    print(f'Migrated {count} synchronous bridge functions', flush=True)
    text = text.replace('use flutter_rust_bridge::{StreamSink, SyncReturn};', 'use crate::bridge_generated::StreamSink;')
    text = text.replace('SyncReturn(', '(')
    if 'SyncReturn' in text:
        raise ValueError('Unmigrated SyncReturn requires manual review')
    text = text.replace('pub enum EventToUI {', '#[flutter_rust_bridge::frb(non_opaque)]\npub enum EventToUI {')
    file.write_text(text)
    replace('src/flutter.rs', 'use flutter_rust_bridge::StreamSink;', 'use crate::bridge_generated::StreamSink;')
    replace('flutter/lib/common.dart', 'dialogTheme: DialogTheme(', 'dialogTheme: DialogThemeData(', count=2)
    replace('flutter/lib/common.dart', 'tabBarTheme: const TabBarTheme(', 'tabBarTheme: const TabBarThemeData(', count=2)
    file = ROOT / 'flutter/pubspec.yaml'
    text = file.read_text()
    text = text.replace("sdk: '^3.1.0'", "sdk: '>=3.13.4 <4.0.0'\n  flutter: '>=3.47.5'")
    packages = ['uuid', 'ffigen', 'build_runner', 'freezed', 'freezed_annotation', 'extended_text', 'google_fonts', 'file_picker', 'flutter_lints']
    pins = {name: latest(name) for name in packages}
    pins['flutter_rust_bridge'] = '2.13.0'
    for name, version in pins.items():
        text, count = re.subn(r'^  ' + re.escape(name) + r':[^\n]*$', f'  {name}: {version}', text, flags=re.M)
        if count != 1:
            raise ValueError(f'{name}: expected one dependency declaration, got {count}')
    text = re.sub(r'^dependency_overrides:\n(?:[ \t]+[^\n]*\n|\n)*', '', text, flags=re.M)
    file.write_text(text)
    (ROOT / 'flutter_rust_bridge.yaml').write_text('''rust_input: crate::flutter_ffi
rust_root: .
rust_output: src/bridge_generated.rs
dart_root: flutter
dart_output: flutter/lib/generated
dart_entrypoint_class_name: RustLib
c_output: flutter/macos/Runner/bridge_generated.h
duplicated_c_output:
  - flutter/ios/Runner/bridge_generated.h
rust_features:
  - flutter
  - linux-pkg-config
add_mod_to_lib: false
web: true
type_64bit_int: true
auto_upgrade_dependency: false
stop_on_error: true
''')
    report = ROOT / 'tools/.reports'
    report.mkdir(parents=True, exist_ok=True)
    (report / 'flutter-migration-pins.json').write_text(json.dumps(pins, indent=2) + '\n')
    for path in ['src/flutter.rs', 'src/flutter_ffi.rs']:
        lines = (ROOT / path).read_text().splitlines()
        for i, line in enumerate(lines):
            if '.add(' in line or '.close(' in line or 'ZeroCopyBuffer' in line:
                print(f'{path}:{i+1}: ' + '\n'.join(lines[max(0,i-2):i+3]))


def diagnose():
    for path in ['flutter/lib/generated/frb_generated.dart', 'flutter/lib/generated/flutter_ffi.dart']:
        file = ROOT / path
        if file.exists():
            text = file.read_text()
            print(f'--- {path} ---\n' + text[:18000])
    for file in (ROOT / 'flutter/lib').rglob('*.dart'):
        if '/generated/' in str(file):
            continue
        for i, line in enumerate(file.read_text().splitlines()):
            if 'RustdeskImpl' in line or 'generated_bridge' in line or 'SessionID =' in line:
                print(f'{file.relative_to(ROOT)}:{i+1}: {line}')


if __name__ == '__main__':
    {'prepare': prepare, 'diagnose': diagnose}[sys.argv[1]]()
