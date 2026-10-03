# Android native migration

`configs/toolchain.json.android` pins AGP 9.4.0, Gradle 9.8.0, Kotlin 2.4.20,
NDK r30 (30.0.16248370), cargo-ndk 4.1.2, Android SDK 37 / build tools 37.0.0,
protobuf plugin 0.10.0 and matching protoc / Java runtime 4.36.2.
The Gradle distribution and generated wrapper JAR have separate SHA-256 pins.

Temurin 25.0.4.1+1 is the selected released LTS runtime. setup-java selects the
feature line, then the exact installed JAVA_RUNTIME_VERSION/build is checked
before Android tooling executes. A new runtime fails until reviewed. Java/Kotlin
bytecode target 17 is distinct from the compiler runtime.

## Behavior and remaining compatibility

- Minimum Android API is now 24 (Android 7.0), consistently in the application,
  vcpkg triplets and cargo-ndk commands. API 23 and below are no longer declared
  targets. Minimum-device testing is still required.
- Namespace/application ID remains `com.carriez.flutter_hbb`. Production signing
  identity, permissions, protocol, licensing and upstream attribution are unchanged.
- Flutter 3.47.5 and existing plugins still require the legacy AGP DSL and external
  Kotlin plugin. `android.newDsl=false` and `android.builtInKotlin=false` are
  explicit upstream compatibility boundaries, not proof that legacy migration is
  complete. Remove them with the supported upstream plugin migration, never by
  patching the SDK or bypassing dependency checks.
- `qr_code_scanner_plus` 2.3.0 replaces the retired scanner package, preserving its
  scan/flash/camera-switch API and avoiding MLKit. The fork is maintenance-only and
  retains ZXing on Android; the entire scanner backend is not yet modernized.
- New SDK nullability is handled by skipping a codec with no video capabilities;
  existing valid hardware codec selection and advertised fields remain unchanged.
- Missing launcher and notification PNGs are restored from the immutable upstream
  resource trees recorded in `configs/android-resources.json`, without redesign.
- F-Droid keeps four ABI paths and distribution-specific patches, but reads numeric
  NDK and cargo-ndk pins from central configuration instead of a floating external
  transparency-log branch. Its custom x86 engine and full distribution build still
  require separate validation.

## Build and verify

Initialize submodules and install the pinned Flutter, JDK and Android command-line
tools on Linux x86_64 with native compiler/build prerequisites:

```sh
python -m pip install -r tools/requirements-dev.txt
python tools/android_toolchain.py --java-only
bash tools/native/install-android-sdk.sh
python tools/android_toolchain.py --runtime
bash tools/native/build-android.sh arm64-v8a
```

The native script also accepts `armeabi-v7a` and `x86_64`. It preserves the full
vcpkg manifest and `flutter,hwcodec` features. It packages the exact compiled Rust
library, verifies APK contents, every ELF architecture and 64-bit 16 KiB load
alignment, ZIP alignment, app ID and SDK levels, then records a revision-bound
SHA-256 manifest. It refuses signing `key.properties` and existing output bundles.
No debug signing identity substitutes for production Release signing.

`android-native.yml` is a read-only three-ABI workflow, including Draft PRs.
Failed builds retain diagnostics and cannot upload successful release artifacts.
Unsigned CI artifacts are not store releases. Fixture tests validate the checker,
not Android devices. `validation.json` explicitly marks device execution and
signature verification as unverified. Camera permissions, MediaProjection,
background services, accessibility, hardware codecs, runtime FFI and remote
connections require emulator/device and cross-device tests.

Tie all pass/fail results to the exact PR commit and Actions run. The historical
15-job release matrix is not certified by the new read-only native workflow;
release-specific JDK setup, signing and publication remain separate migration
work. Dependency review still requires the repository Dependency graph setting.
