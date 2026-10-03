"""Guard the HTTP migration's feature, trust and isolated-test boundaries."""
from pathlib import Path
import os
import subprocess
import tempfile
import tomllib
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class HttpDependencyTests(unittest.TestCase):
    def test_exact_reviewed_range_and_explicit_features(self):
        dependency = tomllib.loads((ROOT / 'Cargo.toml').read_text())['dependencies']['reqwest']
        self.assertEqual(dependency['version'], '0.13.5')
        self.assertIs(dependency['default-features'], False)
        self.assertEqual(set(dependency['features']), {
            'blocking', 'socks', 'json', 'query', 'native-tls-no-alpn',
            'rustls-no-provider', 'gzip', 'zstd'})

    def test_private_integration_target_requires_explicit_fixture_setup(self):
        manifest = tomllib.loads((ROOT / 'Cargo.toml').read_text())
        target = next(t for t in manifest['test'] if t['name'] == 'http_dependency_contract')
        self.assertEqual(target['required-features'], ['http-contract-tests'])
        self.assertEqual(manifest['features']['http-contract-tests'], [])
        self.assertNotIn('http-contract-tests', manifest['features']['default'])
        script = (ROOT / 'tools/native/test-http.sh').read_text()
        self.assertEqual(script.count('--features flutter,linux-pkg-config,http-contract-tests'), 2)
        self.assertIn('timeout --kill-after=5s 180s env HOME=', script)

    def test_lock_has_one_current_http_client(self):
        packages = tomllib.loads((ROOT / 'Cargo.lock').read_text())['package']
        clients = [p for p in packages if p['name'] == 'reqwest']
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]['version'], '0.13.5')
        self.assertEqual(clients[0]['checksum'], '16a1cfa75cc186dd73d5818e510e042e40927bccc9c236b061cea97e1eb08029')
        self.assertIn('rustls-platform-verifier', clients[0]['dependencies'])
        self.assertEqual(len([p for p in packages if p.get('source', '').startswith('git+')]), 59)

    def test_both_factories_use_the_same_shared_trust_configuration(self):
        source = (ROOT / 'src/hbbs_http/http_client.rs').read_text()
        self.assertEqual(source.count('hbb_common::verifier::client_config($danger_accept_invalid_cert)?'), 1)
        self.assertIn('builder.tls_backend_preconfigured(client_config)', source)
        self.assertIn('client_config.alpn_protocols = vec![b"http/1.1".to_vec()]', source)
        self.assertIn('builder.tls_backend_native()', source)
        self.assertIn('builder.tls_danger_accept_invalid_certs(true)', source)
        self.assertIn('$builder.no_proxy()', source)
        self.assertEqual(source.count('configure_http_client!(builder, tls_type, danger_accept_invalid_cert,'), 2)
        for old in ['.use_rustls_tls(', '.use_native_tls(', '.use_preconfigured_tls(', '.danger_accept_invalid_certs(']:
            self.assertNotIn(old, source)

    def test_client_construction_is_fallible_and_proxy_failure_cannot_go_direct(self):
        source = (ROOT / 'src/hbbs_http/http_client.rs').read_text()
        self.assertIn(') -> ResultType<SyncClient>', source)
        self.assertIn(') -> ResultType<AsyncClient>', source)
        self.assertNotIn('<$Client>::new()', source)
        self.assertNotIn('Failed to set up proxy', source)
        self.assertNotIn('Failed to configure proxy', source)
        contract = (ROOT / 'tests/http_dependency_contract.rs').read_text()
        self.assertIn('invalid_explicit_proxy_configuration_never_falls_back_to_direct_sync', contract)
        self.assertIn('invalid_explicit_proxy_configuration_never_falls_back_to_direct_async', contract)

    def test_automatic_insecure_tls_fallback_requires_the_explicit_option(self):
        source = (ROOT / 'src/hbbs_http/http_client.rs').read_text()
        self.assertIn('pub(crate) fn allow_insecure_tls_fallback()', source)
        self.assertIn('keys::OPTION_ALLOW_INSECURE_TLS_FALLBACK', source)
        common = (ROOT / 'src/common.rs').read_text()
        self.assertEqual(common.count('allow_insecure_tls_fallback()'), 2)
        contract = (ROOT / 'tests/http_dependency_contract.rs').read_text()
        for name in [
            'automatic_sync_tls_probe_keeps_certificate_validation_strict_by_default',
            'automatic_async_tls_probe_keeps_certificate_validation_strict_by_default',
            'insecure_tls_probe_requires_explicit_configuration',
        ]:
            self.assertIn(name, contract)

    def test_strict_factories_preserve_https_and_safe_cache_checks(self):
        source = (ROOT / 'src/hbbs_http/http_client.rs').read_text()
        self.assertEqual(source.count('parsed_url.scheme() != "https"'), 2)
        self.assertEqual(source.count('cached_tls_type.is_some() && cached_danger_accept_invalid_cert == Some(false)'), 2)
        self.assertEqual(source.count('        Some(false),\n        Some(false),'), 2)
        self.assertIn('if !auth.username().is_empty() && !auth.password().is_empty()', source)

    def test_real_test_compiles_the_production_module_and_is_not_ignored(self):
        source = (ROOT / 'tests/http_dependency_contract.rs').read_text()
        self.assertIn('#[path = "../src/hbbs_http/http_client.rs"]', source)
        self.assertIn('TcpListener::bind("127.0.0.1:0")', source)
        self.assertIn('shared_rustls_configuration_is_accepted_without_a_backend_fallback', source)
        self.assertNotIn('#[ignore]', source)
        self.assertNotIn('https://example.com', source)
        for name in ['untrusted', 'wrong-host', 'socks5', 'proxy-authorization', 'content-length', 'gzip', 'zstd']:
            self.assertIn(name, source)

    def test_ci_executes_http_before_real_ffi_and_cannot_ignore_failure(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/flutter-validate.yml').read_text())
        steps = workflow['jobs']['linux']['steps']
        tests = [s for s in steps if s.get('run') == 'bash tools/native/test-http.sh']
        self.assertEqual(len(tests), 1)
        self.assertNotIn('if', tests[0])
        self.assertNotIn('continue-on-error', tests[0])
        ffi = next(i for i, s in enumerate(steps) if s.get('name') == 'Exercise actual synchronous and asynchronous FFI')
        self.assertLess(steps.index(tests[0]), ffi)
        self.assertEqual(workflow['permissions'], {'contents': 'read'})

    def test_test_keys_and_trust_are_temporary_not_uploaded(self):
        source = (ROOT / 'tools/native/test-http.sh').read_text()
        for needed in ['set -euo pipefail', 'mktemp -d', "trap 'rm -rf -- \"$fixture\"' EXIT",
                       'HOME="$fixture/home"', 'SSL_CERT_FILE="$fixture/ca.pem"',
                       '--locked', '--no-run --message-format=json', '--test-threads=1',
                       'HTTP_PROXY=http://127.0.0.1:9', 'NO_PROXY= no_proxy=']:
            self.assertIn(needed, source)
        self.assertNotIn('sudo', source)
        self.assertNotIn('update-ca-certificates', source)
        self.assertNotIn('tools/.reports/ca.key', source)
        self.assertNotIn('|| true', source)

    def test_fixture_setup_failure_cleans_keys_and_never_runs_cargo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            runner = root / 'runner'
            runner.mkdir()
            (bin_dir / 'openssl').write_text('#!/bin/sh\nexit 41\n')
            marker = root / 'cargo-ran'
            (bin_dir / 'cargo').write_text(f'#!/bin/sh\ntouch "{marker}"\n')
            for file in bin_dir.iterdir():
                file.chmod(0o755)
            env = dict(os.environ, PATH=f'{bin_dir}{os.pathsep}{os.environ["PATH"]}', RUNNER_TEMP=str(runner))
            result = subprocess.run(['bash', str(ROOT / 'tools/native/test-http.sh')], cwd=root,
                                    env=env, capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())
            self.assertEqual(list(runner.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
