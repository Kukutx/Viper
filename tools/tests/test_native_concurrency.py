"""New PR heads supersede only their own native validation, never release work."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
PR_ONLY = "${{ github.event_name == 'pull_request' }}"
NATIVE = ('android-native', 'apple-native', 'ios-native', 'windows-native',
          'linux-release', 'flutter-validate')


class NativeConcurrencyTests(unittest.TestCase):
    def test_native_pr_runs_are_superseded_without_cancelling_other_events(self):
        for name in NATIVE:
            with self.subTest(workflow=name):
                workflow = yaml.safe_load((ROOT / f'.github/workflows/{name}.yml').read_text())
                concurrency = (workflow['jobs']['windows']['concurrency']
                               if name == 'windows-native' else workflow['concurrency'])
                self.assertEqual(concurrency['cancel-in-progress'], PR_ONLY)
                self.assertIn('${{ github.ref }}', concurrency['group'])
                self.assertIn(name.replace('-native', '') if name != 'flutter-validate'
                              else 'flutter-validation', concurrency['group'])
                if name == 'windows-native':
                    self.assertIn('${{ matrix.arch }}', concurrency['group'])
                    self.assertIn('${{ github.workflow }}', concurrency['group'])

    def test_native_cancellation_applies_only_to_read_only_validation(self):
        for name in NATIVE:
            with self.subTest(workflow=name):
                workflow = yaml.safe_load((ROOT / f'.github/workflows/{name}.yml').read_text())
                self.assertEqual(workflow['permissions'], {'contents': 'read'})
                for job in workflow['jobs'].values():
                    self.assertNotIn('environment', job)
                    self.assertNotIn('permissions', job)

    def test_release_and_maintenance_runs_are_not_cancelled(self):
        for name in ('flutter-nightly', 'flutter-tag', 'fdroid', 'update-webpki-roots'):
            with self.subTest(workflow=name):
                workflow = yaml.safe_load((ROOT / f'.github/workflows/{name}.yml').read_text())
                self.assertIs(workflow['concurrency']['cancel-in-progress'], False)


if __name__ == '__main__':
    unittest.main()
