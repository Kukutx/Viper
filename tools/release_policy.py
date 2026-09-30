"""Check release credentials remain outside PRs and shared build environments."""
from __future__ import annotations

from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE_EXPRESSION = "${{ inputs.upload-artifact && github.repository == 'Kukutx/Viper' && !startsWith(github.event_name, 'pull_request') && (github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/')) }}"
AVAILABILITY = {
    'HAS_ANDROID_SIGNING': "${{ secrets.ANDROID_SIGNING_KEY != '' }}",
    'HAS_MACOS_SIGNING': "${{ secrets.MACOS_P12_BASE64 != '' }}",
    'HAS_WINDOWS_SIGNING': "${{ secrets.SIGN_BASE_URL != '' && secrets.SIGN_SECRET_KEY != '' }}",
}


def allows_release(repository: str, event: str, ref: str, publish: bool) -> bool:
    return (publish is True and repository == 'Kukutx/Viper'
            and not event.startswith('pull_request')
            and (ref == 'refs/heads/main' or ref.startswith('refs/tags/')))


def check_workflow(workflow: dict) -> None:
    shared = workflow.get('env', {})
    if shared.get('RELEASE_ALLOWED') != RELEASE_EXPRESSION:
        raise ValueError('Release trust-boundary expression drift')
    for name, value in shared.items():
        if 'secrets.' in str(value) and AVAILABILITY.get(name) != value:
            raise ValueError('A signing credential escaped into the shared environment')
    for job in workflow.get('jobs', {}).values():
        if 'secrets.' in str(job.get('env', {})):
            raise ValueError('A signing credential escaped into a build job environment')
        for step in job.get('steps', []):
            command = step.get('run', '')
            if 'secrets.' in command:
                raise ValueError('Never interpolate a secret into shell source')
            protected = ('secrets.' in str(step.get('with', {}))
                         or 'secrets.' in str(step.get('env', {}))
                         or step.get('uses', '').startswith('softprops/action-gh-release@'))
            if protected and not re.fullmatch(
                    r"\$\{\{ env\.RELEASE_ALLOWED == 'true' && \(.+\) \}\}", step.get('if', '')):
                raise ValueError('Signing/import/publication step lacks the release guard')
            if step.get('uses', '').startswith('actions/checkout@'):
                if step.get('with', {}).get('persist-credentials') is not False:
                    raise ValueError('Build checkout must not persist its token')


def check(root: Path = ROOT) -> None:
    check_workflow(yaml.safe_load((root / '.github/workflows/flutter-build.yml').read_text(encoding='utf-8')))
    ci = yaml.safe_load((root / '.github/workflows/flutter-ci.yml').read_text(encoding='utf-8'))
    if ci.get('permissions') != {'contents': 'read'}:
        raise ValueError('PR validation must retain read-only permissions')
    for job in ci['jobs'].values():
        if 'secrets' in job or job.get('with', {}).get('upload-artifact') is not False:
            raise ValueError('PR validation must not receive release credentials or publish')


if __name__ == '__main__':
    check()
    print('Release credential boundaries verified; no signing or publishing was executed.')
