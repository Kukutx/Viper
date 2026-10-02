from pathlib import Path
import hashlib

BASELINES = {
    'Cargo.toml': 'ce48e11bedf96cd6bebb874bcb033ecce2bf2b95',
    'src/platform/windows.rs': 'a3c3d68f0508a86ff4f0d47e414a926288bd59ab',
    'tools/windows_native.py': '5d4918f40d151569b25c5607ffd8642d6cb997c4',
}

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected one occurrence: {old[:80]!r}')
    return text.replace(old, new, 1)

for name, expected in BASELINES.items():
    path = Path(name)
    data = path.read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if actual != expected:
        raise ValueError(f'Baseline changed: {name}: {actual}')
    text = data.decode('utf-8')
    if name == 'Cargo.toml':
        text = replace_once(text, 'winreg = "0.11"', 'winreg = "0.56.0"')
        text = replace_once(text, 'windows-service = "0.6"', 'windows-service = "0.8.1"')
    elif name == 'src/platform/windows.rs':
        text = replace_once(text, '        winreg::HKEY_CURRENT_USER,\n', '')
        text = replace_once(text, 'pub fn read_reg_connectivity() -> ResultType<HashMap<String, HashMap<String, RegValue>>>',
                            "pub fn read_reg_connectivity() -> ResultType<HashMap<String, HashMap<String, RegValue<'static>>>>")
        for which in ('map1', 'map2'):
            text = replace_once(text, f'{which}: HashMap<String, HashMap<String, RegValue>>,',
                                f"{which}: HashMap<String, HashMap<String, RegValue<'_>>>,")
        text = replace_once(text, 'old: (value1.bytes.clone(), value1.vtype.clone() as isize)',
                            'old: (value1.bytes.to_vec(), value1.vtype as isize)')
        text = replace_once(text, 'new: (value2.bytes.clone(), value2.vtype.clone() as isize)',
                            'new: (value2.bytes.to_vec(), value2.vtype as isize)')
        text = replace_once(text, '''        let reg_item = hklm.open_subkey_with_flags(&reg_recovery.path, KEY_READ | KEY_WRITE)?;
        if !force {''', '''        let reg_item = hklm.open_subkey_with_flags(&reg_recovery.path, KEY_READ | KEY_WRITE)?;
        restore_reg_value(&reg_item, &reg_recovery, force)
    }

    fn restore_reg_value(
        reg_item: &winreg::RegKey,
        reg_recovery: &RegRecovery,
        force: bool,
    ) -> ResultType<()> {
        if !force {''')
        text = replace_once(text, 'bytes: reg_recovery.new.0,', 'bytes: reg_recovery.new.0.as_slice().into(),')
        text = replace_once(text, 'bytes: reg_recovery.old.0,', 'bytes: reg_recovery.old.0.as_slice().into(),')
        text = replace_once(text, '''    #[inline]
    fn isize_to_reg_type(i: isize) -> RegType {''', '''    #[cfg(test)]
    mod dependency_tests;

    #[inline]
    fn isize_to_reg_type(i: isize) -> RegType {''')
    else:
        anchor = "    command(['cargo', 'test', '--locked', '--release', '--lib', '--features', 'flutter', 'audio', '--', '--test-threads=1'], 'windows-audio-tests.log')\n"
        text = replace_once(text, anchor, anchor + "    command(['cargo', 'test', '--locked', '--release', '--lib', '--features', 'flutter', 'windows_dependency', '--', '--test-threads=1'], 'windows-dependency-tests.log')\n")
    path.write_bytes(text.encode('utf-8'))
