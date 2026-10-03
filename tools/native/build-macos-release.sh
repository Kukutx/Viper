#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
mkdir -p tools/.reports
source_library="$root/target/release/liblibrustdesk.dylib"
test -s "$source_library"
cd flutter
flutter build macos --release --no-pub > ../tools/.reports/macos-release.log 2>&1 || {
  tail -120 ../tools/.reports/macos-release.log
  exit 1
}
bundle="$PWD/build/macos/Build/Products/Release/RustDesk.app"
library="$bundle/Contents/Frameworks/liblibrustdesk.dylib"
test -x "$bundle/Contents/MacOS/RustDesk"
test -s "$bundle/Contents/Info.plist"
test -s "$library"
cmp "$source_library" "$library"
test "$(lipo -archs "$library")" = arm64
otool -L "$bundle/Contents/MacOS/RustDesk" > ../tools/.reports/macos-release-linked-libraries.log
otool -L "$library" >> ../tools/.reports/macos-release-linked-libraries.log
VIPER_NATIVE_LIBRARY="$library" flutter test --no-pub test_native/bridge_ffi_test.dart > ../tools/.reports/macos-release-ffi.log 2>&1 || {
  tail -100 ../tools/.reports/macos-release-ffi.log
  exit 1
}
git diff --exit-code -- pubspec.yaml pubspec.lock macos/Podfile macos/Podfile.lock macos/Runner.xcodeproj
cd "$root"
# Preserve framework symlinks inside an unsigned CI archive, not a flattened .app.
output="$root/dist/macos-arm64-unsigned"
mkdir -p "$output"
tar -czf "$output/RustDesk-macos-arm64-unsigned.tar.gz" -C "$(dirname "$bundle")" "$(basename "$bundle")"
python tools/viper.py manifest "$output" --revision "$(git rev-parse HEAD)"
python tools/viper.py verify "$output"
