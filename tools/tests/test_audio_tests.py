import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('audio_tests', ROOT / 'tools/audio_tests.py')
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


def passing(names):
    return '\n'.join(f'test {name} ... ok' for name in names) + f'\ntest result: ok. {len(names)} passed; 0 failed; 0 ignored; 0 measured; 9 filtered out; finished in 5s\n'


class AudioEvidenceTests(unittest.TestCase):
    def test_both_native_platforms_require_their_production_tests(self):
        for host, count in [('Darwin', 16), ('Windows', 24)]:
            required = audio.required_tests(host)
            self.assertEqual(len(required), count)
            self.assertEqual(set(audio.check_results(passing(required), required)), required)

    def test_linux_cannot_claim_non_linux_playback_coverage(self):
        with self.assertRaises(ValueError):
            audio.required_tests('Linux')

    def test_every_required_test_is_mandatory(self):
        required = audio.required_tests('Windows')
        for missing in required:
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                audio.check_results(passing(required - {missing}), required)

    def test_missing_duplicate_zero_and_inconsistent_results_fail(self):
        required = {'client::audio::test'}
        good = passing(required)
        for text in ['', passing([]), good + good,
                     good.replace('1 passed', '2 passed'), good.replace('0 ignored', '1 ignored'),
                     good.replace('0 measured', '1 measured'), good.replace('... ok', '... ignored'),
                     good.replace('... ok', '... FAILED')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                audio.check_results(text, required)

    def test_real_cargo_command_is_locked_release_and_serial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            required = {'client::audio::test'}
            def run(arguments, **kwargs):
                self.assertEqual(arguments, ['cargo', 'test', '--locked', '--release', '--lib',
                                             '--features', 'flutter', 'client::audio', '--', '--test-threads=1'])
                self.assertEqual(kwargs['cwd'], root)
                self.assertEqual(kwargs['timeout'], 1200)
                kwargs['stdout'].write(passing(required))
                return subprocess.CompletedProcess(arguments, 0)
            with patch.object(audio.subprocess, 'run', side_effect=run):
                self.assertEqual(audio.run_tests(root, 'client::audio', root/'tests.log', required), sorted(required))

    def test_failed_command_cannot_be_hidden_by_successful_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def run(arguments, **kwargs):
                kwargs['stdout'].write(passing({'client::audio::test'}))
                return subprocess.CompletedProcess(arguments, 2)
            with patch.object(audio.subprocess, 'run', side_effect=run), self.assertRaises(RuntimeError):
                audio.run_tests(root, 'client::audio', root/'tests.log', {'client::audio::test'})

    def test_timeout_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(audio.subprocess, 'run', side_effect=subprocess.TimeoutExpired('cargo', 1200)), self.assertRaises(subprocess.TimeoutExpired):
                audio.run_tests(root, 'client::audio', root/'tests.log', {'client::audio::test'})

    def test_stale_report_removed_and_no_report_written_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root/'tools/.reports/audio-contracts.json'
            report.parent.mkdir(parents=True)
            report.write_text('old success')
            (root/'Cargo.lock').write_text('[[package]]\nname="ringbuf"\nversion="0.5.2"\n')
            with patch.object(audio.platform, 'system', return_value='Darwin'), patch.object(audio, 'run_tests', side_effect=RuntimeError('failed')), self.assertRaises(RuntimeError):
                audio.validate(root)
            self.assertFalse(report.exists())

    def test_lock_drift_blocks_success_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root/'Cargo.lock'
            lock.write_text('[[package]]\nname="ringbuf"\nversion="0.5.2"\n')
            def run(*args):
                lock.write_text('changed')
                return list(args[-1])
            with patch.object(audio.platform, 'system', return_value='Darwin'), patch.object(audio, 'run_tests', side_effect=run), self.assertRaises(ValueError):
                audio.validate(root)
            self.assertFalse((root/'tools/.reports/audio-contracts.json').exists())

    def test_both_native_builds_require_tests_before_packaging(self):
        windows = (ROOT/'tools/windows_native.py').read_text()
        self.assertLess(windows.index("str(ROOT / 'tools/audio_tests.py')"), windows.index("report = {'arch': arch"))
        apple = (ROOT/'.github/workflows/apple-native.yml').read_text()
        self.assertLess(apple.index('run: python tools/audio_tests.py'), apple.index('run: bash tools/native/build-macos-release.sh'))


if __name__ == '__main__':
    unittest.main()
