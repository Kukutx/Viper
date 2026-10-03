"""Run cargo-ndk with an API-qualified bindgen target for the selected NDK."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys

from android_toolchain import ROOT, configuration

TARGETS = {
    'aarch64-linux-android': ('aarch64-linux-android', 'aarch64-linux-android'),
    'armv7-linux-androideabi': ('armv7a-linux-androideabi', 'arm-linux-androideabi'),
    'x86_64-linux-android': ('x86_64-linux-android', 'x86_64-linux-android'),
    'i686-linux-android': ('i686-linux-android', 'i686-linux-android'),
}


def environment(target: str, ndk: Path, api: int, inherited: dict[str, str]) -> dict[str, str]:
    if target not in TARGETS or type(api) is not int or not 24 <= api <= 255:
        raise ValueError('An explicit supported Android target and API are required')
    clang_target, headers = TARGETS[target]
    sysroot = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/sysroot'
    if not (sysroot / 'usr/include' / headers).is_dir():
        raise ValueError(f'Missing target headers in the pinned NDK: {sysroot}')
    args = shlex.join([f'--target={clang_target}{api}', f'--sysroot={sysroot}',
                       f'-I{sysroot / "usr/include" / headers}'])
    # cargo-ndk 4.1.2 overwrites the underscore key with an unversioned sysroot.
    # bindgen's target-triple key has precedence and keeps host tools untouched.
    key = f'BINDGEN_EXTRA_CLANG_ARGS_{target}'
    if key in inherited and inherited[key] != args:
        raise ValueError(f'Conflicting Android bindgen flags: {key}')
    return {**inherited, key: args, 'ANDROID_NDK_HOME': str(ndk), 'ANDROID_NDK_ROOT': str(ndk)}


def main() -> int:
    try:
        if len(sys.argv) < 3 or sys.argv[1] not in TARGETS:
            raise ValueError('Usage: android_cargo.py RUST_TARGET CARGO_COMMAND [ARGS...]')
        cfg = configuration(ROOT)
        sdk = os.environ.get('ANDROID_HOME')
        if not sdk:
            raise ValueError('ANDROID_HOME is required')
        ndk = Path(sdk) / 'ndk' / cfg['ndk']
        env = environment(sys.argv[1], ndk, cfg['min_sdk'], dict(os.environ))
        command = ['cargo', 'ndk', '--platform', str(cfg['min_sdk']), '--target', sys.argv[1], *sys.argv[2:]]
        return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
    except (OSError, ValueError, KeyError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
