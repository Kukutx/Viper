#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'iOS validation requires Apple Silicon macOS.' >&2; exit 1; }
mkdir -p tools/.reports
python tools/apple_sdk.py --ios
export DEVELOPER_DIR="$(python -c 'import json; print(json.load(open("configs/toolchain.json"))["apple"]["developer_dir"])')"
revision=$(python tools/build_toolchain.py --value vcpkg.revision)
cmake_version=$(python tools/build_toolchain.py --value cmake)
python -m pip install "cmake==$cmake_version"
brew install nasm pkg-config autoconf automake libtool > tools/.reports/ios-prerequisites.log 2>&1 || { tail -80 tools/.reports/ios-prerequisites.log; exit 1; }
export VCPKG_ROOT="${RUNNER_TEMP:-$root/.tools}/viper-vcpkg-ios-$revision"
export VCPKG_DEFAULT_BINARY_CACHE="$HOME/.cache/viper-vcpkg-ios"
[[ ! -L "$VCPKG_ROOT" ]] || { echo 'Refusing a symlinked vcpkg directory.' >&2; exit 1; }
if [[ -e "$VCPKG_ROOT" ]]; then
  [[ -d "$VCPKG_ROOT/.git" ]] || { echo 'Refusing to overwrite a non-Git directory.' >&2; exit 1; }
  [[ "$(git -C "$VCPKG_ROOT" remote get-url origin)" == https://github.com/microsoft/vcpkg.git ]]
  [[ "$(git -C "$VCPKG_ROOT" rev-parse HEAD)" == "$revision" ]]
  git -C "$VCPKG_ROOT" diff --quiet HEAD --
else
  mkdir -p "$VCPKG_ROOT"
  git -C "$VCPKG_ROOT" init -q
  git -C "$VCPKG_ROOT" remote add origin https://github.com/microsoft/vcpkg.git
  git -C "$VCPKG_ROOT" fetch -q --depth 1 origin "$revision"
  git -C "$VCPKG_ROOT" checkout -q --detach FETCH_HEAD
fi
[[ "$(git -C "$VCPKG_ROOT" rev-parse HEAD)" == "$revision" ]]
mkdir -p "$VCPKG_DEFAULT_BINARY_CACHE"
"$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics > tools/.reports/ios-vcpkg-bootstrap.log 2>&1
# Device deployment flags must not contaminate macOS-hosted build tools.
env -u IPHONEOS_DEPLOYMENT_TARGET "$VCPKG_ROOT/vcpkg" install --triplet arm64-ios \
  --x-install-root="$VCPKG_ROOT/installed" > tools/.reports/ios-vcpkg.log 2>&1 || { tail -120 tools/.reports/ios-vcpkg.log; exit 1; }
for library in yuv jpeg vpx opus aom avcodec; do
  test -s "$VCPKG_ROOT/installed/arm64-ios/lib/lib${library}.a"
done
printf 'export VCPKG_ROOT=%q\nexport VCPKG_DEFAULT_BINARY_CACHE=%q\nexport DEVELOPER_DIR=%q\n' \
  "$VCPKG_ROOT" "$VCPKG_DEFAULT_BINARY_CACHE" "$DEVELOPER_DIR" > tools/.reports/ios-native.env
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'VCPKG_ROOT=%s\nVCPKG_DEFAULT_BINARY_CACHE=%s\nDEVELOPER_DIR=%s\n' \
    "$VCPKG_ROOT" "$VCPKG_DEFAULT_BINARY_CACHE" "$DEVELOPER_DIR" >> "$GITHUB_ENV"
fi
