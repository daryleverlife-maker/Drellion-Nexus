param(
    [Parameter(Mandatory=$true)]
    [string]$Part1,
    [string]$Output = "Drellion-Soundbank-Pack.zip"
)

$ErrorActionPreference = "Stop"

$first = Resolve-Path $Part1
$dir = Split-Path $first -Parent
$name = Split-Path $first -Leaf

if ($name -notmatch "\.part1\.rar$") {
    throw "Part1 must be the first file of a multipart RAR set (for example soundbank.part1.rar)."
}

$prefix = $name -replace "\.part1\.rar$", ""
$parts = 1..4 | ForEach-Object { Join-Path $dir "$prefix.part$_.rar" }
foreach ($part in $parts) {
    if (!(Test-Path $part)) { throw "Missing multipart archive: $part" }
}

$sevenZip = @(
    "$env:ProgramFiles\7-Zip\7z.exe",
    "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $sevenZip) {
    $command = Get-Command 7z.exe -ErrorAction SilentlyContinue
    if ($command) { $sevenZip = $command.Source }
}
if (-not $sevenZip) {
    throw "7-Zip is required to unpack the multipart soundbank archive."
}

$work = Join-Path $env:TEMP ("drellion-soundbank-" + [guid]::NewGuid().ToString("N"))
$extract = Join-Path $work "Soundbank"
New-Item -ItemType Directory -Path $extract -Force | Out-Null

try {
    & $sevenZip x $first "-o$extract" -y
    if ($LASTEXITCODE -ne 0) { throw "7-Zip extraction failed with exit code $LASTEXITCODE." }

    $audio = Get-ChildItem $extract -File -Recurse | Where-Object {
        $_.Extension.ToLowerInvariant() -in @(".wav",".flac",".mp3",".m4a",".aac",".ogg",".opus",".aiff",".aif",".wma")
    }
    if (-not $audio) { throw "No supported audio files were found after extraction." }

    $manifest = [ordered]@{
        product = "Drellion Nexus"
        package = "Drellion Soundbank Pack"
        format_version = 1
        audio_files = $audio.Count
        total_audio_bytes = ($audio | Measure-Object Length -Sum).Sum
        generated_utc = [DateTime]::UtcNow.ToString("o")
    }
    $manifest | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $extract "drellion-soundbank.json") -Encoding UTF8

    $target = Join-Path (Get-Location) $Output
    if (Test-Path $target) { Remove-Item $target -Force }
    Compress-Archive -Path (Join-Path $extract "*") -DestinationPath $target -CompressionLevel Optimal

    $hash = (Get-FileHash $target -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "Created: $target"
    Write-Host "Audio files: $($audio.Count)"
    Write-Host "SHA256: $hash"
}
finally {
    if (Test-Path $work) { Remove-Item $work -Recurse -Force }
}
