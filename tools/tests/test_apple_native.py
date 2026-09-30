"""Regression checks for the explicit Apple native ABI and FRB 2 linking."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class AppleNativeTests(unittest.TestCase):
    def text(self, path):
        return (ROOT / path).read_text(encoding='utf-8')

    def test_native_header_matches_rust_exports(self):
        header = self.text('flutter/native/rustdesk.h')
        rust = self.text('src/flutter.rs')
        signatures = (
            ('bool rustdesk_core_main(void);', r'pub extern "C" fn rustdesk_core_main\(\) -> bool'),
            ('void handle_applicationShouldOpenUntitledFile(void);', r'pub extern "C" fn handle_applicationShouldOpenUntitledFile\(\)'),
            ('const uint8_t *session_get_rgba(const char *session_uuid_str, uintptr_t display);',
             r'pub extern "C" fn session_get_rgba\(\s*session_uuid_str: \*const char,\s*display: usize,?\s*\) -> \*const u8'),
        )
        for declaration, signature in signatures:
            self.assertIn(declaration, header)
            self.assertRegex(rust, signature)
        self.assertIn('extern "C" {', header)

    def test_native_header_is_valid_c_and_cpp(self):
        # Foundation's Linux runner supplies both compilers. Do not silently skip missing tools.
        for name, language in (('cc', 'c'), ('c++', 'c++')):
            compiler = shutil.which(name)
            self.assertIsNotNone(compiler, f'{name} is required to check the native header')
            subprocess.run([compiler, '-x', language, '-fsyntax-only', '-Wall', '-Werror',
                            str(ROOT / 'flutter/native/rustdesk.h')], check=True)

    def test_swift_has_no_retired_bridge_or_plugin_calls(self):
        for path in ('flutter/macos/Runner/AppDelegate.swift', 'flutter/ios/Runner/AppDelegate.swift'):
            self.assertNotIn('dummy_method_to_enforce_bundling', self.text(path))
            self.assertNotIn('dummyMethodToEnforceBundling', self.text(path))
        window = self.text('flutter/macos/Runner/MainFlutterWindow.swift')
        self.assertNotIn('uni_links_desktop', window)
        self.assertIn('import sqflite_darwin', window)
        self.assertIn('AppLinksMacosPlugin.register(', window)
        self.assertIn('FlutterMultiWindowPlugin.setOnWindowCreatedCallback', window)

    def test_apple_uses_explicit_native_headers_not_codegen_placeholders(self):
        config = yaml.safe_load(self.text('flutter_rust_bridge.yaml'))
        self.assertIs(config['full_dep'], False)
        self.assertNotIn('c_output', config)
        self.assertNotIn('duplicated_c_output', config)
        for platform in ('macos', 'ios'):
            header = self.text(f'flutter/{platform}/Runner/Runner-Bridging-Header.h')
            self.assertIn('../../native/rustdesk.h', header)
            self.assertNotIn('bridge_generated.h', header)

    def test_macos_links_the_library_and_uses_one_header(self):
        project = self.text('flutter/macos/Runner.xcodeproj/project.pbxproj')
        self.assertNotIn('bridge_generated.h', project)
        self.assertEqual(project.count('SWIFT_OBJC_BRIDGING_HEADER = "Runner/Runner-Bridging-Header.h";'), 3)
        link = next(line for line in project.splitlines() if '/* liblibrustdesk.dylib in Frameworks */ =' in line)
        self.assertNotIn('Weak', link)

    def test_ios_force_loads_the_archive_in_all_configurations(self):
        project = self.text('flutter/ios/Runner.xcodeproj/project.pbxproj')
        self.assertEqual(len(re.findall(r'"-force_load",\s*"\$\(PROJECT_DIR\)/../../target/aarch64-apple-ios/release/liblibrustdesk.a",', project)), 3)
        self.assertEqual(project.count('DEAD_CODE_STRIPPING = NO;'), 3)


if __name__ == '__main__':
    unittest.main()
