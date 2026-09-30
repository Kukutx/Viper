"""Exercise SDK checkout state with real Git; never download or overwrite a SDK."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FdroidSdkTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'tools/native').mkdir(parents=True)
        (self.root / 'configs').mkdir()
        for name in ('build_toolchain.py',):
            shutil.copyfile(ROOT / 'tools' / name, self.root / 'tools' / name)
        self.script = self.root / 'tools/native/prepare-fdroid-flutter.sh'
        shutil.copyfile(ROOT / 'tools/native/prepare-fdroid-flutter.sh', self.script)
        self.sdk = self.root / 'SDK with spaces'
        self.sdk.mkdir()
        self.git('init', '-b', 'seed')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.sdk / 'bin').mkdir()
        flutter = self.sdk / 'bin/flutter'
        flutter.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$SDK_TEST_LOG"\n')
        flutter.chmod(0o755)
        (self.sdk / 'source.txt').write_text('original\n')
        self.git('add', '.')
        self.git('commit', '-m', 'Fixture SDK')
        self.revision = self.git('rev-parse', 'HEAD').stdout.strip()
        self.git('checkout', '--detach', self.revision)
        self.configuration = {'flutter': '3.47.5', 'flutter_revision': self.revision}
        self.write_config()
        # The SDK executable is a stub; verify Git state independently at invocation.
        (self.root / 'tools/flutter_sdk.py').write_text('''import os, subprocess
assert subprocess.check_output(['git', '-C', os.environ['SDK_TEST_DIRECTORY'], 'branch', '--show-current'], text=True).strip() == 'stable'
''')
        (self.root / 'tools/native/install-flutter.sh').write_text('''#!/usr/bin/env bash
echo unexpected SDK download >&2
exit 97
''')
        self.env = {**os.environ, 'SDK_TEST_LOG': str(self.root / 'invocations.log'),
                    'SDK_TEST_DIRECTORY': str(self.sdk)}

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.sdk), *args], check=True,
                              capture_output=True, text=True)

    def write_config(self):
        (self.root / 'configs/toolchain.json').write_text(json.dumps(self.configuration))

    def run_helper(self, version='3.47.5', directory=None):
        return subprocess.run(['bash', str(self.script), version, str(directory or self.sdk)],
                              env=self.env, capture_output=True, text=True)

    def test_detached_exact_revision_becomes_stable_without_changing_files(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD').stdout.strip(), self.revision)
        self.assertEqual(self.git('branch', '--show-current').stdout.strip(), 'stable')
        self.assertEqual(self.git('status', '--porcelain').stdout, '')

    def test_existing_stable_branch_is_reused_idempotently(self):
        self.git('branch', 'stable', self.revision)
        for _ in range(2):
            result = self.run_helper()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('rev-parse', 'stable').stdout.strip(), self.revision)

    def test_different_revision_is_not_reset(self):
        self.configuration['flutter_revision'] = '0' * 40
        self.write_config()
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git('rev-parse', 'HEAD').stdout.strip(), self.revision)
        self.assertFalse((self.root / 'invocations.log').exists())

    def test_uncommitted_sdk_changes_are_preserved_and_rejected(self):
        (self.sdk / 'source.txt').write_text('unrelated edit\n')
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.sdk / 'source.txt').read_text(), 'unrelated edit\n')
        self.assertFalse((self.root / 'invocations.log').exists())

    def test_other_stable_tip_is_not_overwritten(self):
        self.git('switch', '-c', 'stable')
        (self.sdk / 'source.txt').write_text('other commit\n')
        self.git('add', '.')
        self.git('commit', '-m', 'Other work')
        stable = self.git('rev-parse', 'HEAD').stdout
        self.git('checkout', '--detach', self.revision)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git('rev-parse', 'stable').stdout, stable)

    def test_sdk_symlink_is_rejected(self):
        link = self.root / 'sdk-link'
        link.symlink_to(self.sdk, target_is_directory=True)
        self.assertNotEqual(self.run_helper(directory=link).returncode, 0)

    def test_requested_other_version_is_rejected(self):
        self.assertNotEqual(self.run_helper(version='3.24.5').returncode, 0)
        self.assertFalse((self.root / 'invocations.log').exists())

    def test_installer_failure_is_not_ignored(self):
        self.assertEqual(self.run_helper(directory=self.root / 'new-sdk').returncode, 97)

    def test_fdroid_uses_the_shared_immutable_sdk_preparation(self):
        text = (ROOT / 'flutter/build_fdroid.sh').read_text()
        function = text.split('prepare_flutter() {', 1)[1].split('# Start of script', 1)[0]
        self.assertIn('tools/native/prepare-fdroid-flutter.sh', function)
        self.assertNotIn('git restore', function)
        self.assertNotIn('git checkout', function)


if __name__ == '__main__':
    unittest.main()
