"""Guard the TOTP 6 migration boundary without invoking native build tools."""
from pathlib import Path
import re
import tomllib
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class AuthDependencyTests(unittest.TestCase):
    def test_current_api_has_no_migration_or_serde_compatibility_feature(self):
        manifest = tomllib.loads((ROOT / 'Cargo.toml').read_text())
        dependency = manifest['dependencies']['totp-rs']
        self.assertEqual(dependency['version'], '6.0.0')
        self.assertIs(dependency['default-features'], False)
        self.assertEqual(set(dependency['features']), {'std', 'gen_secret', 'otpauth'})
        self.assertEqual(manifest['dependencies']['sha2'], '0.11.0')
        self.assertEqual(manifest['package']['rust-version'], '1.88')

    def test_storage_schema_and_encryption_are_preserved(self):
        source = (ROOT / 'src/auth_2fa.rs').read_text()
        body = re.search(r'pub struct TOTPInfo \{(.*?)\n\}', source, re.S).group(1)
        self.assertEqual(re.findall(r'pub (\w+): ([^,]+),', body), [
            ('name', 'String'), ('secret', 'Vec<u8>'), ('digits', 'usize'), ('created_at', 'i64')])
        self.assertIn('encrypt_vec_or_original(self.secret.as_slice(), "00", 1024)', source)
        self.assertIn('decrypt_vec_or_original(&totp_info.secret, "00")', source)
        self.assertIn('serde_json::from_str::<TOTPInfo>(data)?', source)
        self.assertIn('serde_json::to_string(&totp_info)?', source)
        self.assertIn('secret.as_bytes().to_vec()', source)

    def test_enrollment_activates_pending_state_only_after_uri_success(self):
        source = (ROOT / 'src/auth_2fa.rs').read_text()
        start = source.index('if let Ok(code) = totp.to_url()')
        self.assertLess(start, source.index('*CURRENT_2FA.lock().unwrap() = Some((info, totp));'))
        self.assertIn('totp::verify_at(totp, &code, SystemTime::now())', source)
        self.assertNotIn('TOTP::', source)
        self.assertNotIn('get_url()', source)

    def test_server_uses_fallible_clock_paths_without_changing_authorization(self):
        source = (ROOT / 'src/server/connection.rs').read_text()
        self.assertIn('require_2fa: Option<totp_rs::Totp>', source)
        self.assertIn('crate::auth_2fa::totp::generate_at(totp, std::time::SystemTime::now())', source)
        self.assertIn('crate::auth_2fa::totp::verify_at(totp, &tfa.code, std::time::SystemTime::now())', source)
        self.assertNotIn('totp.generate_current()', source)
        self.assertNotIn('totp.check_current(', source)
        self.assertIn('self.check_failure(1).await', source)
        self.assertIn('if res {\n                        self.update_failure(failure, true, 1);', source)
        self.assertIn('self.send_login_error(crate::client::LOGIN_MSG_2FA_WRONG)', source)
        self.assertIn('Self::enable_trusted_devices()', source)

    def test_production_policy_does_not_use_unchecked_builder_or_panicking_clock(self):
        source = (ROOT / 'src/auth_2fa/totp.rs').read_text()
        for needed in ['.with_algorithm(Algorithm::SHA1)', '.with_digits(digits.try_into()?)',
                       '.with_skew(1)', '.with_step_duration(30)', '.with_secret(secret)',
                       '.with_issuer(Some("RustDesk Connection"))', '.build()?',
                       'time.duration_since(UNIX_EPOCH)?', 'totp.check(code, seconds).is_some()']:
            self.assertIn(needed, source)
        for forbidden in ['.build_noncompliant(', '.check_current(', '.generate_current(',
                          '.unwrap(', '.expect(', 'println!', 'log::', 'catch_unwind']:
            self.assertNotIn(forbidden, source)

    def test_real_regression_is_unconditional_and_fail_closed_in_ci(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/flutter-validate.yml').read_text())
        steps = workflow['jobs']['linux']['steps']
        selected = [step for step in steps if '--test auth_dependency_contract' in step.get('run', '')]
        self.assertEqual(len(selected), 1)
        step = selected[0]
        self.assertNotIn('if', step)
        self.assertNotIn('continue-on-error', step)
        self.assertIn('--locked', step['run'])
        self.assertIn('--features flutter,linux-pkg-config', step['run'])
        self.assertNotIn('--ignored', step['run'])
        self.assertIn('exit 1', step['run'])
        self.assertLess(next(i for i, item in enumerate(steps) if 'cargo build --locked' in item.get('run', '')), steps.index(step))
        self.assertEqual(workflow['permissions'], {'contents': 'read'})

    def test_vectors_compile_the_same_module_as_enrollment_and_login(self):
        source = (ROOT / 'tests/auth_dependency_contract.rs').read_text()
        self.assertIn('#[path = "../src/auth_2fa/totp.rs"]', source)
        self.assertIn('mod totp;', source)
        self.assertIn('clock_before_epoch_returns_an_error', source)
        self.assertIn('rfc6238_sha1_vectors', source)
        self.assertIn('direct_and_shared_hash_implementations_agree', source)
        self.assertNotIn('#[ignore]', source)


if __name__ == '__main__':
    unittest.main()
