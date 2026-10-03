#!/usr/bin/env bash
python3 tools/android_cargo.py aarch64-linux-android build --locked --release --features flutter,hwcodec
