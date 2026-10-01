# Registry refresh and remaining dependency migrations

Reviewed on 2026-10-01. Baseline: `c4b9373edce3057815ade5eb0bf8bd1d3276ebeb`. Candidate: `dfa424adc707a2dd5eb833d6fa2c59498827ffd7`. This is a compatible-range workspace lock refresh with one preserved-fork repair, not a claim that all direct and transitive packages are on their newest major.

## Scope and counting

`Cargo.lock` contains 1119 package identities after the refresh, compared with 1028 before it. Registry identities increase from 957 to 1048: 369 old `(name, version)` pairs leave the graph and 460 new pairs enter it. Among names present in both graphs, **337 names replace at least one old version with a new version**. Another 29 names only gain an additional version and 3 only lose a redundant version; therefore 369 shared names have changed version sets. These counts must not be described as 460 independent direct-dependency upgrades or proof of deduplication.

The original lock held 60 Git package identities. All 59 other Git identities, including the pinned WebRTC and tungstenite security forks, remain unchanged. The one removed Git identity is `rust-pulsectl`: its exact original source is preserved locally, with the limited migration below. The hbb_common submodule is unchanged. No unrelated manifest range is raised and no override forces incompatible versions together.

| Selected resolved dependency | Previous | Candidate |
| --- | --- | --- |
| tokio | 1.44.2 | 1.53.1 |
| openssl | 0.10.68 | 0.10.81 |
| openssl-sys | 0.9.104 | 0.9.117 |
| reqwest | 0.12.24 | 0.12.28 |
| rustls, 0.23 line | 0.23.28 | 0.23.45 |
| libc | 0.2.171 | 0.2.189 |
| libpulse-binding | 2.28.1 | 2.30.1 |
| libpulse-simple-binding | 2.28.1 | 2.29.0 |

The table describes the committed resolution, not an unrestricted upstream version recommendation. Older parallel major lines can remain where transitive dependencies require them.

## PulseAudio compatibility and regression

The original RustDesk fork at `aa34dde499aa912a3abc5289cc0b547bd07dd6e2` no longer compiles against libpulse-binding 2.30.1 because two deprecated aliases were removed. `libs/pulsectl` preserves its nine source/license/documentation/example files. `FlagSet::NOFLAGS` and `Volume::NORMAL` replace those aliases without changing their numeric meaning; the dependency floor is raised accordingly. Source provenance is reversible and verified by `tools/verify_pulse_vendor.py`. Original authorship, GPL notice and remaining custom-fork behavior are retained.

A real private virtual-device regression exposed a second defect: the source controller looked up `default_sink_name` as an input device. Viper's existing `src/platform/linux.rs::get_default_pa_source` calls this controller. The source-specific implementation now reads `default_source_name` and returns a normal error if none is set. Sink handling, volume arithmetic and shared Viper runtime interfaces are unchanged. This repair is necessary for the migrated default-input path, not general cleanup of the imported fork.

Run [36803186001](https://github.com/Kukutx/Viper/actions/runs/36803186001) compiled the new bindings but failed the unchanged default-source assertion. The repaired preparation [36803591153](https://github.com/Kukutx/Viper/actions/runs/36803591153) passed 289 tool tests and all three actual PulseAudio tests. Its reviewed artifact `11136816396` has SHA-256 `0f1052019e17df2982c66910d9fc233156f87d0e03da27c1047c1cf596373520`; all 18 exported source objects were verified before integration. Cargo metadata confirmed that localizing the fork changed no other resolved package.

The final candidate adds one more tool contract for the explicit `private-server-tests` feature (290 tool tests). Ordinary workspace tests do not unexpectedly connect to a daemon. Linux CI explicitly starts a cookie-protected private PulseAudio service and virtual null sink, enables the integration feature, checks source/sink enumeration and default selection, tests volume round trips and missing-device errors, then cleans up only its own process. No test is ignored and no physical audio device is used.

## Verification records

The pre-repair lock candidate `9ec3b4e6d2942e1ce6554ef404010e55ad58e879` passed Windows x64/arm64, macOS, Android three ABIs and iOS in [36788255173](https://github.com/Kukutx/Viper/actions/runs/36788255173), but failed Linux generation on the removed aliases. That run is not a complete success.

The final preserved-fork candidate is validated by [36803929540](https://github.com/Kukutx/Viper/actions/runs/36803929540). Exact completed results and the later task-head runs are recorded in PR #1; an in-progress or historical run is not evidence for a later commit. This document does not assert that every future head has passed. Platform validation keeps the existing software-codec scope on Windows/macOS and hardware-codec scope on Android/iOS. No signing, installation, device session or production deployment occurs.

Linux job `110185226671` completed successfully on the preserved-fork candidate: 103 Flutter unit tests, three private PulseAudio regressions, three network-interface regressions, three real library FFI tests and three bundled-library FFI tests. Native `cargo check` and build succeeded, the actual Debug desktop bundle was produced, and regenerated bindings and lockfiles were unchanged. The root crate still emitted 45 compiler warnings. The downloaded diagnostic artifact `11136954591` has SHA-256 `3cabc54b572d8c4808abb3aae76655851439634e66769b5d06705ee8a885b163`; its complete build and regression logs were reviewed. This Linux result is not hardware/audio-device or Release-installer acceptance.

## Confirmed Flutter patch conflict

A separate bounded attempt [36805086943](https://github.com/Kukutx/Viper/actions/runs/36805086943) verified the live published wakelock_plus 1.8.1 metadata on 2026-10-01, then failed pub resolution: `desktop_drop 0.8.4` requires `dbus ^0.7.10`, while `wakelock_plus 1.8.1` requires `dbus ^0.8.0`. This is a constraint conflict, not a successful patch upgrade. The task retains wakelock_plus 1.8.0 and its existing pub lock; no forced override, drag/drop removal or hidden downgrade was adopted. The upstream [wakelock changelog](https://github.com/fluttercommunity/wakelock_plus/blob/main/wakelock_plus/CHANGELOG.md) identifies the D-Bus bump as the patch's change. A coordinated drag/drop and D-Bus migration with Linux runtime coverage is still required.

Diagnostic artifact `11136714215` has SHA-256 `bea2d863f28f569b0df46fbeb515c03d8d671177f65424c687c1ef8bc8bc1d22`; its complete solver error was read. Neither the experimental workflow nor its changed manifest is included in the task branch.

## Major/API migrations still outstanding

The direct-dependency audit from 2026-09-30 identifies separate migration groups: HTTP/TLS and hashing/OTP (`reqwest`, `sha2`, `totp-rs`); audio resampling and buffering (`rubato`, `ringbuf`); Windows registry/service/notification APIs; Apple graphics and Objective-C wrappers; Linux input/desktop bindings; and QR/raster/font rendering. Updating the lock within existing constraints does not complete those API changes. Their call sites, security behavior, optional profiles and supported target matrices need coordinated changes and regression tests, rather than rewriting every version declaration.

Sciter's old toolchain/runtime, the special F-Droid x86 engine, the full legacy release-format matrix and six macOS CocoaPods fallback plugins also remain. Dependency graph configuration still blocks GitHub Dependency review. Build success is not a replacement for that security gate or for end-to-end remote audio, GUI, permissions, signing and rollback checks.

## Runner failure handling

The iOS-archive task commit `3dea1a7` separately failed Android arm64 job `110179290440` in [36802361540](https://github.com/Kukutx/Viper/actions/runs/36802361540): Rustup reported a partially installed Rust 1.98.1 toolchain and a `bin/cargo-clippy` component conflict. The cache action logged the error without failing its step; a later Rust invocation stopped the build after vcpkg had already completed. This was before application compilation. The other two Android ABI jobs succeeded. Only the failed job was requested to rerun; its final status must be checked independently.

Android validation now performs mandatory `rustup show`, `rustc --version --verbose` and `cargo --version` before cache initialization and expensive native setup. An installation failure stops immediately; no SDK downgrade, Clippy removal, global toolchain deletion or suppression is introduced. A tool contract checks the commands, unconditional execution and ordering. This additional task change raises the tool suite to 291 tests; the preserved-fork candidate itself contains 290.
