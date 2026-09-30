"""Keep SwiftPM, CocoaPods fallback and Rust library linkage coherent."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]


class MacOSProjectTests(unittest.TestCase):
    def test_every_configuration_resolves_the_linked_rust_library(self):
        project = (ROOT / 'flutter/macos/Runner.xcodeproj/project.pbxproj').read_text()
        searches = re.findall(r'LIBRARY_SEARCH_PATHS = \((.*?)\);', project, re.S)
        self.assertEqual(len(searches), 3)
        for search in searches:
            self.assertIn('../../target/release,', search)
            self.assertNotIn('../../target/debug', search)
            self.assertNotIn('../../target/profile', search)
        self.assertIn('path = ../../target/release/liblibrustdesk.dylib;', project)

    def test_swiftpm_is_integrated_and_prepared_by_the_shared_scheme(self):
        project = (ROOT / 'flutter/macos/Runner.xcodeproj/project.pbxproj').read_text()
        self.assertIn('isa = XCLocalSwiftPackageReference;', project)
        self.assertIn('productName = FlutterGeneratedPluginSwiftPackage;', project)
        scheme = ET.parse(ROOT / 'flutter/macos/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme').getroot()
        actions = scheme.findall('./BuildAction/PreActions/ExecutionAction/ActionContent')
        self.assertEqual(len(actions), 1)
        self.assertIn('macos_assemble.sh prepare', actions[0].attrib['scriptText'])
        self.assertEqual(actions[0].find('./EnvironmentBuildable/BuildableReference').attrib['BlueprintName'], 'Runner')
        self.assertNotIn('/Users/', project)

    def test_maintained_native_forks_remain_locked_as_pods(self):
        lock = yaml.safe_load((ROOT / 'flutter/macos/Podfile.lock').read_text())
        expected = {'desktop_multi_window', 'flutter_custom_cursor', 'screen_retriever',
                    'texture_rgba_renderer', 'window_manager', 'window_size', 'FlutterMacOS'}
        self.assertEqual(set(lock['EXTERNAL SOURCES']), expected)
        for package in expected:
            self.assertRegex(lock['SPEC CHECKSUMS'][package], r'^[a-f0-9]{40}$')
        self.assertEqual(lock['COCOAPODS'], '1.17.0')
        self.assertNotIn('uni_links_desktop', str(lock))
        self.assertNotIn('path_provider_foundation', str(lock))

    def test_native_ci_checks_the_lock_without_accepting_regeneration(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/apple-native.yml').read_text())
        commands = '\n'.join(step.get('run', '') for step in workflow['jobs']['macos']['steps'])
        self.assertIn('pod install --deployment', commands)
        self.assertIn('git diff --exit-code -- Podfile Podfile.lock', commands)
        self.assertIn('flutter/macos/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme', commands)
        self.assertNotIn('--no-enable-swift-package-manager', commands)
        self.assertNotIn('git checkout --', commands)


if __name__ == '__main__':
    unittest.main()
