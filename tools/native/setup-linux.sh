#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
cd "$root"
if [[ "$(uname -s)" != Linux ]]; then
  echo 'This native setup requires Linux.' >&2
  exit 1
fi
case "$(uname -m)" in
  x86_64) triplet=x64-linux ;;
  aarch64) triplet=arm64-linux ;;
  *) echo 'This native setup supports Linux x64 and arm64 only.' >&2; exit 1 ;;
esac
mkdir -p tools/.reports
cmake_version=$(python -c 'import json; print(json.load(open("configs/toolchain.json"))["cmake"])')
revision=$(python -c 'import json; print(json.load(open("configs/toolchain.json"))["vcpkg"]["revision"])')
[[ "$cmake_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]

sudo apt-get update -qq > tools/.reports/apt.log 2>&1
sudo apt-get install -y -qq clang libclang-dev ninja-build pkg-config nasm \
  libgtk-3-dev libasound2-dev libpulse-dev libdbus-1-dev libxdo-dev \
  libxcb-randr0-dev libxcb-shape0-dev libxcb-xfixes0-dev libxfixes-dev \
  libxtst-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
  libvpx-dev libaom-dev libopus-dev libsodium-dev \
  >> tools/.reports/apt.log 2>&1 || { tail -80 tools/.reports/apt.log; exit 1; }
python -m pip install "cmake==$cmake_version"
rustup show

# 发行版 libyuv 缺少 pkg-config 元数据；构建项目固定的真实库和补丁。
export VCPKG_ROOT="${RUNNER_TEMP:-$root/.tools}/viper-vcpkg"
export VCPKG_DEFAULT_BINARY_CACHE="$HOME/.cache/viper-vcpkg"
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
"$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics > tools/.reports/vcpkg.log 2>&1
"$VCPKG_ROOT/vcpkg" install "libyuv:$triplet" --classic \
  --overlay-ports="$root/res/vcpkg" >> tools/.reports/vcpkg.log 2>&1 \
  || { tail -100 tools/.reports/vcpkg.log; exit 1; }
test -f "$VCPKG_ROOT/installed/$triplet/lib/libyuv.a"
test -f "$VCPKG_ROOT/installed/$triplet/include/libyuv.h"
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'VCPKG_ROOT=%s\nNO_PKG_CONFIG_libyuv=1\n' "$VCPKG_ROOT" >> "$GITHUB_ENV"
fi
printf 'export VCPKG_ROOT=%q\nexport NO_PKG_CONFIG_libyuv=1\n' "$VCPKG_ROOT" > tools/.reports/native.env
printf 'Native setup ready. For this shell: source tools/.reports/native.env\n'
