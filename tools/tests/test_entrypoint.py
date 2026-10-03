import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parents[2] / "entrypoint.sh"


@unittest.skipIf(os.name == "nt", "POSIX container entrypoint")
class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = self.root / "args.json"
        cargo = self.root / "cargo"
        cargo.write_text(
            "#!" + sys.executable + "\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['ARG_CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n"
            "sys.exit(int(os.environ.get('EXIT_CODE', '0')))\n",
            encoding="utf-8",
        )
        cargo.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"], VIPER_WORKSPACE=str(self.root), ARG_CAPTURE=str(self.capture), EXIT_CODE="0")

    def invoke(self, *args):
        return subprocess.run(["sh", str(ENTRYPOINT), *args], env=self.env, cwd=self.root, capture_output=True, text=True)

    def test_default_arguments(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.capture.read_text()), ["build", "--locked", "--features", "flutter", "--lib"])

    def test_preserves_literal_arguments(self):
        args = ["test", "space value", "*", "one;echo nope", "$(touch pwned)"]
        result = self.invoke(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.capture.read_text()), args)
        self.assertFalse((self.root / "pwned").exists())

    def test_propagates_child_exit_code(self):
        self.env["EXIT_CODE"] = "37"
        self.assertEqual(self.invoke("build").returncode, 37)

    def test_missing_workspace_fails(self):
        self.env["VIPER_WORKSPACE"] = str(self.root / "missing")
        self.assertNotEqual(self.invoke("build").returncode, 0)
        self.assertFalse(self.capture.exists())
