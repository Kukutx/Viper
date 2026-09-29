"""发布候选 Git 对象供审查；绝不移动分支或发布应用。"""
from pathlib import Path
import base64
import concurrent.futures
import json
import os
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
REPO = 'Kukutx/Viper'
BRANCH = 'refs/heads/codex/viper-foundation-modernization'
EXACT = {'Cargo.toml', 'Cargo.lock', 'flutter_rust_bridge.yaml', 'src/flutter.rs', 'src/flutter_ffi.rs', 'src/bridge_generated.rs', 'src/bridge_generated.io.rs', 'src/bridge_generated.web.rs', 'flutter/pubspec.yaml', 'flutter/pubspec.lock', 'flutter/macos/Runner/bridge_generated.h', 'flutter/ios/Runner/bridge_generated.h', 'flutter/windows/runner/main.cpp', 'flutter/android/build.gradle', 'flutter/android/app/src/main/AndroidManifest.xml', 'flutter/ios/Runner/Info.plist'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def api(path, data):
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + '/git/' + path, data=json.dumps(data).encode(), method='POST', headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json', 'User-Agent': 'Viper-candidate-snapshot', 'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def allowed(path):
    return path in EXACT or path.startswith(('flutter/lib/', 'flutter/packages/dash_chat_2/', 'flutter/test/'))


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != BRANCH:
        raise ValueError('Snapshot restricted to the authorized migration branch')
    parent = git('rev-parse', 'HEAD')
    if parent != os.environ['GITHUB_SHA']:
        raise ValueError('Checkout differs from workflow source')
    names = set(git('diff', '--name-only', '-z', 'HEAD').split('\0'))
    for pattern in ('flutter/lib/generated/**/*', 'flutter/packages/dash_chat_2/**/*', 'src/bridge_generated*.rs'):
        names.update(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern) if p.is_file())
    names.add('flutter_rust_bridge.yaml')
    names = {name for name in names if allowed(name)}
    def blob(name):
        path = ROOT / name
        if path.is_symlink():
            raise ValueError(f'Symlink forbidden: {name}')
        if not path.exists():
            return {'path': name, 'mode': '100644', 'type': 'blob', 'sha': None}
        data = path.read_bytes()
        if len(data) > 5_000_000:
            raise ValueError(f'Unexpected large candidate file: {name}')
        sha = api('blobs', {'encoding': 'base64', 'content': base64.b64encode(data).decode()})['sha']
        return {'path': name, 'mode': '100644', 'type': 'blob', 'sha': sha}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(blob, sorted(names)))
    base = git('rev-parse', 'HEAD^{tree}')
    record = {'parent': parent, 'base_tree': base, 'entries': entries}
    report = ROOT / 'tools/.reports/snapshot.json'
    report.write_text(json.dumps(record, indent=2) + '\n')
    print('CANDIDATE_PARENT=' + parent, flush=True)
    print('CANDIDATE_TREE_ELEMENTS=' + json.dumps(entries, separators=(',', ':')), flush=True)
    try:
        tree = api('trees', {'base_tree': base, 'tree': entries})['sha']
        commit = api('commits', {'message': 'snapshot: unmerged Flutter 2.x migration candidate for review', 'tree': tree, 'parents': [parent]})['sha']
    except urllib.error.HTTPError as error:
        if error.code != 403:
            raise
        print('Tree creation was denied; blob references remain available for authorized connector review.')
        return
    record.update(tree=tree, commit=commit)
    report.write_text(json.dumps(record, indent=2) + '\n')
    print('CANDIDATE_SNAPSHOT=' + commit)
    print('CANDIDATE_TREE=' + tree)
    print('No branch or release was updated. Test results must be checked separately.')


if __name__ == '__main__':
    main()
