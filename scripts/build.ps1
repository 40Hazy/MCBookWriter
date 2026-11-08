param(
    [string]$GameDir = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== BookForge tests =="
if (-not $SkipTests) {
    $python = Join-Path $root "bookforge\.venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        $python = "python"
    }
    Push-Location (Join-Path $root "bookforge")
    try {
        & $python -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw "pytest failed"
        }
    } finally {
        Pop-Location
    }
}

Write-Host "== AutoBook build =="
Push-Location (Join-Path $root "autobook")
try {
    & ".\gradlew.bat" build --no-daemon
    if ($LASTEXITCODE -ne 0) {
        throw "gradle build failed"
    }
    $version = ((Select-String -Path "gradle.properties" -Pattern '^mod_version=(.+)$').Matches[0].Groups[1].Value).Trim()
    $built = Join-Path (Get-Location) "build\libs\autobook-$version.jar"
    if (-not (Test-Path $built)) {
        throw "jar not found: $built"
    }
    $dist = Join-Path $root "dist"
    New-Item -ItemType Directory -Force -Path $dist | Out-Null
    Copy-Item $built (Join-Path $dist "autobook-$version.jar") -Force
    Write-Host "staged: dist\autobook-$version.jar"
} finally {
    Pop-Location
}

if (-not $GameDir) {
    Write-Host "done. pass -GameDir <path> to install and verify."
    exit 0
}

if (-not (Test-Path (Join-Path $GameDir "mods"))) {
    throw "not a game directory (missing mods): $GameDir"
}
$jar = Join-Path $root "dist\autobook-$version.jar"

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($jar)
try {
    $entry = $zip.GetEntry("fabric.mod.json")
    if ($null -eq $entry) {
        throw "fabric.mod.json missing in jar"
    }
    $reader = New-Object System.IO.StreamReader($entry.Open())
    try {
        $meta = $reader.ReadToEnd() | ConvertFrom-Json
    } finally {
        $reader.Dispose()
    }
    if ($meta.version -ne $version) {
        throw "jar version mismatch: $($meta.version) != $version"
    }
    Write-Host "verified jar: $($meta.id) $($meta.version)"
} finally {
    $zip.Dispose()
}

Get-ChildItem (Join-Path $GameDir "mods") -Filter "autobook-*.jar" -File -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "remove old: $($_.Name)"
    Remove-Item $_.FullName -Force
}
Copy-Item $jar (Join-Path $GameDir "mods\autobook-$version.jar") -Force

$configDir = Join-Path $GameDir "autobook"
New-Item -ItemType Directory -Force -Path (Join-Path $configDir "jobs"), (Join-Path $configDir "state") | Out-Null

$fabricApi = Get-ChildItem (Join-Path $GameDir "mods") -Filter "fabric-api-*.jar" -File -ErrorAction SilentlyContinue
if (-not $fabricApi) {
    Write-Warning "fabric-api jar not found in mods; AutoBook requires Fabric API."
}

$jobCount = (Get-ChildItem (Join-Path $configDir "jobs") -Filter "*.json" -File -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "installed: $(Join-Path $GameDir "mods\autobook-$version.jar")"
Write-Host "jobs: $jobCount"
Write-Host "next: launch the game, run /autobook plan <job>, then /autobook start <job>"
