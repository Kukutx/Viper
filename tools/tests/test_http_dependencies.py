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
        self.assertEqual(source.count('hbb_common::verifier::client_config($danger_accept_invalid_cert)'), 1)
        self.assertIn('builder.tls_backend_preconfigured(client_config)', source)
        self.assertIn('config.alpn_protocols = vec![b"http/1.1".to_vec()]', source)
        self.assertIn('builder.tls_backend_native()', source)
        self.assertIn('builder.tls_danger_accept_invalid_certs(true)', source)
        self.assertIn('$builder.no_proxy()', source)
        self.assertEqual(source.count('configure_http_client!(builder, tls_type, danger_accept_invalid_cert,'), 2)
        for old in ['.use_rustls_tls(', '.use_native_tls(', '.use_preconfigured_tls(', '.danger_accept_invalid_certs(']:
            self.assertNotIn(old, source)

    def test_strict_factories_preserve_https_and_safe_cache_checks(self):
        source = (ROOT / 'src/hbbs_http/http_client.rs').read_text()
        self.assertEqual(source.count('parsed_url.scheme() != "https"'), 2)
        self.assertEqual(source.count('matches!(cached_tls_type, Some(TlsType::Rustls | TlsType::NativeTls))'), 2)
        self.assertEqual(source.count('        Some(false),\n        Some(false),\n        true,'), 2)
        self.assertEqual(source.count('.https_only(https_only)'), 2)
        self.assertIn('if !auth.username().is_empty() && !auth.password().is_empty()', source)

    def test_configuration_failures_cannot_create_a_default_client(self):
        source = (ROOT / 'src/hbbs_http/http_client.rs').read_text()
        for forbidden in ['<$Client>::new()', 'unwrap_or_else(', 'Failed to get client config']:
            self.assertNotIn(forbidden, source)
        self.assertIn('Ok(builder.build().map_err(|_| HttpClientConfigError::Builder)?)', source)
        self.assertIn('.map_err(|_| HttpClientConfigError::Tls)?', source)
        self.assertEqual(source.count('.map_err(|_| HttpClientConfigError::Proxy)?'), 2)
        self.assertIn('-> ResultType<SyncClient>', source)
        self.assertIn('-> ResultType<AsyncClient>', source)
        self.assertIn('Invalid configured HTTP proxy', source)

    def test_account_upload_and_request_callers_propagate_configuration_errors(self):
        account = (ROOT / 'src/hbbs_http/account.rs').read_text()
        self.assertIn('fn ensure_client(api_server: &str) -> ResultType<()>', account)
        self.assertEqual(account.count('Self::ensure_client(api_server)?;'), 2)
        self.assertIn('create_http_client_with_url(&login_option_url)?;', account)
        self.assertLess(account.index('create_http_client_with_url(&login_option_url)?;'),
                        account.index('write_guard.warmed_api_server ='))
        upload = (ROOT / 'src/hbbs_http/record_upload.rs').read_text()
        self.assertIn('let client = match create_http_client_with_url(&login_option_url)', upload)
        error = upload[upload.index('Err(error) => {'):upload.index('let mut uploader')]
        self.assertIn('log::error!', error)
        self.assertIn('return;', error)
        common = (ROOT / 'src/common.rs').read_text()
        self.assertEqual(common.count('let client = create_http_client_async(tls_type, false)?;'), 2)
        self.assertIn('    )?\n    .post(url);', common)
        self.assertIn('    )?;\n    let normalized_method', common)
        self.assertEqual(common.count('Err(error) => !error.is::<crate::hbbs_http::HttpClientConfigError>()'), 2)

    def test_negative_transport_contracts_are_native_not_ignored(self):
        source = (ROOT / 'tests/http_dependency_contract.rs').read_text()
        for name in [
            'synchronous_invalid_proxy_never_returns_a_default_client_or_warms_cache',
            'asynchronous_invalid_proxy_never_returns_a_default_client_or_warms_cache',
            'synchronous_unavailable_proxy_does_not_send_upload_directly',
            'asynchronous_unavailable_proxy_does_not_send_credentials_directly',
            'strict_synchronous_clients_block_http_redirects_and_reuse_on_plain_urls',
            'strict_asynchronous_clients_block_http_redirects_and_reuse_on_plain_urls',
            'strict_synchronous_factory_rejects_plain_cache_and_keeps_https_redirects',
            'strict_asynchronous_factory_rejects_plain_cache_and_keeps_https_redirects',
            'nonstrict_sync_factory_does_not_accept_untrusted_tls_without_user_opt_in',
            'nonstrict_async_factory_does_not_accept_untrusted_tls_without_user_opt_in',
        ]:
            self.assertIn('fn ' + name + '()', source)
        self.assertNotIn('#[ignore]', source)

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
