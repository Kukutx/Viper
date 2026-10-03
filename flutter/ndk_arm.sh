#!/usr/bin/env bash
python3 tools/android_cargo.py armv7-linux-androideabi build --locked --release --features flutter,hwcodec
