//! Native dependency contracts. Only private HKCU keys are written; services and
//! the production display/installer registry are never modified by these tests.
use super::{acl, installer_shell, msi_registry, reg_display_settings};
use std::{borrow::Cow, collections::HashMap, io, ptr};
use windows::{
    core::Interface,
    Win32::System::Com::{
        CoCreateInstance, CoInitializeEx, CoUninitialize, IPersistStream,
        CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED,
    },
    Win32::UI::Shell::{IShellLinkW, SHCreateMemStream, ShellLink},
};
use windows_service::{
    service::{ServiceAccess, ServiceControl, ServiceState, ServiceType},
    service_manager::{ServiceManager, ServiceManagerAccess},
};
use winreg::{enums::*, RegKey, RegValue};

struct PrivateKey {
    path: String,
    key: RegKey,
    removed: bool,
}

impl PrivateKey {
    fn new() -> Self {
        // A single random leaf avoids deleting shared test or application roots.
        let path = format!("Software\\ViperDependencyContract-{}", uuid::Uuid::new_v4());
        let (key, disposition) = RegKey::predef(HKEY_CURRENT_USER)
            .create_subkey_with_flags(&path, KEY_READ | KEY_WRITE)
            .expect("create private current-user test key");
        assert_eq!(disposition, REG_CREATED_NEW_KEY);
        Self { path, key, removed: false }
    }

    fn remove(mut self) {
        let current_user = RegKey::predef(HKEY_CURRENT_USER);
        drop(std::mem::replace(&mut self.key, RegKey::predef(HKEY_CURRENT_USER)));
        current_user.delete_subkey_all(&self.path).expect("remove own test key");
        self.removed = true;
        assert_eq!(current_user.open_subkey(&self.path).unwrap_err().kind(), io::ErrorKind::NotFound);
    }
}

impl Drop for PrivateKey {
    fn drop(&mut self) {
        if !self.removed {
            // On assertion failure, cleanup must not panic while unwinding.
            if let Err(error) = RegKey::predef(HKEY_CURRENT_USER).delete_subkey_all(&self.path) {
                eprintln!("private registry fixture cleanup failed: {error}");
            }
        }
    }
}

#[test]
fn registry_typed_values_and_raw_owned_data_roundtrip() {
    let fixture = PrivateKey::new();
    let text = "Viper 测试 🐍";
    let multi = vec!["first".to_owned(), "第二个".to_owned()];
    fixture.key.set_value("Text", &text).unwrap();
    fixture.key.set_value("Dword", &0xfedc_ba98_u32).unwrap();
    fixture.key.set_value("Qword", &0x1234_5678_9abc_def0_u64).unwrap();
    fixture.key.set_value("Multi", &multi).unwrap();
    let raw = RegValue { bytes: Cow::Borrowed(&[0, 128, 255, 0]), vtype: REG_BINARY };
    fixture.key.set_raw_value("Raw", &raw).unwrap();
    assert_eq!(fixture.key.get_value::<String, _>("Text").unwrap(), text);
    assert_eq!(fixture.key.get_value::<u32, _>("Dword").unwrap(), 0xfedc_ba98);
    assert_eq!(fixture.key.get_value::<u64, _>("Qword").unwrap(), 0x1234_5678_9abc_def0);
    assert_eq!(fixture.key.get_value::<Vec<String>, _>("Multi").unwrap(), multi);
    let detached: RegValue<'static> = fixture.key.get_raw_value("Raw").unwrap();
    assert_eq!(detached, raw);
    let names = fixture.key.enum_values().map(|entry| entry.unwrap().0).collect::<Vec<_>>();
    assert_eq!(names.len(), 5);
    assert!(names.iter().any(|name| name == "Raw"));
    assert_eq!(fixture.key.get_value::<String, _>("Missing").unwrap_err().kind(), io::ErrorKind::NotFound);
    fixture.remove();
    assert_eq!(detached.bytes.as_ref(), &[0, 128, 255, 0]);
}

#[test]
fn registry_readonly_view_handles_do_not_gain_write_access() {
    let fixture = PrivateKey::new();
    fixture.key.set_value("Version", &1_u32).unwrap();
    for view in [KEY_WOW64_32KEY, KEY_WOW64_64KEY] {
        let read_only = RegKey::predef(HKEY_CURRENT_USER)
            .open_subkey_with_flags(&fixture.path, KEY_READ | view).unwrap();
        assert_eq!(read_only.get_value::<u32, _>("Version").unwrap(), 1);
        assert_eq!(read_only.set_value("Version", &2_u32).unwrap_err().kind(), io::ErrorKind::PermissionDenied);
    }
    assert_eq!(fixture.key.get_value::<u32, _>("Version").unwrap(), 1);
    fixture.remove();
}

#[test]
fn msi_matching_preserves_case_and_installer_flag_contracts() {
    let fixture = PrivateKey::new();
    let check = || msi_registry::is_matching_entry(&fixture.key, "RustDesk", "private-fixture");
    assert!(!check().unwrap());
    fixture.key.set_value("DisplayName", &"rustdesk").unwrap();
    assert!(!check().unwrap());
    fixture.key.set_value("WindowsInstaller", &1_u32).unwrap();
    assert!(check().unwrap());
    fixture.key.set_value("DisplayName", &"OtherApp").unwrap();
    assert!(!check().unwrap());
    fixture.key.set_value("DisplayName", &"RustDesk").unwrap();
    fixture.key.set_value("WindowsInstaller", &0_u32).unwrap();
    assert!(!check().unwrap());
    fixture.key.set_value("WindowsInstaller", &"1").unwrap();
    assert!(check().is_err());
    assert!(!msi_registry::scanned_entry_matches(check()));
    fixture.key.set_value("WindowsInstaller", &1_u32).unwrap();
    fixture.key.set_value("DisplayName", &42_u32).unwrap();
    assert!(check().is_err());
    fixture.remove();
}

fn recovery() -> reg_display_settings::RegRecovery {
    serde_json::from_value(serde_json::json!({
        "path": "unused-private-key-only", "key": "Recent",
        "old": [[0, 128, 255, 0], 3], "new": [[1, 2, 3, 4], 3]
    })).unwrap()
}

#[test]
fn display_recovery_records_keep_the_existing_serialized_format() {
    let before = HashMap::from([("DISPLAY".to_owned(), HashMap::from([("Recent".to_owned(),
        RegValue { bytes: Cow::Borrowed(&[0, 128, 255, 0]), vtype: REG_BINARY })]))]);
    let after = HashMap::from([("DISPLAY".to_owned(), HashMap::from([("Recent".to_owned(),
        RegValue { bytes: Cow::Owned(vec![1, 2, 3, 4]), vtype: REG_BINARY })]))]);
    let change = reg_display_settings::diff_recent_connectivity(before, after).unwrap();
    let json = serde_json::to_value(change).unwrap();
    assert_eq!(json, serde_json::json!({
        "path": "SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers\\Connectivity\\DISPLAY",
        "key": "Recent", "old": [[0, 128, 255, 0], 3], "new": [[1, 2, 3, 4], 3]
    }));
    let decoded: reg_display_settings::RegRecovery = serde_json::from_value(json.clone()).unwrap();
    assert_eq!(serde_json::to_value(decoded).unwrap(), json);
}

#[test]
fn display_recovery_restores_only_the_expected_value_unless_forced() {
    let fixture = PrivateKey::new();
    let set = |bytes: &[u8]| fixture.key.set_raw_value("Recent", &RegValue {
        bytes: Cow::Borrowed(bytes), vtype: REG_BINARY,
    }).unwrap();
    set(&[1, 2, 3, 4]);
    reg_display_settings::restore_connectivity_value(&fixture.key, recovery(), false).unwrap();
    assert_eq!(fixture.key.get_raw_value("Recent").unwrap().bytes.as_ref(), &[0, 128, 255, 0]);
    set(&[9, 8, 7, 6]);
    reg_display_settings::restore_connectivity_value(&fixture.key, recovery(), false).unwrap();
    assert_eq!(fixture.key.get_raw_value("Recent").unwrap().bytes.as_ref(), &[9, 8, 7, 6]);
    reg_display_settings::restore_connectivity_value(&fixture.key, recovery(), true).unwrap();
    assert_eq!(fixture.key.get_raw_value("Recent").unwrap().bytes.as_ref(), &[0, 128, 255, 0]);
    fixture.key.delete_value("Recent").unwrap();
    assert!(reg_display_settings::restore_connectivity_value(&fixture.key, recovery(), false).is_err());
    fixture.remove();
}

#[test]
fn current_process_identity_and_image_use_the_migrated_windows_api() {
    let pid = std::process::id();
    let sid = acl::current_process_user_sid_string().unwrap();
    assert!(sid.starts_with("S-1-"));
    assert_eq!(super::is_process_running_as_system(pid).unwrap(), sid == "S-1-5-18");
    let queried = super::get_process_executable_path(pid).unwrap();
    assert_eq!(std::fs::canonicalize(queried).unwrap(), std::fs::canonicalize(std::env::current_exe().unwrap()).unwrap());
    assert!(super::is_process_running_as_system(u32::MAX).is_err());
    assert!(super::get_process_executable_path(u32::MAX).is_err());
}

#[test]
fn service_controls_keep_their_win32_wire_values() {
    for (raw, control) in [(1, ServiceControl::Stop), (4, ServiceControl::Interrogate),
                           (5, ServiceControl::Shutdown), (15, ServiceControl::Preshutdown)] {
        // These four notifications have no payload and ignore event_data.
        let decoded = unsafe { ServiceControl::from_raw(raw, 0, ptr::null_mut()) }.unwrap();
        assert_eq!(decoded, control);
        assert_eq!(decoded.raw_service_control_type(), raw);
    }
    assert!(unsafe { ServiceControl::from_raw(u32::MAX, 0, ptr::null_mut()) }.is_err());
}

#[test]
fn service_manager_queries_are_readonly_and_preserve_native_errors() {
    let manager = ServiceManager::local_computer(None::<&str>, ServiceManagerAccess::CONNECT).unwrap();
    // EventLog exists on both supported Windows runners; never start or stop it.
    let event_log = manager.open_service("EventLog", ServiceAccess::QUERY_STATUS).unwrap();
    let status = event_log.query_status().unwrap();
    assert!(status.service_type.intersects(ServiceType::OWN_PROCESS | ServiceType::SHARE_PROCESS));
    if status.current_state == ServiceState::Running {
        assert!(status.process_id.is_some_and(|pid| pid != 0));
    }
    let missing = format!("ViperDependencyContract-{}", uuid::Uuid::new_v4());
    match manager.open_service(&missing, ServiceAccess::QUERY_STATUS) {
        Err(windows_service::Error::Winapi(error)) => assert_eq!(error.raw_os_error(), Some(1060)),
        _ => panic!("missing service must preserve ERROR_SERVICE_DOES_NOT_EXIST"),
    }
    assert!(matches!(manager.open_service("invalid\0name", ServiceAccess::QUERY_STATUS),
                     Err(windows_service::Error::ArgumentHasNulByte(_))));
}

#[test]
fn installer_shortcut_roundtrips_in_memory_without_installing() {
    struct ComGuard;
    impl Drop for ComGuard {
        fn drop(&mut self) { unsafe { CoUninitialize() }; }
    }
    unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok() }.unwrap();
    let _com = ComGuard;
    let system = installer_shell::get_system_executable("cmd.exe").unwrap();
    assert!(system.is_absolute() && system.is_file());
    let system = system.to_str().unwrap();
    let arguments = "/c echo Viper 测试";
    let bytes = installer_shell::shortcut_bytes(system, Some(arguments), Some(system)).unwrap();
    let link: IShellLinkW = unsafe { CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER) }.unwrap();
    let stream = unsafe { SHCreateMemStream(Some(&bytes)) }.unwrap();
    let persist: IPersistStream = link.cast().unwrap();
    unsafe { persist.Load(&stream) }.unwrap();
    let mut buffer = vec![0_u16; 32768];
    unsafe { link.GetArguments(&mut buffer) }.unwrap();
    let len = buffer.iter().position(|value| *value == 0).unwrap();
    assert_eq!(String::from_utf16(&buffer[..len]).unwrap(), arguments);
    let mut icon_index = -1;
    unsafe { link.GetIconLocation(&mut buffer, &mut icon_index) }.unwrap();
    let len = buffer.iter().position(|value| *value == 0).unwrap();
    assert_eq!(String::from_utf16(&buffer[..len]).unwrap(), system);
    assert_eq!(icon_index, 0);
}
