use libpulse_binding::{context::FlagSet, volume::{ChannelVolumes, Volume}};
use pulsectl::controllers::{DeviceControl, SinkController, SourceController};

fn require_private_server() {
    assert_eq!(std::env::var("VIPER_PULSE_TEST").as_deref(), Ok("1"),
        "Run tools/native/test-pulsectl.sh; never use a user's audio server");
    assert!(std::env::var("PULSE_SERVER").unwrap().starts_with("unix:"));
}

#[test]
fn migrated_constants_preserve_the_native_values() {
    assert_eq!(FlagSet::NOFLAGS.bits(), 0);
    assert_eq!(Volume::NORMAL.0, 65_536);
}

#[test]
fn private_sources_preserve_listing_default_selection_and_errors() {
    require_private_server();
    let mut source = SourceController::create().unwrap();
    let devices = source.list_devices().unwrap();
    assert!(devices.iter().any(|d| d.name.as_deref() == Some("viper_ci.monitor")));
    assert!(source.set_default_device("viper_ci.monitor").unwrap());
    assert_eq!(source.get_default_device().unwrap().name.as_deref(), Some("viper_ci.monitor"));
    assert!(source.get_device_by_name("viper_missing_source").is_err());
}

#[test]
fn private_sink_volume_roundtrip_preserves_percent_semantics() {
    require_private_server();
    let mut sink = SinkController::create().unwrap();
    assert!(sink.list_devices().unwrap().iter().any(|d| d.name.as_deref() == Some("viper_ci")));
    assert!(sink.set_default_device("viper_ci").unwrap());
    let device = sink.get_default_device().unwrap();
    assert_eq!(device.name.as_deref(), Some("viper_ci"));
    let mut volumes = ChannelVolumes::default();
    volumes.set(2, Volume(Volume::NORMAL.0 / 2));
    sink.set_device_volume_by_name("viper_ci", &volumes);
    let actual = sink.get_device_by_name("viper_ci").unwrap();
    assert!(actual.volume.get().iter().all(|v| v.0 == 32_768));
    sink.increase_device_volume_by_percent(device.index, 0.25);
    let actual = sink.get_device_by_index(device.index).unwrap();
    assert!(actual.volume.get().iter().all(|v| v.0 == 49_152));
    sink.decrease_device_volume_by_percent(device.index, 0.25);
    let actual = sink.get_device_by_index(device.index).unwrap();
    assert!(actual.volume.get().iter().all(|v| v.0 == 32_768));
    sink.set_device_volume_by_index(device.index, &volumes);
    assert!(sink.get_device_by_name("viper_missing_sink").is_err());
}
