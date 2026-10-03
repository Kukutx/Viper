use super::{diff_recent_connectivity, isize_to_reg_type, restore_reg_value, RegRecovery};
use std::{collections::HashMap, io};
use winreg::{enums::*, RegKey, RegValue};
use windows_service::service::{ServiceControlAccept, ServiceState, ServiceType};

// Never use HKLM, the graphics-driver hive, or the service control manager in tests.
struct PrivateKey {
    path: String,
    key: Option<RegKey>,
}

impl PrivateKey {
    fn new() -> io::Result<Self> {
        let path = format!("Software\\ViperDependencyTest-{}", uuid::Uuid::new_v4());
        let (key, disposition) =
            RegKey::predef(HKEY_CURRENT_USER).create_subkey_with_flags(&path, KEY_READ | KEY_WRITE)?;
        assert_eq!(disposition, REG_CREATED_NEW_KEY);
        Ok(Self { path, key: Some(key) })
    }

    fn key(&self) -> &RegKey {
        self.key.as_ref().unwrap()
    }

    fn remove(mut self) -> io::Result<()> {
        drop(self.key.take());
        RegKey::predef(HKEY_CURRENT_USER).delete_subkey_all(&self.path)?;
        self.path.clear();
        Ok(())
    }
}

impl Drop for PrivateKey {
    fn drop(&mut self) {
        drop(self.key.take());
        if !self.path.is_empty() {
            if let Err(error) = RegKey::predef(HKEY_CURRENT_USER).delete_subkey_all(&self.path) {
                eprintln!("Failed to clean isolated registry test key {}: {error}", self.path);
            }
        }
    }
}

fn raw(bytes: &[u8], vtype: RegType) -> RegValue<'_> {
    RegValue { bytes: bytes.into(), vtype }
}

fn recovery() -> RegRecovery {
    RegRecovery {
        path: "not-used-by-private-key-tests".into(),
        key: "Recent".into(),
        old: (vec![1, 2, 3], REG_BINARY as isize),
        new: (vec![4, 5, 6], REG_BINARY as isize),
    }
}

#[test]
fn windows_dependency_registry_owned_values_survive_key_close() -> io::Result<()> {
    let fixture = PrivateKey::new()?;
    fixture.key().set_raw_value("Raw", &raw(&[0, 255, 1, 128], REG_BINARY))?;
    fixture.key().set_value("Text", &"路径\\RustDesk 🦀")?;
    fixture.key().set_value("Number", &0xfedc_ba98u32)?;
    let values = fixture.key().enum_values().collect::<io::Result<HashMap<_, _>>>()?;
    assert_eq!(fixture.key().get_value::<String, _>("Text")?, "路径\\RustDesk 🦀");
    assert_eq!(fixture.key().get_value::<u32, _>("Number")?, 0xfedc_ba98);
    fixture.remove()?;
    assert_eq!(values["Raw"], raw(&[0, 255, 1, 128], REG_BINARY));
    assert_eq!(values["Number"].bytes.as_ref(), &0xfedc_ba98u32.to_le_bytes());
    Ok(())
}

#[test]
fn windows_dependency_recovery_json_keeps_existing_schema() {
    let original = r#"{"path":"test","key":"Recent","old":[[1,2,3],3],"new":[[4,5,6],3]}"#;
    let value: RegRecovery = serde_json::from_str(original).unwrap();
    assert_eq!(serde_json::to_value(&value).unwrap(), serde_json::from_str::<serde_json::Value>(original).unwrap());
    assert_eq!(value.old, (vec![1, 2, 3], 3));
    assert_eq!(value.new, (vec![4, 5, 6], 3));
}

#[test]
fn windows_dependency_diff_copies_borrowed_snapshots() {
    let before = [1, 2, 3];
    let after = [4, 5, 6];
    fn snapshot(bytes: &[u8]) -> HashMap<String, HashMap<String, RegValue<'_>>> {
        HashMap::from([("TestDisplay".into(), HashMap::from([("Recent".into(), raw(bytes, REG_BINARY))]))])
    }
    let difference = diff_recent_connectivity(snapshot(&before), snapshot(&after)).unwrap();
    assert_eq!(difference.old, (before.to_vec(), REG_BINARY as isize));
    assert_eq!(difference.new, (after.to_vec(), REG_BINARY as isize));
    assert_eq!(difference.key, "Recent");
    assert!(difference.path.ends_with("\\Connectivity\\TestDisplay"));
    assert!(diff_recent_connectivity(snapshot(&before), snapshot(&before)).is_none());
    assert!(diff_recent_connectivity(HashMap::new(), snapshot(&after)).is_none());
}

#[test]
fn windows_dependency_recovery_only_reverts_matching_value() {
    let fixture = PrivateKey::new().unwrap();
    let recovery = recovery();
    fixture.key().set_raw_value("Recent", &raw(&[4, 5, 6], REG_BINARY)).unwrap();
    restore_reg_value(fixture.key(), &recovery, false).unwrap();
    assert_eq!(fixture.key().get_raw_value("Recent").unwrap(), raw(&[1, 2, 3], REG_BINARY));
    fixture.remove().unwrap();
}

#[test]
fn windows_dependency_recovery_preserves_intervening_changes() {
    let fixture = PrivateKey::new().unwrap();
    let recovery = recovery();
    for (bytes, kind) in [(&[7, 8, 9][..], REG_BINARY), (&[4, 5, 6][..], REG_NONE)] {
        fixture.key().set_raw_value("Recent", &raw(bytes, kind.clone())).unwrap();
        restore_reg_value(fixture.key(), &recovery, false).unwrap();
        assert_eq!(fixture.key().get_raw_value("Recent").unwrap(), raw(bytes, kind));
    }
    fixture.remove().unwrap();
}

#[test]
fn windows_dependency_recovery_force_and_missing_value() {
    let fixture = PrivateKey::new().unwrap();
    let recovery = recovery();
    assert!(restore_reg_value(fixture.key(), &recovery, false).is_err());
    restore_reg_value(fixture.key(), &recovery, true).unwrap();
    assert_eq!(fixture.key().get_raw_value("Recent").unwrap(), raw(&[1, 2, 3], REG_BINARY));
    fixture.key().set_raw_value("Recent", &raw(&[7, 8, 9], REG_BINARY)).unwrap();
    restore_reg_value(fixture.key(), &recovery, true).unwrap();
    assert_eq!(fixture.key().get_raw_value("Recent").unwrap(), raw(&[1, 2, 3], REG_BINARY));
    fixture.remove().unwrap();
}

#[test]
fn windows_dependency_msi_metadata_keeps_type_and_identity_checks() {
    let fixture = PrivateKey::new().unwrap();
    let matches = || super::super::msi_registry::is_matching_entry(fixture.key(), "RustDesk", "private-fixture");
    assert!(!matches().unwrap());
    fixture.key().set_value("WindowsInstaller", &1u32).unwrap();
    fixture.key().set_value("DisplayName", &"rUsTdEsK").unwrap();
    assert!(matches().unwrap());
    fixture.key().set_value("DisplayName", &"OtherApp").unwrap();
    assert!(!matches().unwrap());
    fixture.key().set_value("WindowsInstaller", &"1").unwrap();
    assert!(matches().is_err());
    fixture.key().set_raw_value("WindowsInstaller", &raw(&[1], REG_DWORD)).unwrap();
    assert!(matches().is_err());
    fixture.remove().unwrap();
}

#[test]
fn windows_dependency_registry_type_mapping_is_stable() {
    for value in 0..=11 {
        assert_eq!(isize_to_reg_type(value) as isize, value);
    }
    assert_eq!(isize_to_reg_type(-1), REG_NONE);
    assert_eq!(isize_to_reg_type(12), REG_NONE);
}

#[test]
fn windows_dependency_service_ffi_constants_remain_compatible() {
    assert_eq!(super::super::SERVICE_TYPE, ServiceType::OWN_PROCESS);
    assert_eq!(super::super::SERVICE_TYPE.bits(), 0x10);
    assert_eq!(ServiceControlAccept::STOP.bits(), 1);
    assert_eq!(ServiceControlAccept::empty().bits(), 0);
    assert_eq!(ServiceState::Running as u32, 4);
    assert_eq!(ServiceState::Stopped as u32, 1);
}
