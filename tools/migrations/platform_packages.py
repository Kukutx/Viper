"""共同升级共享 win32 依赖的 Flutter 平台插件。"""
from flutter_v2 import ROOT, package
import json
import re

file = ROOT / 'flutter/pubspec.yaml'
text = file.read_text()
report = ROOT / 'tools/.reports/flutter-migration-pins.json'
pins = json.loads(report.read_text())
for name in ('package_info_plus', 'device_info_plus', 'wakelock_plus', 'win32'):
    version = package(name)['version']
    text, count = re.subn(r'^  ' + name + r':[^\n]*$', f'  {name}: {version}', text, flags=re.M)
    if count != 1:
        raise ValueError(f'{name}: expected one dependency declaration')
    pins[name] = version
file.write_text(text)
report.write_text(json.dumps(pins, indent=2) + '\n')
print('Candidate pins:', json.dumps(pins))
