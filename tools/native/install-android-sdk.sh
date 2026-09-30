#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
: "${ANDROID_HOME:?Set ANDROID_HOME to the Android SDK directory}"
manager="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x "$manager" ]]; then
  echo "Missing Android command-line tools: $manager" >&2
  exit 1
fi
read -r sdk build_tools ndk < <(python -c 'import json; a=json.load(open("configs/toolchain.json"))["android"]; print(a["compile_sdk"],a["build_tools"],a["ndk"])')
mkdir -p tools/.reports
"$manager" --list --channel=0 > tools/.reports/android-sdk-packages.log 2>&1
"$manager" "platforms;android-$sdk.0" "build-tools;$build_tools" "ndk;$ndk" > tools/.reports/android-sdk.log 2>&1 || { tail -100 tools/.reports/android-sdk.log; exit 1; }
