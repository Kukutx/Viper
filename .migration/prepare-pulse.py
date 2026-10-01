"""One-use, exact-preimage fork preparation; never changes a Git ref."""
from pathlib import Path
import base64
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
import urllib.request

ROOT = Path.cwd()
REPORT = ROOT / 'tools/.reports'
BLOBS = {
    'Cargo.toml': 'b15da83cadeb4f1a836bebb657478a254631b0df',
    'LICENSE.md': 'c8a328965105abee0d472322bb3c1936dab32d3a',
    'README.md': 'ca8703b1e330f92b803ace2d01261d4a8ed34c9a',
    'src/controllers/errors.rs': 'f4e50292e2ce9a4068773e3646b42799a345ffa3',
    'src/controllers/mod.rs': '2fb1aa92ae36024d070fbc9e01feedfcee658800',
    'src/controllers/types.rs': 'c61ad2f445a9fe35e9f0b5cc83ad1702e11a2812',
    'src/errors.rs': 'b75a8f5335dda15f680653f683493e6e5067f898',
    'src/lib.rs': '073902fd9d3c48aef7d5a1db48e3fb70b5e34562',
    'examples/change_device_vol.rs': '49bb3eac9039ecaa4a2d40db99951bda7bbb1f80',
}
HELPERS = {'libs/pulsectl/VIPER.md', 'libs/pulsectl/tests/pulse_smoke.rs', 'tools/verify_pulse_vendor.py', 'tools/native/test-pulsectl.sh', 'tools/tests/test_pulse_vendor.py'}


def replace(path, old, new):
    text = path.read_text()
    assert text.count(old) == 1, (str(path), old)
    path.write_text(text.replace(old, new))


def prepare():
    src = ROOT / '.pulse-upstream'
    dst = ROOT / 'libs/pulsectl'
    assert not dst.exists()
    assert subprocess.check_output(['git', '-C', str(src), 'rev-parse', 'HEAD'], text=True).strip() == 'aa34dde499aa912a3abc5289cc0b547bd07dd6e2'
    for name, sha in BLOBS.items():
        data = (src / name).read_bytes()
        assert hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest() == sha, name
        p = dst / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    old_source = '''impl DeviceControl<DeviceInfo> for SourceController {
    fn get_default_device(&mut self) -> Result<DeviceInfo, ControllerError> {
        let server_info = self.get_server_info();
        match server_info {
            Ok(info) => self.get_device_by_name(info.default_sink_name.unwrap().as_ref()),
            Err(e) => Err(e),
        }
    }'''
    new_source = '''impl DeviceControl<DeviceInfo> for SourceController {
    fn get_default_device(&mut self) -> Result<DeviceInfo, ControllerError> {
        let server_info = self.get_server_info();
        match server_info {
            Ok(info) => match info.default_source_name {
                Some(name) => self.get_device_by_name(&name),
                None => Err(ControllerError::new(GetInfoError, "No default source available")),
            },
            Err(e) => Err(e),
        }
    }'''
    changes = {
        'Cargo.toml': [('libpulse-binding = "2.26"', 'libpulse-binding = "2.30.1"')],
        'src/lib.rs': [('pulse::context::flags::NOFLAGS', 'pulse::context::FlagSet::NOFLAGS')],
        'src/controllers/mod.rs': [('pulse::volume::VOLUME_NORM.0', 'Volume::NORMAL.0'), (old_source, new_source)],
    }
    for name, pairs in changes.items():
        for old, new in pairs:
            replace(dst / name, old, new)
    meta = {'repository': 'https://github.com/rustdesk-org/pulsectl', 'revision': 'aa34dde499aa912a3abc5289cc0b547bd07dd6e2', 'license': 'GPL-3.0-or-later', 'source_blobs': BLOBS, 'replacements': changes}
    (dst / 'upstream.json').write_text(json.dumps(meta, indent=2) + '\n')
    pack = (ROOT / '.migration/pulse-helpers.json.gz').read_bytes()
    assert hashlib.sha256(pack).hexdigest() == '2fb48de8239512849a452d9d9f85e562686c0fe90280ef37aa2bd32d5c383820'
    entries = json.loads(gzip.decompress(pack))
    assert len(entries) == len(HELPERS) and {x['path'] for x in entries} == HELPERS
    for entry in entries:
        p = ROOT / entry['path']
        assert not p.exists() and entry['mode'] in ('100644', '100755')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(entry['content'])
        p.chmod(int(entry['mode'], 8) & 0o777)
    note = dst / 'VIPER.md'
    text = note.read_text().replace('Only the connection flag spelling and normal-volume constant spelling change;', 'The connection flag spelling and normal-volume constant spelling change;').replace('and the three exact substitutions', 'and the four exact substitutions').replace('The volume formula, stream/device types, operations, callbacks and error behavior are not rewritten.', 'The volume formula, stream/device types, asynchronous operations and callbacks are not rewritten.')
    text += '\nThe private source-selection regression also exposed a pre-existing fork defect used by Viper\'s `get_default_pa_source`: `SourceController` queried the default sink name as though it were an input source. Its source-specific lookup now uses `default_source_name`, returning an explicit error when no default source exists. Sink selection and the rest of the controller API are unchanged. This necessary source-selection repair is recorded separately from the removed libpulse aliases; the original failing test is retained unchanged.\n'
    note.write_text(text)
    replace(ROOT / 'Cargo.toml', 'rust-pulsectl = { git = "https://github.com/rustdesk-org/pulsectl" }', 'rust-pulsectl = { path = "libs/pulsectl" }')
    old = '      - name: Verify reproducible bindings and locked dependencies\n'
    new = '      - name: Verify preserved PulseAudio fork against a private virtual device\n        run: |\n          sudo apt-get install -y pulseaudio pulseaudio-utils\n          bash tools/native/test-pulsectl.sh\n' + old
    replace(ROOT / '.github/workflows/flutter-validate.yml', old, new)
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / 'before.lock').write_bytes((ROOT / 'Cargo.lock').read_bytes())
    paths = sorted([f'libs/pulsectl/{p}' for p in BLOBS] + ['libs/pulsectl/upstream.json'] + list(HELPERS) + ['Cargo.toml', 'Cargo.lock', '.github/workflows/flutter-validate.yml'])
    (REPORT / 'export-paths.json').write_text(json.dumps(paths))


def resolve():
    with (REPORT / 'cargo-metadata.json').open('w') as out:
        subprocess.run(['cargo', 'metadata', '--format-version', '1'], stdout=out, check=True)
    subprocess.run(['cargo', 'metadata', '--locked', '--format-version', '1'], stdout=subprocess.DEVNULL, check=True)
    before = tomllib.loads((REPORT / 'before.lock').read_text())['package']
    after = tomllib.loads((ROOT / 'Cargo.lock').read_text())['package']
    key = lambda p: (p['name'], p['version'], p.get('source', ''))
    assert sorted((p for p in before if p['name'] != 'rust-pulsectl'), key=key) == sorted((p for p in after if p['name'] != 'rust-pulsectl'), key=key), 'Unexpected dependency resolution change'
    old = next(p for p in before if p['name'] == 'rust-pulsectl')
    new = next(p for p in after if p['name'] == 'rust-pulsectl')
    assert old['source'] == 'git+https://github.com/rustdesk-org/pulsectl#aa34dde499aa912a3abc5289cc0b547bd07dd6e2'
    assert new == {k: v for k, v in old.items() if k != 'source'}
    metadata = json.loads((REPORT / 'cargo-metadata.json').read_text())
    pulse = next(p for p in metadata['packages'] if p['name'] == 'rust-pulsectl')
    assert pulse['id'] in metadata['workspace_members']
    print('All other registry/Git packages unchanged; preserved local fork is a workspace member.')


def export():
    manifest = []
    for name in json.loads((REPORT / 'export-paths.json').read_text()):
        p = Path(name)
        assert p.is_file() and not p.is_symlink()
        data = p.read_bytes()
        sha = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        request = urllib.request.Request('https://api.github.com/repos/Kukutx/Viper/git/blobs', data=json.dumps({'encoding': 'base64', 'content': base64.b64encode(data).decode()}).encode(), headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=60) as response:
            actual = json.load(response)['sha']
        assert actual == sha
        dest = REPORT / 'reviewed-source' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        manifest.append({'path': name, 'mode': '100755' if p.stat().st_mode & 0o111 else '100644', 'type': 'blob', 'sha': sha, 'sha256': hashlib.sha256(data).hexdigest()})
    (REPORT / 'reviewed-blobs.json').write_text(json.dumps(manifest, indent=2) + '\n')


{'prepare': prepare, 'resolve': resolve, 'export': export}[sys.argv[1]]()
