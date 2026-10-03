"""Install and verify pinned Rust in a fresh CI-only rustup home."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def bootstrap(root: Path, environment: dict[str, str]) -> dict:
    if environment.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('This bootstrap is for GitHub Actions only; local Rust is not changed')
    runner_temp = Path(environment.get('RUNNER_TEMP', ''))
    github_env = Path(environment.get('GITHUB_ENV', ''))
    if not runner_temp.is_absolute() or runner_temp.is_symlink() or not runner_temp.is_dir():
        raise ValueError('RUNNER_TEMP must be an existing regular absolute directory')
    if not github_env.is_absolute() or github_env.is_symlink() or not github_env.is_file():
        raise ValueError('GITHUB_ENV must be an existing regular absolute file')
    if any(c in str(runner_temp) for c in '\r\n'):
        raise ValueError('Unsafe runner directory')
    version = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))['rust']
    toolchain = tomllib.loads((root / 'rust-toolchain.toml').read_text(encoding='utf-8'))['toolchain']
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Rust must be pinned to a stable release')
    if toolchain.get('channel') != version or toolchain.get('profile') != 'minimal':
        raise ValueError('Rust toolchain and central configuration disagree')
    components = toolchain.get('components')
    if not isinstance(components, list) or not {'rustfmt', 'clippy'}.issubset(components):
        raise ValueError('Both rustfmt and clippy must remain installed')
    if any(not isinstance(c, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', c) for c in components):
        raise ValueError('Invalid Rust component')
    rustup = shutil.which('rustup', path=environment.get('PATH'))
    if not rustup:
        raise ValueError('rustup is required')

    home = Path(tempfile.mkdtemp(prefix='viper-rustup-', dir=runner_temp)).resolve()
    env = {**environment, 'RUSTUP_HOME': str(home), 'RUSTUP_TOOLCHAIN': version}
    # Cargo caches and global rustup installations are intentionally untouched.
    reports = root / 'tools/.reports'
    reports.mkdir(parents=True, exist_ok=True)
    with (reports / 'ci-rust-install.log').open('w', encoding='utf-8') as log:
        def run(arguments: list[str]) -> str:
            result = subprocess.run(
                [rustup, *arguments], cwd=root, env=env, text=True,
                encoding='utf-8', errors='replace', stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=600, check=False,
            )
            log.write(result.stdout)
            log.flush()
            if result.returncode:
                raise RuntimeError(f'Rust bootstrap command failed ({result.returncode}); see {log.name}')
            return result.stdout.strip()

        run(['toolchain', 'install', version, '--profile', 'minimal',
             '--component', ','.join(components), '--no-self-update'])
        tools = {}
        for name in ('rustc', 'cargo', 'rustfmt', 'cargo-clippy'):
            path = Path(run(['which', '--toolchain', version, name]))
            if not path.is_absolute() or not path.is_file() or not path.resolve().is_relative_to(home):
                raise RuntimeError(f'{name} did not resolve to the isolated toolchain')
            tools[name] = str(path.resolve())
        compiler = run(['run', version, 'rustc', '-vV'])
        if re.search(r'^release: (.+)$', compiler, re.MULTILINE) is None:
            raise RuntimeError('Rust compiler did not report its release')
        if not re.search(rf'^release: {re.escape(version)}$', compiler, re.MULTILINE):
            raise RuntimeError('Rust compiler version drift')
        for command in ('cargo', 'rustfmt', 'cargo-clippy'):
            if not run(['run', version, command, '--version']):
                raise RuntimeError(f'{command} did not report its version')

    report = {'rust': version, 'rustup_home': str(home), 'tools': tools, 'compiler': compiler}
    (reports / 'ci-rust.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    # Export only after every check succeeds, so no later step sees a partial install.
    with github_env.open('a', encoding='utf-8') as stream:
        stream.write(f'RUSTUP_HOME={home}\nRUSTUP_TOOLCHAIN={version}\n')
    return report


if __name__ == '__main__':
    try:
        report = bootstrap(ROOT, dict(os.environ))
        print(f"Verified isolated Rust {report['rust']}, rustfmt and clippy")
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        print(f'Rust bootstrap failed: {error}', file=sys.stderr)
        raise SystemExit(1)
