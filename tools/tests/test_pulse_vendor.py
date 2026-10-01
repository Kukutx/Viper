"""Provenance and CI contracts for the preserved PulseAudio fork."""
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import verify_pulse_vendor as verifier


class PulseVendorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'libs/pulsectl', self.root / 'libs/pulsectl')
        shutil.copyfile(ROOT / 'Cargo.toml', self.root / 'Cargo.toml')

    def test_original_fork_is_preserved(self):
        self.assertEqual(verifier.verify(self.root), 9)

    def test_license_change_is_rejected(self):
        (self.root / 'libs/pulsectl/LICENSE.md').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'outside the migration'):
            verifier.verify(self.root)

    def test_unrelated_code_change_is_rejected(self):
        with (self.root / 'libs/pulsectl/src/lib.rs').open('a') as out:
            out.write('\n// unreviewed code\n')
        with self.assertRaisesRegex(ValueError, 'outside the migration'):
            verifier.verify(self.root)

    def test_old_api_is_rejected(self):
        p = self.root / 'libs/pulsectl/src/controllers/mod.rs'
        p.write_text(p.read_text().replace('Volume::NORMAL.0', 'pulse::volume::VOLUME_NORM.0'))
        with self.assertRaisesRegex(ValueError, 'migration diff'):
            verifier.verify(self.root)

    def test_missing_or_symlinked_source_is_rejected(self):
        p = self.root / 'libs/pulsectl/src/errors.rs'
        p.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing regular'):
            verifier.verify(self.root)
        p.symlink_to(ROOT / 'libs/pulsectl/src/errors.rs')
        with self.assertRaisesRegex(ValueError, 'Missing regular'):
            verifier.verify(self.root)

    def test_extra_module_is_rejected(self):
        (self.root / 'libs/pulsectl/src/extra.rs').write_text('')
        with self.assertRaisesRegex(ValueError, 'module set'):
            verifier.verify(self.root)

    def test_old_source_and_separate_lock_are_rejected(self):
        manifest = self.root / 'Cargo.toml'
        original = manifest.read_text()
        manifest.write_text(original.replace('path = "libs/pulsectl"', 'git = "https://github.com/rustdesk-org/pulsectl"'))
        with self.assertRaisesRegex(ValueError, 'local fork'):
            verifier.verify(self.root)
        manifest.write_text(original)
        (self.root / 'libs/pulsectl/Cargo.lock').write_text('version = 4\n')
        with self.assertRaisesRegex(ValueError, 'only dependency lock'):
            verifier.verify(self.root)

    def test_private_server_tests_are_explicit_and_enabled_in_ci(self):
        manifest = tomllib.loads((ROOT / 'libs/pulsectl/Cargo.toml').read_text())
        target = next(t for t in manifest['test'] if t['name'] == 'pulse_smoke')
        self.assertEqual(target['required-features'], ['private-server-tests'])
        self.assertEqual(manifest['features']['private-server-tests'], [])
        self.assertIn('--features private-server-tests', (ROOT / 'tools/native/test-pulsectl.sh').read_text())

    def test_ci_runs_real_private_audio_without_suppression(self):
        source = (ROOT / '.github/workflows/flutter-validate.yml').read_text()
        self.assertIn('bash tools/native/test-pulsectl.sh', source)
        script = (ROOT / 'tools/native/test-pulsectl.sh').read_text()
        self.assertIn('module-null-sink sink_name=viper_ci', script)
        self.assertIn('cargo test --locked -p rust-pulsectl --test pulse_smoke', script)
        self.assertNotIn('--ignored', script)
        self.assertNotIn('auth-anonymous', script)
        self.assertIn('kill "$pid"', script)


if __name__ == '__main__':
    unittest.main()
