"""Fail closed for signing/import/publication and keep secret values out of shell text."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from release_policy import allows_release, check, check_workflow
from signing_identity import normalize_identity


class ReleasePolicyTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load((ROOT / '.github/workflows/flutter-build.yml').read_text())

    def test_committed_workflows(self):
        check(ROOT)

    def test_trust_boundary_matrix(self):
        for repo in ('Kukutx/Viper', 'fork/Viper'):
            for event in ('pull_request', 'pull_request_target', 'push', 'workflow_dispatch', 'schedule'):
                for ref in ('refs/heads/main', 'refs/tags/v1.5.0', 'refs/heads/topic', 'refs/pull/1/merge'):
                    for publish in (True, False, 'true', None):
                        expected = (repo == 'Kukutx/Viper' and event not in ('pull_request', 'pull_request_target')
                                    and ref in ('refs/heads/main', 'refs/tags/v1.5.0') and publish is True)
                        with self.subTest(repo=repo, event=event, ref=ref, publish=publish):
                            self.assertEqual(allows_release(repo, event, ref, publish), expected)

    def test_shared_secret_value_is_rejected(self):
        self.workflow['env']['ANDROID_SIGNING_KEY'] = '${{ secrets.ANDROID_SIGNING_KEY }}'
        with self.assertRaisesRegex(ValueError, 'shared environment'):
            check_workflow(self.workflow)

    def test_job_secret_value_is_rejected(self):
        self.workflow['jobs']['generate-sbom']['env'] = {'KEY': '${{ secrets.ANDROID_SIGNING_KEY }}'}
        with self.assertRaisesRegex(ValueError, 'job environment'):
            check_workflow(self.workflow)

    def test_each_credential_and_publication_step_requires_a_guard(self):
        count = 0
        for key, job in self.workflow['jobs'].items():
            for i, step in enumerate(job.get('steps', [])):
                if ('secrets.' in str(step) or step.get('uses', '').startswith('softprops/action-gh-release@')):
                    count += 1
                    changed = deepcopy(self.workflow)
                    changed['jobs'][key]['steps'][i].pop('if', None)
                    with self.subTest(job=key, step=i), self.assertRaisesRegex(ValueError, 'release guard'):
                        check_workflow(changed)
        self.assertGreater(count, 10)

    def test_shell_secret_interpolation_is_rejected(self):
        self.workflow['jobs']['generate-sbom']['steps'].append({'run': 'echo ${{ secrets.KEY }}'})
        with self.assertRaisesRegex(ValueError, 'shell source'):
            check_workflow(self.workflow)

    def test_pr_policy_drift_is_rejected(self):
        self.workflow['env']['RELEASE_ALLOWED'] = '${{ inputs.upload-artifact }}'
        with self.assertRaisesRegex(ValueError, 'trust-boundary'):
            check_workflow(self.workflow)

    def test_notarization_key_is_temporary_and_cleaned_on_failure(self):
        job = self.workflow['jobs']['build-for-macOS']
        steps = {step.get('name'): step for step in job['steps'] if step.get('name')}
        self.assertEqual(steps['Import notarize key']['with']['fileDir'], '${{ runner.temp }}/viper-signing')
        cleanup = steps['Remove temporary notarization credential']
        self.assertIn('always()', cleanup['if'])
        self.assertEqual(cleanup['run'], 'rm -f -- "$NOTARIZE_KEY"')
        self.assertNotIn('secrets.', steps['Codesign app and create signed dmg']['run'])


class SigningIdentityTests(unittest.TestCase):
    def test_plain_identity_and_hash_are_preserved(self):
        for identity in ('Developer ID Application: Example (TEAM123)', 'a' * 40):
            self.assertEqual(normalize_identity(identity), identity)

    def test_historical_surrounding_quotes_are_parsed_without_a_shell(self):
        for quote in ('"', "'"):
            self.assertEqual(normalize_identity(quote + 'Developer ID: Example' + quote), 'Developer ID: Example')

    def test_shell_metacharacters_are_literal_data(self):
        identity = 'Developer ID: $(touch never-executed); `command`'
        self.assertEqual(normalize_identity(identity), identity)

    def test_invalid_empty_adhoc_options_and_multiple_quoted_tokens_fail(self):
        for identity in ('', ' ', '-', '--sign', '\"\"', '\"a\" \"b\"', "'unterminated", 'id\nother', 'a\x00b', 'x' * 513):
            with self.subTest(identity=repr(identity)), self.assertRaises(ValueError):
                normalize_identity(identity)


if __name__ == '__main__':
    unittest.main()
