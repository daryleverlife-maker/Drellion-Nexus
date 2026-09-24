param(
    [string]$Version = "v1.0.0",
    [string]$ReleaseDir = "."
)

$ErrorActionPreference = "Stop"

$setup = Join-Path $ReleaseDir "Drellion-Nexus-Setup.exe"
$portable = Join-Path $ReleaseDir "Drellion-Nexus-Portable.zip"
$soundbank = Join-Path $ReleaseDir "Drellion-Soundbank-Pack.zip"
$checksums = Join-Path $ReleaseDir "checksums.sha256"

$required = @($setup, $portable, $soundbank)
foreach ($file in $required) {
    if (!(Test-Path $file)) {
        throw "Missing required release file: $file"
    }
}

if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required. Install it from https://cli.github.com/ then run: gh auth login"
}

gh auth status | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated. Run: gh auth login"
}

$hashLines = foreach ($file in $required) {
    $hash = (Get-FileHash $file -Algorithm SHA256).Hash.ToLower()
    "$hash  $(Split-Path $file -Leaf)"
}
$hashLines | Set-Content $checksums -Encoding ascii

$notesPath = Join-Path $ReleaseDir "release-notes-v1.0.0.md"
@("# Drellion Nexus 1.0", "", "Primary downloads:", "", "- Drellion-Nexus-Setup.exe", "- Drellion-Nexus-Portable.zip", "- Drellion-Soundbank-Pack.zip", "", "The soundbank is optional but recommended for the full offline library experience.") | Set-Content $notesPath -Encoding utf8

gh release view $Version --repo daryleverlife-maker/Drellion-Nexus *> $null
if ($LASTEXITCODE -eq 0) {
    gh release upload $Version $setup $portable $soundbank $checksums --repo daryleverlife-maker/Drellion-Nexus --clobber
} else {
    gh release create $Version $setup $portable $soundbank $checksums --repo daryleverlife-maker/Drellion-Nexus --title "Drellion Nexus 1.0" --notes-file $notesPath
}

Write-Host ""
Write-Host "Published Drellion Nexus $Version"
Write-Host "https://github.com/daryleverlife-maker/Drellion-Nexus/releases/tag/$Version"