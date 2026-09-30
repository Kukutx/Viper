"""The distribution entry must call the same unsigned iOS verification as PRs."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class IosReleaseEntryTests(unittest.TestCase):
    def test_distribution_has_no_independent_unverified_ios_build(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/flutter-build.yml').read_text())
        job = workflow['jobs']['build-rustdesk-ios']
        self.assertEqual(job['uses'], './.github/workflows/ios-native.yml')
        self.assertEqual(job['needs'], ['generate-bridge'])
        self.assertEqual(job['permissions'], {'contents': 'read'})
        for forbidden in ('steps', 'secrets', 'if', 'runs-on', 'strategy'):
            self.assertNotIn(forbidden, job)

    def test_shared_job_builds_source_checked_out_for_the_call(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/ios-native.yml').read_text())
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        triggers = workflow.get('on', workflow.get(True))
        self.assertIn('workflow_call', triggers)
        self.assertEqual(triggers['push']['branches'], ['main'])
        self.assertIn('pull_request', triggers)
        job = workflow['jobs']['ios']
        steps = job['steps']
        checkout = next(step for step in steps if step.get('uses', '').startswith('actions/checkout@'))
        self.assertIs(checkout['with']['persist-credentials'], False)
        self.assertNotIn('ref', checkout['with'])
        self.assertNotIn('secrets.', str(workflow))
        self.assertNotIn('continue-on-error', str(workflow))
        build = next(i for i, step in enumerate(steps) if step.get('run') == 'bash tools/native/build-ios.sh')
        upload = next(i for i, step in enumerate(steps) if step.get('with', {}).get('path') == 'dist/ios-arm64-unsigned/')
        self.assertLess(build, upload)
        self.assertNotIn('if', steps[upload])
        self.assertEqual(steps[upload]['with']['if-no-files-found'], 'error')


if __name__ == '__main__':
    unittest.main()
