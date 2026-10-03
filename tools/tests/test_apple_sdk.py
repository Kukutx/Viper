"""Fail closed on SDK drift and preserve both native build configurations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('apple_sdk', ROOT / 'tools/apple_sdk.py')
sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk)


class AppleSdkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        developer = self.root / 'Xcode.app/Contents/Developer'
        developer.mkdir(parents=True)
        (self.root / 'configs').mkdir()
        (self.root / 'configs/toolchain.json').write_text(json.dumps({'apple': {
            'developer_dir': str(developer), 'xcode': '27.0', 'build': '27A266a',
            'macos_sdk': '27.0', 'cocoapods': '1.17.0',
        }}), encoding='utf-8')
        self.outputs = ['Xcode 27.0\nBuild version 27A266a\n', '27.0\n', '1.17.0\n']

    def invoke(self, code=0):
        results = [subprocess.CompletedProcess([], code, text, '') for text in self.outputs]
        with patch.object(sdk.platform, 'system', return_value='Darwin'), \
             patch.object(sdk.subprocess, 'run', side_effect=results) as run:
            result = sdk.verify(self.root)
            for call in run.call_args_list:
                self.assertTrue(call.kwargs['env']['DEVELOPER_DIR'].endswith('Contents/Developer'))
                self.assertEqual(call.kwargs['timeout'], 120)
            return result

    def test_exact_toolchain_is_recorded(self):
        self.assertEqual(self.invoke()['macos_sdk'], '27.0')
        self.assertTrue((self.root / 'tools/.reports/apple-toolchain.json').is_file())

    def test_beta_or_other_build_is_rejected(self):
        self.outputs[0] = 'Xcode 27.0\nBuild version 27A5218g\n'
        with self.assertRaisesRegex(RuntimeError, 'Wrong Xcode'):
            self.invoke()

    def test_different_xcode_is_rejected(self):
        self.outputs[0] = 'Xcode 16.4\nBuild version 16F6\n'
        with self.assertRaisesRegex(RuntimeError, 'Wrong Xcode'):
            self.invoke()

    def test_sdk_drift_is_rejected(self):
        self.outputs[1] = '27.2\n'
        with self.assertRaisesRegex(RuntimeError, 'Wrong macos_sdk'):
            self.invoke()

    def test_pods_drift_is_rejected(self):
        self.outputs[2] = '1.16.2\n'
        with self.assertRaisesRegex(RuntimeError, 'Wrong cocoapods'):
            self.invoke()

    def test_command_failure_is_fatal(self):
        with self.assertRaisesRegex(RuntimeError, 'inspection failed'):
            self.invoke(1)

    def test_missing_xcode_has_no_fallback(self):
        import shutil
        shutil.rmtree(self.root / 'Xcode.app')
        with patch.object(sdk.platform, 'system', return_value='Darwin'), \
             patch.object(sdk.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'missing'):
                sdk.verify(self.root)
            run.assert_not_called()

    def test_non_macos_is_rejected(self):
        with patch.object(sdk.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(RuntimeError, 'requires macOS'):
                sdk.verify(self.root)

    def test_native_workflow_uses_pinned_runner_and_both_modes(self):
        config = json.loads((ROOT / 'configs/toolchain.json').read_text())['apple']
        workflow = yaml.safe_load((ROOT / '.github/workflows/apple-native.yml').read_text())
        job = workflow['jobs']['macos']
        self.assertEqual(job['runs-on'], config['runner'])
        commands = '\n'.join(step.get('run', '') for step in job['steps'])
        self.assertIn('python tools/apple_sdk.py --github-env', commands)
        self.assertIn('flutter build macos --debug --no-pub', commands)
        self.assertIn('bash tools/native/build-macos-release.sh', commands)
        self.assertEqual(job['env']['FLUTTER_XCODE_CODE_SIGNING_ALLOWED'], 'NO')
        self.assertNotIn('continue-on-error', str(workflow))

    def test_release_inherits_pod_and_swiftpm_linker_flags(self):
        import re
        project = (ROOT / 'flutter/macos/Runner.xcodeproj/project.pbxproj').read_text()
        flags = re.findall(r'OTHER_LDFLAGS = \((.*?)\);', project, re.S)
        self.assertEqual(len(flags), 2)
        for value in flags:
            self.assertIn('"$(inherited)"', value)
            self.assertIn('__CGPreLoginApp', value)
            self.assertIn('"-sectcreate"', value)


if __name__ == '__main__':
    unittest.main()
