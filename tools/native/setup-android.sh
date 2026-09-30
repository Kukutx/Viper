#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
cd "$root"
case "${1:-}" in
  arm64-v8a|armeabi-v7a|x86_64|x86) abi=$1 ;;
  *) echo 'Usage: setup-android.sh <arm64-v8a|armeabi-v7a|x86_64|x86>' >&2; exit 2 ;;
esac
if [[ "$(uname -s)/$(uname -m)" != Linux/x86_64 ]]; then
  echo 'Android native setup currently requires Linux x86_64.' >&2
  exit 1
fi
: "${ANDROID_HOME:?Android SDK is required}"
mkdir -p tools/.reports
ndk=$(python tools/build_toolchain.py --value android.ndk)
revision=$(python tools/build_toolchain.py --value vcpkg.revision)
cmake_version=$(python tools/build_toolchain.py --value cmake)
[[ "$ndk" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$revision" =~ ^[a-f0-9]{40}$ ]]
python -m pip install "cmake==$cmake_version"
sdkmanager "ndk;$ndk" > tools/.reports/ndk-setup.log 2>&1 || { tail -100 tools/.reports/ndk-setup.log; exit 1; }
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/$ndk"
export ANDROID_NDK_ROOT="$ANDROID_NDK_HOME"
grep -Eq "^Pkg.Revision[[:space:]]*=[[:space:]]*$ndk[[:space:]]*$" "$ANDROID_NDK_HOME/source.properties"
export VCPKG_ROOT="${RUNNER_TEMP:-$root/.tools}/viper-vcpkg-android"
export VCPKG_DEFAULT_BINARY_CACHE="$HOME/.cache/viper-vcpkg-android"
if [[ -L "$VCPKG_ROOT" ]]; then
  echo 'Refusing a symlinked vcpkg checkout.' >&2; exit 1
fi
mkdir -p "$VCPKG_ROOT" "$VCPKG_DEFAULT_BINARY_CACHE"
if [[ ! -d "$VCPKG_ROOT/.git" ]]; then
  test -z "$(ls -A "$VCPKG_ROOT")"
  git -C "$VCPKG_ROOT" init -q
  git -C "$VCPKG_ROOT" remote add origin https://github.com/microsoft/vcpkg.git
fi
test "$(git -C "$VCPKG_ROOT" remote get-url origin)" = https://github.com/microsoft/vcpkg.git
test -z "$(git -C "$VCPKG_ROOT" status --porcelain --untracked-files=no)"
git -C "$VCPKG_ROOT" fetch -q --depth 1 origin "$revision"
git -C "$VCPKG_ROOT" checkout -q --detach FETCH_HEAD
test "$(git -C "$VCPKG_ROOT" rev-parse HEAD)" = "$revision"
"$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics > tools/.reports/vcpkg-bootstrap.log 2>&1
bash flutter/build_android_deps.sh "$abi" > tools/.reports/android-vcpkg.log 2>&1 || { tail -120 tools/.reports/android-vcpkg.log; exit 1; }
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'ANDROID_NDK_HOME=%s\nANDROID_NDK_ROOT=%s\nVCPKG_ROOT=%s\n' "$ANDROID_NDK_HOME" "$ANDROID_NDK_ROOT" "$VCPKG_ROOT" >> "$GITHUB_ENV"
fi
printf 'export ANDROID_NDK_HOME=%q\nexport ANDROID_NDK_ROOT=%q\nexport VCPKG_ROOT=%q\n' "$ANDROID_NDK_HOME" "$ANDROID_NDK_ROOT" "$VCPKG_ROOT" > tools/.reports/android-native.env
