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
    if workflow.get('permissions') != {'contents': 'read'}:
        raise ValueError('Release workflow must be read-only by default')
    shared = workflow.get('env', {})
    if shared.get('RELEASE_ALLOWED') != RELEASE_EXPRESSION:
        raise ValueError('Release trust-boundary expression drift')
    for name, value in shared.items():
        if 'secrets.' in str(value) and AVAILABILITY.get(name) != value:
            raise ValueError('A signing credential escaped into the shared environment')
    publication_steps = []
    staged_steps = []
    for job_name, job in workflow.get('jobs', {}).items():
        if 'secrets.' in str(job.get('env', {})):
            raise ValueError('A signing credential escaped into a build job environment')
        for step in job.get('steps', []):
            command = step.get('run', '')
            if 'secrets.' in command:
                raise ValueError('Never interpolate a secret into shell source')
            is_publication = step.get('uses', '').startswith('softprops/action-gh-release@')
            is_staged_release = (step.get('uses', '').startswith('actions/upload-artifact@')
                                 and str(step.get('with', {}).get('name', '')).startswith('release-'))
            if is_publication:
                publication_steps.append((job_name, step))
            if is_staged_release:
                staged_steps.append((job_name, step))
            protected = ('secrets.' in str(step.get('with', {}))
                         or 'secrets.' in str(step.get('env', {}))
                         or is_publication or is_staged_release)
            if protected and not re.fullmatch(
                    r"\$\{\{ env\.RELEASE_ALLOWED == 'true' && \(.+\) \}\}", step.get('if', '')):
                raise ValueError('Signing/import/publication step lacks the release guard')
            if step.get('uses', '').startswith('actions/checkout@'):
                if step.get('with', {}).get('persist-credentials') is not False:
                    raise ValueError('Build checkout must not persist its token')

    if len(publication_steps) != 1 or publication_steps[0][0] != 'publish-release':
        raise ValueError('Exactly one final publication step is allowed')
    if len(staged_steps) != 15:
        raise ValueError('Every historical publication path must stage an immutable artifact')
    publish_job = workflow['jobs']['publish-release']
    if publish_job.get('permissions') != {'contents': 'write'}:
        raise ValueError('Only the final publisher may receive contents write permission')
    required = set(workflow['jobs']) - {'publish-release'}
    if set(publish_job.get('needs', [])) != required:
        raise ValueError('Final publisher must wait for every build and evidence job')
    condition = str(publish_job.get('if', ''))
    for name in required:
        if f"needs.{name}.result == 'success'" not in condition:
            raise ValueError(f'Final publisher does not require success from {name}')


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
