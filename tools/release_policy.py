"""Check release credentials stay in guarded build steps and publication is centralized."""
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
        raise ValueError('Build workflow must be read-only')
    shared = workflow.get('env', {})
    if shared.get('RELEASE_ALLOWED') != RELEASE_EXPRESSION:
        raise ValueError('Release trust-boundary expression drift')
    for name, value in shared.items():
        if 'secrets.' in str(value) and AVAILABILITY.get(name) != value:
            raise ValueError('A signing credential escaped into the shared environment')

    staged_steps = []
    for job in workflow.get('jobs', {}).values():
        if 'secrets.' in str(job.get('env', {})):
            raise ValueError('A signing credential escaped into a build job environment')
        for step in job.get('steps', []):
            command = step.get('run', '')
            if 'secrets.' in command:
                raise ValueError('Never interpolate a secret into shell source')
            if step.get('uses', '').startswith('softprops/action-gh-release@'):
                raise ValueError('Build jobs may stage assets but may not publish releases')
            is_staged_release = (step.get('uses', '').startswith('actions/upload-artifact@')
                                 and str(step.get('with', {}).get('name', '')).startswith('release-'))
            if is_staged_release:
                staged_steps.append(step)
            protected = ('secrets.' in str(step.get('with', {}))
                         or 'secrets.' in str(step.get('env', {}))
                         or is_staged_release)
            if protected and not re.fullmatch(
                    r"\$\{\{ env\.RELEASE_ALLOWED == 'true' && \(.+\) \}\}", step.get('if', '')):
                raise ValueError('Signing/import/staging step lacks the release guard')
            if step.get('uses', '').startswith('actions/checkout@'):
                if step.get('with', {}).get('persist-credentials') is not False:
                    raise ValueError('Build checkout must not persist its token')
    if len(staged_steps) != 15:
        raise ValueError('Every historical publication path must stage an immutable artifact')
    names = [str(step['with']['name']) for step in staged_steps]
    if len(names) != len(set(names)):
        raise ValueError('Release staging artifact names must be unique')


def check_publisher(workflow: dict) -> None:
    if workflow.get('permissions') != {'contents': 'write'}:
        raise ValueError('Publisher must have explicit contents write permission')
    jobs = workflow.get('jobs', {})
    if set(jobs) != {'publish'}:
        raise ValueError('Publisher workflow must contain exactly one job')
    job = jobs['publish']
    if 'pull_request' not in str(job.get('if', '')):
        raise ValueError('Publisher trust boundary must explicitly reject pull requests')
    publications = [step for step in job.get('steps', [])
                    if step.get('uses', '').startswith('softprops/action-gh-release@')]
    if len(publications) != 1:
        raise ValueError('Publisher must have exactly one release publication step')
    downloads = [step for step in job.get('steps', [])
                 if step.get('uses', '').startswith('actions/download-artifact@')]
    if len(downloads) != 1 or downloads[0].get('with', {}).get('pattern') != 'release-*':
        raise ValueError('Publisher must consume only staged release artifacts')
    release = publications[0]
    if release.get('with', {}).get('fail_on_unmatched_files') is not True:
        raise ValueError('Publisher must fail when staged assets are missing')
    if 'release-staging/**/*' not in str(release.get('with', {}).get('files', '')):
        raise ValueError('Publisher must publish the verified staging tree')


def check_caller(workflow: dict, build_job: str, tag: str) -> None:
    if workflow.get('permissions') != {'contents': 'read'}:
        raise ValueError('Release callers must be read-only by default')
    jobs = workflow.get('jobs', {})
    build = jobs[build_job]
    if build.get('uses') != './.github/workflows/flutter-build.yml':
        raise ValueError('Release caller must use the canonical build workflow')
    if build.get('with', {}).get('upload-artifact') is not True:
        raise ValueError('Release build must stage artifacts')
    publisher = jobs.get('publish-release', {})
    if publisher.get('uses') != './.github/workflows/release-publish.yml':
        raise ValueError('Release caller must use the canonical publisher')
    if publisher.get('needs') != [build_job]:
        raise ValueError('Publisher must wait for the complete reusable build')
    if publisher.get('permissions') != {'contents': 'write'}:
        raise ValueError('Only the publisher caller job may receive contents write')
    if publisher.get('with', {}).get('upload-tag') != tag:
        raise ValueError('Publisher tag input drift')


def check(root: Path = ROOT) -> None:
    check_workflow(yaml.safe_load((root / '.github/workflows/flutter-build.yml').read_text(encoding='utf-8')))
    check_publisher(yaml.safe_load((root / '.github/workflows/release-publish.yml').read_text(encoding='utf-8')))
    check_caller(yaml.safe_load((root / '.github/workflows/flutter-tag.yml').read_text(encoding='utf-8')),
                 'run-flutter-tag-build', '${{ github.ref_name }}')
    check_caller(yaml.safe_load((root / '.github/workflows/flutter-nightly.yml').read_text(encoding='utf-8')),
                 'run-flutter-nightly-build', 'nightly')
    ci = yaml.safe_load((root / '.github/workflows/flutter-ci.yml').read_text(encoding='utf-8'))
    if ci.get('permissions') != {'contents': 'read'}:
        raise ValueError('PR validation must retain read-only permissions')
    for job in ci['jobs'].values():
        if 'secrets' in job or job.get('with', {}).get('upload-artifact') is not False:
            raise ValueError('PR validation must not receive release credentials or publish')


if __name__ == '__main__':
    check()
    print('Release credential and single-publication boundaries verified.')
