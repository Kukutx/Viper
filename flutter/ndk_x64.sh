#!/usr/bin/env bash
cargo ndk --platform "$(python3 -c 'import json; print(json.load(open("configs/toolchain.json"))["android"]["min_sdk"])')" --target x86_64-linux-android build --locked --release --features flutter
