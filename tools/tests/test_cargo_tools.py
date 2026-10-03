import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cargo_tools


class CargoToolTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'configs').mkdir()
        self.config = self.root / 'configs/toolchain.json'
        self.config.write_text(json.dumps({'cargo_expand': '1.0.126'}))

    def test_missing_tool_installs_locked_into_project(self):
        with patch.object(cargo_tools.subprocess, 'run') as run, patch.object(cargo_tools.subprocess, 'check_output', return_value='cargo-expand 1.0.126\n'):
            env = cargo_tools.expand_environment(self.root)
        command = run.call_args.args[0]
        self.assertEqual(command, ['cargo', 'install', 'cargo-expand', '--version', '1.0.126', '--locked', '--root', str(self.root / '.tools/cargo')])
        self.assertTrue(run.call_args.kwargs['check'])
        self.assertTrue(env['PATH'].startswith(str(self.root / '.tools/cargo/bin')))

    def test_existing_exact_tool_is_reused(self):
        executable = self.root / '.tools/cargo/bin' / ('cargo-expand.exe' if cargo_tools.os.name == 'nt' else 'cargo-expand')
        executable.parent.mkdir(parents=True)
        executable.touch()
        with patch.object(cargo_tools.subprocess, 'run') as run, patch.object(cargo_tools.subprocess, 'check_output', return_value='cargo-expand 1.0.126\n'):
            cargo_tools.expand_environment(self.root)
        run.assert_not_called()

    def test_reject_version_range(self):
        self.config.write_text(json.dumps({'cargo_expand': '^1.0.126'}))
        with self.assertRaises(ValueError): cargo_tools.expand_environment(self.root)

    def test_reject_prerelease(self):
        self.config.write_text(json.dumps({'cargo_expand': '1.0.127-beta.1'}))
        with self.assertRaises(ValueError): cargo_tools.expand_environment(self.root)

    def test_install_failure_is_fatal(self):
        with patch.object(cargo_tools.subprocess, 'run', side_effect=subprocess.CalledProcessError(12, ['cargo'])):
            with self.assertRaises(subprocess.CalledProcessError): cargo_tools.expand_environment(self.root)

    def test_installed_wrong_version_is_fatal(self):
        with patch.object(cargo_tools.subprocess, 'run'), patch.object(cargo_tools.subprocess, 'check_output', return_value='cargo-expand 1.0.1'):
            with self.assertRaises(ValueError): cargo_tools.expand_environment(self.root)

    def test_symlinked_tool_directory_is_rejected(self):
        (self.root / '.tools').symlink_to(self.root / 'configs', target_is_directory=True)
        with self.assertRaises(ValueError): cargo_tools.expand_environment(self.root)


if __name__ == '__main__':
    unittest.main()
