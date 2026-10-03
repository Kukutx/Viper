"""Read a codesign identity as data, never as shell source."""
from __future__ import annotations

import os
import shlex
import sys


def normalize_identity(value: str) -> str:
    if not value or len(value) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Invalid codesign identity')
    value = value.strip()
    if value.startswith(('"', "'")):
        # Older configuration stored surrounding shell quotes in this secret.
        parts = shlex.split(value, posix=True)
        if len(parts) != 1:
            raise ValueError('Codesign identity must identify exactly one signer')
        value = parts[0]
    if not value or value.startswith('-'):
        raise ValueError('An explicit signing identity is required; ad-hoc signing is forbidden')
    return value


if __name__ == '__main__':
    try:
        print(normalize_identity(os.environ.get('MACOS_CODESIGN_IDENTITY', '')))
    except ValueError:
        print('ERROR: Invalid MACOS_CODESIGN_IDENTITY; no signing was performed.', file=sys.stderr)
        raise SystemExit(1)
