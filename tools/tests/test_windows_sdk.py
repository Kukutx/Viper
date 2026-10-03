"""The Windows bootstrap must not patch an SDK or overwrite an existing checkout."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
with patch.object(sys, 'path', [str(ROOT / 'tools'), *sys.path]):
    spec = importlib.util.spec_from_file_location('install_windows_flutter', ROOT / 'tools/install_windows_flutter.py')
    sdk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdk)


class WindowsSdkTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.destination = self.root / 'new-sdk'
        self.revision = 'a' * 40

    def test_exact_revision_then_stable_without_sdk_edits(self):
        with patch.object(sdk, 'command', side_effect=['', self.revision + '\n', '']) as run:
            sdk.prepare_checkout(self.destination, '3.47.5', self.revision)
        commands = [c.args[0] for c in run.call_args_list]
        self.assertIn(sdk.SOURCE, commands[0])
        self.assertEqual(commands[1][-2:], ['rev-parse', 'HEAD'])
        self.assertEqual(commands[2][-3:], ['switch', '-c', 'stable'])
        self.assertNotIn('reset', str(commands))
        self.assertNotIn('engine.stamp', str(commands))

    def test_existing_directory_is_preserved(self):
        self.destination.mkdir()
        file = self.destination / 'user-data'
        file.write_text('keep')
        with patch.object(sdk, 'command') as run, self.assertRaises(ValueError):
            sdk.prepare_checkout(self.destination, '3.47.5', self.revision)
        run.assert_not_called()
        self.assertEqual(file.read_text(), 'keep')

    def test_symlink_is_rejected(self):
        self.destination.symlink_to(self.root / 'missing', target_is_directory=True)
        with patch.object(sdk, 'command') as run, self.assertRaises(ValueError):
            sdk.prepare_checkout(self.destination, '3.47.5', self.revision)
        run.assert_not_called()

    def test_tag_drift_prevents_channel_selection(self):
        with patch.object(sdk, 'command', side_effect=['', 'b' * 40]) as run, self.assertRaises(ValueError):
            sdk.prepare_checkout(self.destination, '3.47.5', self.revision)
        self.assertEqual(run.call_count, 2)

    def test_clone_failure_is_not_recovered_with_a_different_sdk(self):
        with patch.object(sdk, 'command', side_effect=subprocess.CalledProcessError(1, ['git'])) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                sdk.prepare_checkout(self.destination, '3.47.5', self.revision)
        self.assertEqual(run.call_count, 1)

    def test_floating_version_is_rejected_before_network(self):
        for version, sha in [('stable', self.revision), ('3.47.5', 'main')]:
            with patch.object(sdk, 'command') as run, self.assertRaises(ValueError):
                sdk.prepare_checkout(self.destination, version, sha)
            run.assert_not_called()

    def test_workflow_bootstraps_native_sdk_and_keeps_early_evidence(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/windows-native.yml').read_text())
        steps = workflow['jobs']['windows']['steps']
        commands = '\n'.join(s.get('run', '') for s in steps)
        self.assertIn('python tools/install_windows_flutter.py --github-env', commands)
        self.assertIn('git rev-parse HEAD > tools/.reports/revision.txt', commands)
        self.assertFalse(any(s.get('uses', '').startswith('subosito/') for s in steps))
        source = (ROOT / 'tools/install_windows_flutter.py').read_text()
        self.assertIn('pe_machine(dart) != MACHINES[arch]', source)
        self.assertIn("'diff', '--exit-code', 'HEAD'", source)


if __name__ == '__main__':
    unittest.main()
