"""Keep reviewed Windows dependencies, native contracts and real portable payloads connected."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_api_contract', ROOT / 'tools/windows_native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class WindowsDependencyTests(unittest.TestCase):
    def test_manifest_and_lock_use_reviewed_published_packages(self):
        manifest = tomllib.loads((ROOT / 'Cargo.toml').read_text())
        dependencies = manifest['target']['cfg(target_os = "windows")']['dependencies']
        self.assertEqual(dependencies['windows']['version'], '0.62.2')
        self.assertEqual(dependencies['winreg'], '0.56.0')
        self.assertEqual(dependencies['windows-service'], '0.8.1')
        portable = tomllib.loads((ROOT / 'libs/portable/Cargo.toml').read_text())
        self.assertEqual(portable['target']['cfg(target_os = "windows")']['dependencies']['windows']['version'], '0.62.2')
        self.assertEqual(manifest['package']['rust-version'], '1.88')
        packages = tomllib.loads((ROOT / 'Cargo.lock').read_text())['package']
        for name, version, checksum in [
            ('windows', '0.62.2', '527fadee13e0c05939a6a05d5bd6eec6cd2e3dbd648b9f8e447c6518133d8580'),
            ('windows-service', '0.8.1', '857224b3b211c6f3616921f081ee54721ee3ad2ace2fac6a6337e032f7b4dcf2'),
            ('winreg', '0.56.0', '7d6f32a0ff4a9f6f01231eb2059cc85479330739333e0e58cadf03b6af2cca10'),
        ]:
            selected = [p for p in packages if p['name'] == name and p['version'] == version]
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]['checksum'], checksum)
        self.assertFalse(any(p['name'] == 'windows' and p['version'] == '0.61.3' for p in packages))
        self.assertFalse(any(p['name'] == 'windows-service' and p['version'] == '0.6.0' for p in packages))

    def test_registry_data_ownership_and_serialized_recovery_stay_explicit(self):
        source = (ROOT / 'src/platform/windows.rs').read_text()
        self.assertNotIn('winreg::HKEY_CURRENT_USER', source)
        self.assertIn("RegValue<'static>", source)
        self.assertIn('old: (Vec<u8>, isize)', source)
        self.assertIn('new: (Vec<u8>, isize)', source)
        self.assertIn('restore_connectivity_value(&reg_item, reg_recovery, force)', source)
        self.assertIn('#[cfg(test)]\nmod dependency_contract_tests;', source)

    def test_platform_and_audio_gates_precede_packaging(self):
        tree = ast.parse((ROOT / 'tools/windows_native.py').read_text())
        build = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
        calls = [n.value for n in build.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
        def logged(name):
            return next(c for c in calls if len(c.args) > 1 and isinstance(c.args[1], ast.Constant) and c.args[1].value == name)
        api = logged('windows-api-tests.log')
        self.assertEqual(ast.literal_eval(api.args[0]), [
            'cargo', 'test', '--locked', '--release', '--lib', '--features', 'flutter',
            'platform::windows::dependency_contract_tests', '--', '--test-threads=1'])
        self.assertLess(calls.index(logged('windows-audio-tests.log')), calls.index(api))
        self.assertLess(calls.index(api), calls.index(logged('windows-flutter.log')))
        portable = next(c for c in calls if isinstance(c.func, ast.Name) and c.func.id == 'build_portable')
        self.assertLess(calls.index(logged('windows-ffi.log')), calls.index(portable))

    def test_existing_portable_inputs_fail_before_any_child_process(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'libs/portable').mkdir(parents=True)
            data = root / 'libs/portable/data.bin'
            data.write_bytes(b'previous user build')
            with patch.object(native, 'ROOT', root), patch.object(native, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'overwrite portable build input'):
                    native.build_portable(root / 'bundle', 'x64')
                command.assert_not_called()
            self.assertEqual(data.read_bytes(), b'previous user build')

    def test_existing_portable_output_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'dist/windows-arm64-portable-unsigned').mkdir(parents=True)
            with patch.object(native, 'ROOT', root), patch.object(native, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'overwrite portable output'):
                    native.build_portable(root / 'bundle', 'arm64')
                command.assert_not_called()

    def test_portable_payload_test_is_explicit_and_compression_is_pinned(self):
        portable = tomllib.loads((ROOT / 'libs/portable/Cargo.toml').read_text())
        self.assertEqual(portable['features']['native-payload-tests'], [])
        self.assertNotIn('default', portable['features'])
        self.assertEqual((ROOT / 'libs/portable/requirements.txt').read_text().strip(), 'Brotli==1.2.0')
        source = (ROOT / 'libs/portable/src/bin_reader.rs').read_text()
        self.assertIn('#[cfg(all(test, windows, feature = "native-payload-tests"))]', source)
        self.assertIn('read_embedded().expect', source)
        self.assertIn('assert_eq!(actual_names, expected_names)', source)


if __name__ == '__main__':
    unittest.main()
