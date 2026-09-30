"""Build the reviewed FRB generator from Cargo sources, including for F-Droid."""
from pathlib import Path
import json
import os
import re
import subprocess


def install(root: Path) -> Path:
    spec = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))['flutter_rust_bridge']
    version = spec['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Source generator requires an exact stable version')
    directory = root / '.tools/frb-source'
    for path in (root / '.tools', directory, directory / 'bin'):
        if path.is_symlink():
            raise ValueError('Source generator tool directory cannot be a symlink')
    executable = directory / 'bin' / ('flutter_rust_bridge_codegen.exe' if os.name == 'nt' else 'flutter_rust_bridge_codegen')
    if executable.is_symlink():
        raise ValueError('Source generator executable cannot be a symlink')
    # cargo validates registry checksums and builds the release's own locked graph.
    # Never fall back to a prebuilt executable when source compilation fails.
    subprocess.run(['cargo', 'install', 'flutter_rust_bridge_codegen', '--version', '=' + version,
                    '--locked', '--root', str(directory)], cwd=root, check=True)
    actual = subprocess.check_output([str(executable), '--version'], cwd=root, text=True).strip()
    if not actual or actual.split()[-1] != version:
        raise ValueError(f'Source generator version mismatch: {actual}')
    return executable
