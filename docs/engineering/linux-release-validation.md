# Linux native Release validation

`linux-release.yml` validates x64 on `ubuntu-24.04` and arm64 on
`ubuntu-24.04-arm`, using native runners rather than emulated architecture
containers. Both use the central Flutter/Dart/Rust/CMake pins, strict lockfiles,
committed FRB bindings and an isolated CI Rust installation. Native setup keeps
the existing x64 path and selects the matching libyuv vcpkg triplet on arm64.

```sh
bash tools/native/setup-linux.sh
source tools/.reports/native.env
python tools/linux_release.py
```

The entry point first runs the common Flutter preflight, then compiles the Rust
Release library and Flutter AOT application with `--no-pub`. It checks required
resources and executable permissions, every bundled ELF architecture, all
NEEDED dependency resolutions, and the bundled Rust library's SHA-256 against
that build's Cargo output. It runs the existing synchronous/asynchronous FFI
regressions against the package's library, not a substitute.

Only after those checks and source/lock drift checks pass does it produce
`dist/linux-<arch>-unsigned/`. The tar archive preserves executable bits and
safe relative symlinks; absolute, escaping or dangling links and special files
are rejected. An existing output directory is never overwritten. The archive,
validation report and full source revision are covered by the common release
manifest and SHA-256 verification. Diagnostics are uploaded even on failure;
the package is uploaded only on success. Nothing is published to Releases or a
package registry, and no signing credential is used.

This is a `flutter,linux-pkg-config` software-codec validation profile. It does
not remove or replace hardware codecs, DRM or the historical packaging jobs.
The existing Linux Debug/bridge/PulseAudio regression workflow is retained.
These native Release archives are not DEB/RPM/AppImage/Flatpak acceptance,
minimum-system compatibility, GUI/remote session validation, signatures or a
production deployment. Distribution libraries still follow the runner's package
repository; this is not a claim of bit-for-bit hermetic reproducibility.

Any result is specific to its source revision. Added test configuration is not
proof of a successful native build; consult the exact workflow run in PR #1.
