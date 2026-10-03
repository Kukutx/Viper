#!/usr/bin/env bash
# Install the official, immutable SDK checkout on Linux x64 or arm64.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# != 1 || "$1" != /* ]]; then
  echo 'Usage: install-flutter.sh ABSOLUTE_EMPTY_SDK_DIRECTORY' >&2
  exit 2
fi
destination="$1"
version="$(python3 "$root/tools/build_toolchain.py" --value flutter)"
revision="$(python3 "$root/tools/build_toolchain.py" --value flutter_revision)"
if [[ -L "$destination" || -e "$destination" ]]; then
  echo 'SDK destination must not already exist; an existing SDK must not be overwritten.' >&2
  exit 1
fi
git clone --depth 1 --branch "$version" https://github.com/flutter/flutter.git "$destination"
test "$(git -C "$destination" rev-parse HEAD)" = "$revision"
git -C "$destination" switch -c stable
export PATH="$destination/bin:$PATH"
python3 "$root/tools/flutter_sdk.py"
