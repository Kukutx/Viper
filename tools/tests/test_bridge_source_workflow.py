"""The source-only generator path must run and compare bindings in read-only CI."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class BridgeSourceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load((ROOT / '.github/workflows/bridge-source.yml').read_text())
        self.steps = self.workflow['jobs']['source']['steps']

    def test_source_compilation_is_required_before_parity(self):
        commands = [step.get('run', '') for step in self.steps]
        compile_index = next(i for i, text in enumerate(commands) if 'generate --from-source' in text)
        parity_index = next(i for i, text in enumerate(commands) if 'check_bridge_outputs.py' in text)
        self.assertLess(compile_index, parity_index)
        self.assertIn('exit 1;', commands[compile_index])
        self.assertIn('git diff --exit-code HEAD -- Cargo.lock flutter/pubspec.yaml flutter/pubspec.lock', commands[parity_index])
        self.assertNotIn('if', self.steps[compile_index])
        self.assertNotIn('if', self.steps[parity_index])

    def test_job_cannot_write_refs_or_use_release_secrets(self):
        self.assertEqual(self.workflow['permissions'], {'contents': 'read'})
        for step in self.steps:
            self.assertNotIn('continue-on-error', step)
            self.assertNotIn('secrets.', str(step))
        checkout = self.steps[0]
        self.assertFalse(checkout['with']['persist-credentials'])
        self.assertEqual(checkout['with']['submodules'], 'recursive')
        sdk = next(step for step in self.steps if step.get('uses', '').startswith('subosito/'))
        self.assertEqual(sdk['with']['flutter-version'], '${{ env.FLUTTER_VERSION }}')


if __name__ == '__main__':
    unittest.main()
