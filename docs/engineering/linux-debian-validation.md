# Native Debian package validation

This entry extends the existing native Linux Release validation. It does not replace the explicit DRM package route, hardware-codec builds, or the other distribution formats. The package remains `rustdesk`, with the original application identity, AGPL licence, desktop entries, systemd service and four maintainer scripts.

## Usage and scope

On the matching Ubuntu 24.04 x64 or arm64 build host, install `dpkg-dev`, prepare the existing native/Flutter environment, and run:

```sh
python tools/linux_release.py
python tools/linux_deb.py
```

The first command must complete for the same HEAD, architecture and stock `flutter,linux-pkg-config` profile. The Debian entry rejects missing/stale evidence, changed Rust bytes, modified Release archives, mixed DRM artifacts and existing output directories. It does not accept an arbitrary downloaded binary or silently rebuild it with another SDK.

The resulting `dist/linux-<arch>-deb-unsigned/` contains the `.deb`, source revision, validation report and SHA-256 manifest. Ordinary CI has only `contents: read`; output upload is conditional on successful verification. No signing credentials, package repository upload or machine installation is performed.

## Checks

The stock legacy entry and the new packager share `configs/linux-deb-control.in`. The legacy renderer remains byte-equivalent, including its architecture-specific extra dependencies. The new entry retains those runtime requirements and adds `dpkg-shlibdeps` constraints derived from all actual ELF objects. Missing dependency information is not ignored. In particular, binaries built against a newer libc must not claim to support older systems merely because the package format is Debian.

The package is built without root privileges using `dpkg-deb --root-owner-group`. Both its data archive and control archive are checked before extraction: exact file set, types, modes, ownership, links and SHA-256 content. Absolute, escaping or dangling links, special files, privileged/world-writable modes and duplicate paths are rejected. The original resource and maintainer-script bytes are preserved. `md5sums` is included for the standard dpkg format; SHA-256 remains the integrity check.

Two serializations of the same staged inputs and source timestamp must be byte-identical. This checks repeatable package serialization, not reproducibility of independently rebuilt Rust/Flutter binaries. After raw extraction into a temporary directory, all files are compared again, ELF architecture and Rust identity are checked, and the three existing Flutter FFI tests load the extracted Rust library. The extracted maintainer scripts are not executed.

## Restored resources

The imported repository omitted two files that its existing Debian builders already referenced. These unmodified RustDesk assets are restored by exact upstream Git blob, not recreated or rebranded:

- `res/128x128@2x.png`: `89abf23a68ae85d0f28cdb90d1b08ad36db9d2c8`.
- `res/scalable.svg`: `50cab67a3e0369ed1fd3d036f5b485f9f3ca9b76`.

Source repository: https://github.com/rustdesk/rustdesk. Regression tests verify both complete blob identities. The source licence and upstream attribution are retained.

## Validation boundary

The unit suite includes real dpkg archive round-trips and deliberately mocked native/FFI failure paths. Only the native CI job verifies a real application and extracted-library FFI; these are separate evidence. A successful archive is not proof of dependency installation, systemd/Polkit execution, GUI startup, hardware codecs, cross-machine remote control, minimum-system compatibility, upgrade/rollback or signature validity. Those checks remain required before production delivery. The unchanged original maintainer scripts can start/stop services during a real installation; this validation does not run them.

References: [dpkg-deb](https://manpages.debian.org/trixie/dpkg/dpkg-deb.1.en.html), including root ownership, raw extraction and `SOURCE_DATE_EPOCH`; [dpkg-shlibdeps](https://manpages.debian.org/trixie/dpkg-dev/dpkg-shlibdeps.1.en.html), including private-library search and generated dependency constraints.

## Accepted candidate evidence (2026-10-01)

Candidate `b0838bbde729dd7e0afd5d7457456838b827e0f6` passed [run 36852694409](https://github.com/Kukutx/Viper/actions/runs/36852694409), including all 376 tool tests, actionlint, base/hbb_common tests, and native x64 / arm64 jobs `110337831440` / `110337831472`. Each architecture built the actual Release application, inspected 15 ELF files and 79 payload entries, and passed the three FFI tests again using the library extracted from its `.deb`. The package and native-build source-difference logs are empty.

| Architecture | Diagnostic artifact / ZIP SHA-256 | Package artifact / ZIP SHA-256 |
| --- | --- | --- |
| x64 | `11157520397` / `9c5347f985ccb0bd175504fb83ad76d92d40425e4dc64e38674793dc4f6d1823` | `11157330899` / `2fd6af63d77f3db13f828561e85187c601154e6936f4a381e9e75eadecd35438` |
| arm64 | `11157695548` / `20774e93f750a4a197ed7d1a36ee9fe53d5367d1e56eed1719eb588a8efde236` | `11158035427` / `334c6c261fd9bcb1d5ce35142919e66f928e8210cf4d5731d6a7a33644ea6767` |

Both complete diagnostics and both package artifacts were downloaded and independently checked. Inner `rustdesk-1.5.0-amd64.deb` is 20,308,164 bytes, SHA-256 `c5a6f9c27e0984e40419b4847f13950a5b41c89a8973b4d67868a8f45f0211c5`; the arm64 package is 19,151,824 bytes, SHA-256 `b714b61a174aa761c6bfd81d9cd25611c4c437dfb7c8774ae0bf64434b7cf5c6`. The manifests, both archive ownership tables, all original maintainer scripts, licence, Rust library hash/architecture and runner mode were rechecked without installation.

The computed constraints include `libc6 (>= 2.39)` and the Ubuntu 24.04 library generation; these are not generic older-Debian binaries. Each build still reports 45 root-crate Rust warnings and six `scrap` warnings. `dpkg-shlibdeps` also reports private-plugin naming, unused-link and plugin-symbol warnings, which remain in the diagnostics. This is not a warning-free build or GUI validation. Later commits must use their own CI results; this immutable candidate record does not imply that subsequent task-head runs have completed.
