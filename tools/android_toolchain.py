"""Validate the shared Android toolchain before executing downloaded tools."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ABIS = {
    'arm64-v8a': ('aarch64-linux-android', 'arm64-android', 'android-arm64', 2, 183, 'aarch64-linux-android'),
    'armeabi-v7a': ('armv7-linux-androideabi', 'arm-neon-android', 'android-arm', 1, 40, 'arm-linux-androideabi'),
    'x86_64': ('x86_64-linux-android', 'x64-android', 'android-x64', 2, 62, 'x86_64-linux-android'),
}


def configuration(root: Path = ROOT) -> dict:
    data = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))['android']
    for key in ('agp', 'gradle', 'kotlin', 'ndk', 'cargo_ndk', 'protobuf_plugin', 'protobuf', 'build_tools'):
        if not isinstance(data.get(key), str) or not re.fullmatch(r'\d+\.\d+\.\d+', data[key]):
            raise ValueError(f'{key}: exact stable version required')
    if not re.fullmatch(r'\d+(?:\.\d+){2,3}\+\d+', data['jdk']):
        raise ValueError('JDK runtime version and build must be pinned')
    for key in ('gradle_sha256', 'wrapper_sha256'):
        if not re.fullmatch(r'[a-f0-9]{64}', data[key]):
            raise ValueError(f'{key}: SHA-256 required')
    for key in ('compile_sdk', 'target_sdk', 'min_sdk', 'jvm_target'):
        if type(data.get(key)) is not int:
            raise ValueError(f'{key}: integer required')
    if not 23 <= data['min_sdk'] <= data['target_sdk'] <= data['compile_sdk']:
        raise ValueError('Android SDK levels must be ordered and meet the NDK minimum')
    return data


def properties(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if '=' not in line:
            raise ValueError(f'Malformed property in {path}')
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip().strip('"')
        if key in result:
            raise ValueError(f'Duplicate property {key} in {path}')
        result[key] = value
    return result


def check(root: Path = ROOT, runtime: bool = False) -> dict:
    data = configuration(root)
    wrapper = root / 'flutter/android/gradle/wrapper'
    props = properties(wrapper / 'gradle-wrapper.properties')
    url = props['distributionUrl'].replace('\\:', ':')
    if url != f"https://services.gradle.org/distributions/gradle-{data['gradle']}-bin.zip":
        raise ValueError('Gradle distribution version or origin drift')
    if props.get('distributionSha256Sum') != data['gradle_sha256']:
        raise ValueError('Gradle distribution checksum drift')
    jar = wrapper / 'gradle-wrapper.jar'
    if jar.is_symlink() or hashlib.sha256(jar.read_bytes()).hexdigest() != data['wrapper_sha256']:
        raise ValueError('Gradle wrapper JAR checksum mismatch')
    if runtime:
        verify_java(data)
        sdk_home = os.environ.get('ANDROID_HOME')
        if not sdk_home:
            raise ValueError('ANDROID_HOME is required')
        sdk = Path(sdk_home)
        ndk = sdk / 'ndk' / data['ndk']
        if properties(ndk / 'source.properties').get('Pkg.Revision') != data['ndk']:
            raise ValueError('NDK revision mismatch')
        for path in (sdk / 'platforms' / f"android-{data['compile_sdk']}.0" / 'android.jar',
                     sdk / 'build-tools' / data['build_tools'] / 'zipalign'):
            if not path.is_file():
                raise ValueError(f'Missing pinned Android SDK tool: {path}')
    return data


def verify_java(data: dict) -> None:
    java_home = os.environ.get('JAVA_HOME')
    if not java_home:
        raise ValueError('JAVA_HOME is required')
    actual = properties(Path(java_home) / 'release').get('JAVA_RUNTIME_VERSION', '')
    if actual.removesuffix('-LTS') != data['jdk']:
        raise ValueError(f'JDK runtime drift: {actual}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', action='store_true')
    parser.add_argument('--env', action='store_true')
    parser.add_argument('--java-only', action='store_true')
    args = parser.parse_args()
    try:
        data = check(runtime=args.runtime)
        if args.java_only:
            verify_java(data)
        if args.env:
            names = {'ANDROID_JDK_VERSION': 'jdk', 'ANDROID_NDK_VERSION': 'ndk',
                     'ANDROID_COMPILE_SDK': 'compile_sdk', 'ANDROID_BUILD_TOOLS': 'build_tools',
                     'CARGO_NDK_VERSION': 'cargo_ndk', 'ANDROID_MIN_SDK': 'min_sdk'}
            print('ANDROID_JDK_FEATURE=' + data['jdk'].split('.')[0])
            for name, key in names.items():
                print(f'{name}={data[key]}')
        else:
            print('Android toolchain checks passed; APK and device tests are separate checks.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
