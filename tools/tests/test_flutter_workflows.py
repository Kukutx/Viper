from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]


class FlutterWorkflowTests(unittest.TestCase):
    def workflow(self, name):
        return yaml.safe_load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'))

    def test_shared_bridge_uses_the_canonical_validator(self):
        jobs = self.workflow('bridge.yml')['jobs']
        self.assertEqual(jobs['validate']['uses'], './.github/workflows/flutter-validate.yml')
        self.assertEqual(jobs['export']['needs'], ['validate'])

    def test_existing_consumers_receive_the_same_current_files(self):
        export = self.workflow('bridge.yml')['jobs']['export']
        self.assertEqual(set(export['strategy']['matrix']['artifact']),
                         {'bridge-artifact', 'bridge-artifact-flutter-3.44'})
        upload = export['steps'][-1]['with']
        self.assertEqual(upload['path'].splitlines(),
                         ['src/bridge_generated.rs', 'flutter/lib/generated/*.dart'])
        self.assertEqual(upload['if-no-files-found'], 'error')
        self.assertEqual(export['steps'][0]['with']['ref'], '${{ github.sha }}')

    def test_bridge_has_no_parallel_old_generation_path(self):
        text = (ROOT / '.github/workflows/bridge.yml').read_text(encoding='utf-8')
        for obsolete in ('1.80.1', '--rust-input', 'generated_bridge.dart',
                         'cargo install', 'pub upgrade', 'sed -i', 'git apply'):
            self.assertNotIn(obsolete, text)

    def test_validation_remains_read_only_and_fail_closed(self):
        for name in ('bridge.yml', 'flutter-validate.yml', 'flutter-platform-tests.yml', 'apple-native.yml'):
            workflow = self.workflow(name)
            self.assertEqual(workflow['permissions'], {'contents': 'read'})
            for job in workflow['jobs'].values():
                self.assertNotIn('secrets', job)
                for step in job.get('steps', []):
                    self.assertNotIn('continue-on-error', step)
                    self.assertNotIn('secrets.', str(step))

    def test_new_generated_files_are_not_silently_accepted(self):
        steps = self.workflow('flutter-validate.yml')['jobs']['linux']['steps']
        codegen = next(step['run'] for step in steps if step.get('name') ==
                       'Verify reproducible bindings and locked dependencies')
        self.assertIn('git diff --exit-code', codegen)
        self.assertIn('git ls-files --others -- src/bridge_generated.rs flutter/lib/generated', codegen)
        self.assertIn('python tools/check_bridge_outputs.py', codegen)

    def test_bundle_build_follows_native_compilation(self):
        steps = self.workflow('flutter-validate.yml')['jobs']['linux']['steps']
        names = [step.get('name') for step in steps]
        self.assertLess(names.index('Check and build the native Flutter library'),
                        names.index('Build and validate the Linux desktop bundle'))
        bundle = next(step for step in steps if step.get('name') ==
                      'Build and validate the Linux desktop bundle')
        self.assertEqual(bundle['run'], 'bash tools/native/build-linux-bundle.sh')
        self.assertNotIn('if', bundle)

    def test_desktop_dart_checks_use_the_shared_sdk_and_lockfile(self):
        job = self.workflow('flutter-platform-tests.yml')['jobs']['dart']
        self.assertEqual(set(job['strategy']['matrix']['os']), {'windows-2022', 'macos-14'})
        sdk = next(step for step in job['steps'] if step.get('uses', '').startswith('subosito/'))
        self.assertEqual(sdk['with']['flutter-version'], '${{ env.FLUTTER_VERSION }}')
        commands = '\n'.join(step.get('run', '') for step in job['steps'])
        self.assertIn('flutter pub get --enforce-lockfile', commands)
        self.assertIn('flutter test --no-pub test ', commands)
        self.assertNotIn('test_native/', commands)
        self.assertNotIn('pub upgrade', commands)

    def test_sdk_bootstrap_uses_the_shared_strict_version_verifier(self):
        steps = self.workflow('flutter-platform-tests.yml')['jobs']['dart']['steps']
        command = next(step['run'] for step in steps if step.get('name') ==
                       'Verify SDK and locked dependencies')
        self.assertIn('python tools/flutter_sdk.py', command)
        self.assertNotIn('json.loads', command)
        self.assertNotIn('|| true', command)
        self.assertTrue((ROOT / 'tools/tests/test_flutter_sdk.py').is_file())


if __name__ == '__main__':
    unittest.main()
