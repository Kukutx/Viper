"""Regression tests for common build configuration and failure propagation."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import build_toolchain
import bridge_source
import prepare_flutter


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'configs').mkdir()
        (self.root / '.github/workflows').mkdir(parents=True)
        self.data = {'rust':'1.98.1','flutter':'3.47.5','cmake':'4.4.3',
                     'vcpkg':{'revision':'a'*40}}
        (self.root / 'configs/toolchain.json').write_text(json.dumps(self.data))
        self.workflow = self.root / '.github/workflows/flutter-build.yml'
        self.workflow.write_text('env:\n'+''.join(f'  {key}: "old"\n' for key in build_toolchain.MIRRORS))

    def test_writes_are_idempotent_and_checked(self):
        build_toolchain.sync(self.root,True)
        first = self.workflow.read_bytes()
        build_toolchain.sync(self.root)
        build_toolchain.sync(self.root,True)
        self.assertEqual(first,self.workflow.read_bytes())

    def test_drift_fails_without_modifying_the_file(self):
        first=self.workflow.read_bytes()
        with self.assertRaisesRegex(ValueError,'drift'):
            build_toolchain.sync(self.root)
        self.assertEqual(first,self.workflow.read_bytes())

    def test_duplicate_mirror_is_rejected(self):
        self.workflow.write_text(self.workflow.read_text()+'  RUST_VERSION: "other"\n')
        with self.assertRaisesRegex(ValueError,'Expected one'):
            build_toolchain.sync(self.root,True)

    def test_missing_mirror_is_rejected(self):
        self.workflow.write_text('env:\n')
        with self.assertRaisesRegex(ValueError,'Expected one'):
            build_toolchain.sync(self.root,True)

    def test_unsafe_scalar_is_rejected(self):
        for value in ('1.0; echo bad', 'version\nKEY=bad', {'nested':True}, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_toolchain.value({'version':value},'version')

    def test_nested_scalar(self):
        self.assertEqual(build_toolchain.value(self.data,'vcpkg.revision'),'a'*40)

    def test_repository_mirrors(self):
        build_toolchain.sync(ROOT)


class SourceGeneratorTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        (self.root/'configs').mkdir()
        self.config=self.root/'configs/toolchain.json'
        self.config.write_text(json.dumps({'flutter_rust_bridge':{'version':'2.13.0'}}))

    def test_exact_version_and_lockfile_are_required(self):
        with patch.object(bridge_source.subprocess,'run') as run, \
             patch.object(bridge_source.subprocess,'check_output',return_value='flutter_rust_bridge_codegen 2.13.0\n'):
            result=bridge_source.install(self.root)
        self.assertIn('--locked',run.call_args.args[0])
        self.assertIn('=2.13.0',run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs['cwd'],self.root)
        self.assertTrue(run.call_args.kwargs['check'])
        self.assertEqual(result.parent,self.root/'.tools/frb-source/bin')

    def test_compile_failure_does_not_download_a_fallback(self):
        with patch.object(bridge_source.subprocess,'run',side_effect=subprocess.CalledProcessError(101,['cargo'])), \
             patch.object(bridge_source.subprocess,'check_output') as version:
            with self.assertRaises(subprocess.CalledProcessError):
                bridge_source.install(self.root)
            version.assert_not_called()

    def test_wrong_built_version_is_rejected(self):
        with patch.object(bridge_source.subprocess,'run'), \
             patch.object(bridge_source.subprocess,'check_output',return_value='codegen 1.80.1'):
            with self.assertRaisesRegex(ValueError,'mismatch'):
                bridge_source.install(self.root)

    def test_unpinned_version_is_rejected(self):
        for version in ('^2.13.0','2.13.0-beta.1','latest'):
            self.config.write_text(json.dumps({'flutter_rust_bridge':{'version':version}}))
            with self.subTest(version=version), self.assertRaises(ValueError):
                bridge_source.install(self.root)

    def test_symlink_tool_directory_is_rejected(self):
        (self.root/'other').mkdir()
        (self.root/'.tools').symlink_to(self.root/'other',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):
            bridge_source.install(self.root)


class PackagingPreflightTests(unittest.TestCase):
    def test_all_gates_run_before_locked_resolution(self):
        with patch.object(prepare_flutter.subprocess,'run') as run, \
             patch.object(prepare_flutter.shutil,'which',return_value=r'C:\SDK with spaces\flutter.bat'):
            prepare_flutter.prepare(ROOT)
        commands=[call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands),5)
        self.assertTrue(commands[0][1].endswith('flutter_sdk.py'))
        self.assertTrue(commands[1][1].endswith('bridge.py'))
        self.assertTrue(commands[2][1].endswith('check_bridge_outputs.py'))
        self.assertEqual(commands[3],[r'C:\SDK with spaces\flutter.bat','pub','get','--enforce-lockfile'])
        self.assertIn('HEAD',commands[4])
        self.assertTrue(all(call.kwargs['check'] for call in run.call_args_list))

    def test_every_gate_failure_stops_packaging(self):
        for index in range(5):
            with self.subTest(gate=index), \
                 patch.object(prepare_flutter.shutil,'which',return_value='flutter'), \
                 patch.object(prepare_flutter.subprocess,'run',side_effect=[None]*index+[subprocess.CalledProcessError(17,['tool'])]) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    prepare_flutter.prepare(ROOT)
                self.assertEqual(run.call_count,index+1)

    def test_build_entries_preflight_even_when_skipping_cargo(self):
        tree=ast.parse((ROOT/'build.py').read_text())
        entries=['build_flutter_deb','build_flutter_dmg','build_flutter_arch_manjaro','build_flutter_windows']
        for node in tree.body:
            if isinstance(node,ast.FunctionDef) and node.name in entries:
                with self.subTest(entry=node.name):
                    self.assertIsInstance(node.body[0],ast.Expr)
                    self.assertEqual(ast.unparse(node.body[0]),'prepare_flutter_build()')
                entries.remove(node.name)
        self.assertFalse(entries)

    def test_print_features_does_not_run_packaging_or_downloads(self):
        result=subprocess.run([sys.executable,str(ROOT/'build.py'),'--flutter','--drm','--print-features'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('drm',result.stdout)
        self.assertIn('flutter',result.stdout)
        self.assertNotIn('Verified',result.stdout)


class BuildMatrixTests(unittest.TestCase):
    def setUp(self):
        self.workflow=yaml.safe_load((ROOT/'.github/workflows/flutter-build.yml').read_text())
        self.jobs=self.workflow['jobs']

    def test_all_original_platform_jobs_are_preserved(self):
        self.assertEqual(set(self.jobs),{'generate-sbom','generate-bridge','build-RustDeskTempTopMostWindow',
            'build-for-windows-flutter','build-for-windows-sciter','build-rustdesk-ios','build-for-macOS',
            'publish_unsigned','build-rustdesk-android','build-rustdesk-android-universal',
            'build-rustdesk-linux','build-rustdesk-linux-drm','build-rustdesk-linux-sciter','build-appimage','build-flatpak'})

    def test_flutter_jobs_use_one_sdk(self):
        for job in self.jobs.values():
            for step in job.get('steps',[]):
                if step.get('uses','').startswith('subosito/flutter-action@'):
                    self.assertEqual(step['with']['flutter-version'],'${{ env.FLUTTER_VERSION }}')
        for old in ('MAC_RUST_VERSION','ANDROID_FLUTTER_VERSION','FLUTTER_WINDOWS_ARM_VERSION','FLUTTER_ELINUX_VERSION'):
            self.assertNotIn(old,self.workflow['env'])

    def test_linux_builds_are_native_and_keep_both_architectures(self):
        matrix=self.jobs['build-rustdesk-linux']['strategy']['matrix']['job']
        self.assertEqual({x['arch'] for x in matrix},{'x86_64','aarch64'})
        # PyYAML's YAML 1.1 parser interprets the unquoted key `on` as True.
        self.assertEqual({x.get('on',x.get(True)) for x in matrix},{'ubuntu-24.04','ubuntu-24.04-arm'})
        for job in ('build-rustdesk-linux','build-rustdesk-linux-drm'):
            text=str(self.jobs[job])
            for old in ('run-on-arch-action','flutter-elinux','libclang-10','llvm-10','safe.directory "*"'):
                self.assertNotIn(old,text)
            self.assertIn('tools/native/install-flutter.sh',text)

    def test_drm_regressions_and_packaged_provenance_are_not_removed(self):
        text=str(self.jobs['build-rustdesk-linux-drm'])
        for required in ('drm_capturer_tests','ipc::test','hotspot_provenance_tests','hotspot_guess_tests',
                         'selected no tests','libdrmtap.so.0','--drm --hwcodec --unix-file-copy-paste'):
            self.assertIn(required,text)

    def test_retired_source_and_sdk_patch_steps_are_gone(self):
        for job in self.jobs.values():
            for step in job.get('steps',[]):
                self.assertNotIn(step.get('name'),('Patch flutter','Patch RustDesk sources for Flutter 3.44 (arm64)',
                                  'Replace engine with rustdesk custom flutter engine','Disable rust bridge build'))
        text=(ROOT/'build.py').read_text()
        self.assertNotIn('generated_bridge.dart',text)
        self.assertNotIn('ffi_bindgen_function_refactor',text)

    def test_bridge_consumers_use_the_single_current_artifact(self):
        for job in self.jobs.values():
            for step in job.get('steps',[]):
                if step.get('name')=='Restore bridge files':
                    self.assertEqual(step['with']['name'],'bridge-artifact')

    def test_fdroid_keeps_all_abis_without_the_retired_bridge_path(self):
        text=(ROOT/'flutter/build_fdroid.sh').read_text()
        for abi in ('arm64-v8a)','armeabi-v7a)','x86_64)','x86)'):
            self.assertIn(abi,text)
        for retired in ('FLUTTER_BRIDGE_VERSION','generated_bridge.dart','--features "uuid"','git clean -dffx','flutter_3.24.4_dropdown'):
            self.assertNotIn(retired,text)
        self.assertIn('tools/bridge.py generate --from-source',text)
        self.assertIn('git apply res/fdroid/patches/*.patch',text)
        self.assertIn('flutter pub get --enforce-lockfile',text)

    def test_preview_runner_label_is_explicit_not_an_ignored_error(self):
        config=yaml.safe_load((ROOT/'.github/actionlint.yaml').read_text())
        self.assertEqual(config,{'self-hosted-runner':{'labels':['xcode-27']}})


if __name__=='__main__':
    unittest.main()
