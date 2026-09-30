"""An iOS-only toolchain must not execute CocoaPods or accept SDK drift."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from apple_sdk import verify


class IosSdkTests(unittest.TestCase):
    def test_ios_sdk_is_checked_without_cocoapods(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'configs').mkdir()
            expected = {'apple': {'developer_dir': name, 'xcode': '27.0', 'build': '27A266a', 'macos_sdk': '27.0'}, 'ios': {'sdk': '27.0'}}
            (root / 'configs/toolchain.json').write_text(json.dumps(expected))
            def command(args, **kwargs):
                self.assertNotEqual(args[0], 'pod')
                self.assertEqual(kwargs['env']['DEVELOPER_DIR'], name)
                output = 'Xcode 27.0\nBuild version 27A266a\n' if args[0] == 'xcodebuild' else '27.0\n'
                return subprocess.CompletedProcess(args, 0, output, '')
            with patch('apple_sdk.platform.system', return_value='Darwin'), patch('apple_sdk.subprocess.run', side_effect=command) as run:
                self.assertEqual(verify(root, ios=True)['ios_sdk'], '27.0')
                self.assertEqual(run.call_count, 3)
            expected['ios']['sdk'] = '27.1'
            (root / 'configs/toolchain.json').write_text(json.dumps(expected))
            with patch('apple_sdk.platform.system', return_value='Darwin'), patch('apple_sdk.subprocess.run', side_effect=command):
                with self.assertRaisesRegex(RuntimeError, 'Wrong ios_sdk'):
                    verify(root, ios=True)


if __name__ == '__main__':
    unittest.main()
