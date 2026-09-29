#!/usr/bin/env bash
set -euo pipefail

# libyuv 的发行版开发包不提供 .pc；使用项目已固定、已打补丁的真实静态库。
root=$(git rev-parse --show-toplevel)
revision=$(python -c 'import json; print(json.load(open("configs/toolchain.json"))["vcpkg"]["revision"])')
export VCPKG_ROOT="$RUNNER_TEMP/viper-vcpkg"
mkdir -p "$VCPKG_ROOT" "$HOME/.cache/viper-vcpkg"
export VCPKG_DEFAULT_BINARY_CACHE="$HOME/.cache/viper-vcpkg"
git -C "$VCPKG_ROOT" init -q
git -C "$VCPKG_ROOT" remote add origin https://github.com/microsoft/vcpkg.git
git -C "$VCPKG_ROOT" fetch -q --depth 1 origin "$revision"
git -C "$VCPKG_ROOT" checkout -q --detach FETCH_HEAD
test "$(git -C "$VCPKG_ROOT" rev-parse HEAD)" = "$revision"
"$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics > tools/.reports/vcpkg.log 2>&1
"$VCPKG_ROOT/vcpkg" install libyuv:x64-linux --classic --overlay-ports="$root/res/vcpkg" >> tools/.reports/vcpkg.log 2>&1 || { tail -100 tools/.reports/vcpkg.log; exit 1; }
test -f "$VCPKG_ROOT/installed/x64-linux/lib/libyuv.a"
test -f "$VCPKG_ROOT/installed/x64-linux/include/libyuv.h"
printf 'VCPKG_ROOT=%s\nNO_PKG_CONFIG_libyuv=1\n' "$VCPKG_ROOT" >> "$GITHUB_ENV"
tail -20 tools/.reports/vcpkg.log
