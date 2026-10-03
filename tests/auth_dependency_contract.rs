//! Tests the production TOTP policy, not a substitute implementation.
#[path = "../src/auth_2fa/totp.rs"]
mod totp;

use sha2::{Digest, Sha256, Sha512};
use std::time::{Duration, UNIX_EPOCH};
use totp_rs::{Algorithm, Secret};

const SECRET: &[u8] = b"12345678901234567890";

#[test]
fn rfc6238_sha1_vectors_preserve_six_and_eight_digit_tokens() {
    let vectors = [
        (59, "94287082", "287082"),
        (1_111_111_109, "07081804", "081804"),
        (1_111_111_111, "14050471", "050471"),
        (1_234_567_890, "89005924", "005924"),
        (2_000_000_000, "69279037", "279037"),
        (20_000_000_000, "65353130", "353130"),
    ];
    for (digits, index) in [(6, 2), (8, 1)] {
        let value = totp::build_totp(SECRET, digits, "123456789").unwrap();
        for (seconds, eight, six) in vectors {
            let expected = if index == 2 { six } else { eight };
            let time = UNIX_EPOCH + Duration::from_secs(seconds);
            assert_eq!(totp::generate_at(&value, time).unwrap().to_string(), expected);
            assert!(totp::verify_at(&value, expected, time).unwrap());
        }
    }
}

#[test]
fn configured_policy_and_secret_are_not_changed_by_builder_defaults() {
    let value = totp::build_totp(SECRET, 6, "123456789").unwrap();
    assert_eq!(value.algorithm(), Algorithm::SHA1);
    assert_eq!(value.digits(), 6);
    assert_eq!(value.skew(), 1);
    assert_eq!(value.step(), 30);
    assert_eq!(value.secret().as_bytes(), SECRET);
    assert_eq!(value.account_name(), "123456789");
    assert_eq!(value.issuer(), Some("RustDesk Connection"));
}

#[test]
fn login_skew_accepts_only_the_original_one_step_window() {
    let value = totp::build_totp(SECRET, 6, "123456789").unwrap();
    let seconds = 1_234_567_890_u64;
    let time = UNIX_EPOCH + Duration::from_secs(seconds);
    for delta in [-60_i64, -30, 0, 30, 60] {
        let token = value.generate((seconds as i64 + delta) as u64).to_string();
        assert_eq!(totp::verify_at(&value, &token, time).unwrap(), delta.abs() <= 30);
    }
}

#[test]
fn malformed_codes_are_not_normalized_into_valid_tokens() {
    let value = totp::build_totp(SECRET, 6, "123456789").unwrap();
    let time = UNIX_EPOCH + Duration::from_secs(1_234_567_890);
    assert!(totp::verify_at(&value, "005924", time).unwrap());
    for code in ["", "5924", "+05924", " 05924", "005924 ", "005924\n", "００５９２４", "00-924", "00592a", "000000"] {
        assert!(!totp::verify_at(&value, code, time).unwrap(), "invalid fixture accepted");
    }
}

#[test]
fn clock_before_epoch_returns_an_error_in_both_authentication_paths() {
    let value = totp::build_totp(SECRET, 6, "123456789").unwrap();
    let time = UNIX_EPOCH - Duration::from_secs(1);
    assert!(totp::generate_at(&value, time).is_err());
    assert!(totp::verify_at(&value, "755224", time).is_err());
}

#[test]
fn epoch_boundary_does_not_underflow_the_skew_window() {
    let value = totp::build_totp(SECRET, 6, "123456789").unwrap();
    assert_eq!(totp::generate_at(&value, UNIX_EPOCH).unwrap().to_string(), "755224");
    assert!(totp::verify_at(&value, "755224", UNIX_EPOCH).unwrap());
}

#[test]
fn invalid_stored_digits_cannot_be_truncated_or_accepted() {
    for digits in [0, 5, 9, 255, 262, usize::MAX] {
        assert!(totp::build_totp(SECRET, digits, "123456789").is_err());
    }
    for digits in [6, 7, 8] {
        assert_eq!(totp::build_totp(SECRET, digits, "123456789").unwrap().digits() as usize, digits);
    }
}

#[test]
fn missing_or_short_stored_secrets_are_never_replaced_by_random_defaults() {
    for length in [0, 1, 15] {
        assert!(totp::build_totp(&SECRET[..length], 6, "123456789").is_err());
    }
    assert!(totp::build_totp(&SECRET[..16], 6, "123456789").is_ok());
}

#[test]
fn issuer_and_account_constraints_remain_validated() {
    assert!(totp::build_totp(SECRET, 6, "invalid:account").is_err());
    let no_account = totp::build_totp(SECRET, 6, "").unwrap();
    assert!(no_account.to_url().is_err());
}

#[test]
fn enrollment_uri_retains_issuer_secret_digits_and_period() {
    let value = totp::build_totp(SECRET, 6, "123456789").unwrap();
    let url = url::Url::parse(&value.to_url().unwrap()).unwrap();
    assert_eq!(url.scheme(), "otpauth");
    assert_eq!(url.host_str(), Some("totp"));
    assert_eq!(url.path(), "/RustDesk%20Connection:123456789");
    let query: std::collections::BTreeMap<_, _> = url.query_pairs().into_owned().collect();
    assert_eq!(query["secret"], "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ");
    assert_eq!(query["issuer"], "RustDesk Connection");
    assert_eq!(query.get("digits").map(String::as_str).unwrap_or("6"), "6");
    assert_eq!(query.get("period").map(String::as_str).unwrap_or("30"), "30");
    assert_eq!(query.get("algorithm").map(String::as_str).unwrap_or("SHA1"), "SHA1");
}

#[test]
fn generated_secrets_keep_the_original_160_bit_raw_storage() {
    let secret = Secret::generate();
    assert_eq!(secret.as_bytes().len(), 20);
    let raw = secret.as_bytes().to_vec();
    let value = totp::build_totp(&raw, 6, "123456789").unwrap();
    assert_eq!(value.secret().as_bytes(), raw);
}

#[test]
fn sha256_known_answers_and_incremental_input_remain_identical() {
    for (input, expected) in [
        ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
        ("hello world", "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"),
    ] {
        assert_eq!(hex::encode(Sha256::digest(input.as_bytes())), expected);
        let mut incremental = Sha256::new();
        for byte in input.as_bytes() {
            incremental.update([*byte]);
        }
        let result: [u8; 32] = incremental.finalize().into();
        assert_eq!(hex::encode(result), expected);
    }
}

#[test]
fn sha512_known_answer_is_preserved() {
    assert_eq!(
        hex::encode(Sha512::digest(b"abc")),
        concat!("ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a",
                "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f")
    );
}

#[test]
fn direct_and_shared_hash_implementations_agree_without_moving_the_shared_fork() {
    use hbb_common::sha2::{Digest as SharedDigest, Sha256 as SharedSha256};
    for bytes in [vec![], vec![0], vec![255; 4097], (0..=255).collect()] {
        assert_eq!(Sha256::digest(&bytes).as_slice(), SharedSha256::digest(&bytes).as_slice());
    }
}
