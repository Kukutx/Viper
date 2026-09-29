# Viper managed chat dependency

Source: https://pub.dev/api/archives/dash_chat_2-0.0.21.tar.gz
Version: 0.0.21
SHA-256: 87ff33cbd1d5fe6241eb6c2044de32d64ef888f5d2ec9b4ab75a949d4b3742d3

This is the latest stable published source, with the upstream license preserved.
The RustDesk fork differed from its upstream by disabling the input toolbar bottom SafeArea;
that behavior is preserved without retaining the obsolete 0.0.18 Git dependency.
Local changes: current Dart/Flutter floor, intl ^0.20.3, bottom SafeArea false, no package publication.
No dependency_overrides are used. Run package analysis and Viper chat regression tests when updating.

Dart 3.13: removed an unreachable default in the exhaustive separator-frequency switch.
