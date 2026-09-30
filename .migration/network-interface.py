"""One-time reviewed migration from default-net to its maintained successor."""
from pathlib import Path
import re

p=Path('Cargo.toml'); text=p.read_text()
old='default-net = "0.14"'
assert text.count(old)==1
p.write_text(text.replace(old,'netdev = { version = "=0.46.3", default-features = false }'))
p=Path('src/lan.rs'); text=p.read_text()
assert text.count('default_net::get_interfaces()')==4
text=text.replace('default_net::get_interfaces()', 'netdev::get_interfaces()')
text=text.replace('ipv4.addr.clone()', 'ipv4.addr()')
text=re.sub(r'\bipv4\.addr\b(?!\s*\()', 'ipv4.addr()', text)
text=text.replace('x.addr == *local_ipv4', 'x.addr() == *local_ipv4')
text=text.replace('x.addr == *local_ipv6', 'x.addr() == *local_ipv6')
text=text.replace('    // TODO: maybe we should use a better way to get ipv4 addresses.\n    // But currently, it\'s ok to use `[Ipv4Addr::UNSPECIFIED]` for discovery.\n    // `netdev::get_interfaces()` causes undefined symbols error when `flutter build` on iOS simulator x86_64\n', '    // Preserve OS-selected broadcast routing on iOS; other platforms enumerate addresses.\n')
p.write_text(text)
p=Path('flutter/ios/Runner.xcodeproj/project.pbxproj');text=p.read_text()
anchor='\t\t\t\t\t"\\"SystemConfiguration\\"",\n'
assert text.count(anchor)==3
p.write_text(text.replace(anchor,anchor+'\t\t\t\t\t"-framework",\n\t\t\t\t\t"\\"Network\\"",\n'))
