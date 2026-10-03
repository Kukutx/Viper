"""Keep the Windows migration and its native regression attached to normal CI."""
import ast
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]


class WindowsDependencyTests(unittest.TestCase):
    def test_manifest_and_resolved_application_dependencies_agree(self):
        manifest = tomllib.loads((ROOT / 'Cargo.toml').read_text(encoding='utf-8'))
        deps = manifest['target']['cfg(target_os = "windows")']['dependencies']
        packages = tomllib.loads((ROOT / 'Cargo.lock').read_text(encoding='utf-8'))['package']
        for name, version in [('winreg', '0.56.0'), ('windows-service', '0.8.1')]:
            self.assertEqual(deps[name], version)
            package = next(p for p in packages if p['name'] == name and p['version'] == version)
            self.assertEqual(package['source'], 'registry+https://github.com/rust-lang/crates.io-index')
            self.assertRegex(package['checksum'], r'^[0-9a-f]{64}$')
            self.assertNotIn(name, manifest.get('patch', {}).get('crates-io', {}))
        application = next(p for p in packages if p['name'] == manifest['package']['name'])
        self.assertIn('winreg 0.56.0', application['dependencies'])
        self.assertIn('windows-service', application['dependencies'])
        self.assertNotIn('winreg 0.11.0', application['dependencies'])
        self.assertEqual(len([p for p in packages if p.get('source', '').startswith('git+')]), 59)

    def test_direct_windows_crate_uses_current_reviewed_api(self):
        root = tomllib.loads((ROOT / 'Cargo.toml').read_text(encoding='utf-8'))
        portable = tomllib.loads((ROOT / 'libs/portable/Cargo.toml').read_text(encoding='utf-8'))
        for manifest in (root, portable):
            dep = manifest['target']['cfg(target_os = "windows")']['dependencies']['windows']
            self.assertEqual(dep['version'], '0.62.2')
        packages = tomllib.loads((ROOT / 'Cargo.lock').read_text(encoding='utf-8'))['package']
        current = next(p for p in packages if p['name'] == 'windows' and p['version'] == '0.62.2')
        self.assertEqual(current['source'], 'registry+https://github.com/rust-lang/crates.io-index')
        self.assertEqual(len(current['checksum']), 64)
        application = next(p for p in packages if p['name'] == root['package']['name'])
        packer = next(p for p in packages if p['name'] == portable['package']['name'])
        self.assertIn('windows 0.62.2', application['dependencies'])
        self.assertIn('windows 0.62.2', packer['dependencies'])
        self.assertNotIn('windows 0.61.3', application['dependencies'])
        self.assertNotIn('windows 0.61.3', packer['dependencies'])

    def test_service_state_contract_uses_public_representation(self):
        source = (ROOT / 'src/platform/windows/reg_display_settings/dependency_tests.rs').read_text(encoding='utf-8')
        for state, value in [('Running', 4), ('Stopped', 1)]:
            self.assertNotIn(f'ServiceState::{state}.to_raw()', source)
            self.assertIn(f'assert_eq!(ServiceState::{state} as u32, {value});', source)

    def test_real_native_regressions_are_unconditional_and_precede_packaging(self):
        module = ast.parse((ROOT / 'tools/windows_native.py').read_text(encoding='utf-8'))
        build = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
        calls = [n.value for n in build.body if isinstance(n, ast.Expr)
                 and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                 and n.value.func.id == 'command']
        by_log = {c.args[1].value: c for c in calls if len(c.args) > 1 and isinstance(c.args[1], ast.Constant)}
        regression = by_log['windows-dependency-tests.log']
        self.assertEqual(ast.literal_eval(regression.args[0]), [
            'cargo', 'test', '--locked', '--release', '--lib', '--features', 'flutter',
            'windows_dependency', '--', '--test-threads=1'])
        self.assertLess(calls.index(by_log['windows-cargo.log']), calls.index(regression))
        self.assertLess(calls.index(by_log['windows-audio-tests.log']), calls.index(regression))
        self.assertLess(calls.index(regression), calls.index(by_log['windows-flutter.log']))
        source = (ROOT / 'src/platform/windows.rs').read_text(encoding='utf-8')
        self.assertIn('    #[cfg(test)]\n    mod dependency_tests;', source)
        tests = (ROOT / 'src/platform/windows/reg_display_settings/dependency_tests.rs').read_text(encoding='utf-8')
        self.assertEqual(tests.count('fn windows_dependency_'), 9)
        self.assertNotIn('#[ignore]', tests)
        self.assertNotIn('RegKey::predef(HKEY_LOCAL_MACHINE)', tests)
        self.assertNotIn('service_manager::', tests)


if __name__ == '__main__':
    unittest.main()
