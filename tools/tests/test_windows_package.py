"""Reject stale or unsafe Windows archives without running a native compiler."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
with patch.object(sys, 'path', [str(ROOT / 'tools'), *sys.path]):
    spec = importlib.util.spec_from_file_location('package_windows', ROOT / 'tools/package_windows.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)


class WindowsPackageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        self.output = self.root / 'result.zip'

    def test_archive_preserves_binary_bytes_and_relative_paths(self):
        (self.bundle / 'data').mkdir()
        (self.bundle / 'rustdesk.exe').write_bytes(b'\x00\xffPE')
        (self.bundle / 'data/asset').write_bytes(b'asset')
        package.archive_bundle(self.bundle, self.output)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(set(archive.namelist()), {'RustDesk/rustdesk.exe', 'RustDesk/data/asset'})
            self.assertEqual(archive.read('RustDesk/rustdesk.exe'), b'\x00\xffPE')

    def test_empty_bundle_is_rejected(self):
        with self.assertRaises(ValueError):
            package.archive_bundle(self.bundle, self.output)
        self.assertFalse(self.output.exists())

    def test_symlinks_are_rejected_before_creating_archive(self):
        (self.bundle / 'link').symlink_to(self.root / 'outside')
        with self.assertRaises(ValueError):
            package.archive_bundle(self.bundle, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_archive_is_not_overwritten(self):
        (self.bundle / 'file').write_bytes(b'new')
        self.output.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            package.archive_bundle(self.bundle, self.output)
        self.assertEqual(self.output.read_bytes(), b'keep')

    def test_only_empty_directories_are_rejected(self):
        (self.bundle / 'empty').mkdir()
        with self.assertRaises(ValueError):
            package.archive_bundle(self.bundle, self.output)
        self.assertFalse(self.output.exists())

    def test_stale_validation_evidence_prevents_packaging(self):
        reports = self.root / 'tools/.reports'
        reports.mkdir(parents=True)
        for evidence in (
            {'revision': 'b' * 40, 'arch': 'x64', 'rust_library_sha256': 'd' * 64},
            {'revision': 'a' * 40, 'arch': 'arm64', 'rust_library_sha256': 'd' * 64},
            {'revision': 'a' * 40, 'arch': 'x64', 'rust_library_sha256': 'e' * 64},
        ):
            (reports / 'windows-native.json').write_text(json.dumps(evidence))
            with patch.object(package, 'host', return_value='x64'), \
                 patch.object(package, 'check_bundle'), \
                 patch.object(package, 'digest', return_value='d' * 64), \
                 patch.object(package.subprocess, 'check_output', return_value='a' * 40), \
                 patch.object(package, 'archive_bundle') as archive:
                with self.assertRaises(ValueError):
                    package.package(self.root)
                archive.assert_not_called()
            self.assertFalse((self.root / 'dist').exists())

    def test_workflow_does_not_package_or_upload_failed_builds(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/windows-native.yml').read_text())
        self.assertNotIn('concurrency', workflow)
        job = workflow['jobs']['windows']
        self.assertIn('matrix.arch', job['concurrency']['group'])
        archive = next(s for s in job['steps'] if s.get('name') == 'Archive the validated unsigned bundle')
        self.assertNotIn('if', archive)
        upload = job['steps'][-1]
        self.assertNotIn('if', upload)
        self.assertEqual(upload['with']['if-no-files-found'], 'error')
        self.assertEqual(workflow['permissions'], {'contents': 'read'})


if __name__ == '__main__':
    unittest.main()
