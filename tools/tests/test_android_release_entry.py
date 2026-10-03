"""Require current SDKs and deny credential use in all PR-triggered Android publishing."""
import json
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class AndroidReleaseEntryTests(unittest.TestCase):
    def setUp(self):
        workflow = yaml.safe_load((ROOT/'.github/workflows/flutter-build.yml').read_text())
        self.jobs = [workflow['jobs'][key] for key in ('build-rustdesk-android', 'build-rustdesk-android-universal')]

    def test_both_release_routes_validate_the_shared_jdk_and_ndk(self):
        for job in self.jobs:
            with self.subTest(job=job['name']):
                steps = job['steps']
                java = next(s for s in steps if s.get('uses', '').startswith('actions/setup-java@'))
                self.assertEqual(java['with']['java-version'], '${{ env.ANDROID_JDK_FEATURE }}')
                names = [s.get('name') for s in steps]
                self.assertLess(names.index('Require the pinned Android JDK runtime'), names.index('Build rustdesk'))
                self.assertLess(names.index('Install and verify the pinned Android SDK'), names.index('Build rustdesk'))
                code = '\n'.join(s.get('run', '') for s in steps)
                for gate in ('tools/android_toolchain.py --env', 'tools/android_toolchain.py --java-only',
                             'tools/android_toolchain.py --runtime', 'tools/native/install-android-sdk.sh',
                             'flutter config --jdk-dir="$JAVA_HOME"'):
                    self.assertIn(gate, code)
                self.assertNotIn('java-17', str(job))
                self.assertNotIn('openjdk-17', str(job))
                self.assertNotIn('nttld/setup-ndk', str(job))

    def test_packaging_never_patches_gradle_or_uses_a_debug_signer(self):
        for job in self.jobs:
            step = next(s for s in job['steps'] if s.get('name') == 'Build rustdesk')
            self.assertNotIn('sed -i', step['run'])
            self.assertNotIn('signingConfigs.debug', step['run'])
            self.assertIn('test -L flutter/android/key.properties', step['run'])
            self.assertIn('tools/prepare_flutter.py', step['run'])
            self.assertNotIn('JAVA_HOME', step.get('env', {}))

    def test_signing_uses_the_pinned_build_tools_and_blocks_all_pr_events(self):
        for job in self.jobs:
            version = next(s for s in job['steps'] if s.get('name') == 'Setup sign tool version variable')['run']
            self.assertIn('BUILD_TOOL_VERSION="$ANDROID_BUILD_TOOLS"', version)
            self.assertNotIn('tail -n', version)
            for step in job['steps']:
                if step.get('name') in ('Sign app APK', 'Publish signed apk package', 'Publish unsigned apk package', 'Upload Artifacts'):
                    guard = step['if']
                    self.assertIn("!startsWith(github.event_name, 'pull_request')", guard)
                    self.assertIn('inputs.upload-artifact', guard)

    def test_native_rust_failure_stops_before_cache_and_expensive_builds(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/android-native.yml').read_text())
        job = workflow['jobs']['android']
        steps = job['steps']
        gate_index = next(i for i, step in enumerate(steps)
                          if step.get('run', '').strip() == 'python tools/ci_rust.py')
        gate = steps[gate_index]
        self.assertEqual(gate['run'].strip(), 'python tools/ci_rust.py')
        self.assertNotIn('if', gate)
        self.assertNotIn('continue-on-error', gate)
        self.assertNotIn('continue-on-error', job)
        for index, step in enumerate(steps):
            if step.get('uses', '').startswith(('Swatinem/rust-cache@', 'actions/setup-java@')):
                self.assertLess(gate_index, index)
            if step.get('name') in ('Install native prerequisites and the exact SDK',
                                   'Build the real native library and unsigned APK'):
                self.assertLess(gate_index, index)

    def test_all_native_triplets_use_the_central_minimum(self):
        minimum = json.loads((ROOT/'configs/toolchain.json').read_text())['android']['min_sdk']
        for triplet in ('arm-neon', 'arm64', 'x64', 'x86'):
            path = ROOT/f'res/vcpkg-triplets/{triplet}-android.cmake'
            self.assertEqual(re.findall(r'set\(VCPKG_CMAKE_SYSTEM_VERSION (\d+)\)', path.read_text()), [str(minimum)])

    def test_rust_entry_scripts_keep_locks_and_are_invoked_by_bash(self):
        commands = '\n'.join(s.get('run', '') for s in self.jobs[0]['steps'])
        self.assertIn('cargo install cargo-ndk --version "=${{ env.CARGO_NDK_VERSION }}" --locked', commands)
        self.assertIn('bash ./flutter/build_android_deps.sh', commands)
        for arch in ('arm', 'arm64', 'x64', 'x86'):
            self.assertIn(f'bash ./flutter/ndk_{arch}.sh', commands)
            self.assertIn('build --locked --release', (ROOT/f'flutter/ndk_{arch}.sh').read_text())
            self.assertIn('python3 tools/android_cargo.py', (ROOT/f'flutter/ndk_{arch}.sh').read_text())


if __name__ == '__main__':
    unittest.main()
