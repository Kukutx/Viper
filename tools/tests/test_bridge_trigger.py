from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class BridgeTriggerTests(unittest.TestCase):
    def test_export_is_consumer_driven_and_still_requires_validation(self):
        # BaseLoader preserves GitHub's `on` key instead of YAML 1.1 boolean coercion.
        workflow = yaml.load((ROOT / '.github/workflows/bridge.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow['on']), {'workflow_call', 'workflow_dispatch'})
        self.assertEqual(workflow['jobs']['validate']['uses'], './.github/workflows/flutter-validate.yml')
        self.assertEqual(workflow['jobs']['export']['needs'], ['validate'])


if __name__ == '__main__':
    unittest.main()
