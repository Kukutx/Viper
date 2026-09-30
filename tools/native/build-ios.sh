#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'iOS validation requires Apple Silicon macOS.' >&2; exit 1; }
: "${VCPKG_ROOT:?Run tools/native/setup-ios.sh and load tools/.reports/ios-native.env first}"
mkdir -p tools/.reports
python tools/apple_sdk.py --ios
export DEVELOPER_DIR="$(python -c 'import json; print(json.load(open("configs/toolchain.json"))["apple"]["developer_dir"])')"
minimum=$(python tools/build_toolchain.py --value ios.minimum)
python tools/prepare_flutter.py
[[ ! -e flutter/ios/Podfile && ! -e flutter/ios/Podfile.lock ]]
rustup target add aarch64-apple-ios
rustup component add llvm-tools-preview
env IPHONEOS_DEPLOYMENT_TARGET="$minimum" cargo build --locked --release \
  --target aarch64-apple-ios --lib --features flutter,hwcodec \
  > tools/.reports/ios-cargo.log 2>&1 || { tail -120 tools/.reports/ios-cargo.log; exit 1; }
test -s target/aarch64-apple-ios/release/liblibrustdesk.a
(
  cd flutter
  export FLUTTER_XCODE_IPHONEOS_DEPLOYMENT_TARGET="$minimum"
  export FLUTTER_XCODE_CODE_SIGNING_ALLOWED=NO
  flutter build ios --release --no-codesign --no-pub \
    > ../tools/.reports/ios-flutter.log 2>&1 || { tail -120 ../tools/.reports/ios-flutter.log; exit 1; }
)
python tools/verify_ios_bundle.py flutter/build/ios/iphoneos/Runner.app \
  target/aarch64-apple-ios/release/liblibrustdesk.a --report tools/.reports/ios-bundle.json
git diff --exit-code HEAD -- flutter/ios flutter/pubspec.yaml flutter/pubspec.lock Cargo.toml Cargo.lock \
  src/lan.rs libs/scrap/build.rs res/vcpkg-triplets/arm64-ios.cmake
[[ -z "$(git ls-files --others --exclude-standard -- flutter/ios)" ]] || { echo 'Uncommitted native project files were generated.' >&2; exit 1; }
[[ ! -e flutter/ios/Podfile && ! -e flutter/ios/Podfile.lock ]]
mkdir -p dist/ios-arm64-unsigned
tar -czf dist/ios-arm64-unsigned/Runner-ios-arm64-unsigned.tar.gz \
  -C flutter/build/ios/iphoneos Runner.app
python tools/viper.py manifest dist/ios-arm64-unsigned --revision "$(git rev-parse HEAD)"
python tools/viper.py verify dist/ios-arm64-unsigned
