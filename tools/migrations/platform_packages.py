"""迁移失去维护的链接插件，并核对全部直接 hosted 依赖。"""
from flutter_v2 import ROOT, package, replace
from concurrent.futures import ThreadPoolExecutor
import json
import re
import yaml

file = ROOT / 'flutter/pubspec.yaml'
text = file.read_text()
old = '''  uni_links:
    git:
      url: https://github.com/rustdesk-org/uni_links
      path: uni_links
      ref: f416118d843a7e9ed117c7bb7bdc2deda5a9e86f
'''
if text.count(old) != 1:
    raise ValueError('uni_links Git dependency drift')
text = text.replace(old, '')
text, count = re.subn(r'^  uni_links_desktop:[^\n]*\n', '', text, flags=re.M)
if count != 1:
    raise ValueError('uni_links_desktop dependency drift')
text = text.replace('dependencies:\n', 'dependencies:\n  app_links: any\n', 1)
spec = yaml.safe_load(text)
names = [name for section in ('dependencies', 'dev_dependencies') for name, value in spec[section].items() if isinstance(value, str) and name != 'flutter_rust_bridge']
with ThreadPoolExecutor(max_workers=8) as pool:
    pins = dict(zip(names, pool.map(lambda name: package(name)['version'], names)))
for name, version in pins.items():
    text, count = re.subn(r'^  ' + re.escape(name) + r':[^\n]*$', f'  {name}: {version}', text, flags=re.M)
    if count != 1:
        raise ValueError(f'{name}: expected one dependency declaration')
file.write_text(text)
report = ROOT / 'tools/.reports/flutter-migration-pins.json'
record = json.loads(report.read_text())
record.update(pins)
report.write_text(json.dumps(record, indent=2) + '\n')
replace('flutter/lib/common.dart', "import 'package:uni_links/uni_links.dart';", "import 'package:app_links/app_links.dart';")
replace('flutter/lib/common.dart', 'final sub = uriLinkStream.listen(', 'final sub = AppLinks().uriLinkStream.listen(')
replace('flutter/windows/runner/main.cpp', '#include <uni_links_desktop/uni_links_desktop_plugin.h>', '#include <app_links/app_links_plugin_c_api.h>')
replace('flutter/windows/runner/main.cpp', 'DispatchToUniLinksDesktop(hwnd);', 'SendAppLink(hwnd);')
replace('flutter/android/app/src/main/AndroidManifest.xml', '            <!-- Intent for deep linking-->', '            <meta-data android:name="flutter_deeplinking_enabled" android:value="false" />\n\n            <!-- Intent for deep linking-->')
replace('flutter/ios/Runner/Info.plist', '<plist version="1.0">\n<dict>\n', '<plist version="1.0">\n<dict>\n\t<key>FlutterDeepLinkingEnabled</key>\n\t<false/>\n')
file = ROOT / 'flutter/android/build.gradle'
file.write_text(file.read_text().replace("    uni_links: 'name.avioli.unilinks',\n", ''))
print('Candidate hosted pins:', json.dumps(record), flush=True)
lines = (ROOT / 'flutter/lib/common.dart').read_text().splitlines()
for i, line in enumerate(lines):
    if 'listenUniLinks' in line or 'AppLinks().uriLinkStream' in line:
        print('\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0, i-10), min(len(lines), i+35))))
