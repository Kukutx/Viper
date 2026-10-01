//! Viper's TOTP parameters and fallible wall-clock boundary.
use hbb_common::ResultType;
use std::time::{SystemTime, SystemTimeError, UNIX_EPOCH};
use totp_rs::{Algorithm, Builder, Token, Totp};

pub(crate) fn build_totp(secret: &[u8], digits: usize, account: &str) -> ResultType<Totp> {
    Ok(Builder::new()
        .with_algorithm(Algorithm::SHA1)
        .with_digits(digits.try_into()?)
        .with_skew(1)
        .with_step_duration(30)
        .with_secret(secret)
        .with_issuer(Some("RustDesk Connection"))
        .with_account_name(account)
        .build()?)
}

// The upstream *_current methods now panic before the Unix epoch. Keep clock
// errors fallible so enrollment and login cannot authorize or crash on them.
pub(crate) fn verify_at(
    totp: &Totp,
    code: &str,
    time: SystemTime,
) -> Result<bool, SystemTimeError> {
    let seconds = time.duration_since(UNIX_EPOCH)?.as_secs();
    Ok(totp.check(code, seconds).is_some())
}

pub(crate) fn generate_at(totp: &Totp, time: SystemTime) -> Result<Token, SystemTimeError> {
    let seconds = time.duration_since(UNIX_EPOCH)?.as_secs();
    Ok(totp.generate(seconds))
}
