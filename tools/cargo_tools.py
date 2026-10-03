"""Install the repository-pinned cargo-expand without changing the user's Cargo tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess


def expand_environment(root: Path) -> dict[str, str]:
    version = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))['cargo_expand']
    if not isinstance(version, str) or re.fullmatch(r'\d+\.\d+\.\d+', version) is None:
        raise ValueError('cargo-expand must be pinned to an exact stable version')
    prefix = root / '.tools/cargo'
    executable = prefix / 'bin' / ('cargo-expand.exe' if os.name == 'nt' else 'cargo-expand')
    for path in (root / '.tools', prefix, prefix / 'bin', executable):
        if path.is_symlink():
            raise ValueError(f'Cargo tool path must not be a symlink: {path}')
    environment = dict(os.environ)
    environment['PATH'] = str(executable.parent) + os.pathsep + environment.get('PATH', '')
    expected = 'cargo-expand ' + version

    def installed_version() -> str:
        return subprocess.check_output([str(executable), '--version'], cwd=root, text=True, encoding='utf-8').strip()

    if not executable.is_file() or installed_version() != expected:
        subprocess.run(
            ['cargo', 'install', 'cargo-expand', '--version', version, '--locked', '--root', str(prefix)],
            cwd=root, check=True,
        )
    if installed_version() != expected:
        raise ValueError('Installed cargo-expand does not match the repository pin')
    print(f'Using {expected}: {executable}')
    return environment
