# CI Rust installation isolation

The Android arm64 job in run `36802361540` failed before Rust compilation: the
hosted runner contained a partially installed toolchain, and rustup reported a
`bin/cargo-clippy` conflict. The cache action reported success despite its
`rustc -vV` probe failing, so native dependency preparation ran unnecessarily.

`python tools/ci_rust.py` is a GitHub Actions-only bootstrap. It creates a fresh
private `RUSTUP_HOME` under `RUNNER_TEMP`, installs the central stable Rust pin
and the components declared in `rust-toolchain.toml`, and requires rustfmt and
Clippy. It verifies executable locations, compiler release and tool execution
before exporting the home and toolchain through `GITHUB_ENV`. Android invokes
it before any cache probing or native dependency setup.

The existing Cargo home/cache and global rustup installation are not changed,
uninstalled or repaired. Failed installation and verification stop the job;
there is no fallback version, partial environment export or disabled component.
The new home is temporary job state, not a dependency source or shared cache.
Diagnostics are in `tools/.reports/ci-rust-install.log` and `ci-rust.json`.

This changes CI initialization only, not application runtime behavior. Tool
installation verification is not equivalent to Clippy linting, native builds,
APK validation, device execution or signing; those retain separate results.

Reference: https://rust-lang.github.io/rustup/environment-variables.html
