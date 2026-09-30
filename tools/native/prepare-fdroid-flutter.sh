#!/usr/bin/env bash
# Keep F-Droid's source-built SDK on the reviewed stable commit, without resets.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# != 2 || "$2" != /* ]]; then
  echo 'Usage: prepare-fdroid-flutter.sh VERSION ABSOLUTE_SDK_DIRECTORY' >&2
  exit 2
fi
version="$(python3 "$root/tools/build_toolchain.py" --value flutter)"
revision="$(python3 "$root/tools/build_toolchain.py" --value flutter_revision)"
if [[ "$1" != "$version" ]]; then
  echo 'F-Droid SDK request differs from the reviewed version.' >&2
  exit 1
fi
sdk="$2"
if [[ -L "$sdk" ]]; then
  echo 'SDK directory cannot be a symlink.' >&2
  exit 1
fi
if [[ ! -e "$sdk" ]]; then
  bash "$root/tools/native/install-flutter.sh" "$sdk"
else
  test -d "$sdk/.git"
  if [[ "$(git -C "$sdk" rev-parse HEAD)" != "$revision" ]]; then
    echo 'Existing SDK is a different version; use a new SDK directory.' >&2
    exit 1
  fi
  git -C "$sdk" diff --exit-code HEAD --
  if git -C "$sdk" show-ref --verify --quiet refs/heads/stable; then
    test "$(git -C "$sdk" rev-parse refs/heads/stable)" = "$revision"
    git -C "$sdk" switch stable
  else
    git -C "$sdk" switch -c stable
  fi
fi
export PATH="$sdk/bin:$PATH"
flutter config --no-analytics
python3 "$root/tools/flutter_sdk.py"
