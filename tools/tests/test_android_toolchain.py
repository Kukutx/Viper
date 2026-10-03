"""Configuration and CI regression checks; no device execution is simulated as success."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import android_toolchain as android


class AndroidToolchainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'configs').mkdir()
        self.cfg = json.loads((ROOT / 'configs/toolchain.json').read_text())
        wrapper = self.root / 'flutter/android/gradle/wrapper'
        wrapper.mkdir(parents=True)
        for name in ('gradle-wrapper.jar', 'gradle-wrapper.properties'):
            shutil.copyfile(ROOT / 'flutter/android/gradle/wrapper' / name, wrapper / name)
        self.write_config()
        self.java = self.root / 'java'
        self.java.mkdir()
        (self.java / 'release').write_text(f'JAVA_RUNTIME_VERSION="{self.cfg["android"]["jdk"]}-LTS"\n')
        self.sdk = self.root / 'sdk'
        ndk = self.sdk / 'ndk' / self.cfg['android']['ndk']
        ndk.mkdir(parents=True)
        (ndk / 'source.properties').write_text(f'Pkg.Revision = {self.cfg["android"]["ndk"]}\n')
        for name in (f'platforms/android-{self.cfg["android"]["compile_sdk"]}.0/android.jar',
                     f'build-tools/{self.cfg["android"]["build_tools"]}/zipalign'):
            p = self.sdk / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'tool fixture, not executed')
        env = patch.dict(os.environ, {'JAVA_HOME': str(self.java), 'ANDROID_HOME': str(self.sdk)})
        env.start()
        self.addCleanup(env.stop)

    def write_config(self):
        (self.root / 'configs/toolchain.json').write_text(json.dumps(self.cfg))

    def test_pinned_files_and_runtime_metadata(self):
        self.assertEqual(android.check(self.root, runtime=True), self.cfg['android'])

    def test_reject_wrong_java_build(self):
        (self.java / 'release').write_text('JAVA_RUNTIME_VERSION="25.0.0+1"\n')
        with self.assertRaisesRegex(ValueError, 'JDK runtime drift'):
            android.check(self.root, runtime=True)

    def test_missing_java_has_no_fallback(self):
        with patch.dict(os.environ, {'JAVA_HOME': ''}), self.assertRaises(ValueError):
            android.verify_java(self.cfg['android'])

    def test_reject_wrong_ndk(self):
        (self.sdk / 'ndk' / self.cfg['android']['ndk'] / 'source.properties').write_text('Pkg.Revision=28.2.13676358\n')
        with self.assertRaisesRegex(ValueError, 'NDK revision'):
            android.check(self.root, runtime=True)

    def test_missing_platform_jar_fails(self):
        for p in self.sdk.rglob('android.jar'):
            p.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing pinned'):
            android.check(self.root, runtime=True)

    def test_wrapper_tampering_is_rejected(self):
        (self.root / 'flutter/android/gradle/wrapper/gradle-wrapper.jar').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'JAR checksum'):
            android.check(self.root)

    def test_wrapper_symlink_is_rejected(self):
        jar = self.root / 'flutter/android/gradle/wrapper/gradle-wrapper.jar'
        data = jar.read_bytes()
        jar.unlink()
        (self.root / 'other.jar').write_bytes(data)
        jar.symlink_to(self.root / 'other.jar')
        with self.assertRaisesRegex(ValueError, 'JAR checksum'):
            android.check(self.root)

    def test_download_origin_cannot_drift(self):
        props = self.root / 'flutter/android/gradle/wrapper/gradle-wrapper.properties'
        props.write_text(props.read_text().replace('services.gradle.org', 'example.com'))
        with self.assertRaisesRegex(ValueError, 'origin drift'):
            android.check(self.root)

    def test_download_checksum_cannot_drift(self):
        self.cfg['android']['gradle_sha256'] = 'a' * 64
        self.write_config()
        with self.assertRaisesRegex(ValueError, 'checksum drift'):
            android.check(self.root)

    def test_prerelease_unpinned_versions_and_boolean_sdk_are_rejected(self):
        for key, value in (('agp', '9.+'), ('kotlin', '2.5.0-Beta1'), ('jdk', '25'), ('min_sdk', True), ('target_sdk', 22)):
            with self.subTest(key=key):
                original = self.cfg['android'][key]
                self.cfg['android'][key] = value
                self.write_config()
                with self.assertRaises(ValueError):
                    android.configuration(self.root)
                self.cfg['android'][key] = original

    def test_duplicate_runtime_property_is_rejected(self):
        (self.java / 'release').write_text('JAVA_RUNTIME_VERSION="25.0.0+1"\nJAVA_RUNTIME_VERSION="25.0.1+1"\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate property'):
            android.check(self.root, runtime=True)


class AndroidIntegrationTests(unittest.TestCase):
    def test_workflow_is_read_only_and_runs_all_three_supported_release_abis(self):
        wf = yaml.safe_load((ROOT / '.github/workflows/android-native.yml').read_text())
        self.assertEqual(wf['permissions'], {'contents': 'read'})
        job = wf['jobs']['android']
        self.assertEqual(set(job['strategy']['matrix']['abi']), set(android.ABIS))
        self.assertNotIn('if', job)
        self.assertNotIn('secrets', str(job))
        self.assertNotIn('continue-on-error', str(job))
        steps = job['steps']
        names = [s.get('name') for s in steps]
        self.assertLess(names.index('Require the pinned JDK runtime and build'), names.index('Install native prerequisites and the exact SDK'))
        self.assertLess(names.index('Install native prerequisites and the exact SDK'), names.index('Build the real native library and unsigned APK'))
        self.assertNotIn('if', steps[-1])

    def test_application_keeps_identity_and_never_uses_debug_release_signing(self):
        app = (ROOT / 'flutter/android/app/build.gradle').read_text()
        self.assertIn('applicationId "com.carriez.flutter_hbb"', app)
        self.assertIn('namespace "com.carriez.flutter_hbb"', app)
        self.assertNotIn('signingConfigs.debug', app)
        self.assertIn('if (keystorePropertiesFile.exists())', app)
        self.assertIn('--locked', app)
        self.assertNotIn('strictly("1.9.10")', app)
        self.assertIn("keepDebugSymbols += ['**/librustdesk.so']", app)

    def test_native_build_preserves_hardware_codecs_and_checks_packaged_identity(self):
        script = (ROOT / 'tools/native/build-android.sh').read_text()
        for command in ('bash flutter/build_android_deps.sh', '--features flutter,hwcodec',
                        'tools/verify_android_apk.py', 'zipalign" -c -P 16',
                        'tools/viper.py manifest', 'tools/viper.py verify', '--runtime'):
            self.assertIn(command, script)
        self.assertNotIn('|| true', script)
        self.assertNotIn('signingConfigs.debug', script)

    def test_fdroid_uses_numeric_pinned_ndk_and_keeps_four_abis(self):
        script = (ROOT / 'flutter/build_fdroid.sh').read_text()
        self.assertEqual(script.count('--value android.ndk'), 2)
        self.assertIn('--value android.cargo_ndk', script)
        self.assertNotIn('android-sdk-transparency-log/-/raw/master', script)
        self.assertNotIn('--platform 21', script)
        for abi in ('arm64-v8a', 'armeabi-v7a', 'x86_64', 'x86'):
            self.assertIn(abi, script)

    def test_qr_api_migration_preserves_scanning_and_does_not_add_mlkit(self):
        pub = yaml.safe_load((ROOT / 'flutter/pubspec.yaml').read_text())
        self.assertNotIn('qr_code_scanner', pub['dependencies'])
        self.assertEqual(pub['dependencies']['qr_code_scanner_plus'], '2.3.0')
        text = (ROOT / 'flutter/lib/mobile/pages/scan_page.dart').read_text()
        for name in ('QRView', 'scannedDataStream', 'toggleFlash', 'flipCamera'):
            self.assertIn(name, text)
        self.assertNotIn('mobile_scanner', pub['dependencies'])

    def test_video_capabilities_are_checked_before_use(self):
        source = (ROOT / 'flutter/android/app/src/main/kotlin/com/carriez/flutter_hbb/MainActivity.kt').read_text()
        body = source[source.index('    private fun setCodecInfo()'):source.index('    private fun onVoiceCallStarted()')]
        self.assertEqual(body.count('caps.videoCapabilities'), 1)
        self.assertIn('val videoCaps = caps.videoCapabilities ?: return@forEach', body)
        self.assertLess(body.index('val videoCaps'), body.index('videoCaps.isSizeSupported'))
        self.assertIn('videoCaps.bitrateRange', body)

    def test_current_flutter_legacy_boundary_is_explicit(self):
        props = android.properties(ROOT / 'flutter/android/gradle.properties')
        self.assertEqual(props['android.newDsl'], 'false')
        self.assertEqual(props['android.builtInKotlin'], 'false')
        self.assertIn('Flutter 3.47.5', android.configuration()['compatibility_note'])


if __name__ == '__main__':
    unittest.main()
