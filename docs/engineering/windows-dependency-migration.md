# Windows registry and service dependency migration

Reviewed on 2026-10-02 from `655c019b63a96b7d2c0b7b19143cab601a3e79cf`.
The application's Windows dependencies move from winreg 0.11.0 to **0.56.0**
and windows-service 0.6.0 to **0.8.1**. The official registry's
`max_stable_version`, non-yanked status and package checksums were checked during
preparation; upstream API changes were reviewed against
[winreg](https://github.com/gentoo90/winreg-rs/blob/master/CHANGELOG.md) and
[windows-service v0.8.1](https://github.com/mullvad/windows-service-rs/releases/tag/v0.8.1).
This does not migrate every Windows binding or remove all old transitive crates.

## Runtime contract

winreg now stores `RegValue.bytes` as `Cow<[u8]>`. Values returned from registry
enumeration are explicitly owned (`RegValue<'static>`); snapshot comparisons accept
borrowed values but copy their bytes into the existing recovery record. `RegRecovery`
keeps its serialized `path`, `key`, `old` and `new` fields and `(Vec<u8>, isize)`
tuples. No settings migration or change to stored registry type numbers is needed.
The registry type enum is Clone but not Copy; the necessary type clones are retained.

Restore writes borrow the recovery bytes without changing them. The existing
check-before-write algorithm still restores only when the current raw value equals
the recorded replacement, unless the caller explicitly supplies `force`. Missing
keys, read errors and write errors still propagate. This is not an atomic registry
transaction; a change between the read and write remains outside this contract.
The small `restore_reg_value` helper permits regression tests against a private key;
the production entry still opens the same HKLM path with `KEY_READ | KEY_WRITE`.

The old winapi `HKEY_CURRENT_USER` import is removed so RegKey uses the matching
winreg/windows-sys handle. No pointer cast or registry-view fallback is introduced.
MSI scanning, 32/64-bit view flags, display settings paths, application identities,
service names, accepted service controls, startup/shutdown behavior and privileges
are not changed. windows-service's additional non-exhaustive variants are covered
by the existing wildcard; the service callback and dispatcher are not rewritten.

## Regression and normal CI

`src/platform/windows/reg_display_settings/dependency_tests.rs` adds nine Rust tests:
owned values after closing a key, UTF-16 text and numeric data, recovery JSON,
borrowed snapshots, conditional and forced restores, intervening value/type changes,
missing values, MSI metadata validation (including malformed DWORD) and service ABI
constant mappings. Registry tests use a unique HKCU Software child and clean it up;
normal completion requires successful cleanup, and unwinding has a cleanup fallback.
They never use the real GraphicsDrivers hive, HKLM, an installed application's keys
or the service control manager. Service constant tests are not service execution.

After the existing Release library build and audio tests, `tools/windows_native.py`
unconditionally runs:

```sh
cargo test --locked --release --lib --features flutter windows_dependency -- --test-threads=1
```

A failed command preserves `tools/.reports/windows-dependency-tests.log` and blocks
Flutter packaging. The normal x64 and arm64 workflow remains read-only and also
retains audio, package architecture/library consistency, real FFI and source-drift
checks. Two Python contracts keep the resolved application dependencies and this
unconditional ordering covered; the complete tool suite has 392 tests.

## Lockfile and preparation evidence

Cargo generated the lockfile using a targeted update, then `cargo metadata --locked`
verified it. Package identities move from 1129 to 1130: old windows-service leaves,
new windows-service and winreg enter. Every other identity is unchanged, including
all 59 Git packages and commits; no new dependency override is introduced.
The old winreg 0.11.0 still serves the maintained machine-uid and wallpaper forks;
winreg 0.10.1 serves portable-pty. These are not the application's new direct binding
and must be migrated with their callers rather than forcibly overridden.

Preparation run: [37046785218](https://github.com/Kukutx/Viper/actions/runs/37046785218).
Artifact: `11244822117`, ZIP SHA-256
`07978784e7a8d35f1942f1f307277aba270806952be3fbc68fc9a576938ee767`.
Generated Cargo.lock blob: `0370fa22542ff115895ef4d7b7a3328eeb1f03ff`.
The downloaded source objects match the reviewed local files byte-for-byte.
A separate data-only job stored immutable blobs; it did not execute repository
code or move refs. Temporary preparation code is not included in the task branch.

Local Python 3.13.5 passed all 392 tool tests and configuration/bridge checks;
this is not the pinned Python 3.14.7 CI or a Windows application compilation.
Same-commit native results must be read from PR #1 and its Actions jobs, not inferred
from dependency resolution or the previous commit's green builds.

## Remaining acceptance

Real service registration, start/stop, shutdown, MSI installation/uninstallation,
registry view behavior on supported Windows versions, graphics driver recovery,
hardware codecs, GUI, remote sessions, signing and deployment still require their
separate acceptance. No production service or machine was changed in this migration.
The repository Dependency graph setting remains an independent security-review
blocker; it is not bypassed by these tests. Keep the overall migration PR as Draft.
