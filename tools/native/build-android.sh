#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
abi=${1:?Usage: build-android.sh arm64-v8a|armeabi-v7a|x86_64}
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'Android native validation requires a Linux x86_64 host.' >&2
  exit 1
fi
python tools/android_toolchain.py --runtime
if [[ -e flutter/android/key.properties || -L flutter/android/key.properties ]]; then
  echo 'Unsigned CI build refuses a signing key.properties file.' >&2
  exit 1
fi
read -r target triplet platform sysroot < <(python - "$abi" <<'PY'
import sys
sys.path.insert(0, 'tools')
from android_toolchain import ABIS
if sys.argv[1] not in ABIS:
    raise SystemExit('Unsupported Android ABI')
t, v, p, _, _, s = ABIS[sys.argv[1]]
print(t, v, p, s)
PY
)
read -r ndk cargo_ndk api < <(python -c 'import json; a=json.load(open("configs/toolchain.json"))["android"]; print(a["ndk"],a["cargo_ndk"],a["min_sdk"])')
revision=$(python tools/build_toolchain.py --value vcpkg.revision)
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/$ndk"
export ANDROID_NDK_ROOT="$ANDROID_NDK_HOME"
export VCPKG_ROOT="$root/.tools/vcpkg-android"
export VCPKG_DEFAULT_BINARY_CACHE="$root/.tools/android-vcpkg-cache"
export VCPKG_OVERLAY_TRIPLETS="$root/res/vcpkg-triplets"
export VCPKG_OVERLAY_PORTS="$root/res/vcpkg"
for dir in .tools .tools/vcpkg-android .tools/android-vcpkg-cache .tools/cargo-ndk; do
  if [[ -L "$dir" ]]; then echo "Refusing symlink tool directory: $dir" >&2; exit 1; fi
done
mkdir -p tools/.reports "$VCPKG_ROOT" "$VCPKG_DEFAULT_BINARY_CACHE"
if [[ ! -d "$VCPKG_ROOT/.git" ]]; then
  git -C "$VCPKG_ROOT" init -q
  git -C "$VCPKG_ROOT" remote add origin https://github.com/microsoft/vcpkg.git
fi
[[ "$(git -C "$VCPKG_ROOT" remote get-url origin)" == https://github.com/microsoft/vcpkg.git ]]
[[ -z "$(git -C "$VCPKG_ROOT" status --porcelain)" ]]
git -C "$VCPKG_ROOT" fetch -q --depth 1 origin "$revision"
git -C "$VCPKG_ROOT" checkout -q --detach FETCH_HEAD
[[ "$(git -C "$VCPKG_ROOT" rev-parse HEAD)" == "$revision" ]]
"$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics > tools/.reports/android-vcpkg-bootstrap.log 2>&1
bash flutter/build_android_deps.sh "$abi" > tools/.reports/android-vcpkg.log 2>&1 || { tail -120 tools/.reports/android-vcpkg.log; exit 1; }
rustup target add "$target"
cargo install cargo-ndk --locked --version "=$cargo_ndk" --root .tools/cargo-ndk > tools/.reports/android-cargo-ndk.log 2>&1 || { tail -100 tools/.reports/android-cargo-ndk.log; exit 1; }
export PATH="$root/.tools/cargo-ndk/bin:$PATH"
# cargo-ndk rejects direct execution; Cargo supplies its required environment and subcommand.
actual=$(cargo ndk --version)
printf '%s\n' "$actual" > tools/.reports/android-cargo-ndk-version.txt
[[ "$actual" == "cargo-ndk $cargo_ndk" ]]
export RUSTFLAGS="${RUSTFLAGS:-} -C link-arg=-Wl,-z,max-page-size=16384 -C link-arg=-Wl,-z,common-page-size=16384"
python tools/android_cargo.py "$target" build --locked --release --lib --features flutter,hwcodec > tools/.reports/android-cargo.log 2>&1 || { tail -150 tools/.reports/android-cargo.log; exit 1; }
jni="flutter/android/app/src/main/jniLibs/$abi"
mkdir -p "$jni"
cp "target/$target/release/liblibrustdesk.so" "$jni/librustdesk.so"
cp "$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/$sysroot/libc++_shared.so" "$jni/"
python tools/prepare_flutter.py
flutter config --jdk-dir="$JAVA_HOME"
(cd flutter && flutter build apk --release --no-pub --target-platform "$platform" --split-per-abi) > tools/.reports/android-release.log 2>&1 || { tail -150 tools/.reports/android-release.log; exit 1; }
apk="flutter/build/app/outputs/flutter-apk/app-$abi-release.apk"
python tools/verify_android_apk.py "$apk" "target/$target/release/liblibrustdesk.so" --abi "$abi" --report tools/.reports/android-apk.json
build_tools=$(python tools/build_toolchain.py --value android.build_tools)
"$ANDROID_HOME/build-tools/$build_tools/zipalign" -c -P 16 -v 4 "$apk" > tools/.reports/android-zipalign.log 2>&1
"$ANDROID_HOME/build-tools/$build_tools/aapt" dump badging "$apk" > tools/.reports/android-badging.log
python - <<'PY'
from pathlib import Path
from sys import path
path.insert(0, 'tools')
from android_toolchain import configuration
cfg = configuration()
text = Path('tools/.reports/android-badging.log').read_text()
for value in ("package: name='com.carriez.flutter_hbb'", f"sdkVersion:'{cfg['min_sdk']}'", f"targetSdkVersion:'{cfg['target_sdk']}'"):
    if value not in text:
        raise SystemExit(f'APK manifest drift: {value}')
PY
git diff --exit-code HEAD -- Cargo.lock flutter/pubspec.yaml flutter/pubspec.lock flutter/android/gradle.properties flutter/android/settings.gradle flutter/android/app/build.gradle
out="dist/android-$abi-unsigned"
if [[ -e "$out" || -L "$out" ]]; then echo "Output already exists: $out" >&2; exit 1; fi
mkdir -p "$out"
cp "$apk" "$out/RustDesk-android-$abi-unsigned.apk"
cp tools/.reports/android-apk.json "$out/validation.json"
python tools/viper.py manifest "$out" --revision "$(git rev-parse HEAD)"
python tools/viper.py verify "$out"
