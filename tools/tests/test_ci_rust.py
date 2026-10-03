from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_rust


class CiRustTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'configs').mkdir()
        (self.root / 'configs/toolchain.json').write_text('{"rust": "1.98.1"}')
        (self.root / 'rust-toolchain.toml').write_text(
            '[toolchain]\nchannel="1.98.1"\nprofile="minimal"\ncomponents=["rustfmt","clippy"]\n')
        self.runner = self.root / 'runner with spaces'
        self.runner.mkdir()
        self.output = self.root / 'github-env'
        self.output.write_text('EXISTING=value\n')
        self.global_home = self.root / 'global-rust'
        self.global_home.mkdir()
        (self.global_home / 'do-not-touch').write_text('user files')
        self.env = {'GITHUB_ACTIONS': 'true', 'RUNNER_TEMP': str(self.runner),
                    'GITHUB_ENV': str(self.output), 'RUSTUP_HOME': str(self.global_home),
                    'CARGO_HOME': str(self.root / 'user-cargo'), 'PATH': os.environ['PATH']}
        self.calls = []
        self.fail = None
        self.wrong_version = False
        self.escaped_tool = False
        self.empty_tool = False
        self.missing_tool = False
        self.timeout = False

    def fake_run(self, command, **options):
        self.calls.append((command, options))
        home = Path(options['env']['RUSTUP_HOME'])
        self.assertNotEqual(home, self.global_home)
        self.assertEqual(options['env']['CARGO_HOME'], self.env['CARGO_HOME'])
        if self.timeout:
            raise subprocess.TimeoutExpired(command, 600)
        if self.fail == command[1]:
            return subprocess.CompletedProcess(command, 7, 'deliberate failure\n')
        if command[1] == 'which':
            tool = home / 'toolchains/pinned/bin' / command[-1]
            tool.parent.mkdir(parents=True, exist_ok=True)
            if self.escaped_tool:
                tool = self.global_home / 'do-not-touch'
            elif not self.missing_tool:
                tool.touch()
            text = str(tool)
        elif command[-1] == '-vV':
            text = 'rustc\nrelease: ' + ('1.99.0' if self.wrong_version else '1.98.1')
        elif self.empty_tool and command[-2] == 'rustfmt':
            text = ''
        else:
            text = 'tool version\n'
        return subprocess.CompletedProcess(command, 0, text)

    def invoke(self):
        with patch('ci_rust.shutil.which', return_value='/usr/bin/rustup'), \
             patch('ci_rust.subprocess.run', side_effect=self.fake_run):
            return ci_rust.bootstrap(self.root, self.env)

    def assert_no_export(self):
        self.assertEqual(self.output.read_text(), 'EXISTING=value\n')
        self.assertEqual((self.global_home / 'do-not-touch').read_text(), 'user files')

    def test_exact_components_and_isolated_home(self):
        report = self.invoke()
        self.assertEqual(report['rust'], '1.98.1')
        install = self.calls[0][0]
        self.assertIn('rustfmt,clippy', install)
        self.assertIn('--no-self-update', install)
        self.assertTrue(Path(report['rustup_home']).is_relative_to(self.runner))
        self.assertEqual(self.env['RUSTUP_HOME'], str(self.global_home))
        self.assertIn('RUSTUP_TOOLCHAIN=1.98.1\n', self.output.read_text())
        self.assertTrue((self.root / 'tools/.reports/ci-rust.json').is_file())

    def test_non_ci_is_rejected_before_install(self):
        self.env['GITHUB_ACTIONS'] = 'false'
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.calls, [])
        self.assert_no_export()

    def test_missing_runner_directory(self):
        self.env['RUNNER_TEMP'] = str(self.root / 'missing')
        with self.assertRaises(ValueError): self.invoke()
        self.assert_no_export()

    def test_relative_runner_directory(self):
        self.env['RUNNER_TEMP'] = 'relative'
        with self.assertRaises(ValueError): self.invoke()
        self.assert_no_export()

    def test_missing_environment_file(self):
        self.output.unlink()
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.calls, [])

    def test_symlinked_directory(self):
        link = self.root / 'link'
        link.symlink_to(self.runner, target_is_directory=True)
        self.env['RUNNER_TEMP'] = str(link)
        with self.assertRaises(ValueError): self.invoke()
        self.assert_no_export()

    def test_symlinked_environment_file(self):
        link = self.root / 'link'
        link.symlink_to(self.output)
        self.env['GITHUB_ENV'] = str(link)
        with self.assertRaises(ValueError): self.invoke()
        self.assert_no_export()

    def test_unpinned_or_drifted_toolchain(self):
        for version in ('stable', 'nightly', '1.98.2'):
            with self.subTest(version=version):
                (self.root / 'configs/toolchain.json').write_text(json.dumps({'rust': version}))
                with self.assertRaises(ValueError): self.invoke()
                self.assert_no_export()

    def test_clippy_cannot_be_removed(self):
        path = self.root / 'rust-toolchain.toml'
        path.write_text(path.read_text().replace(',"clippy"', ''))
        with self.assertRaises(ValueError): self.invoke()
        self.assert_no_export()

    def test_missing_rustup(self):
        with patch('ci_rust.shutil.which', return_value=None), self.assertRaises(ValueError):
            ci_rust.bootstrap(self.root, self.env)
        self.assert_no_export()

    def test_install_and_probe_failures_do_not_export(self):
        for step in ('toolchain', 'which', 'run'):
            with self.subTest(step=step):
                self.fail = step
                with self.assertRaises(RuntimeError): self.invoke()
                self.assert_no_export()

    def test_wrong_compiler_version(self):
        self.wrong_version = True
        with self.assertRaises(RuntimeError): self.invoke()
        self.assert_no_export()

    def test_missing_component_binary(self):
        self.missing_tool = True
        with self.assertRaises(RuntimeError): self.invoke()
        self.assert_no_export()

    def test_tool_outside_isolated_home(self):
        self.escaped_tool = True
        with self.assertRaises(RuntimeError): self.invoke()
        self.assert_no_export()

    def test_empty_tool_version(self):
        self.empty_tool = True
        with self.assertRaises(RuntimeError): self.invoke()
        self.assert_no_export()

    def test_timeout_does_not_export(self):
        self.timeout = True
        with self.assertRaises(subprocess.TimeoutExpired): self.invoke()
        self.assert_no_export()

    def test_android_installs_before_cache_and_native_prerequisites(self):
        workflow = (ci_rust.ROOT / '.github/workflows/android-native.yml').read_text()
        start = workflow.index('python tools/ci_rust.py')
        self.assertLess(start, workflow.index('Swatinem/rust-cache@'))
        self.assertLess(start, workflow.index('Install native prerequisites'))
        self.assertNotIn('continue-on-error:', workflow)


if __name__ == '__main__':
    unittest.main()
