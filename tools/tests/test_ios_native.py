"""Check device-bundle invariants with fixtures, not an iOS execution claim."""
from pathlib import Path
import hashlib
import json
import plistlib
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import verify_ios_bundle as bundle_tool


class IosBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'Runner.app'
        self.archive = self.root / 'liblibrustdesk.a'
        self.expected = {'minimum': '15.0', 'sdk': '27.0'}
        self.info = {
            'CFBundleIdentifier': 'com.carriez.flutterHbb', 'CFBundleExecutable': 'Runner',
            'MinimumOSVersion': '15.0', 'DTSDKName': 'iphoneos27.0',
            'CFBundleSupportedPlatforms': ['iPhoneOS'],
            'UIApplicationSceneManifest': {'UISceneConfigurations': {
                'UIWindowSceneSessionRoleApplication': [{'UISceneDelegateClassName': 'FlutterSceneDelegate'}]}},
        }
        for p in (self.bundle / 'Runner', self.bundle / 'Frameworks/App.framework/App',
                  self.bundle / 'Frameworks/Flutter.framework/Flutter', self.archive,
                  self.bundle / 'Frameworks/App.framework/flutter_assets/AssetManifest.bin'):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'fixture, not a compiled application')
        self.write_info()
        self.mock = patch.object(bundle_tool, 'inspect', side_effect=self.inspect).start()
        self.addCleanup(patch.stopall)

    def write_info(self):
        (self.bundle / 'Info.plist').write_bytes(plistlib.dumps(self.info))

    def inspect(self, args):
        if args[1] == 'lipo':
            return 'arm64\n'
        if args[1] == 'nm':
            return '\n'.join('000000 T ' + name for name in bundle_tool.BRIDGE_SYMBOLS)
        self.fail(f'Unexpected inspection: {args}')

    def verify(self):
        return bundle_tool.verify(self.bundle, self.archive, self.expected)

    def test_success_reports_static_evidence_not_device_execution(self):
        result = self.verify()
        self.assertEqual(result['device_execution'], 'not-verified')
        self.assertEqual(result['signature'], 'not-verified')
        self.assertEqual(result['runner_sha256'], hashlib.sha256((self.bundle / 'Runner').read_bytes()).hexdigest())
        self.assertEqual(result['rust_archive_sha256'], hashlib.sha256(self.archive.read_bytes()).hexdigest())

    def test_each_identity_platform_and_sdk_field_is_enforced(self):
        for key in ('CFBundleIdentifier', 'CFBundleExecutable', 'MinimumOSVersion', 'DTSDKName', 'CFBundleSupportedPlatforms'):
            old = self.info.pop(key)
            self.write_info()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'metadata drift'):
                self.verify()
            self.info[key] = old

    def test_missing_scene_delegate(self):
        self.info.pop('UIApplicationSceneManifest')
        self.write_info()
        with self.assertRaisesRegex(ValueError, 'scene delegate'):
            self.verify()

    def test_invalid_plist(self):
        (self.bundle / 'Info.plist').write_bytes(b'not a plist')
        with self.assertRaises(plistlib.InvalidFileException):
            self.verify()

    def test_missing_and_empty_native_files(self):
        for p in (self.bundle / 'Runner', self.archive, self.bundle / 'Frameworks/App.framework/App',
                  self.bundle / 'Frameworks/Flutter.framework/Flutter'):
            original = p.read_bytes()
            p.write_bytes(b'')
            with self.subTest(path=p), self.assertRaisesRegex(ValueError, 'native file'):
                self.verify()
            p.write_bytes(original)
        self.archive.unlink()
        with self.assertRaisesRegex(ValueError, 'native file'):
            self.verify()

    def test_missing_flutter_assets(self):
        (self.bundle / 'Frameworks/App.framework/flutter_assets/AssetManifest.bin').unlink()
        with self.assertRaisesRegex(ValueError, 'Flutter assets'):
            self.verify()

    def test_each_binary_architecture_is_checked(self):
        for suffix in ('Runner', 'App', 'Flutter', 'liblibrustdesk.a'):
            def inspect(args):
                return 'x86_64\n' if args[1] == 'lipo' and Path(args[-1]).name == suffix else self.inspect(args)
            self.mock.side_effect = inspect
            with self.subTest(binary=suffix), self.assertRaisesRegex(ValueError, 'only arm64'):
                self.verify()

    def test_each_static_bridge_symbol_is_required(self):
        for symbol in bundle_tool.BRIDGE_SYMBOLS:
            def inspect(args):
                if args[1] == 'nm':
                    return '\n'.join('000000 T ' + name for name in bundle_tool.BRIDGE_SYMBOLS - {symbol})
                return self.inspect(args)
            self.mock.side_effect = inspect
            with self.subTest(symbol=symbol), self.assertRaisesRegex(ValueError, 'Unlinked'):
                self.verify()

    def test_inspection_errors_are_not_ignored(self):
        self.mock.side_effect = ValueError('xcrun failed')
        with self.assertRaisesRegex(ValueError, 'xcrun failed'):
            self.verify()

    def test_symlinked_native_file_and_bundle_are_rejected(self):
        p = self.bundle / 'Runner'
        p.unlink()
        p.symlink_to(self.archive)
        with self.assertRaisesRegex(ValueError, 'native file'):
            self.verify()
        link = self.root / 'alias.app'
        link.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'regular iOS'):
            bundle_tool.verify(link, self.archive, self.expected)



class IosSourceTests(unittest.TestCase):
    def test_deployment_floor_has_one_source(self):
        expected = json.loads((ROOT / 'configs/toolchain.json').read_text())['ios']['minimum']
        project = (ROOT / 'flutter/ios/Runner.xcodeproj/project.pbxproj').read_text()
        self.assertEqual(re.findall(r'IPHONEOS_DEPLOYMENT_TARGET = ([0-9.]+);', project), [expected] * 3)
        triplet = (ROOT / 'res/vcpkg-triplets/arm64-ios.cmake').read_text()
        self.assertIn(f'set(VCPKG_OSX_DEPLOYMENT_TARGET {expected})', triplet)

    def test_swiftpm_replaces_pods_without_removing_plugins(self):
        for name in ('Podfile', 'Podfile.lock'):
            self.assertFalse((ROOT / 'flutter/ios' / name).exists())
        project = (ROOT / 'flutter/ios/Runner.xcodeproj/project.pbxproj').read_text()
        for retired in ('Pods_Runner.framework', '[CP]', 'Pods-Runner', '\"file_selector_ios\"', '\"path_provider_foundation\"'):
            self.assertNotIn(retired, project)
        self.assertIn('FlutterGeneratedPluginSwiftPackage in Frameworks', project)
        self.assertIn('XCLocalSwiftPackageReference', project)
        scheme = ET.parse(ROOT / 'flutter/ios/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme')
        self.assertTrue(any('xcode_backend.sh' in p.attrib.get('scriptText', '') for p in scheme.findall('.//ActionContent')))

    def test_scene_registration_and_deep_links_are_preserved(self):
        info = plistlib.loads((ROOT / 'flutter/ios/Runner/Info.plist').read_bytes())
        self.assertIs(info['FlutterDeepLinkingEnabled'], False)
        scene = info['UIApplicationSceneManifest']
        self.assertIs(scene['UIApplicationSupportsMultipleScenes'], False)
        self.assertEqual(scene['UISceneConfigurations']['UIWindowSceneSessionRoleApplication'][0]['UISceneDelegateClassName'], 'FlutterSceneDelegate')
        app = (ROOT / 'flutter/ios/Runner/AppDelegate.swift').read_text()
        self.assertIn('FlutterImplicitEngineDelegate', app)
        self.assertIn('GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)', app)
        self.assertNotIn('register(with: self)', app)

    def test_original_image_blobs_are_restored(self):
        pins = json.loads((ROOT / 'configs/ios-resources.json').read_text())
        self.assertEqual(len(pins), 18)
        for name, sha in pins.items():
            data = (ROOT / name).read_bytes()
            self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertEqual(hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest(), sha)

    def test_network_dependency_is_pinned_and_unsupported_apple_apis_removed(self):
        manifest = tomllib.loads((ROOT / 'Cargo.toml').read_text())
        self.assertEqual(manifest['dependencies']['netdev'], {'version': '=0.46.3', 'default-features': False})
        self.assertNotIn('default-net', manifest['dependencies'])
        packages = tomllib.loads((ROOT / 'Cargo.lock').read_text())['package']
        self.assertFalse({'default-net', 'system-configuration', 'system-configuration-sys'} & {p['name'] for p in packages})
        self.assertEqual([p['version'] for p in packages if p['name'] == 'netdev'], ['0.46.3'])

    def test_native_workflow_has_no_credentials_or_runtime_source_patch(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/ios-native.yml').read_text())
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertNotIn('secrets.', str(workflow))
        self.assertNotIn('contents: write', str(workflow))
        self.assertEqual(workflow['jobs']['ios']['runs-on'], json.loads((ROOT / 'configs/toolchain.json').read_text())['apple']['runner'])
        for step in workflow['jobs']['ios']['steps']:
            self.assertNotIn('git apply', step.get('run', ''))
        setup = (ROOT / 'tools/native/setup-ios.sh').read_text()
        self.assertIn('env -u IPHONEOS_DEPLOYMENT_TARGET', setup)
        build = (ROOT / 'tools/native/build-ios.sh').read_text()
        for command in ('--locked', '--features flutter,hwcodec', '--no-codesign --no-pub', 'git diff --exit-code HEAD', 'verify_ios_bundle.py'):
            self.assertIn(command, build)
        self.assertNotIn('pod install', setup + build)


if __name__ == '__main__':
    unittest.main()
