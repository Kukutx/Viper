$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = (& git rev-parse --show-toplevel).Trim()
Set-Location $root
& python tools/prepare_flutter.py
& cargo build --locked --release --lib --features flutter *> tools/.reports/windows-cargo.log
$native = Join-Path $root 'target/release/librustdesk.dll'
if (-not (Test-Path $native)) { throw 'Missing compiled Rust DLL' }
Push-Location flutter
try {
    & flutter build windows --release --no-pub *> ../tools/.reports/windows-flutter.log
    $bundle = Join-Path $PWD 'build/windows/x64/runner/Release'
    foreach ($path in @('rustdesk.exe','librustdesk.dll','flutter_windows.dll','data/icudtl.dat','data/flutter_assets/AssetManifest.bin')) {
        if (-not (Test-Path "$bundle/$path")) { throw "Missing bundled $path" }
    }
    if ((Get-FileHash "$bundle/librustdesk.dll").Hash -ne (Get-FileHash $native).Hash) { throw 'Bundled Rust library differs from Cargo output' }
    $env:VIPER_NATIVE_LIBRARY = "$bundle/librustdesk.dll"
    & flutter test --no-pub test_native/bridge_ffi_test.dart *> ../tools/.reports/windows-ffi.log
    & git diff --exit-code -- pubspec.yaml pubspec.lock windows
    $dist = Join-Path $root 'dist/windows-x64-unsigned'
    if (Test-Path $dist) { throw 'Refusing to mix new output with an existing distribution' }
    New-Item $dist -ItemType Directory | Out-Null
    Compress-Archive -Path "$bundle/*" -DestinationPath "$dist/RustDesk-windows-x64-unsigned.zip"
    $revision = (& git rev-parse HEAD).Trim()
    & python ../tools/viper.py manifest $dist --revision $revision
    & python ../tools/viper.py verify $dist
} finally {
    Pop-Location
}
