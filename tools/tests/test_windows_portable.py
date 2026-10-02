"""Exercise portable orchestration failures; child builds here are mocked, not native evidence."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('portable_orchestration', ROOT / 'tools/windows_native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class WindowsPortableTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.project = self.root / 'libs/portable'
        self.project.mkdir(parents=True)
        (self.root / 'tools/.reports').mkdir(parents=True)
        self.bundle = self.root / 'bundle'
        (self.bundle / 'data').mkdir(parents=True)
        (self.bundle / 'rustdesk.exe').write_bytes(b'unit-test source executable')
        (self.bundle / 'data/asset').write_bytes(b'\0\xffasset')
        self.packed = self.root / 'target/release/rustdesk-portable-packer.exe'
        self.packed.parent.mkdir(parents=True)
        self.output = self.root / 'dist/windows-x64-portable-unsigned'
        self.payload = b'unit-test compressed payload'
        self.calls = []
        self.failure = None
        self.machine = native.MACHINES['x64']
        self.embed = True
        self.mutate_source = False
        self.patch_root = patch.object(native, 'ROOT', self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.patch_command = patch.object(native, 'command', side_effect=self.command)
        self.command_mock = self.patch_command.start()
        self.addCleanup(self.patch_command.stop)
        check = patch.object(native.subprocess, 'check_output', return_value='a' * 40 + '\n')
        check.start()
        self.addCleanup(check.stop)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('VIPER_TEST_PORTABLE_BUNDLE', None)

    def command(self, args, log, *unused):
        self.calls.append((args, log))
        if log == 'windows-portable-build.log':
            (self.project / 'data.bin').write_bytes(self.payload)
            (self.project / 'app_metadata.toml').write_text('timestamp = 1\n')
            data = bytearray(80)
            data[:2] = b'MZ'
            struct.pack_into('<I', data, 60, 64)
            data[64:68] = b'PE\0\0'
            struct.pack_into('<H', data, 68, self.machine)
            self.packed.write_bytes(data + (self.payload if self.embed else b'not embedded'))
        if log == 'windows-portable-tests.log':
            self.assertEqual(os.environ.get('VIPER_TEST_PORTABLE_BUNDLE'), str(self.bundle))
            if self.mutate_source:
                (self.bundle / 'data/asset').write_bytes(b'changed bytes')
        if log == self.failure:
            raise subprocess.CalledProcessError(17, args)
        return ''

    def assert_no_success_output(self):
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root / 'tools/.reports/windows-portable.json').exists())
        self.assertNotIn('windows-portable-manifest.log', [log for _, log in self.calls])

    def assert_inputs_removed(self):
        self.assertFalse((self.project / 'data.bin').exists())
        self.assertFalse((self.project / 'app_metadata.toml').exists())

    def test_mocked_success_records_exact_inputs_and_verifies_the_manifest(self):
        native.build_portable(self.bundle, 'x64')
        report = json.loads((self.output / 'portable-validation.json').read_text())
        self.assertEqual(report['revision'], 'a' * 40)
        self.assertEqual(report['arch'], 'x64')
        self.assertEqual(report['signing'], 'not-performed')
        self.assertEqual(report['application_execution'], 'not-performed')
        self.assertEqual(report['payload_sha256'], hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(report['executable_sha256'], native.digest(self.packed))
        self.assertEqual(report['files'], [
            {'path': 'data/asset', 'size': 7, 'sha256': native.digest(self.bundle / 'data/asset')},
            {'path': 'rustdesk.exe', 'size': 27, 'sha256': native.digest(self.bundle / 'rustdesk.exe')},
        ])
        self.assertEqual((self.output / self.packed.name).read_bytes(), self.packed.read_bytes())
        logs = [log for _, log in self.calls]
        self.assertEqual(logs, ['windows-portable-python.log', 'windows-portable-build.log',
            'windows-portable-tests.log', 'windows-portable-source-drift.log',
            'windows-portable-manifest.log', 'windows-portable-verify.log'])
        self.assertEqual(self.calls[1][0][2:8], ['-f', str(self.bundle), '-o', str(self.project), '-e', str(self.bundle / 'rustdesk.exe')])
        self.assertEqual(self.calls[2][0], ['cargo', 'test', '--locked', '--release', '-p',
            'rustdesk-portable-packer', '--features', 'native-payload-tests'])
        self.assertEqual(self.calls[-2][0][-2:], ['--revision', 'a' * 40])
        self.assertNotIn('VIPER_TEST_PORTABLE_BUNDLE', os.environ)
        self.assert_inputs_removed()

    def test_arm64_requires_and_records_native_machine(self):
        self.machine = native.MACHINES['arm64']
        native.build_portable(self.bundle, 'arm64')
        report = json.loads((self.root / 'dist/windows-arm64-portable-unsigned/portable-validation.json').read_text())
        self.assertEqual(report['arch'], 'arm64')
        self.assert_inputs_removed()

    def test_success_restores_a_preexisting_test_environment(self):
        os.environ['VIPER_TEST_PORTABLE_BUNDLE'] = 'preserve-user-setting'
        native.build_portable(self.bundle, 'x64')
        self.assertEqual(os.environ['VIPER_TEST_PORTABLE_BUNDLE'], 'preserve-user-setting')

    def test_failed_test_restores_environment_and_cleans_only_generated_inputs(self):
        os.environ['VIPER_TEST_PORTABLE_BUNDLE'] = 'preserve-user-setting'
        (self.project / 'user-file').write_text('keep')
        self.failure = 'windows-portable-tests.log'
        with self.assertRaises(subprocess.CalledProcessError):
            native.build_portable(self.bundle, 'x64')
        self.assertEqual(os.environ['VIPER_TEST_PORTABLE_BUNDLE'], 'preserve-user-setting')
        self.assertEqual((self.project / 'user-file').read_text(), 'keep')
        self.assert_inputs_removed()
        self.assert_no_success_output()

    def test_failed_build_cleans_partial_generator_output(self):
        self.failure = 'windows-portable-build.log'
        with self.assertRaises(subprocess.CalledProcessError):
            native.build_portable(self.bundle, 'x64')
        self.assert_inputs_removed()
        self.assert_no_success_output()

    def test_failed_python_setup_never_starts_generator(self):
        self.failure = 'windows-portable-python.log'
        with self.assertRaises(subprocess.CalledProcessError):
            native.build_portable(self.bundle, 'x64')
        self.assertEqual(len(self.calls), 1)
        self.assert_inputs_removed()
        self.assert_no_success_output()

    def test_wrong_architecture_blocks_tests_and_output(self):
        self.machine = native.MACHINES['arm64']
        with self.assertRaisesRegex(ValueError, 'native architecture'):
            native.build_portable(self.bundle, 'x64')
        self.assertEqual(len(self.calls), 2)
        self.assert_inputs_removed()
        self.assert_no_success_output()

    def test_inexact_embedding_blocks_tests_and_output(self):
        self.embed = False
        with self.assertRaisesRegex(ValueError, 'exact generated payload'):
            native.build_portable(self.bundle, 'x64')
        self.assertEqual(len(self.calls), 2)
        self.assert_inputs_removed()
        self.assert_no_success_output()

    def test_empty_payload_is_not_accepted_as_a_substring(self):
        self.payload = b''
        with self.assertRaisesRegex(ValueError, 'exact generated payload'):
            native.build_portable(self.bundle, 'x64')
        self.assert_inputs_removed()
        self.assert_no_success_output()

    def test_mutating_bundle_during_packaging_blocks_output(self):
        self.mutate_source = True
        with self.assertRaisesRegex(ValueError, 'source changed'):
            native.build_portable(self.bundle, 'x64')
        self.assert_inputs_removed()
        self.assert_no_success_output()

    def test_tracked_source_drift_is_fatal(self):
        self.failure = 'windows-portable-source-drift.log'
        with self.assertRaises(subprocess.CalledProcessError):
            native.build_portable(self.bundle, 'x64')
        self.assert_inputs_removed()
        self.assert_no_success_output()

    def test_missing_application_is_rejected_without_starting_processes(self):
        (self.bundle / 'rustdesk.exe').unlink()
        with self.assertRaisesRegex(ValueError, 'actual application'):
            native.build_portable(self.bundle, 'x64')
        self.command_mock.assert_not_called()
        self.assert_no_success_output()

    def test_symlink_input_is_rejected_without_following_it(self):
        (self.bundle / 'link').symlink_to(self.root / 'outside')
        with self.assertRaisesRegex(ValueError, 'cannot contain links'):
            native.build_portable(self.bundle, 'x64')
        self.command_mock.assert_not_called()
        self.assert_no_success_output()

    def test_junction_input_is_rejected_without_starting_processes(self):
        # Junction creation itself is Windows-only; exercise the positive probe.
        with patch.object(Path, 'is_junction', return_value=True):
            with self.assertRaisesRegex(ValueError, 'cannot contain links'):
                native.build_portable(self.bundle, 'x64')
        self.command_mock.assert_not_called()
        self.assert_no_success_output()

    def test_case_colliding_paths_are_rejected(self):
        (self.bundle / 'RUSTDESK.EXE').write_bytes(b'collision')
        # Supply both spellings even on a case-insensitive host filesystem.
        paths = [self.bundle / 'rustdesk.exe', self.bundle / 'RUSTDESK.EXE']
        with patch.object(Path, 'rglob', return_value=paths):
            with self.assertRaisesRegex(ValueError, 'Case-colliding'):
                native.build_portable(self.bundle, 'x64')
        self.command_mock.assert_not_called()
        self.assert_no_success_output()

    def test_existing_generated_metadata_is_not_deleted(self):
        metadata = self.project / 'app_metadata.toml'
        metadata.write_text('user metadata')
        with self.assertRaisesRegex(ValueError, 'overwrite portable build input'):
            native.build_portable(self.bundle, 'x64')
        self.assertEqual(metadata.read_text(), 'user metadata')
        self.command_mock.assert_not_called()

    def test_final_manifest_failure_is_not_ignored(self):
        self.failure = 'windows-portable-verify.log'
        with self.assertRaises(subprocess.CalledProcessError) as error:
            native.build_portable(self.bundle, 'x64')
        self.assertEqual(error.exception.returncode, 17)
        self.assert_inputs_removed()
        self.assertEqual(self.calls[-1][1], 'windows-portable-verify.log')


if __name__ == '__main__':
    unittest.main()
