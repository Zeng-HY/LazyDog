$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $projectRoot "dist"
$appRoot = Join-Path $distRoot "VoiceAnywhere"
$archive = Join-Path $distRoot "VoiceAnywhere-windows-x64.zip"

Set-Location -LiteralPath $projectRoot
uv run pyinstaller --noconfirm --clean --windowed --name VoiceAnywhere --collect-all sounddevice --add-data "shared\auto_default_policy_v1.txt;shared" --runtime-hook scripts\pyi_rth_voiceanywhere.py src\voiceanywhere\__main__.py

if (-not (Test-Path (Join-Path $appRoot "VoiceAnywhere.exe"))) {
    throw "PyInstaller 未生成发布程序。"
}

# PyInstaller can discover ICU 78 from an unrelated Poppler directory on this PC.
# Qt6Core imports Windows' built-in icuuc.dll interface; a bundled ICU 78 copy has
# incompatible, version-suffixed exports and prevents QtCore.pyd from loading.
$internalRoot = (Resolve-Path (Join-Path $appRoot "_internal")).Path
foreach ($fileName in @("icuuc.dll", "icudt78.dll")) {
    $candidate = Join-Path $internalRoot $fileName
    if (Test-Path $candidate) {
        $resolved = (Resolve-Path $candidate).Path
        if (-not $resolved.StartsWith($internalRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "拒绝删除发布目录外的文件：$resolved"
        }
        Remove-Item -LiteralPath $resolved -Force
    }
}

if (Test-Path $archive) {
    Remove-Item -LiteralPath $archive -Force
}
Compress-Archive -LiteralPath $appRoot -DestinationPath $archive -CompressionLevel Optimal
Write-Host "发布目录：$appRoot"
Write-Host "可分发压缩包：$archive"
