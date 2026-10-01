from pathlib import Path
import json
import os
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linux_release as release


def elf(machine=62, kind=3):
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HH', header, 16, kind, machine)
    return bytes(header)


class LinuxReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / 'bundle'
        for name in ('lib', 'data/flutter_assets'):
            (self.bundle / name).mkdir(parents=True)
        for name in ('rustdesk', 'lib/librustdesk.so', 'lib/libflutter_linux_gtk.so', 'lib/libapp.so'):
            (self.bundle / name).write_bytes(elf())
        (self.bundle / 'rustdesk').chmod(0o755)
        (self.bundle / 'data/icudtl.dat').write_bytes(b'icu')
        (self.bundle / 'data/flutter_assets/asset').write_bytes(b'asset')
        self.source = self.root / 'source.so'
        self.source.write_bytes(elf())

    def test_both_architectures(self):
        for arch, machine in release.MACHINES.items():
            with self.subTest(arch=arch):
                for path in [self.source, self.bundle / 'rustdesk', *self.bundle.glob('lib/*')]:
                    path.write_bytes(elf(machine))
                self.assertEqual(len(release.check_bundle(self.bundle, self.source, arch)), 4)

    def test_wrong_library_architecture(self):
        (self.bundle / 'lib/libapp.so').write_bytes(elf(183))
        with self.assertRaisesRegex(ValueError, 'architecture'):
            release.check_bundle(self.bundle, self.source, 'x64')

    def test_plugin_architecture_is_checked(self):
        (self.bundle / 'lib/plugin.so').write_bytes(elf(183))
        with self.assertRaisesRegex(ValueError, 'architecture'):
            release.check_bundle(self.bundle, self.source, 'x64')

    def test_non_elf_library(self):
        (self.bundle / 'lib/plugin.so').write_bytes(b'not a library')
        with self.assertRaisesRegex(ValueError, 'Non-ELF'):
            release.check_bundle(self.bundle, self.source, 'x64')

    def test_invalid_elf_headers(self):
        for data in (b'\x7fELF', b'X' * 64, elf(kind=1), elf().replace(b'\x02\x01\x01', b'\x01\x01\x01', 1)):
            with self.subTest(data=data):
                self.source.write_bytes(data)
                with self.assertRaises(ValueError): release.elf_machine(self.source)

    def test_required_file_missing_or_empty(self):
        path = self.bundle / 'lib/libapp.so'
        path.write_bytes(b'')
        with self.assertRaises(ValueError): release.check_bundle(self.bundle, self.source, 'x64')
        path.unlink()
        with self.assertRaises(ValueError): release.check_bundle(self.bundle, self.source, 'x64')

    def test_missing_executable_permission(self):
        (self.bundle / 'rustdesk').chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'permission'):
            release.check_bundle(self.bundle, self.source, 'x64')

    def test_rust_library_byte_drift(self):
        self.source.write_bytes(elf() + b'different')
        with self.assertRaisesRegex(ValueError, 'differs'):
            release.check_bundle(self.bundle, self.source, 'x64')

    def test_empty_assets(self):
        (self.bundle / 'data/flutter_assets/asset').unlink()
        with self.assertRaisesRegex(ValueError, 'assets'):
            release.check_bundle(self.bundle, self.source, 'x64')

    def test_internal_relative_symlink_is_preserved_in_archive(self):
        link = self.bundle / 'lib/plugin.so'
        link.symlink_to('librustdesk.so')
        release.check_bundle(self.bundle, self.source, 'x64')
        archive = release.archive_bundle(self.bundle, self.root / 'dist', 'x64', 'a' * 40)
        with tarfile.open(archive) as tar:
            self.assertTrue(tar.getmember('RustDesk/lib/plugin.so').issym())
            self.assertEqual(tar.getmember('RustDesk/lib/plugin.so').linkname, 'librustdesk.so')
            self.assertTrue(tar.getmember('RustDesk/rustdesk').mode & 0o111)
            self.assertEqual(tar.extractfile('RustDesk/lib/librustdesk.so').read(), self.source.read_bytes())

    def test_unsafe_symlinks(self):
        link = self.bundle / 'link'
        for target in ('../source.so', '/etc/passwd', 'missing', 'link'):
            with self.subTest(target=target):
                link.symlink_to(target)
                with self.assertRaises(ValueError): release.check_tree(self.bundle)
                link.unlink()

    def test_required_file_cannot_be_a_symlink(self):
        path = self.bundle / 'data/icudtl.dat'
        path.unlink()
        path.symlink_to('flutter_assets/asset')
        with self.assertRaises(ValueError): release.check_bundle(self.bundle, self.source, 'x64')

    def test_unsafe_file_name(self):
        (self.bundle / 'unsafe\nname').touch()
        with self.assertRaises(ValueError): release.check_tree(self.bundle)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX FIFO test')
    def test_special_file_is_rejected(self):
        os.mkfifo(self.bundle / 'fifo')
        with self.assertRaises(ValueError): release.check_tree(self.bundle)

    def test_stale_output_is_not_overwritten(self):
        dest = self.root / 'dist'
        dest.mkdir()
        (dest / 'keep').write_text('previous output')
        with self.assertRaises(ValueError): release.archive_bundle(self.bundle, dest, 'x64', 'a' * 40)
        self.assertEqual((dest / 'keep').read_text(), 'previous output')

    def test_archive_requires_full_revision_and_known_architecture(self):
        for arch, revision in (('x86', 'a' * 40), ('x64', 'abc123'), ('x64', '../bad')):
            with self.subTest(arch=arch, revision=revision), self.assertRaises(ValueError):
                release.archive_bundle(self.bundle, self.root / 'dist', arch, revision)

    def test_linkage_errors_fail(self):
        with patch.object(release, 'command', side_effect=['(NEEDED)', 'libmissing.so => not found']):
            with self.assertRaisesRegex(ValueError, 'Unresolved'):
                release.check_linkage([self.bundle / 'rustdesk'])
        with patch.object(release, 'command', side_effect=subprocess.CalledProcessError(1, 'readelf')):
            with self.assertRaises(subprocess.CalledProcessError):
                release.check_linkage([self.bundle / 'rustdesk'])

    def test_no_needed_entries_does_not_run_ldd(self):
        with patch.object(release, 'command', return_value='There is no dynamic section') as command:
            release.check_linkage([self.bundle / 'lib/libapp.so'])
            self.assertEqual(command.call_count, 1)

    def run_build(self, fail_at=None):
        destination = self.root / 'flutter/build/linux/x64/release/bundle'
        destination.parent.mkdir(parents=True)
        self.bundle.rename(destination)
        target = self.root / 'target/release/liblibrustdesk.so'
        target.parent.mkdir(parents=True)
        self.source.rename(target)
        (self.root / 'tools/.reports').mkdir(parents=True)
        calls = []

        def fake_command(args, log, *rest):
            calls.append(log)
            if log == fail_at:
                raise subprocess.CalledProcessError(9, args)
            if args[:2] == ['git', 'rev-parse']:
                return 'a' * 40
            return 'no dynamic dependencies'

        with patch.object(release, 'ROOT', self.root), \
             patch.object(release.platform, 'system', return_value='Linux'), \
             patch.object(release.platform, 'machine', return_value='x86_64'), \
             patch.object(release, 'command', side_effect=fake_command):
            release.build()
        return calls

    def test_build_orders_preflight_compilation_ffi_and_archive_checks(self):
        calls = self.run_build()
        self.assertLess(calls.index('linux-release-preflight.log'), calls.index('linux-release-cargo.log'))
        self.assertLess(calls.index('linux-release-cargo.log'), calls.index('linux-release-flutter.log'))
        self.assertLess(calls.index('linux-release-ffi.log'), calls.index('linux-release-manifest.log'))
        self.assertEqual(calls[-1], 'linux-release-verify.log')
        report = json.loads((self.root / 'dist/linux-x64-unsigned/validation.json').read_text())
        self.assertEqual(report['signature'], 'not-verified')
        self.assertEqual(report['gui_and_device_execution'], 'not-verified')

    def test_ffi_failure_cannot_create_a_release_archive(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_build('linux-release-ffi.log')
        self.assertFalse((self.root / 'dist').exists())

    def test_build_failure_cannot_create_a_release_archive(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_build('linux-release-cargo.log')
        self.assertFalse((self.root / 'dist').exists())

    def test_source_drift_cannot_create_a_release_archive(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_build('linux-release-source.log')
        self.assertFalse((self.root / 'dist').exists())

    def test_native_setup_retains_x64_and_adds_arm64(self):
        setup = (release.ROOT / 'tools/native/setup-linux.sh').read_text()
        self.assertIn('x86_64) triplet=x64-linux', setup)
        self.assertIn('aarch64) triplet=arm64-linux', setup)
        self.assertIn('"libyuv:$triplet"', setup)
        self.assertIn('installed/$triplet/lib/libyuv.a', setup)

    def test_native_ci_is_read_only_and_keeps_debug_checks(self):
        root = release.ROOT
        workflow = yaml.safe_load((root / '.github/workflows/linux-release.yml').read_text())
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        matrix = workflow['jobs']['linux-release']['strategy']['matrix']['include']
        self.assertEqual({m['runner'] for m in matrix}, {'ubuntu-24.04', 'ubuntu-24.04-arm'})
        text = (root / '.github/workflows/linux-release.yml').read_text()
        self.assertNotIn('secrets.', text)
        self.assertNotIn('continue-on-error:', text)
        self.assertIn('python tools/ci_rust.py', text)
        self.assertIn('build-linux-bundle.sh', (root / '.github/workflows/flutter-validate.yml').read_text())


if __name__ == '__main__':
    unittest.main()
