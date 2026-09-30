$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = (& git rev-parse --show-toplevel).Trim()
Set-Location $root
if (-not $IsWindows -or [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64') {
    throw 'This validation profile requires a Windows x64 host.'
}
$config = Get-Content configs/toolchain.json -Raw | ConvertFrom-Json
$spec = Get-Content configs/windows-toolchain.json -Raw | ConvertFrom-Json
New-Item tools/.reports -ItemType Directory -Force | Out-Null
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vs = @(& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json | ConvertFrom-Json)
if ($vs.Count -ne 1 -or $vs[0].installationVersion -ne $spec.visual_studio) {
    throw "Expected Visual Studio $($spec.visual_studio); found $($vs.installationVersion)"
}
$vs | ConvertTo-Json -Depth 8 | Set-Content tools/.reports/windows-visual-studio.json -Encoding utf8
& python -m pip install "cmake==$($config.cmake)"
$llvm = Join-Path $env:RUNNER_TEMP 'viper-llvm'
$archive = Join-Path $env:RUNNER_TEMP 'viper-llvm.tar.xz'
Invoke-WebRequest $spec.llvm_url -OutFile $archive
if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $spec.llvm_sha256) {
    throw 'LLVM archive checksum mismatch'
}
New-Item $llvm -ItemType Directory -Force | Out-Null
& tar -xf $archive -C $llvm --strip-components=1
$env:LIBCLANG_PATH = Join-Path $llvm 'bin'
$env:PATH = "$env:LIBCLANG_PATH;$env:PATH"
$version = (& "$llvm/bin/clang.exe" --version | Out-String)
if ($version -notmatch "clang version $([regex]::Escape($spec.llvm))\b") { throw $version }
$version | Set-Content tools/.reports/windows-clang.txt -Encoding utf8
& rustup show
$env:VCPKG_ROOT = Join-Path $env:RUNNER_TEMP 'viper-vcpkg-windows'
$env:VCPKG_DEFAULT_BINARY_CACHE = Join-Path $env:USERPROFILE '.cache/viper-vcpkg-windows'
New-Item $env:VCPKG_DEFAULT_BINARY_CACHE -ItemType Directory -Force | Out-Null
if (-not (Test-Path "$env:VCPKG_ROOT/.git")) {
    & git init -q $env:VCPKG_ROOT
    & git -C $env:VCPKG_ROOT remote add origin https://github.com/microsoft/vcpkg.git
}
if ((& git -C $env:VCPKG_ROOT remote get-url origin).Trim() -ne 'https://github.com/microsoft/vcpkg.git') { throw 'Unexpected vcpkg remote' }
& git -C $env:VCPKG_ROOT fetch -q --depth 1 origin $config.vcpkg.revision
& git -C $env:VCPKG_ROOT checkout -q --detach FETCH_HEAD
if ((& git -C $env:VCPKG_ROOT rev-parse HEAD).Trim() -ne $config.vcpkg.revision) { throw 'vcpkg revision mismatch' }
& "$env:VCPKG_ROOT/bootstrap-vcpkg.bat" -disableMetrics *> tools/.reports/windows-vcpkg.log
& "$env:VCPKG_ROOT/vcpkg.exe" install --classic --triplet=x64-windows-static libyuv libvpx opus aom "--overlay-ports=$root/res/vcpkg" *>> tools/.reports/windows-vcpkg.log
foreach ($name in @('yuv','vpx','opus','aom')) {
    if (-not (Test-Path "$env:VCPKG_ROOT/installed/x64-windows-static/lib/$name.lib")) { throw "Missing $name library" }
}
if ($env:GITHUB_ENV) {
    "VCPKG_ROOT=$env:VCPKG_ROOT" | Out-File $env:GITHUB_ENV -Encoding utf8 -Append
    "LIBCLANG_PATH=$env:LIBCLANG_PATH" | Out-File $env:GITHUB_ENV -Encoding utf8 -Append
    $env:LIBCLANG_PATH | Out-File $env:GITHUB_PATH -Encoding utf8 -Append
}
