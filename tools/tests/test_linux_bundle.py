import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'linux' and shutil.which('bash') and shutil.which('git'),
                     'Linux, bash and git are required')
class LinuxBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'flutter').mkdir()
        (self.root / 'target/debug').mkdir(parents=True)
        (self.root / 'target/debug/liblibrustdesk.so').write_bytes(b'native')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.command('flutter', '''
import os
from pathlib import Path
import sys
mode = os.environ.get('VIPER_TEST_MODE', '')
if sys.argv[1:] == ['build', 'linux', '--debug', '--no-pub']:
    if mode == 'build-failure':
        sys.exit(23)
    bundle = Path('build/linux/x64/debug/bundle')
    (bundle / 'lib').mkdir(parents=True)
    (bundle / 'data/flutter_assets').mkdir(parents=True)
    (bundle / 'data/icudtl.dat').write_bytes(b'icu')
    if mode != 'missing-executable':
        (bundle / 'rustdesk').write_bytes(b'executable')
        (bundle / 'rustdesk').chmod(0o755)
    (bundle / 'lib/librustdesk.so').write_bytes(b'wrong' if mode == 'wrong-library' else b'native')
elif sys.argv[1:] == ['test', '--no-pub', 'test_native/bridge_ffi_test.dart']:
    expected = str(Path('build/linux/x64/debug/bundle/lib/librustdesk.so').resolve())
    assert os.environ['VIPER_NATIVE_LIBRARY'] == expected
    sys.exit(1 if mode == 'ffi-failure' else 0)
else:
    sys.exit(99)
''')
        self.command('ldd', '''
import os
import sys
if os.environ.get('VIPER_TEST_MODE') == 'ldd-failure':
    sys.exit(1)
print('libexample.so => not found' if os.environ.get('VIPER_TEST_MODE') == 'missing-dependency' else 'libexample.so => /usr/lib/libexample.so')
''')

    def command(self, name, body):
        path = self.bin / name
        path.write_text(f'#!{sys.executable}\n{body}', encoding='utf-8')
        path.chmod(0o755)

    def run_bundle(self, mode=''):
        env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
               'VIPER_TEST_MODE': mode}
        return subprocess.run(['bash', str(ROOT / 'tools/native/build-linux-bundle.sh')],
                              cwd=self.root, env=env, capture_output=True, text=True)

    def test_success_checks_the_installed_library(self):
        result = self.run_bundle()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'tools/.reports/bundle-ffi-tests.log').exists())

    def test_missing_rust_library_fails(self):
        (self.root / 'target/debug/liblibrustdesk.so').unlink()
        self.assertNotEqual(self.run_bundle().returncode, 0)

    def test_build_failure_is_not_ignored(self):
        self.assertNotEqual(self.run_bundle('build-failure').returncode, 0)

    def test_missing_executable_fails(self):
        self.assertNotEqual(self.run_bundle('missing-executable').returncode, 0)

    def test_wrong_bundled_library_fails(self):
        self.assertNotEqual(self.run_bundle('wrong-library').returncode, 0)

    def test_unresolved_link_dependency_fails(self):
        self.assertNotEqual(self.run_bundle('missing-dependency').returncode, 0)

    def test_link_inspection_failure_is_not_ignored(self):
        self.assertNotEqual(self.run_bundle('ldd-failure').returncode, 0)

    def test_real_ffi_step_failure_is_not_ignored(self):
        self.assertNotEqual(self.run_bundle('ffi-failure').returncode, 0)


if __name__ == '__main__':
    unittest.main()
