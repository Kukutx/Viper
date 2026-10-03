import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge


class ArchiveTests(unittest.TestCase):
    def archive(self, entries):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w:gz') as archive:
            for name, data, kind in entries:
                info = tarfile.TarInfo(name)
                info.type = kind
                info.size = len(data) if kind == tarfile.REGTYPE else 0
                archive.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
        return output.getvalue()

    def test_only_requested_executable_is_read(self):
        data = self.archive([('bin/codegen', b'code', tarfile.REGTYPE), ('../../outside', b'ignored', tarfile.REGTYPE)])
        self.assertEqual(bridge.binary_from_archive(data, 'codegen', False), b'code')

    def test_missing_executable(self):
        with self.assertRaises(ValueError):
            bridge.binary_from_archive(self.archive([]), 'codegen', False)

    def test_duplicate_executable(self):
        data = self.archive([('a/codegen', b'a', tarfile.REGTYPE), ('b/codegen', b'b', tarfile.REGTYPE)])
        with self.assertRaises(ValueError):
            bridge.binary_from_archive(data, 'codegen', False)

    def test_symlink_executable(self):
        with self.assertRaises(ValueError):
            bridge.binary_from_archive(self.archive([('codegen', b'', tarfile.SYMTYPE)]), 'codegen', False)

    def test_windows_archive(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('bin/codegen.exe', b'windows')
        self.assertEqual(bridge.binary_from_archive(output.getvalue(), 'codegen.exe', True), b'windows')


class VersionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'configs').mkdir()
        (self.root / 'flutter').mkdir()
        (self.root / 'configs/toolchain.json').write_text(json.dumps({'flutter_rust_bridge': {'version': '2.13.0'}}))
        (self.root / 'Cargo.toml').write_text('[dependencies]\nflutter_rust_bridge = {version = "=2.13.0"}\n')
        (self.root / 'flutter/pubspec.yaml').write_text('dependencies:\n  flutter_rust_bridge: 2.13.0\n')
        (self.root / 'flutter_rust_bridge.yaml').write_text('auto_upgrade_dependency: false\nstop_on_error: true\n')

    def test_matching_versions(self):
        bridge.check(self.root)

    def test_reject_rust_version_range(self):
        (self.root / 'Cargo.toml').write_text('[dependencies]\nflutter_rust_bridge = {version = "2.13.0"}\n')
        with self.assertRaises(ValueError):
            bridge.check(self.root)

    def test_reject_dart_version_range(self):
        (self.root / 'flutter/pubspec.yaml').write_text('dependencies:\n  flutter_rust_bridge: ^2.13.0\n')
        with self.assertRaises(ValueError):
            bridge.check(self.root)

    def test_reject_hidden_dependency_upgrade(self):
        (self.root / 'flutter_rust_bridge.yaml').write_text('auto_upgrade_dependency: true\nstop_on_error: true\n')
        with self.assertRaises(ValueError):
            bridge.check(self.root)

    def test_reject_ignored_generation_errors(self):
        (self.root / 'flutter_rust_bridge.yaml').write_text('auto_upgrade_dependency: false\nstop_on_error: false\n')
        with self.assertRaises(ValueError):
            bridge.check(self.root)

    def test_reject_prerelease(self):
        (self.root / 'configs/toolchain.json').write_text(json.dumps({'flutter_rust_bridge': {'version': '2.14.0-beta.2'}}))
        with self.assertRaises(ValueError):
            bridge.configuration(self.root)


if __name__ == '__main__':
    unittest.main()
