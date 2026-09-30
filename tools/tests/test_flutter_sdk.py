import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import flutter_sdk


class FlutterSdkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'configs').mkdir()
        (self.root / 'configs/toolchain.json').write_text(json.dumps({'flutter': '3.47.5', 'dart': '3.13.4'}))
        self.sdk = {'frameworkVersion': '3.47.5', 'dartSdkVersion': '3.13.4 (stable)', 'channel': 'stable'}

    def verify(self, version=None, bootstrap_code=0, machine_code=0):
        output = json.dumps(self.sdk) if version is None else version
        results = [
            subprocess.CompletedProcess(['flutter', '--version'], bootstrap_code, 'Building flutter tool...\n版本\n', 'bootstrap details'),
            subprocess.CompletedProcess(['flutter', '--version', '--machine'], machine_code, output, 'version details'),
        ]
        with patch.object(flutter_sdk.shutil, 'which', return_value=r'C:\SDK with spaces\flutter.bat'), patch.object(flutter_sdk.subprocess, 'run', side_effect=results) as run:
            executable = flutter_sdk.verify(self.root)
        return executable, run

    def test_strict_json_after_bootstrap_and_windows_path(self):
        executable, run = self.verify()
        self.assertEqual(executable, r'C:\SDK with spaces\flutter.bat')
        self.assertEqual(run.call_args_list[1].args[0], [executable, '--version', '--machine'])
        reports = self.root / 'tools/.reports'
        self.assertIn('版本', (reports / 'flutter-bootstrap.log').read_text(encoding='utf-8'))
        self.assertEqual(json.loads((reports / 'flutter-version.json').read_text()), self.sdk)
        self.assertEqual((reports / 'flutter-version.json.stderr.log').read_text(), 'version details')

    def test_flutter_version_mismatch(self):
        self.sdk['frameworkVersion'] = '3.24.5'
        with self.assertRaises(ValueError): self.verify()

    def test_dart_version_mismatch(self):
        self.sdk['dartSdkVersion'] = '3.12.0'
        with self.assertRaises(ValueError): self.verify()

    def test_nonstable_channel(self):
        self.sdk['channel'] = 'beta'
        with self.assertRaises(ValueError): self.verify()

    def test_empty_dart_version(self):
        self.sdk['dartSdkVersion'] = ''
        with self.assertRaises(ValueError): self.verify()

    def test_missing_flutter(self):
        with patch.object(flutter_sdk.shutil, 'which', return_value=None), patch.object(flutter_sdk.subprocess, 'run') as run:
            with self.assertRaises(ValueError): flutter_sdk.verify(self.root)
            run.assert_not_called()

    def test_bootstrap_failure(self):
        with self.assertRaises(subprocess.CalledProcessError): self.verify(bootstrap_code=17)

    def test_machine_command_failure(self):
        with self.assertRaises(subprocess.CalledProcessError): self.verify(machine_code=23)

    def test_prefixed_json_is_rejected(self):
        with self.assertRaises(ValueError): self.verify('Resolving dependencies...\n' + json.dumps(self.sdk))

    def test_nonobject_json_is_rejected(self):
        with self.assertRaises(ValueError): self.verify('[]')


if __name__ == '__main__':
    unittest.main()
