#!/usr/bin/env bash
cargo ndk --platform "$(python3 -c 'import json; print(json.load(open("configs/toolchain.json"))["android"]["min_sdk"])')" --target aarch64-linux-android build --locked --release --features flutter,hwcodec
