import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("viper", Path(__file__).parents[1] / "viper.py")
viper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(viper)
SHA = "a" * 40
LOCK = {"actions/checkout": {"sha": SHA, "version": "v7.0.1"}}


class ActionsTests(unittest.TestCase):
    def test_exact_pin(self):
        self.assertIn(SHA, viper.action_text("- uses: actions/checkout@" + SHA, LOCK))

    def test_reject_tag(self):
        with self.assertRaises(ValueError):
            viper.action_text("- uses: actions/checkout@v7", LOCK)

    def test_write_and_idempotence(self):
        text = viper.action_text("- uses: actions/checkout@v4 # old", LOCK, True)
        self.assertEqual(text, viper.action_text(text, LOCK, True))

    def test_ignore_comments_and_local(self):
        text = "# - uses: actions/checkout@v3\n- uses: ./.github/actions/local"
        self.assertEqual(text, viper.action_text(text, LOCK))

    def test_reject_retired_action(self):
        with self.assertRaises(ValueError):
            viper.action_text("- uses: actions-rs/cargo@v1", LOCK, True)

    def test_reject_unknown(self):
        with self.assertRaises(ValueError):
            viper.action_text("- uses: someone/unknown@" + SHA, LOCK)


class InventoryTests(unittest.TestCase):
    def test_alias_and_target_scope(self):
        data = {"target": {"cfg(unix)": {"dependencies": {"pulse": {"package": "libpulse-binding", "version": "2.27"}}}}}
        row = viper.cargo_rows("Cargo.toml", data)[0]
        self.assertEqual(row["name"], "libpulse-binding")
        self.assertEqual(row["alias"], "pulse")
        self.assertEqual(row["scope"], "target.cfg(unix).dependencies")

    def test_fork_not_registry(self):
        rows = viper.cargo_rows("Cargo.toml", {"dependencies": {"fork": {"git": "https://github.com/example/fork", "rev": SHA}}})
        self.assertEqual(rows[0]["source"], "git")

    def test_workspace_not_registry(self):
        rows = viper.cargo_rows("Cargo.toml", {"dependencies": {"shared": {"workspace": True}}})
        self.assertEqual(rows[0]["source"], "workspace")


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "client.bin").write_bytes(b"release")

    def save(self):
        data = viper.make_manifest(self.root, SHA)
        self.write(data)
        return data

    def write(self, data):
        (self.root / "release-manifest.json").write_text(json.dumps(data), encoding="utf-8")

    def test_nested_manifest_is_not_excluded(self):
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "release-manifest.json").write_text("tracked artifact")
        data = self.save()
        self.assertEqual(len(data["artifacts"]), 2)
        (nested / "release-manifest.json").write_text("tampered")
        with self.assertRaises(ValueError):
            viper.verify_manifest(self.root)

    def test_roundtrip(self):
        self.save()
        viper.verify_manifest(self.root)

    def test_modified(self):
        self.save()
        (self.root / "client.bin").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            viper.verify_manifest(self.root)

    def test_added(self):
        self.save()
        (self.root / "extra.bin").write_bytes(b"x")
        with self.assertRaises(ValueError):
            viper.verify_manifest(self.root)

    def test_missing(self):
        self.save()
        (self.root / "client.bin").unlink()
        with self.assertRaises(ValueError):
            viper.verify_manifest(self.root)

    def test_duplicate(self):
        data = self.save()
        data["artifacts"] *= 2
        self.write(data)
        with self.assertRaises(ValueError):
            viper.verify_manifest(self.root)

    def test_traversal(self):
        data = self.save()
        data["artifacts"][0]["path"] = "../client.bin"
        self.write(data)
        with self.assertRaises(ValueError):
            viper.verify_manifest(self.root)

    def test_absolute_path(self):
        data = self.save()
        data["artifacts"][0]["path"] = "/client.bin"
        self.write(data)
        with self.assertRaises(ValueError):
            viper.verify_manifest(self.root)

    def test_empty_release(self):
        (self.root / "client.bin").unlink()
        with self.assertRaises(ValueError):
            viper.make_manifest(self.root, SHA)

    def test_short_revision(self):
        with self.assertRaises(ValueError):
            viper.make_manifest(self.root, "abcdef")

    @unittest.skipIf(os.name == "nt", "Requires POSIX symlinks")
    def test_symlink(self):
        (self.root / "link.bin").symlink_to(self.root / "client.bin")
        with self.assertRaises(ValueError):
            viper.make_manifest(self.root, SHA)


if __name__ == "__main__":
    unittest.main()
