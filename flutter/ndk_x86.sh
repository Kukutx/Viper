#!/usr/bin/env bash

#
# Fix OpenSSL build with Android NDK clang on 32-bit architectures
#

export CFLAGS="-DBROKEN_CLANG_ATOMICS"
export CXXFLAGS="-DBROKEN_CLANG_ATOMICS"

cargo ndk --platform "$(python3 -c 'import json; print(json.load(open("configs/toolchain.json"))["android"]["min_sdk"])')" --target i686-linux-android build --locked --release --features flutter
