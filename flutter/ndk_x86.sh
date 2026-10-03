#!/usr/bin/env bash

#
# Fix OpenSSL build with Android NDK clang on 32-bit architectures
#

export CFLAGS="-DBROKEN_CLANG_ATOMICS"
export CXXFLAGS="-DBROKEN_CLANG_ATOMICS"

python3 tools/android_cargo.py i686-linux-android build --locked --release --features flutter
