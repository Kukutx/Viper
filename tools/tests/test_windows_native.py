"""Validate PE checks and fail-closed native build orchestration."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('windows_native', ROOT / 'tools/windows_native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class WindowsNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        self.source = self.root / 'source.dll'
        self.binary(self.source)
        for name in ('rustdesk.exe', 'librustdesk.dll', 'flutter_windows.dll'):
            self.binary(self.bundle / name)
        (self.bundle / 'data/flutter_assets').mkdir(parents=True)
        for name in ('icudtl.dat', 'app.so', 'flutter_assets/asset.json'):
            (self.bundle / 'data' / name).write_bytes(b'asset')

    def binary(self, path, machine=0x8664):
        data = bytearray(80)
        data[:2] = b'MZ'
        struct.pack_into('<I', data, 60, 64)
        data[64:68] = b'PE\0\0'
        struct.pack_into('<H', data, 68, machine)
        path.write_bytes(data)

    def test_valid_native_bundle(self):
        native.check_bundle(self.bundle, self.source, 'x64')

    def test_arm64_bundle(self):
        self.binary(self.source, 0xAA64)
        for path in self.bundle.glob('*.*'):
            self.binary(path, 0xAA64)
        native.check_bundle(self.bundle, self.source, 'arm64')

    def test_wrong_architecture_is_rejected(self):
        self.binary(self.bundle / 'flutter_windows.dll', 0xAA64)
        with self.assertRaises(ValueError):
            native.check_bundle(self.bundle, self.source, 'x64')

    def test_truncated_or_invalid_header_is_rejected(self):
        for data in (b'MZ', b'0' * 80, b'MZ' + b'\0' * 78):
            self.source.write_bytes(data)
            with self.assertRaises(ValueError):
                native.pe_machine(self.source)

    def test_out_of_bounds_header_is_rejected(self):
        data = bytearray(self.source.read_bytes())
        struct.pack_into('<I', data, 60, 0xffffffff)
        self.source.write_bytes(data)
        with self.assertRaises(ValueError):
            native.pe_machine(self.source)

    def test_wrong_rust_library_is_rejected(self):
        with self.source.open('ab') as stream:
            stream.write(b'other build')
        with self.assertRaises(ValueError):
            native.check_bundle(self.bundle, self.source, 'x64')

    def test_missing_or_empty_asset_is_rejected(self):
        for action in ('empty', 'missing'):
            path = self.bundle / 'data/app.so'
            path.write_bytes(b'')
            if action == 'missing':
                path.unlink()
            with self.assertRaises(ValueError):
                native.check_bundle(self.bundle, self.source, 'x64')

    def test_empty_asset_directory_is_rejected(self):
        (self.bundle / 'data/flutter_assets/asset.json').unlink()
        with self.assertRaises(ValueError):
            native.check_bundle(self.bundle, self.source, 'x64')

    def test_non_windows_host_is_rejected(self):
        with patch.object(native.platform, 'system', return_value='Linux'):
            with self.assertRaises(ValueError):
                native.host()

    def test_child_failure_is_fatal_and_log_is_preserved(self):
        with patch.object(native, 'ROOT', self.root), patch.object(native.subprocess, 'run') as run:
            run.return_value.returncode = 7
            with self.assertRaises(subprocess.CalledProcessError) as error:
                native.command(['false'], 'failure.log', cwd=self.root)
            self.assertEqual(error.exception.returncode, 7)
            self.assertTrue((self.root / 'tools/.reports/failure.log').is_file())

    def test_unpinned_llvm_is_rejected_before_download(self):
        config = {'llvm': 'latest', 'assets': {'x64': {'name': 'bad.tar.xz', 'sha256': '0' * 64}}}
        with patch.object(native.urllib.request, 'urlopen') as download:
            with self.assertRaises(ValueError):
                native.install_llvm(config, 'x64')
            download.assert_not_called()

    def test_workflow_is_read_only_and_covers_both_native_hosts(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/windows-native.yml').read_text())
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        job = workflow['jobs']['windows']
        self.assertEqual({item['arch'] for item in job['strategy']['matrix']['include']}, {'x64', 'arm64'})
        self.assertFalse(job['strategy']['fail-fast'])
        self.assertNotIn('secrets.', str(workflow))
        self.assertNotIn('continue-on-error', str(workflow))
        self.assertIn('python tools/windows_native.py', str(workflow))
        config = json.loads((ROOT / 'configs/toolchain.json').read_text())['windows']
        self.assertEqual(config['visual_studio_major'], 18)
        for arch in ('x64', 'arm64'):
            self.assertRegex(config['assets'][arch]['sha256'], r'^[0-9a-f]{64}$')


if __name__ == '__main__':
    unittest.main()
