"""Exercise the Cargo subcommand version gate without compiling native libraries."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CargoNdkEntryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ndk tools ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.private = self.root / '.tools/cargo-ndk/bin'
        self.private.mkdir(parents=True)
        (self.root / 'tools/.reports').mkdir(parents=True)
        cargo = self.root / 'bin/cargo'
        cargo.parent.mkdir()
        cargo.write_text('#!/bin/bash\nset -eu\n[[ "$*" == "ndk --version" ]]\n'
                         'export CARGO="$0"\nexec cargo-ndk "$@"\n')
        cargo.chmod(0o755)
        ndk = self.private / 'cargo-ndk'
        ndk.write_text('#!/bin/bash\nset -eu\n: "${CARGO:?Cargo must launch this tool}"\n'
                       '[[ "$*" == "ndk --version" ]]\n'
                       'printf "%s\\n" "$TEST_VERSION"\nexit "$TEST_EXIT"\n')
        ndk.chmod(0o755)
        script = (ROOT / 'tools/native/build-android.sh').read_text()
        start = script.index('export PATH="$root/.tools/cargo-ndk/bin:$PATH"')
        end = script.index('export RUSTFLAGS=', start)
        self.block = script[start:end]
        self.environment = {**os.environ, 'PATH': str(cargo.parent) + os.pathsep + os.environ['PATH'],
                            'TEST_VERSION': 'cargo-ndk 4.1.2', 'TEST_EXIT': '0'}
        self.environment.pop('CARGO', None)

    def run_gate(self):
        return subprocess.run(['bash', '-c', 'set -euo pipefail\nroot=$PWD\ncargo_ndk=4.1.2\n' + self.block],
                              cwd=self.root, env=self.environment, capture_output=True, text=True)

    def test_private_tool_is_launched_through_cargo_and_recorded(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'tools/.reports/android-cargo-ndk-version.txt').read_text(),
                         'cargo-ndk 4.1.2\n')

    def test_different_or_malformed_tool_identity_is_rejected(self):
        for version in ('cargo-ndk 3.1.2', 'other-tool 4.1.2', 'cargo-ndk 4.1.2-beta',
                        'prefix\ncargo-ndk 4.1.2', ''):
            with self.subTest(version=version):
                self.environment['TEST_VERSION'] = version
                self.assertNotEqual(self.run_gate().returncode, 0)

    def test_failed_version_command_is_not_accepted(self):
        self.environment['TEST_EXIT'] = '19'
        self.assertEqual(self.run_gate().returncode, 19)


if __name__ == '__main__':
    unittest.main()
