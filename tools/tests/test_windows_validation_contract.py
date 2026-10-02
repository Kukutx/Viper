"""Exercise native evidence and packaging failures, independent of a Windows host."""
import ast
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
with patch.object(sys, 'path', [str(ROOT / 'tools'), *sys.path]):
    spec = importlib.util.spec_from_file_location('audit_package_windows', ROOT / 'tools/package_windows.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    import windows_native as native


def test_log(passed=9, failed=0, ignored=0, measured=0, status='ok', total=None):
    total = passed + failed + ignored + measured if total is None else total
    return (f'running {total} tests\n'
            f'test result: {status}. {passed} passed; {failed} failed; {ignored} ignored; '
            f'{measured} measured; 334 filtered out; finished in 0.01s\n')


class NativeEvidenceTests(unittest.TestCase):
    def test_nonempty_success_and_growth(self):
        self.assertEqual(native.verified_test_counts(test_log(), 9)['passed'], 9)
        self.assertEqual(native.verified_test_counts(test_log(10), 9)['passed'], 10)

    def test_empty_or_reduced_suite_is_rejected(self):
        for count in (0, 8):
            with self.subTest(count=count), self.assertRaises(ValueError):
                native.verified_test_counts(test_log(count), 9)

    def test_failure_is_rejected_even_with_fabricated_ok_status(self):
        for status in ('ok', 'FAILED'):
            with self.subTest(status=status), self.assertRaises(ValueError):
                native.verified_test_counts(test_log(failed=1, status=status), 9)

    def test_ignored_or_measured_tests_are_not_successes(self):
        for text in (test_log(ignored=1), test_log(measured=1)):
            with self.subTest(text=text), self.assertRaises(ValueError):
                native.verified_test_counts(text, 9)

    def test_incomplete_duplicate_and_inconsistent_output_is_rejected(self):
        for text in ('', 'running 9 tests\n', test_log() + test_log(),
                     test_log(total=10), test_log().split('\n', 1)[1]):
            with self.subTest(text=text), self.assertRaises(ValueError):
                native.verified_test_counts(text, 9)

    def test_invalid_test_floor_is_rejected(self):
        for minimum in (0, -1, True, '9'):
            with self.subTest(minimum=minimum), self.assertRaises(ValueError):
                native.verified_test_counts(test_log(), minimum)

    def test_crlf_and_compiler_diagnostics_are_preserved(self):
        text = 'warning: retained compiler diagnostic\n' + test_log(48)
        self.assertEqual(native.verified_test_counts(text.replace('\n', '\r\n'), 48)['passed'], 48)


class NativeBinaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bundle = self.root / 'flutter/build/windows/x64/runner/Release'
        self.bundle.mkdir(parents=True)
        self.source = self.root / 'target/release/librustdesk.dll'
        self.source.parent.mkdir(parents=True)
        self.binary(self.source)
        for name in ('rustdesk.exe', 'librustdesk.dll', 'flutter_windows.dll', 'plugin.dll'):
            self.binary(self.bundle / name)
        assets = self.bundle / 'data/flutter_assets'
        assets.mkdir(parents=True)
        for name in ('app.so', 'icudtl.dat', 'flutter_assets/asset'):
            (self.bundle / 'data' / name).write_bytes(b'fixture')

    def binary(self, path, machine=0x8664):
        data = bytearray(80)
        data[:2] = b'MZ'
        struct.pack_into('<I', data, 60, 64)
        data[64:68] = b'PE\0\0'
        struct.pack_into('<H', data, 68, machine)
        path.write_bytes(data)

    def inventory(self):
        return native.check_bundle(self.bundle, self.source, 'x64')

    def test_every_plugin_is_hashed_and_sorted(self):
        inventory = self.inventory()
        self.assertEqual([item['path'] for item in inventory],
                         ['flutter_windows.dll', 'librustdesk.dll', 'plugin.dll', 'rustdesk.exe'])
        for item in inventory:
            self.assertEqual(item['sha256'], native.digest(self.bundle / item['path']))
            self.assertEqual(item['machine'], 0x8664)

    def test_wrong_plugin_architecture_is_rejected(self):
        self.binary(self.bundle / 'plugin.dll', 0xAA64)
        with self.assertRaises(ValueError):
            self.inventory()

    def test_nested_and_uppercase_native_files_are_checked(self):
        directory = self.bundle / 'plugins'
        directory.mkdir()
        self.binary(directory / 'Nested.DLL', 0xAA64)
        with self.assertRaises(ValueError):
            self.inventory()

    def test_invalid_plugin_header_is_rejected(self):
        (self.bundle / 'plugin.dll').write_bytes(b'not a PE')
        with self.assertRaises(ValueError):
            self.inventory()

    def test_linked_bundle_and_reference_are_rejected(self):
        link = self.root / 'bundle-link'
        link.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaises(ValueError):
            native.check_bundle(link, self.source, 'x64')
        ref = self.root / 'source-link.dll'
        ref.symlink_to(self.source)
        with self.assertRaises(ValueError):
            native.check_bundle(self.bundle, ref, 'x64')

    def test_linked_child_directory_is_rejected_before_descent(self):
        (self.bundle / 'outside').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.inventory()

    def test_junction_is_rejected_before_descent(self):
        directory = self.bundle / 'junction'
        directory.mkdir()
        with patch.object(Path, 'is_junction', autospec=True, side_effect=lambda path: path == directory):
            with self.assertRaises(ValueError):
                self.inventory()

    def test_unchanged_inventory_can_be_packaged(self):
        reports = self.root / 'tools/.reports'
        reports.mkdir(parents=True)
        evidence = {'revision': 'a' * 40, 'arch': 'x64',
                    'rust_library_sha256': native.digest(self.source),
                    'native_binaries': self.inventory()}
        (reports / 'windows-native.json').write_text(json.dumps(evidence))
        with patch.object(package, 'host', return_value='x64'), \
             patch.object(package.subprocess, 'check_output', return_value='a' * 40), \
             patch.object(package.subprocess, 'run') as manifest:
            output = package.package(self.root)
        with zipfile.ZipFile(output / 'RustDesk-windows-x64-unsigned.zip') as archive:
            self.assertEqual(archive.read('RustDesk/plugin.dll'), (self.bundle / 'plugin.dll').read_bytes())
        self.assertEqual(json.loads((output / 'build-profile.json').read_text()), evidence)
        self.assertEqual([call.args[0][2] for call in manifest.call_args_list], ['manifest', 'verify'])

    def test_same_architecture_plugin_tampering_blocks_packaging(self):
        self.reject_changed_inventory('tamper')

    def test_added_removed_or_missing_inventory_blocks_packaging(self):
        for mutation in ('add', 'remove', 'missing'):
            with self.subTest(mutation=mutation):
                self.reject_changed_inventory(mutation)

    def reject_changed_inventory(self, mutation):
        inventory = self.inventory()
        reports = self.root / 'tools/.reports'
        reports.mkdir(parents=True, exist_ok=True)
        evidence = {'revision': 'a' * 40, 'arch': 'x64',
                    'rust_library_sha256': native.digest(self.source), 'native_binaries': inventory}
        if mutation == 'tamper':
            with (self.bundle / 'plugin.dll').open('ab') as stream:
                stream.write(b'changed after validation')
        elif mutation == 'add':
            self.binary(self.bundle / 'extra.dll')
        elif mutation == 'remove':
            (self.bundle / 'plugin.dll').unlink()
        else:
            evidence.pop('native_binaries')
        (reports / 'windows-native.json').write_text(json.dumps(evidence))
        with patch.object(package, 'host', return_value='x64'), \
             patch.object(package.subprocess, 'check_output', return_value='a' * 40), \
             patch.object(package, 'archive_bundle') as archive:
            with self.assertRaises(ValueError):
                package.package(self.root)
            archive.assert_not_called()
        self.assertFalse((self.root / 'dist').exists())


class WindowsBudgetTests(unittest.TestCase):
    def test_cold_build_budget_leaves_bounded_finalization_time(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/windows-native.yml').read_text())
        job = workflow['jobs']['windows']
        self.assertEqual(job['timeout-minutes'], '${{ matrix.job-timeout }}')
        build = next(s for s in job['steps'] if s.get('name') == 'Build and verify the native Release bundle')
        self.assertEqual(build['timeout-minutes'], '${{ matrix.build-timeout }}')
        limits = {entry['arch']: entry for entry in job['strategy']['matrix']['include']}
        for entry in limits.values():
            self.assertGreaterEqual(entry['job-timeout'] - entry['build-timeout'], 20)
            self.assertLessEqual(entry['job-timeout'], 90)
        self.assertGreater(limits['arm64']['job-timeout'], limits['x64']['job-timeout'])
        self.assertNotIn('continue-on-error', str(workflow))
        self.assertFalse(job['strategy']['fail-fast'])

    def test_native_test_floors_are_checked_before_flutter_packaging(self):
        module = ast.parse((ROOT / 'tools/windows_native.py').read_text())
        build = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
        calls = [n for n in ast.walk(build) if isinstance(n, ast.Call)]
        validations = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'verified_test_counts']
        self.assertEqual(len(validations), 2)
        self.assertEqual([n.args[1].value for n in validations], [48, 9])
        commands = {n.args[1].value: n for n in calls if isinstance(n.func, ast.Name)
                    and n.func.id == 'command' and len(n.args) > 1 and isinstance(n.args[1], ast.Constant)}
        for validation, log in zip(validations, ['windows-audio-tests.log', 'windows-dependency-tests.log']):
            self.assertLess(commands[log].lineno, validation.lineno)
            self.assertLess(validation.lineno, commands['windows-flutter.log'].lineno)
            self.assertIn(log, ast.unparse(validation.args[0]))

    def test_cache_keys_cover_the_native_dependency_installer(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/windows-native.yml').read_text())
        steps = workflow['jobs']['windows']['steps']
        keys = [s['with']['key'] for s in steps if s.get('uses', '').startswith(('actions/cache/restore@', 'actions/cache/save@'))]
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys[0], keys[1])
        for dependency in ('configs/toolchain.json', 'tools/windows_native.py', 'res/vcpkg/**'):
            self.assertIn(dependency, keys[0])


if __name__ == '__main__':
    unittest.main()
