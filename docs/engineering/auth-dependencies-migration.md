# Authentication dependency migration

Version review: 2026-10-01. Base task revision: `e2ff7ab2ceef9f1602848d48c9202df58a71c385`.

## Versions and scope

The root crate moves its direct `sha2` dependency from 0.10 to 0.11.0 and `totp-rs` from 5.x to 6.0.0. The latter uses its `Totp`/`Builder`/`Token` API with `default-features = false` and only `std`, `gen_secret`, and `otpauth` enabled. The upstream `migration` compatibility feature and serde compatibility representation are not used. The root crate's minimum Rust declaration becomes 1.88, the TOTP dependency's minimum; the actual project compiler remains the pinned 1.98.1.

Sources: [SHA-2 release](https://docs.rs/crate/sha2/0.11.0), [TOTP release](https://docs.rs/crate/totp-rs/6.0.0), and [upstream API migration](https://github.com/constantoine/totp-rs/blob/v6.0.0/MIGRATION.md). API signatures are checked against the tagged source, not inferred from deprecated aliases.

This is not a global cryptography replacement. `hbb_common` and all other maintained Git dependencies keep their revisions and their own transitive hash versions. Viper call sites deliberately importing `hbb_common::sha2` continue to use that shared implementation. The root's direct SHA-2 consumer and the new TOTP dependency use 0.11; old transitive versions are not forced out by overrides.

## Preserved authentication behavior

Viper still persists its own `TOTPInfo` fields (`name: String`, `secret: Vec<u8>`, `digits: usize`, `created_at: i64`), not the upstream `Totp` serde representation. The existing encrypted byte-vector format, encryption version `00`, option key, secret decryption rules and application identity are unchanged. Existing users do not need to re-enroll solely because of this dependency migration.

The production `src/auth_2fa/totp.rs` module owns only the construction and wall-clock boundary required by the new API. It explicitly retains SHA-1, the stored digit count, one adjacent step on either side, a 30-second period, `RustDesk Connection`, and the account name. Supplied secrets are always set explicitly, so missing or invalid stored secrets fail validation rather than triggering the builder's random-secret default. Oversized `usize` digit counts are checked before narrowing to the new API's `u8`.

Upstream 6.0 changes current-time methods from fallible results to panics for clocks before the Unix epoch. Viper obtains a fallible timestamp and calls the explicit-time methods. Enrollment and connection checks preserve their prior error handling. A valid token is represented by `Some(counter)`, not by assuming the result is a boolean. Rate limiting, trusted-device rules, reconnect behavior and the conditions for granting authorization are not changed. Telegram formatting receives the new displayable `Token`; delivery, destination selection and message content are otherwise unchanged. No tokens or secrets are written to diagnostic logs.

The enrollment URI is now fallible. Pending enrollment state is activated only after successful URI creation. A failed URI is not returned or persisted as if enrollment had succeeded.

## Regression evidence

`tests/auth_dependency_contract.rs` compiles the same production policy module used by enrollment and login. It covers RFC 6238 SHA-1 vectors with six/eight digits, leading zeros, exact clock-skew bounds, malformed input, pre-epoch and epoch clocks, invalid stored parameters, secret size, URI fields, SHA-256/SHA-512 known answers and direct/shared SHA-256 output parity. `tools/tests/test_auth_dependencies.py` guards call-site integration, unchanged storage/encryption fields, disabled compatibility features and unconditional fail-closed CI execution.

The normal Linux bridge workflow runs the Rust integration target with the committed lock after the native library build. Platform compilation still separately checks the call-site changes on Windows, macOS, Android and iOS. Precise completed run IDs are recorded in PR #1; neither configuration nor an in-progress run is counted as successful validation.

## Remaining boundary

These deterministic tests do not exercise a real authenticator application, encrypted credentials copied from a user's machine, Telegram delivery, cross-device remote login, device permissions or signed installation. They do not add replay protection or change the existing trusted-device/security policy. HTTP/TLS, shared-server crypto, native dependency majors and release/deployment work outside this migration remain separate tasks. No production signing, publication or deployment is performed.
