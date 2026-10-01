"""Core validation must not trust a partially installed runner Rust toolchain."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class FoundationToolchainTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load((ROOT / '.github/workflows/foundation.yml').read_text())
        self.core = self.workflow['jobs']['core']
        self.steps = self.core['steps']
        self.gate_index = next(i for i, step in enumerate(self.steps)
                               if step.get('run') == 'python tools/ci_rust.py')

    def test_python_is_pinned_before_rust_initialization(self):
        setup_index = next(i for i, step in enumerate(self.steps)
                           if step.get('uses', '').startswith('actions/setup-python@'))
        self.assertLess(setup_index, self.gate_index)
        self.assertEqual(self.steps[setup_index]['with']['python-version-file'], '.python-version')

    def test_rust_initialization_cannot_be_skipped_or_ignored(self):
        self.assertNotIn('if', self.core)
        self.assertNotIn('continue-on-error', self.core)
        gate = self.steps[self.gate_index]
        self.assertNotIn('if', gate)
        self.assertNotIn('continue-on-error', gate)
        self.assertNotIn('rustup show', [step.get('run') for step in self.steps])

    def test_isolation_precedes_cache_and_core_work(self):
        for index, step in enumerate(self.steps):
            if step.get('uses', '').startswith('Swatinem/rust-cache@') or step.get('name') in (
                    'Install core prerequisites', 'Verify lockfile resolution', 'Core library tests'):
                self.assertLess(self.gate_index, index)

    def test_lock_resolution_and_complete_core_tests_are_preserved(self):
        metadata = next(step for step in self.steps if step.get('name') == 'Verify lockfile resolution')
        self.assertEqual(metadata['run'], 'cargo metadata --locked --format-version 1 > "$RUNNER_TEMP/cargo-metadata.json"')
        tests = next(step for step in self.steps if step.get('name') == 'Core library tests')
        self.assertEqual(tests['run'], 'cargo test --locked -p base -p hbb_common --lib')
        self.assertNotIn('if', tests)
        self.assertNotIn('continue-on-error', tests)

    def test_diagnostics_survive_failure_without_publication_rights(self):
        upload = next(step for step in self.steps if step.get('uses', '').startswith('actions/upload-artifact@'))
        self.assertEqual(upload['if'], 'always()')
        self.assertEqual(upload['with']['path'], 'tools/.reports/')
        self.assertEqual(upload['with']['if-no-files-found'], 'error')
        self.assertEqual(self.workflow['permissions'], {'contents': 'read'})
        self.assertNotIn('permissions', self.core)
        self.assertNotIn('environment', self.core)

    def test_foundation_gate_requires_both_jobs(self):
        gate = self.workflow['jobs']['gate']
        self.assertEqual(set(gate['needs']), {'repository', 'core'})
        self.assertEqual(gate['if'], 'always()')
        self.assertEqual(gate['steps'][0]['env'], {
            'REPOSITORY_RESULT': '${{ needs.repository.result }}',
            'CORE_RESULT': '${{ needs.core.result }}',
        })
        self.assertEqual(gate['steps'][0]['run'].splitlines(), [
            'test "$REPOSITORY_RESULT" = success', 'test "$CORE_RESULT" = success'])


if __name__ == '__main__':
    unittest.main()
