"""Test XCArchive metadata and real tar safety with synthetic binary fixtures."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import package_ios as packager


class IosPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive_dir = self.root / 'flutter/build/ios/archive'
        self.archive = self.archive_dir / 'Runner.xcarchive'
        self.app = self.archive / 'Products/Applications/Runner.app'
        self.app.mkdir(parents=True)
        (self.app / 'Runner').write_bytes(b'synthetic executable')
        self.info = {'ApplicationProperties': {'ApplicationPath': 'Applications/Runner.app',
                                              'CFBundleIdentifier': 'com.carriez.flutterHbb'}}
        self.save_info()
        self.bundle = self.root / 'flutter/build/ios/iphoneos/Runner.app'
        self.bundle.mkdir(parents=True)
        (self.bundle / 'Runner').write_bytes(b'synthetic executable')
        (self.root / 'configs').mkdir()
        (self.root / 'configs/toolchain.json').write_text(json.dumps(
            {'rust': '1.98.1', 'ios': {'minimum': '15.0', 'sdk': '27.0'}}))
        self.revision = 'a' * 40
        self.reader = patch.object(packager, 'rust_llvm_nm', return_value=(Path('/fixture/llvm-nm'), {'llvm': '22.1.8'})).start()
        self.verifier = patch.object(packager, 'verify', return_value={'device_execution': 'not-verified'}).start()
        self.git = patch.object(packager.subprocess, 'check_output', return_value=self.revision + '\n').start()
        self.run = patch.object(packager.subprocess, 'run').start()
        self.addCleanup(patch.stopall)

    def save_info(self):
        (self.archive / 'Info.plist').write_bytes(plistlib.dumps(self.info))

    def test_regular_single_archive(self):
        self.assertEqual(packager.archive_application(self.archive_dir), (self.archive, self.app))

    def test_missing_or_multiple_archives_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'regular XCArchive output'):
            packager.archive_application(self.root / 'absent')
        (self.archive_dir / 'Other.xcarchive').mkdir()
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            packager.archive_application(self.archive_dir)

    def test_archive_path_and_identity_are_enforced(self):
        for key, value in [('ApplicationPath', '../../Runner.app'),
                           ('ApplicationPath', '/Applications/Runner.app'),
                           ('CFBundleIdentifier', 'other.application')]:
            original = self.info['ApplicationProperties'][key]
            self.info['ApplicationProperties'][key] = value
            self.save_info()
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                packager.archive_application(self.archive_dir)
            self.info['ApplicationProperties'][key] = original

    def test_invalid_or_missing_archive_metadata(self):
        path = self.archive / 'Info.plist'
        for data in (b'', b'not plist', plistlib.dumps([]), plistlib.dumps({}),
                     plistlib.dumps({'ApplicationProperties': []})):
            path.write_bytes(data)
            with self.subTest(data=data), self.assertRaises((ValueError, plistlib.InvalidFileException)):
                packager.archive_application(self.archive_dir)
        path.unlink()
        with self.assertRaises(ValueError):
            packager.archive_application(self.archive_dir)

    def test_missing_archived_application(self):
        (self.app / 'Runner').unlink()
        self.app.rmdir()
        with self.assertRaisesRegex(ValueError, 'archived Runner'):
            packager.archive_application(self.archive_dir)

    def test_symlinked_metadata_or_archive_are_rejected(self):
        real = self.root / 'Info.plist'
        (self.archive / 'Info.plist').rename(real)
        (self.archive / 'Info.plist').symlink_to(real)
        with self.assertRaises(ValueError):
            packager.archive_application(self.archive_dir)
        actual = self.root / 'actual.xcarchive'
        self.archive.rename(actual)
        self.archive.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(ValueError):
            packager.archive_application(self.archive_dir)

    def test_real_tar_preserves_relative_framework_links(self):
        framework = self.bundle / 'Frameworks/Test.framework'
        target = framework / 'Versions/A'
        target.mkdir(parents=True)
        (target / 'Test').write_bytes(b'framework')
        (framework / 'Test').symlink_to('Versions/A/Test')
        output = self.root / 'safe.tar.gz'
        packager.archive_tree(self.bundle, output)
        with tarfile.open(output) as archive:
            entry = archive.getmember('Runner.app/Frameworks/Test.framework/Test')
            self.assertTrue(entry.issym())
            self.assertEqual(entry.linkname, 'Versions/A/Test')
            self.assertEqual(archive.extractfile('Runner.app/Runner').read(), b'synthetic executable')

    def test_absolute_outside_and_dangling_links_are_rejected(self):
        other = self.root / 'outside'
        other.write_bytes(b'not part of the bundle')
        link = self.bundle / 'unsafe'
        for target in (str(other), '../../../../../../outside', 'missing'):
            link.symlink_to(target)
            destination = self.root / 'bad.tar.gz'
            with self.subTest(target=target), self.assertRaises((ValueError, OSError)):
                packager.archive_tree(self.bundle, destination)
            self.assertFalse(destination.exists())
            link.unlink()

    def test_empty_source_and_existing_tar_are_rejected(self):
        empty = self.root / 'empty'
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, 'empty'):
            packager.archive_tree(empty, self.root / 'empty.tar.gz')
        output = self.root / 'exists.tar.gz'
        output.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            packager.archive_tree(self.bundle, output)
        self.assertEqual(output.read_bytes(), b'preserve')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX special-file test')
    def test_special_files_are_rejected(self):
        os.mkfifo(self.bundle / 'pipe')
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            packager.archive_tree(self.bundle, self.root / 'bad.tar.gz')

    def test_package_revalidates_both_apps_and_binds_report_to_revision(self):
        output = packager.package(self.root)
        apps = [c.args[0] for c in self.verifier.call_args_list]
        self.assertEqual(apps, [self.bundle, self.app])
        self.assertTrue(all(c.kwargs['symbol_tool'] == Path('/fixture/llvm-nm') for c in self.verifier.call_args_list))
        report = json.loads((output / 'build-profile.json').read_text())
        self.assertEqual(report['revision'], self.revision)
        self.assertEqual(report['ipa_export'], 'not-performed')
        self.assertEqual(report['signing'], 'not-performed')
        self.assertEqual(report['device_execution'], 'not-verified')
        self.assertEqual(len(list(output.glob('*.tar.gz'))), 2)
        self.assertEqual([c.args[0][2] for c in self.run.call_args_list], ['manifest', 'verify'])
        self.assertTrue(all(c.kwargs['check'] for c in self.run.call_args_list))

    def test_failed_archive_validation_does_not_create_artifacts(self):
        self.verifier.side_effect = [{}, ValueError('missing archived symbol')]
        with self.assertRaisesRegex(ValueError, 'archived symbol'):
            packager.package(self.root)
        self.assertFalse((self.root / 'dist').exists())
        self.run.assert_not_called()

    def test_incomplete_source_revision_is_rejected(self):
        self.git.return_value = 'short\n'
        with self.assertRaisesRegex(ValueError, 'complete source'):
            packager.package(self.root)
        self.assertFalse((self.root / 'dist').exists())

    def test_existing_artifact_directory_is_not_overwritten(self):
        output = self.root / 'dist/ios-arm64-unsigned'
        output.mkdir(parents=True)
        marker = output / 'keep'
        marker.write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'fresh'):
            packager.package(self.root)
        self.assertEqual(marker.read_text(), 'preserve')
        self.reader.assert_not_called()

    def test_manifest_failure_prevents_success(self):
        self.run.side_effect = subprocess.CalledProcessError(9, ['manifest'])
        with self.assertRaises(subprocess.CalledProcessError):
            packager.package(self.root)


class IosReleaseEntryTests(unittest.TestCase):
    def test_full_matrix_uses_the_canonical_read_only_ios_workflow(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/flutter-build.yml').read_text())
        ios = workflow['jobs']['build-rustdesk-ios']
        self.assertEqual(ios, {'needs': ['generate-bridge'],
                              'uses': './.github/workflows/ios-native.yml',
                              'permissions': {'contents': 'read'}})

    def test_native_workflow_preserves_static_library_and_bundle_artifacts(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/ios-native.yml').read_text())
        self.assertIn('${{ github.workflow }}', workflow['concurrency']['group'])
        steps = workflow['jobs']['ios']['steps']
        artifacts = [s['with'] for s in steps if s.get('uses', '').startswith('actions/upload-artifact@')]
        self.assertTrue(any(s['name'] == 'liblibrustdesk.a' for s in artifacts))
        self.assertTrue(any(s['path'] == 'dist/ios-arm64-unsigned/' for s in artifacts))
        self.assertTrue(all(s['if-no-files-found'] == 'error' for s in artifacts))
        self.assertNotIn('secrets.', str(workflow))

    def test_build_and_archive_use_locked_unsigned_commands_before_packaging(self):
        build = (ROOT / 'tools/native/build-ios.sh').read_text()
        app = build.index('flutter build ios --release --no-codesign --no-pub')
        archive = build.index('flutter build ipa --release --no-codesign --no-pub')
        unchanged = build.index('git diff --exit-code HEAD')
        package = build.index('python tools/package_ios.py')
        self.assertLess(app, archive)
        self.assertLess(archive, unchanged)
        self.assertLess(unchanged, package)
        self.assertIn('Use a fresh XCArchive output directory.', build)
        self.assertIn('set -euo pipefail', build)


if __name__ == '__main__':
    unittest.main()
