#!/usr/bin/env bash
cargo ndk --platform "$(python3 -c 'import json; print(json.load(open("configs/toolchain.json"))["android"]["min_sdk"])')" --target armv7-linux-androideabi build --locked --release --features flutter,hwcodec
