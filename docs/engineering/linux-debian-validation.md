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
