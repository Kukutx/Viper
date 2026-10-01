from pathlib import Path
import ast
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linux_deb as deb
from test_linux_release import elf

ROOT = deb.ROOT


class DebianTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / 'bundle'
        (self.bundle / 'lib').mkdir(parents=True)
        (self.bundle / 'data/flutter_assets').mkdir(parents=True)
        for name in ('rustdesk', 'lib/librustdesk.so', 'lib/libflutter_linux_gtk.so', 'lib/libapp.so'):
            (self.bundle / name).write_bytes(elf())
        (self.bundle / 'rustdesk').chmod(0o755)
        (self.bundle / 'data/icudtl.dat').write_bytes(b'icu')
        (self.bundle / 'data/flutter_assets/file with space').write_bytes(b'asset')
        self.bundle.chmod(0o755)
        for relative in (*deb.RESOURCES, *['res/DEBIAN/' + s for s in deb.SCRIPTS], 'configs/linux-deb-control.in'):
            source = ROOT / relative
            dest = self.root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)

    def stage(self):
        directory = self.root / 'stage'
        with patch.object(deb, 'ROOT', self.root):
            deb.stage(self.bundle, directory)
        return directory

    def tar(self, tree, change=None):
        archive = self.root / 'test.tar'
        with tarfile.open(archive, 'w') as tar:
            for name in deb.tree_manifest(tree):
                member = tar.gettarinfo(str(tree / name), arcname='.' if not name else './' + name)
                member.uid = member.gid = 0
                member.uname = member.gname = 'root'
                if change:
                    change(member)
                with (tree / name).open('rb') if member.isreg() else io.BytesIO() as stream:
                    tar.addfile(member, stream if member.isreg() else None)
        return archive

    def test_template_preserves_original_metadata_and_runtime_requirements(self):
        source = ast.parse((ROOT / 'build.py').read_text())
        method = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'generate_control_file')
        calls = []
        class Sink(io.StringIO):
            def close(s): calls.append(s.getvalue()); super().close()
        namespace = {'Path': Path, 'REPO_ROOT': str(ROOT), 'system2': lambda _: None,
                     'get_deb_arch': lambda: 'arm64', 'get_deb_extra_depends': lambda: ', libatomic1',
                     'open': lambda *_: Sink()}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'build.py', 'exec'), namespace)
        namespace['generate_control_file']('1.5.0')
        template = (ROOT / 'configs/linux-deb-control.in').read_text()
        self.assertEqual(calls, [template % ('1.5.0', 'arm64', ', libatomic1')])
        text = deb.control_text('1.5.0', 'x64', 'libc6 (>= 2.38)', 100, 'a' * 40)
        for line in (template % ('1.5.0', 'amd64', '')).strip().splitlines():
            self.assertIn(line, text)
        self.assertIn('X-Viper-Source-Revision: ' + 'a' * 40, text)

    def test_bad_control_values_are_rejected(self):
        for position, values in ((0, ['1.5.0-rc1', '../bad', '1\nPackage: other']),
                                 (1, ['x86', 'amd64', 'arm64\n']),
                                 (2, ['', 'libc6\nPackage: bad', '${shlibs:Depends}']),
                                 (3, [0, -1, True]), (4, ['abc', 'a' * 39, 'g' * 40])):
            for value in values:
                args = ['1.5.0', 'x64', 'libc6 (>= 2.38)', 10, 'a' * 40]
                args[position] = value
                with self.subTest(position=position, value=value), self.assertRaises(ValueError):
                    deb.control_text(*args)

    def test_both_architectures_have_correct_control(self):
        for arch, native in deb.DEB_ARCH.items():
            self.assertIn('Architecture: ' + native, deb.control_text('1.5.0', arch, 'libc6', 1, 'a' * 40))

    def test_original_scripts_resources_and_license_are_preserved(self):
        tree = self.stage()
        for source, path in deb.RESOURCES.items():
            self.assertEqual((tree / path).read_bytes(), (ROOT / source).read_bytes())
        for script in deb.SCRIPTS:
            self.assertEqual((tree / 'DEBIAN' / script).read_bytes(), (ROOT / 'res/DEBIAN' / script).read_bytes())
            self.assertEqual((tree / 'DEBIAN' / script).stat().st_mode & 0o7777, 0o755)
        self.assertEqual((tree / 'usr/share/rustdesk/files/polkit').read_bytes(), b'#!/bin/sh\n')
        self.assertFalse((tree / 'usr/bin/rustdesk').exists())

    def test_old_stage_is_preserved_and_rejected(self):
        self.stage()
        with self.assertRaises(ValueError): self.stage()
        self.assertTrue((self.root / 'stage/usr/share/rustdesk/rustdesk').is_file())

    def test_missing_or_symlinked_resources_are_rejected(self):
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                path = self.root / 'res/rustdesk.service'
                path.unlink()
                if symlink: path.symlink_to('rustdesk.desktop')
                with patch.object(deb, 'ROOT', self.root), self.assertRaises(ValueError):
                    deb.stage(self.bundle, self.root / ('stage-' + str(symlink)))
                if path.is_symlink(): path.unlink()
                shutil.copyfile(ROOT / 'res/rustdesk.service', path)

    def test_resource_collision_is_rejected(self):
        (self.bundle / 'files/systemd').mkdir(parents=True)
        (self.bundle / 'files/systemd/rustdesk.service').write_text('unexpected')
        with self.assertRaises(ValueError): self.stage()

    def test_privileged_world_writable_and_control_paths_are_rejected(self):
        binary = self.bundle / 'rustdesk'
        for mode in (0o4755, 0o2755, 0o1755, 0o777):
            binary.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(ValueError): deb.tree_manifest(self.bundle)
        binary.chmod(0o755)
        (self.bundle / 'name\tbad').write_text('bad')
        with self.assertRaises(ValueError): deb.tree_manifest(self.bundle)

    def test_tar_roundtrip_and_relative_link(self):
        (self.bundle / 'lib/alias.so').symlink_to('librustdesk.so')
        tree = self.stage()
        deb.verify_tar(self.tar(tree), deb.tree_manifest(tree))

    def test_tar_ownership_content_type_path_and_mode_drift_are_rejected(self):
        tree = self.stage()
        mutations = [lambda m: setattr(m, 'uid', 1001), lambda m: setattr(m, 'gid', 1001),
                     lambda m: setattr(m, 'mode', 0o777), lambda m: setattr(m, 'name', '../escape'),
                     lambda m: setattr(m, 'name', '/absolute'), lambda m: setattr(m, 'type', tarfile.FIFOTYPE)]
        expected = deb.tree_manifest(tree)
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                deb.verify_tar(self.tar(tree, mutate), expected)
        archive = self.tar(tree)
        (tree / 'usr/share/rustdesk/rustdesk').write_bytes(b'different')
        with self.assertRaises(ValueError): deb.verify_tar(archive, deb.tree_manifest(tree))

    def test_tar_duplicates_extra_and_missing_entries_are_rejected(self):
        tree = self.stage()
        expected = deb.tree_manifest(tree)
        archive = self.tar(tree)
        with tarfile.open(archive, 'a') as tar:
            tar.add(tree / 'usr/share/rustdesk/rustdesk', arcname='./usr/share/rustdesk/rustdesk')
        with self.assertRaisesRegex(ValueError, 'Duplicate'): deb.verify_tar(archive, expected)
        archive = self.tar(tree)
        with tarfile.open(archive, 'a') as tar:
            member = tarfile.TarInfo('extra'); member.mode = 0o644
            tar.addfile(member, io.BytesIO())
        with self.assertRaises(ValueError): deb.verify_tar(archive, expected)
        archive = self.tar(tree)
        expected['missing'] = ('file', 0o644, 'a' * 64)
        with self.assertRaises(ValueError): deb.verify_tar(archive, expected)

    def test_manifest_capture_failure_is_fatal(self):
        with patch.object(deb.subprocess, 'run', side_effect=subprocess.CalledProcessError(2, 'dpkg-deb')):
            with self.assertRaises(subprocess.CalledProcessError):
                deb.capture_tar(self.root / 'missing.deb', '--fsys-tarfile', self.root / 'out.tar')

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian archive tool required')
    def test_real_rootless_deb_roundtrip_including_all_control_scripts(self):
        tree = self.stage()
        control = tree / 'DEBIAN'
        (control / 'control').write_text(deb.control_text('1.5.0', 'x64', 'libc6', 100, 'a' * 40))
        payload = {key: value for key, value in deb.tree_manifest(tree).items()
                   if key != 'DEBIAN' and not key.startswith('DEBIAN/')}
        package = self.root / 'actual.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(tree), str(package)],
                       stdout=subprocess.PIPE, check=True)
        for argument, expected in (('--fsys-tarfile', payload), ('--ctrl-tarfile', deb.tree_manifest(control))):
            tar = self.root / (argument[2:] + '.tar')
            deb.capture_tar(package, argument, tar)
            deb.verify_tar(tar, expected)

    def test_restored_icons_are_the_exact_upstream_blobs(self):
        for name, sha in (('128x128@2x.png', '89abf23a68ae85d0f28cdb90d1b08ad36db9d2c8'),
                          ('scalable.svg', '50cab67a3e0369ed1fd3d036f5b485f9f3ca9b76')):
            data = (ROOT / 'res' / name).read_bytes()
            self.assertEqual(hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest(), sha)

    def test_root_permissions_cannot_bypass_the_manifest(self):
        self.bundle.chmod(0o777)
        with self.assertRaises(ValueError): deb.tree_manifest(self.bundle)

    def pipeline(self, fail=None, dependency_output='shlibs:Depends=libc6 (>= 2.38)\n'):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.revision = 'a' * 40
        bundle = self.root / 'flutter/build/linux/x64/release/bundle'
        bundle.parent.mkdir(parents=True)
        self.bundle.rename(bundle)
        self.bundle = bundle
        self.native = self.root / 'target/release/liblibrustdesk.so'
        self.native.parent.mkdir(parents=True)
        shutil.copyfile(bundle / 'lib/librustdesk.so', self.native)
        (self.root / 'tools/.reports').mkdir(parents=True)
        (self.root / 'Cargo.toml').write_text('[package]\nversion = "1.5.0"\n')
        self.previous = self.root / 'dist/linux-x64-unsigned'
        archive = deb.release.archive_bundle(bundle, self.previous, 'x64', self.revision)
        self.report = {'revision': self.revision, 'architecture': 'x64', 'build_mode': 'release',
                       'features': ['flutter', 'linux-pkg-config'], 'ffi': 'passed',
                       'rust_library_sha256': deb.release.digest(self.native),
                       'archive_sha256': deb.release.digest(archive)}
        self.save_evidence()
        self.output = self.root / 'dist/linux-x64-deb-unsigned'
        self.commands = []
        def command(args, log, cwd=None, env=None):
            self.commands.append((args, log, env))
            if log == fail:
                raise subprocess.CalledProcessError(1, args)
            if args[:2] == ['git', 'rev-parse']: return self.revision + '\n'
            if args[:2] == ['git', 'show']: return '1790850000\n'
            if args[:2] == ['dpkg', '--print-architecture']: return 'amd64\n'
            if args[0] == 'dpkg-shlibdeps': return dependency_output
            if args[0] == 'flutter' or args[:2] == ['git', 'diff']: return ''
            self.assertEqual(args[0], 'dpkg-deb')
            return subprocess.run(args, cwd=cwd, env=env, check=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True).stdout
        stack.enter_context(patch.object(deb, 'ROOT', self.root))
        stack.enter_context(patch.object(deb.release, 'ROOT', self.root))
        stack.enter_context(patch.object(deb.release, 'command', side_effect=command))
        stack.enter_context(patch.object(deb.platform, 'system', return_value='Linux'))
        stack.enter_context(patch.object(deb.platform, 'machine', return_value='x86_64'))

    def save_evidence(self):
        (self.previous / 'validation.json').write_text(json.dumps(self.report))
        (self.previous / 'release-manifest.json').write_text(
            json.dumps(deb.viper.make_manifest(self.previous, self.revision)))

    def test_stale_or_wrong_release_evidence_cannot_be_packaged(self):
        self.pipeline()
        valid = self.report.copy()
        for key, value in (('revision', 'b' * 40), ('architecture', 'arm64'), ('build_mode', 'debug'),
                           ('ffi', 'not-verified'), ('features', ['flutter', 'hwcodec'])):
            self.report = {**valid, key: value}; self.save_evidence()
            with self.subTest(key=key), self.assertRaises(ValueError): deb.package()
            self.assertFalse(self.output.exists())
        self.assertFalse(any(args[0] == 'dpkg-deb' for args, _, _ in self.commands))

    def test_report_and_archive_tampering_are_not_accepted(self):
        self.pipeline()
        (self.previous / 'validation.json').write_text('{}')
        with self.assertRaises(ValueError): deb.package()
        self.assertFalse(self.output.exists())
        self.save_evidence()
        self.report['archive_sha256'] = '0' * 64; self.save_evidence()
        with self.assertRaisesRegex(ValueError, 'archive digest'): deb.package()

    def test_changed_rust_identity_cannot_be_packaged(self):
        self.pipeline()
        self.report['rust_library_sha256'] = '0' * 64; self.save_evidence()
        with self.assertRaisesRegex(ValueError, 'wrong Rust library'): deb.package()
        self.assertFalse(self.output.exists())

    def test_stale_output_is_not_deleted_or_replaced(self):
        self.pipeline()
        self.output.mkdir(); (self.output / 'keep').write_text('user file')
        with self.assertRaisesRegex(ValueError, 'overwrite'): deb.package()
        self.assertEqual((self.output / 'keep').read_text(), 'user file')

    def test_drm_payload_cannot_be_relabelled_as_stock(self):
        self.pipeline()
        (self.bundle / 'lib/libdrmtap.so.0').write_bytes(elf())
        with self.assertRaisesRegex(ValueError, 'DRM'): deb.package()
        self.assertFalse(self.output.exists())

    def test_dependency_resolution_failure_cannot_create_artifacts(self):
        self.pipeline(fail='linux-deb-shlibdeps.log')
        with self.assertRaises(subprocess.CalledProcessError): deb.package()
        self.assertFalse(self.output.exists())

    def test_missing_dependency_result_cannot_create_artifacts(self):
        self.pipeline(dependency_output='warning without result\n')
        with self.assertRaisesRegex(ValueError, 'system library dependencies'): deb.package()
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian archive tool required')
    def test_package_pipeline_revalidates_extracted_files_before_mocked_ffi(self):
        self.pipeline()
        deb.package()
        result = json.loads((self.output / 'validation.json').read_text())
        self.assertEqual(result['signature'], 'not-verified')
        self.assertEqual(result['installed_service_and_gui'], 'not-verified')
        self.assertEqual(result['repeated_serialization'], 'identical')
        self.assertEqual(result['revision'], self.revision)
        deb.viper.verify_manifest(self.output)
        names = [log for _, log, _ in self.commands]
        self.assertLess(names.index('linux-deb-extract.log'), names.index('linux-deb-ffi.log'))
        ffi = next(env for _, log, env in self.commands if log == 'linux-deb-ffi.log')
        self.assertIn('/extracted/usr/share/rustdesk/lib/librustdesk.so', ffi['VIPER_NATIVE_LIBRARY'])
        self.assertEqual(names.count('linux-deb-build-0.log'), 1)
        self.assertEqual(names.count('linux-deb-build-1.log'), 1)

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian archive tool required')
    def test_failed_extracted_ffi_never_publishes_package(self):
        self.pipeline(fail='linux-deb-ffi.log')
        with self.assertRaises(subprocess.CalledProcessError): deb.package()
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian archive tool required')
    def test_failed_source_parity_never_publishes_package(self):
        self.pipeline(fail='linux-deb-source.log')
        with self.assertRaises(subprocess.CalledProcessError): deb.package()
        self.assertFalse(self.output.exists())

    def test_archive_creation_failure_never_publishes_package(self):
        self.pipeline(fail='linux-deb-build-0.log')
        with self.assertRaises(subprocess.CalledProcessError): deb.package()
        self.assertFalse(self.output.exists())

    def test_workflow_cannot_upload_failed_deb_or_access_signing_credentials(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/linux-release.yml').read_text())
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        steps = workflow['jobs']['linux-release']['steps']
        indexes = [i for i, s in enumerate(steps) if s.get('run') == 'python tools/linux_deb.py']
        self.assertEqual(len(indexes), 1)
        index = indexes[0]
        self.assertNotIn('if', steps[index])
        self.assertNotIn('continue-on-error', steps[index])
        self.assertEqual(steps[index - 1]['run'], 'python tools/linux_release.py')
        upload = [s for s in steps[index + 1:] if 'deb-unsigned' in s.get('with', {}).get('name', '')]
        self.assertEqual(len(upload), 1)
        self.assertNotIn('if', upload[0])
        self.assertEqual(upload[0]['with']['if-no-files-found'], 'error')
        self.assertNotIn('secrets.', str(workflow))
        self.assertNotIn('--ignore-missing-info', (ROOT / 'tools/linux_deb.py').read_text())
        self.assertNotIn('--no-check', (ROOT / 'tools/linux_deb.py').read_text())


if __name__ == '__main__':
    unittest.main()
