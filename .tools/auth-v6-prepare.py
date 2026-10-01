"""One-time, fail-closed preparation; never writes a branch or a tag."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e2ff7ab2ceef9f1602848d48c9202df58a71c385'
EXPECTED = {
    'Cargo.toml': '76c370aa60ca12c778cc4eb8916f056257b8dcff',
    'src/auth_2fa.rs': '1c243bc77646ba94b8c27682439a6dc49e4a7ccd',
    'src/server/connection.rs': '7ed59b40c50ed3275a386ec53998b9ba119e7d97',
    '.github/workflows/flutter-validate.yml': '6925cb8e5528f9f8d669580a0cb11ce74351fdeb',
}
PATHS = [*EXPECTED, 'Cargo.lock', 'src/auth_2fa/totp.rs',
         'tests/auth_dependency_contract.rs', 'tools/tests/test_auth_dependencies.py',
         'docs/engineering/auth-dependencies-migration.md']


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected one exact replacement: {old!r}')
    return text.replace(old, new)


def apply():
    for path, expected in EXPECTED.items():
        if blob((ROOT / path).read_bytes()) != expected:
            raise ValueError(f'Unreviewed input: {path}')
    manifest = (ROOT / 'Cargo.toml').read_text()
    for old, new in [
        ('rust-version = "1.75"', 'rust-version = "1.88"'),
        ('sha2 = "0.10"', 'sha2 = "0.11.0"'),
        ('totp-rs = { version = "5.4", default-features = false, features = ["gen_secret", "otpauth"] }',
         'totp-rs = { version = "6.0.0", default-features = false, features = ["std", "gen_secret", "otpauth"] }'),
    ]:
        manifest = replace(manifest, old, new)
    (ROOT / 'Cargo.toml').write_text(manifest)
    path = ROOT / 'src/auth_2fa.rs'
    source = path.read_text()
    for old, new in [
        ('use std::sync::Mutex;', 'use std::{sync::Mutex, time::SystemTime};'),
        ('use totp_rs::{Algorithm, Secret, TOTP};', 'use totp_rs::{Secret, Totp};\n\npub(crate) mod totp;'),
        ('Mutex<Option<(TOTPInfo, TOTP)>>', 'Mutex<Option<(TOTPInfo, Totp)>>'),
        ('const ISSUER: &str = "RustDesk";\nconst TAG_LOGIN: &str = "Connection";\n\n', ''),
        ('    fn new_totp(&self) -> ResultType<TOTP> {\n        let totp = TOTP::new(\n            Algorithm::SHA1,\n            self.digits,\n            1,\n            30,\n            self.secret.clone(),\n            Some(format!("{} {}", ISSUER, TAG_LOGIN)),\n            self.name.clone(),\n        )?;\n        Ok(totp)\n    }',
         '    fn new_totp(&self) -> ResultType<Totp> {\n        totp::build_totp(&self.secret, self.digits, &self.name)\n    }'),
        ('Secret::generate_secret()', 'Secret::generate()'),
        ('secret: secret.to_bytes()?', 'secret: secret.as_bytes().to_vec()'),
        ('pub fn from_str(data: &str) -> ResultType<TOTP>', 'pub fn from_str(data: &str) -> ResultType<Totp>'),
        ('            let code = totp.get_url();\n            *CURRENT_2FA.lock().unwrap() = Some((info, totp));\n            return code;',
         '            if let Ok(code) = totp.to_url() {\n                *CURRENT_2FA.lock().unwrap() = Some((info, totp));\n                return code;\n            }'),
        ('totp.check_current(&code)', 'totp::verify_at(totp, &code, SystemTime::now())'),
        ('pub fn get_2fa(raw: Option<String>) -> Option<TOTP>', 'pub fn get_2fa(raw: Option<String>) -> Option<Totp>'),
    ]:
        source = replace(source, old, new)
    path.write_text(source)
    path = ROOT / 'src/server/connection.rs'
    source = path.read_text()
    for old, new in [
        ('Option<totp_rs::TOTP>', 'Option<totp_rs::Totp>'),
        ('totp.generate_current()', 'crate::auth_2fa::totp::generate_at(totp, std::time::SystemTime::now())'),
        ('totp.check_current(&tfa.code)', 'crate::auth_2fa::totp::verify_at(totp, &tfa.code, std::time::SystemTime::now())'),
    ]:
        source = replace(source, old, new)
    path.write_text(source)
    path = ROOT / '.github/workflows/flutter-validate.yml'
    source = path.read_text()
    source = replace(source, '      - name: Exercise actual synchronous and asynchronous FFI',
        '      - name: Verify authentication dependency contracts\n'
        '        run: |\n'
        '          cargo test --locked --test auth_dependency_contract --features flutter,linux-pkg-config > tools/.reports/auth-dependencies.log 2>&1 || { tail -100 tools/.reports/auth-dependencies.log; exit 1; }\n'
        '      - name: Exercise actual synchronous and asynchronous FFI')
    path.write_text(source)


def git_packages(lock):
    """Compare actual Git identities across Cargo's v3/v4 URL serialization."""
    if lock['version'] not in (3, 4):
        raise ValueError('Unreviewed Cargo lock format')
    result = []
    for package in lock['package']:
        source = package.get('source', '')
        if not source.startswith('git+'):
            continue
        url = urlsplit(source)
        if len(url.fragment) != 40 or any(c not in '0123456789abcdef' for c in url.fragment):
            raise ValueError('Git source must retain a full commit')
        if lock['version'] == 4:
            query = tuple(parse_qsl(url.query, keep_blank_values=True, strict_parsing=True))
        else:
            # v3 stored reference values literally, including '+' and '%'.
            query = tuple(tuple(part.split('=', 1)) for part in url.query.split('&')) if url.query else ()
        if any(len(pair) != 2 or pair[0] not in {'branch', 'tag', 'rev'} for pair in query) or len(query) > 1:
            raise ValueError('Unreviewed Git reference query')
        result.append((package['name'], package['version'], url.scheme, url.netloc,
                       url.path, query, url.fragment))
    return sorted(result)


def validate_resolution():
    before = tomllib.loads(subprocess.check_output(['git', 'show', f'{BASE}:Cargo.lock'], cwd=ROOT, text=True))
    after = tomllib.loads((ROOT / 'Cargo.lock').read_text())
    previous, current = git_packages(before), git_packages(after)
    evidence = {'before': previous, 'after': current, 'removed': sorted(set(previous) - set(current)),
                'added': sorted(set(current) - set(previous)), 'unused_patches': after.get('patch', {}),
                'lock_formats': [before['version'], after['version']],
                'raw_sources_before': [p['source'] for p in before['package'] if p.get('source', '').startswith('git+')],
                'raw_sources_after': [p['source'] for p in after['package'] if p.get('source', '').startswith('git+')]}
    (ROOT / 'tools/.reports/auth-git-identities.json').write_text(json.dumps(evidence, indent=2) + '\n')
    if previous != current:
        raise ValueError('Maintained Git package identities changed; see auth-git-identities.json')
    metadata = json.loads((ROOT / 'tools/.reports/auth-metadata.json').read_text())
    for name, version in [('flutter_rust_bridge', '2.13.0'), ('netdev', '0.46.3'), ('totp-rs', '6.0.0')]:
        if {p['version'] for p in metadata['packages'] if p['name'] == name} != {version}:
            raise ValueError(f'Unexpected version resolution: {name}')
    package = next(p for p in metadata['packages'] if p['name'] == 'totp-rs')
    node = next(n for n in metadata['resolve']['nodes'] if n['id'] == package['id'])
    if set(node['features']) & {'migration', 'serde'}:
        raise ValueError('Effective TOTP compatibility features were enabled')
    root = next(p for p in metadata['packages'] if p['manifest_path'] == str(ROOT / 'Cargo.toml'))
    root_node = next(n for n in metadata['resolve']['nodes'] if n['id'] == root['id'])
    sha_id = next(d['pkg'] for d in root_node['deps'] if d['name'] == 'sha2')
    sha = next(p for p in metadata['packages'] if p['id'] == sha_id)
    if sha['version'] != '0.11.0':
        raise ValueError('Root SHA-2 did not migrate')
    return after, node


def export():
    after, node = validate_resolution()
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    changed = subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines()
    if set(changed) != set(EXPECTED) | {'Cargo.lock'}:
        raise ValueError(f'Unexpected patch scope: {changed}')
    output = ROOT / '.tools/auth-v6-reviewed'
    output.mkdir()
    records = []
    for name in PATHS:
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'Missing regular output: {name}')
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        data = source.read_bytes()
        records.append({'path': name, 'sha': blob(data), 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)})
    (output / 'objects.json').write_text(json.dumps({'base': BASE, 'files': records, 'git_packages_preserved': sum(p.get('source', '').startswith('git+') for p in after['package']), 'totp_features': node['features']}, indent=2) + '\n')
    (output / 'migration.patch').write_bytes(subprocess.check_output(['git', 'diff', '--', *EXPECTED, 'Cargo.lock'], cwd=ROOT))
    print(json.dumps(records, indent=2))


if __name__ == '__main__':
    {'apply': apply, 'validate': validate_resolution, 'export': export}[sys.argv[1]]()
