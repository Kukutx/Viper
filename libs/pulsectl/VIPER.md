# Viper PulseAudio fork maintenance

Source: `rustdesk-org/pulsectl` at `aa34dde499aa912a3abc5289cc0b547bd07dd6e2`, previously selected by Viper's Cargo.lock. Original RustDesk fork behavior, authorship, README, example and GPL-3.0-or-later notice are preserved. This is not a replacement with the unrelated registry package.

The compatible registry refresh selects libpulse-binding 2.30.1, which removed two deprecated aliases used by this fork. The connection flag spelling and normal-volume constant spelling change; flags remain zero and normal volume remains 65536. The dependency floor is raised to 2.30.1. The volume formula, stream/device types, asynchronous operations and callbacks are not rewritten. The upstream standalone Cargo.lock is not copied: Viper's workspace lock is authoritative.

`upstream.json` records every imported file's original Git blob and the five exact substitutions. `python tools/verify_pulse_vendor.py` reconstructs and verifies all imported bytes, including the license. Future source edits require an explicitly reviewed provenance update; tests are separately maintained Viper additions. Existing upstream unwrap/error-handling choices remain out of scope for this API migration.

CI compiles the fork and runs an isolated private PulseAudio daemon with a virtual null sink. The test verifies source/sink enumeration, default-device selection, volume changes/readback, and unknown-device errors. It does not use physical audio hardware, prove PipeWire compatibility, or validate an end-to-end remote audio session.

The private source-selection regression also exposed a pre-existing fork defect used by Viper's `get_default_pa_source`: `SourceController` queried the default sink name as though it were an input source. Its source-specific lookup now uses `default_source_name`, returning an explicit error when no default source exists. Sink selection and the rest of the controller API are unchanged. This necessary source-selection repair is recorded separately from the removed libpulse aliases; the original failing test is retained unchanged.

The private-server integration target requires the explicit `private-server-tests` Cargo feature. The CI wrapper enables it and runs all three tests without ignoring failures. Ordinary workspace unit tests do not unexpectedly require or connect to an audio daemon. This test-only feature changes no production library code or dependencies.
