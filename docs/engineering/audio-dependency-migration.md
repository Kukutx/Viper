# Audio dependency migration

Reviewed on 2026-10-02 from task baseline `29e154ecb91e29d04a68bea81070aa93b46bcdfd`.
This changes ringbuf 0.3.3 to 0.5.2 and the optional Rubato helper from 0.12.0 to
5.0.1. It does not switch Viper's streaming audio backend or complete the remaining
platform, packaging or device migrations.

## Published inputs and dependency graph

The published, non-yanked stable versions were queried from crates.io, and the
crate archives were checked against their registry SHA-256 checksums. The input
snapshot is GitHub Actions run `36941744957`, artifact `11200089619`, ZIP SHA-256
`7098cded6a72dce42f714980dd3ad160f4c7e16977942b5f5e32400cb484a8a9`.
The upstream sources are [ringbuf](https://github.com/agerasev/ringbuf) and
[Rubato](https://github.com/HEnquist/rubato); inspection used the downloaded release
archives, not a floating branch as the build input.

Cargo generated the lockfile in run `36943069982`, artifact `11200656706`, ZIP
SHA-256 `2e052170704b4bb98c98a2319ebf0d80ff432d873ccd73db1dc6cb415a920069`.
Only ringbuf and rubato package identities are replaced. Six transitive identities
enter the graph: audio-codec-algorithms, audioadapter, audioadapter-buffers,
audioadapter-sample, visibility and windowfunctions. Package identities increase
from 1123 to 1129, not a claim that all 1129 dependencies are latest or deduplicated.
All other package identities, including 59 Git package identities and their exact
commits, remain unchanged. The cpal/security forks, hbb_common Gitlink, Flutter pub
lock, FRB version and generated bindings are not modified.

## Ring-buffer behavior

The non-Linux PCM buffer keeps `HeapRb<f32>` under the same mutex and shared state.
The retired private `RbBase`/`Rb` imports are replaced by the public Consumer,
Observer, Producer and RingBuffer traits where used. The new NonZeroUsize capacity
is converted with `.get()`. Capacity, overwrite direction, discontinuity generation,
watermark shrink policy, locking and callback recovery algorithms are unchanged.

Additional regressions cover wrap-around overwrite of stereo frames, capacity
changes and allocation-free slice operations. Existing playback tests still cover
underflow, contention, poisoned mutexes, discontinuities, stream reconfiguration,
recovery and capture/resampler buffer reuse. They run on the real Windows x64/arm64
and macOS arm64 Rust targets, not only through Python source checks. They do not
open a remote session or replace physical audio-device acceptance testing.

## Optional Rubato helper

The baseline optional helper already used a four-argument constructor while locked
Rubato 0.12 requires five arguments and returns a Result. Its process invocation
also predates that API. The default build did not exercise this branch. This
migration establishes a tested optional configuration; a successful old optional
build or sample-for-sample equivalence is not assumed.

`common::resample_channels` retains its signature and interleaved f32 input/output.
It uses Rubato 5's `Async<f64>` fixed-input sinc resampler and the library's re-exported
interleaved adapter. Filter settings remain 256 taps, explicit 0.95 cutoff,
Nearest interpolation, oversampling factor 160 and BlackmanHarris2. No extra direct
adapter dependency or dependency override is introduced.

Empty input returns empty output. Invalid rates, unsupported channels and incomplete
stereo frames are rejected; fallible construction/processing errors are logged
before returning the helper's existing empty-output error result. The helper still
constructs fresh filter state for each call and processes one chunk. It is not a
streaming replacement and does not flush/filter-delay-compensate an entire signal.
Rubato 5's first fixed-input chunk has its own startup/output-length semantics;
bit-identical output to Rubato 0.12 is not asserted. Tests verify the new frame count,
mono/stereo separation, deterministic independent calls, passband gain and alias
suppression. The default `use_dasp` feature and `src/audio_resampler.rs` remain intact.

## Required validation entry points

Linux, after the normal native environment setup:

```sh
cargo test --locked --test rubato_dependency_contract \
  --features flutter,linux-pkg-config,use_rubato
```

This dedicated integration target requires `use_rubato`; ordinary workspace tests
do not silently enable an optional audio backend. Linux CI executes it after the
default-feature bundle and real FFI checks, so the optional build cannot replace the
library that those checks validate.

Windows and macOS, within their configured native build environment:

```sh
cargo test --locked --release --lib --features flutter audio -- --test-threads=1
```

Windows invokes the command inside `tools/windows_native.py`, where the VS, LLVM
and vcpkg environment is available. macOS invokes it in `apple-native.yml`. Both run
before packaging, without ignored tests or allowed failures. The Linux optional
helper test does not establish Rubato runtime execution on Apple/mobile devices.

## Regression surface

- `src/client.rs`, `src/client/audio_playback.rs`: required ringbuf trait/capacity API
  migration in the existing non-Linux audio buffer and playback path; no algorithm
  or shared state redesign.
- `src/client/audio_playback_tests.rs`, `src/client/tests/audio_state_tests.rs`: public
  trait imports so existing regressions compile with the migrated dependency.
- `src/common.rs`: only the optional Rubato helper consumes the replacement API.
- `Cargo.toml`/`Cargo.lock`: two direct upgrades, their resolver-managed dependencies,
  and an explicit opt-in integration test target.
- Windows/macOS/Linux validation entry points: execute real audio regressions and
  retain their logs. Existing default build, source parity and FFI steps remain.

Protocol, application/signing identity, system permissions, localization and the
single `agent.md` rule entry are unchanged. No signature, installation, service
start, publication, deployment or physical-device audio quality test is implied by
compilation and test results.

## Validation provenance

The native candidate is `db3c3af4e77018cb1471c0ba5cf13f084e0e201c`,
[run 36943306766](https://github.com/Kukutx/Viper/actions/runs/36943306766).
It uses the same production changes, generated lockfile and regression tests later
selected for the task branch; its temporary orchestration file is not a production
workflow. Candidate results do not automatically establish a later task commit's
CI result. PR #1 records those two revisions and their outcomes separately.

The workspace lock SHA-256 is
`7ce899dc62274ace340db006432249c112302a50b98a39b067baf7082ece095c`.
The tool suite grows from 385 to 390 tests; all 390 passed in the resolver CI and
in the separate non-root offline run. The native candidate's Foundation repository,
core and gate jobs also completed successfully. Source-level tool tests are not
substitutes for the Rust audio tests, bundle FFI or platform builds.

Native diagnostic logs preserve warnings and explicit device/signing exclusions.
The dependency-review repository setting remains a separate blocker and is not
bypassed by any audio migration workflow.
