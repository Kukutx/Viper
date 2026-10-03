#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
cd "$root"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This bundle validation supports Linux x86_64 only.' >&2
  exit 1
fi
mkdir -p tools/.reports
test -f target/debug/liblibrustdesk.so

(cd flutter && flutter build linux --debug --no-pub) \
  > tools/.reports/bundle-build.log 2>&1 \
  || { tail -100 tools/.reports/bundle-build.log; exit 1; }

bundle="$root/flutter/build/linux/x64/debug/bundle"
test -x "$bundle/rustdesk"
test -f "$bundle/data/icudtl.dat"
test -d "$bundle/data/flutter_assets"
# Check the installed library, not just the Cargo output used by the earlier test.
cmp target/debug/liblibrustdesk.so "$bundle/lib/librustdesk.so"
{
  ldd "$bundle/rustdesk"
  ldd "$bundle/lib/librustdesk.so"
} > tools/.reports/bundle-linkage.log 2>&1
if grep -q 'not found' tools/.reports/bundle-linkage.log; then
  cat tools/.reports/bundle-linkage.log >&2
  exit 1
fi

(cd flutter && VIPER_NATIVE_LIBRARY="$bundle/lib/librustdesk.so" \
  flutter test --no-pub test_native/bridge_ffi_test.dart) \
  > tools/.reports/bundle-ffi-tests.log 2>&1 \
  || { tail -100 tools/.reports/bundle-ffi-tests.log; exit 1; }
tail -10 tools/.reports/bundle-ffi-tests.log
printf 'Linux debug bundle built; bundled native library passed FFI validation.\n'
