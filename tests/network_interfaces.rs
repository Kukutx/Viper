//! Regression contracts for the default-net to netdev interface migration.
use netdev::ipnet::{Ipv4Net, Ipv6Net};

#[test]
fn ipv4_host_address_is_not_replaced_by_the_network_prefix() {
    let interface: Ipv4Net = "192.0.2.17/24".parse().unwrap();
    assert_eq!(interface.addr().to_string(), "192.0.2.17");
    assert_ne!(interface.addr(), interface.network());
}

#[test]
fn ipv6_host_address_is_preserved_for_mac_lookup() {
    let interface: Ipv6Net = "2001:db8::1234/64".parse().unwrap();
    assert_eq!(interface.addr().to_string(), "2001:db8::1234");
    assert_ne!(interface.addr(), interface.network());
}

#[test]
fn actual_interface_enumeration_preserves_loopback_and_mac_text() {
    let interfaces = netdev::get_interfaces();
    assert!(interfaces.iter().any(|interface| {
        interface.ipv4.iter().any(|ip| ip.addr().is_loopback())
            || interface.ipv6.iter().any(|ip| ip.addr().is_loopback())
    }));
    for mac in interfaces.iter().filter_map(|interface| interface.mac_addr.as_ref()) {
        let text = mac.address();
        let octets: Vec<_> = text.split(':').collect();
        assert_eq!(octets.len(), 6);
        assert!(octets.iter().all(|octet| octet.len() == 2 && u8::from_str_radix(octet, 16).is_ok()));
    }
}
