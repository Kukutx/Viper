from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_bridge_outputs as outputs


class BridgeOutputTests(unittest.TestCase):
    def git(self, *arguments):
        return subprocess.run(['git', *arguments], cwd=self.root, check=True, capture_output=True)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Bridge output test')
        for name in outputs.REQUIRED:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('generated fixture\n')
        (self.root / '.gitignore').write_text('*.h\nflutter/lib/generated/*\n')
        self.git('add', '-f', '.', *outputs.REQUIRED)
        self.git('commit', '-qm', 'fixture')

    def test_complete_tracked_outputs(self):
        outputs.check(self.root)

    def test_missing_dart_output(self):
        (self.root / outputs.REQUIRED[-1]).unlink()
        with self.assertRaises(ValueError): outputs.check(self.root)

    def test_empty_output(self):
        (self.root / outputs.REQUIRED[0]).write_bytes(b'')
        with self.assertRaises(ValueError): outputs.check(self.root)

    def test_untracked_ignored_output(self):
        self.git('rm', '--cached', outputs.REQUIRED[-1])
        with self.assertRaises(ValueError): outputs.check(self.root)

    def test_generated_dart_drift(self):
        (self.root / outputs.REQUIRED[-1]).write_text('different\n')
        with self.assertRaises(subprocess.CalledProcessError): outputs.check(self.root)

    def test_regeneration_drift(self):
        (self.root / outputs.REQUIRED[0]).write_text('changed\n')
        with self.assertRaises(subprocess.CalledProcessError): outputs.check(self.root)

    def test_staged_drift(self):
        (self.root / outputs.REQUIRED[0]).write_text('changed\n')
        self.git('add', outputs.REQUIRED[0])
        with self.assertRaises(subprocess.CalledProcessError): outputs.check(self.root)

    def test_new_ignored_generated_file(self):
        (self.root / outputs.DART_DIRECTORY / 'new.dart').write_text('new\n')
        with self.assertRaises(ValueError): outputs.check(self.root)

    def test_new_committed_generated_file(self):
        (self.root / outputs.DART_DIRECTORY / 'new.dart').write_text('new\n')
        self.git('add', '-f', outputs.DART_DIRECTORY + '/new.dart')
        self.git('commit', '-qm', 'new generator output')
        outputs.check(self.root)

    def test_symlink_output(self):
        path = self.root / outputs.REQUIRED[0]
        path.unlink()
        path.symlink_to(self.root / outputs.REQUIRED[-1])
        with self.assertRaises(ValueError): outputs.check(self.root)


if __name__ == '__main__':
    unittest.main()
