from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class LinuxReleaseSdkTests(unittest.TestCase):
    def test_arm64_uses_the_existing_immutable_sdk_installer(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/linux-release.yml').read_text())
        steps = workflow['jobs']['linux-release']['steps']
        archive_step = next(s for s in steps if s.get('uses', '').startswith('subosito/flutter-action@'))
        self.assertEqual(archive_step['if'], "matrix.arch == 'x64'")
        source_step = next(s for s in steps if 'install-flutter.sh' in s.get('run', ''))
        self.assertEqual(source_step['if'], "matrix.arch == 'arm64'")
        self.assertIn('bash tools/native/install-flutter.sh "$sdk"', source_step['run'])
        self.assertIn('"$GITHUB_PATH"', source_step['run'])
        self.assertNotIn('|| true', source_step['run'])

