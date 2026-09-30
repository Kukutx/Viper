#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
: "${VCPKG_ROOT:?Use the repository builder image or configure pinned vcpkg first}"
test "$(git -C "$VCPKG_ROOT" rev-parse HEAD)" = "$(python3 tools/build_toolchain.py --value vcpkg.revision)"
# A project-owned venv avoids modifying the host or container Python installation.
test ! -L .tools && test ! -L .tools/python
python3 -m venv .tools/python
source .tools/python/bin/activate
python3 -m pip install -r tools/requirements-dev.txt
if ! command -v flutter >/dev/null 2>&1; then
  sdk_parent="$(mktemp -d)"
  trap 'rm -rf "$sdk_parent"' EXIT
  bash tools/native/install-flutter.sh "$sdk_parent/flutter"
  export PATH="$sdk_parent/flutter/bin:$PATH"
fi
python3 tools/flutter_sdk.py
"$VCPKG_ROOT/vcpkg" install --x-install-root="$VCPKG_ROOT/installed"
python3 tools/bridge.py generate
python3 tools/check_bridge_outputs.py
python3 build.py --flutter --hwcodec
