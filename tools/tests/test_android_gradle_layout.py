"""Keep build-directory assignment ahead of all application evaluation."""
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class AndroidGradleLayoutTests(unittest.TestCase):
    def test_all_directories_are_set_before_any_project_evaluates_app(self):
        text = (ROOT / 'flutter/android/build.gradle').read_text()
        blocks = re.findall(r'^subprojects \{\n(.*?)^\}', text, re.M | re.S)
        layout = [i for i, block in enumerate(blocks) if 'layout.buildDirectory.set' in block]
        evaluation = [i for i, block in enumerate(blocks) if 'evaluationDependsOn' in block]
        self.assertEqual(len(layout), 1)
        self.assertEqual(len(evaluation), 1)
        self.assertLess(layout[0], evaluation[0])

    def test_real_gradle_regression_runs_before_expensive_native_compilation(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/android-native.yml').read_text())
        steps = workflow['jobs']['android']['steps']
        names = [step.get('name') for step in steps]
        check = names.index('Verify Gradle evaluation order')
        self.assertLess(check, names.index('Build the real native library and unsigned APK'))
        self.assertEqual(steps[check]['run'], 'python tools/check_android_gradle_layout.py')
        self.assertNotIn('if', steps[check])
        self.assertNotIn('continue-on-error', steps[check])

    def test_default_r8_rules_remain_enabled(self):
        text = (ROOT / 'flutter/android/app/build.gradle').read_text()
        self.assertIn("getDefaultProguardFile('proguard-android-optimize.txt')", text)
        self.assertNotRegex(text, r'(minifyEnabled|shrinkResources)\s*(?:=\s*)?false')


if __name__ == '__main__':
    unittest.main()
