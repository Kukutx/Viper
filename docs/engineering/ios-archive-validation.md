# iOS archive validation

Reviewed on 2026-10-01. This record describes the exact candidate accepted into the task branch; later commits require their own CI results.

Candidate `2392d994f64dc5b046c1c7e54aabdbb5f81da5f3` passed [run 36787190006](https://github.com/Kukutx/Viper/actions/runs/36787190006), including Foundation and iOS job `110131310800`. The five implementation files were verified against the reviewed blob manifest from run `36787058399`. The 18 archive-specific tests also passed in an offline checkout before integration.

The old `build-rustdesk-ios` task now reuses `ios-native.yml` with read-only contents permission. It builds a Release application and a separate unsigned XCArchive with the same locked source, then verifies both applications and packages them. The original Rust static-library artifact remains available. No signing credentials are passed to the reusable workflow.

Diagnostics artifact `11131406938` has SHA-256 `c137e01d132cdad129a53708449d5618a8efd15850da5e89a9c42a640e53121e`. The downloaded report confirms Xcode 27.0, iOS SDK 27, minimum iOS 15, and Rust 1.98.1 with its LLVM 22.1.8 symbol reader. All 11 required native/FRB exports exist in both the linked applications and the original Rust archive. `ios-changes.patch` is empty. Flutter reports a 244.3 MB `Runner.xcarchive` and explicitly skips IPA export because codesigning is disabled.

Packaging rejects stale output directories, multiple archives, invalid application metadata, empty trees, special files, absolute links, dangling links and links outside the bundle. Valid relative framework links are preserved. The output includes a full source revision and a verified SHA-256 manifest.

## Remaining boundary

This is unsigned application/archive validation, not device execution, runtime FFI on iPhone, signing, installation, IPA export or App Store delivery. Existing Rust warnings and Flutter's default launch-image warning remain visible. This change does not redesign assets, change identity, permissions or runtime application code, and does not authorize production release.
