"""Keep audio API migration and native execution attached to their production paths."""
import ast
from pathlib import Path
import tomllib
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class AudioDependencyTests(unittest.TestCase):
    def test_reviewed_versions_are_resolved_without_legacy_audio_packages(self):
        manifest = tomllib.loads((ROOT / 'Cargo.toml').read_text())
        self.assertEqual(manifest['dependencies']['rubato'], {'version': '5.0.1', 'optional': True})
        dependency = manifest['target']['cfg(not(target_os = "linux"))']['dependencies']['ringbuf']
        self.assertEqual(dependency, '0.5.2')
        packages = tomllib.loads((ROOT / 'Cargo.lock').read_text())['package']
        for name, version, checksum in [
            ('ringbuf', '0.5.2', '0b123165531e325df9079f56c036f2da4103a5d5abfef9e2fda4b9c34d1ef7aa'),
            ('rubato', '5.0.1', 'cc1e951b9f5432ec1422f4dcfa5733fc501265902612edf5ef8bd8ecdd960930'),
        ]:
            resolved = [p for p in packages if p['name'] == name]
            self.assertEqual(len(resolved), 1)
            self.assertEqual((resolved[0]['version'], resolved[0]['checksum']), (version, checksum))

    def test_rubato_stays_optional_and_streaming_selection_does_not_change(self):
        manifest = tomllib.loads((ROOT / 'Cargo.toml').read_text())
        self.assertEqual(manifest['features']['default'], ['use_dasp'])
        self.assertEqual(manifest['features']['use_rubato'], ['rubato'])
        target = next(t for t in manifest['test'] if t['name'] == 'rubato_dependency_contract')
        self.assertEqual(target['required-features'], ['use_rubato'])
        source = (ROOT / 'src/common.rs').read_text()
        for retired in ['InterpolationParameters, InterpolationType', 'SincFixedIn']:
            self.assertNotIn(retired, source)
        for setting in ['sinc_len: 256', 'f_cutoff: Some(0.95)', 'oversampling_factor: 160',
                        'SincInterpolationType::Nearest', 'WindowFunction::BlackmanHarris2', 'FixedAsync::Input']:
            self.assertIn(setting, source)

    def test_current_ring_traits_replace_private_or_retired_imports(self):
        for path in ['src/client.rs', 'src/client/audio_playback.rs',
                     'src/client/audio_playback_tests.rs', 'src/client/tests/audio_state_tests.rs']:
            source = (ROOT / path).read_text()
            self.assertNotIn('ring_buffer::RbBase', source)
            self.assertNotIn('use ringbuf::Rb;', source)
            self.assertIn('use ringbuf::traits::', source)

    def test_optional_api_runs_after_default_bundle_without_ignoring_errors(self):
        flow = yaml.safe_load((ROOT / '.github/workflows/flutter-validate.yml').read_text())
        steps = flow['jobs']['linux']['steps']
        step = next(s for s in steps if s.get('name') == 'Verify the optional Rubato resampling API')
        self.assertIn('cargo test --locked --test rubato_dependency_contract --features flutter,linux-pkg-config,use_rubato', step['run'])
        self.assertNotIn('if', step)
        self.assertNotIn('continue-on-error', step)
        self.assertNotIn('|| true', step['run'])
        bundle = next(s for s in steps if s.get('name') == 'Build and validate the Linux desktop bundle')
        self.assertLess(steps.index(bundle), steps.index(step))

    def test_native_audio_execution_precedes_packaging_and_keeps_platform_scope(self):
        flow = yaml.safe_load((ROOT / '.github/workflows/apple-native.yml').read_text())
        steps = flow['jobs']['macos']['steps']
        audio = next(s for s in steps if s.get('name') == 'Verify native audio buffering and recovery')
        self.assertIn('cargo test --locked --release --lib --features flutter audio -- --test-threads=1', audio['run'])
        self.assertNotIn('if', audio)
        self.assertNotIn('continue-on-error', audio)
        package = next(s for s in steps if s.get('name') == 'Build the desktop bundle without signing')
        self.assertLess(steps.index(audio), steps.index(package))
        module = ast.parse((ROOT / 'tools/windows_native.py').read_text())
        build = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
        commands = [n.value for n in build.body if isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                    and n.value.func.id == 'command']
        call = next(c for c in commands if len(c.args) > 1 and isinstance(c.args[1], ast.Constant)
                    and c.args[1].value == 'windows-audio-tests.log')
        self.assertEqual(ast.literal_eval(call.args[0]), [
            'cargo', 'test', '--locked', '--release', '--lib', '--features', 'flutter',
            'audio', '--', '--test-threads=1'])


if __name__ == '__main__':
    unittest.main()
