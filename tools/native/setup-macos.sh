#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
cd "$root"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo 'This native validation setup requires an Apple Silicon macOS host.' >&2
  exit 1
fi
mkdir -p tools/.reports
cmake_version=$(python -c 'import json; print(json.load(open("configs/toolchain.json"))["cmake"])')
revision=$(python -c 'import json; print(json.load(open("configs/toolchain.json"))["vcpkg"]["revision"])')
[[ "$cmake_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
python -m pip install "cmake==$cmake_version"
brew install nasm pkg-config autoconf automake libtool > tools/.reports/macos-prerequisites.log 2>&1 || { tail -80 tools/.reports/macos-prerequisites.log; exit 1; }
xcodebuild -version
rustup show

export VCPKG_ROOT="${RUNNER_TEMP:-$root/.tools}/viper-vcpkg-macos"
export VCPKG_DEFAULT_BINARY_CACHE="$HOME/.cache/viper-vcpkg-macos"
mkdir -p "$VCPKG_ROOT" "$VCPKG_DEFAULT_BINARY_CACHE"
if [[ ! -d "$VCPKG_ROOT/.git" ]]; then
  git -C "$VCPKG_ROOT" init -q
  git -C "$VCPKG_ROOT" remote add origin https://github.com/microsoft/vcpkg.git
fi
if [[ "$(git -C "$VCPKG_ROOT" remote get-url origin)" != https://github.com/microsoft/vcpkg.git ]]; then
  echo 'Unexpected vcpkg remote; refusing to modify this checkout.' >&2
  exit 1
fi
git -C "$VCPKG_ROOT" fetch -q --depth 1 origin "$revision"
git -C "$VCPKG_ROOT" checkout -q --detach FETCH_HEAD
test "$(git -C "$VCPKG_ROOT" rev-parse HEAD)" = "$revision"
"$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics > tools/.reports/macos-vcpkg.log 2>&1
# This is the software-codec validation profile, not the hardware-codec release matrix.
"$VCPKG_ROOT/vcpkg" install --classic --triplet=arm64-osx \
  libyuv libvpx opus aom --overlay-ports="$root/res/vcpkg" \
  >> tools/.reports/macos-vcpkg.log 2>&1 || { tail -120 tools/.reports/macos-vcpkg.log; exit 1; }
for library in yuv vpx opus aom; do
  test -s "$VCPKG_ROOT/installed/arm64-osx/lib/lib${library}.a"
done
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'VCPKG_ROOT=%s\n' "$VCPKG_ROOT" >> "$GITHUB_ENV"
fi
printf 'export VCPKG_ROOT=%q\n' "$VCPKG_ROOT" > tools/.reports/macos-native.env
