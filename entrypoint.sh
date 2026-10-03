#!/bin/sh
set -eu

cd "${VIPER_WORKSPACE:-/workspace}"
if [ "$#" -eq 0 ]; then
    set -- build --locked --features flutter --lib
fi
exec cargo "$@"
