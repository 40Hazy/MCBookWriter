param(
    # Before release, only build 1.21.8 by default; pass -Versions for other targets.
    [string[]]$Versions = @("1.21.8"),
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$autobook = Join-Path $root "autobook"
$propertiesPath = Join-Path $autobook "gradle.properties"
$dist = Join-Path $root "dist"

# Fabric API version for each supported Minecraft version.
# loaderMin: declared fabricloader dependency floor in fabric.mod.json (matches the Fabric API floor).
# modmenu: Mod Menu compile-only version; empty means no Mod Menu entrypoint for that target.
$fabricApi = @{
    "26.2" = @{ api = "0.161.0+26.2"; loader = "0.20.1"; loaderMin = "0.18.4"; java = 25; unobfuscated = $true; modmenu = "" }
    "26.1.2" = @{ api = "0.155.3+26.1.2"; loader = "0.20.1"; loaderMin = "0.18.4"; java = 25; unobfuscated = $true; modmenu = "" }
    "26.1.1" = @{ api = "0.155.3+26.1.2"; loader = "0.20.1"; loaderMin = "0.18.4"; java = 25; unobfuscated = $true; modmenu = "" }
    "26.1" = @{ api = "0.155.3+26.1.2"; loader = "0.20.1"; loaderMin = "0.18.4"; java = 25; unobfuscated = $true; modmenu = "" }
    "1.21.11" = @{ api = "0.141.6+1.21.11"; loader = "0.20.1"; loaderMin = "0.17.3"; java = 21; modmenu = "17.0.1" }
    "1.21.8" = @{ api = "0.136.1+1.21.8"; loader = "0.16.14"; loaderMin = "0.16.13"; java = 21; modmenu = "" }
    "1.21.7" = @{ api = "0.129.0+1.21.7"; loader = "0.16.14"; loaderMin = "0.16.13"; java = 21; modmenu = "" }
    "1.21.6" = @{ api = "0.128.2+1.21.6"; loader = "0.16.14"; loaderMin = "0.16.13"; java = 21; modmenu = "15.0.2" }
    "1.21.5" = @{ api = "0.128.2+1.21.5"; loader = "0.16.14"; loaderMin = "0.16.10"; java = 21; modmenu = "14.0.2" }
}

$original = [System.IO.File]::ReadAllText($propertiesPath)
$properties26 = Join-Path $root "autobook-26\gradle.properties"
$original26 = [System.IO.File]::ReadAllText($properties26)
$version = [regex]::Match($original, "(?m)^mod_version=(.+)$").Groups[1].Value.Trim()
New-Item -ItemType Directory -Force -Path $dist | Out-Null

function Write-Properties([string]$text) {
    [System.IO.File]::WriteAllText(
        $propertiesPath,
        $text,
        [System.Text.UTF8Encoding]::new($false)
    )
}

try {
    foreach ($mc in $Versions) {
        if (-not $fabricApi.ContainsKey($mc)) {
            throw "Unsupported target version: $mc (available: $($fabricApi.Keys -join ', '))"
        }
        $spec = $fabricApi[$mc]
        Write-Host "== AutoBook build for Minecraft $mc =="

        if ($spec.unobfuscated) {
            $project26 = Join-Path $root "autobook-26"
            $text26 = $original26 -replace "(?m)^mod_version=(.+)$", "mod_version=$version"
            $text26 = $text26 -replace "(?m)^minecraft_version=(.+)$", "minecraft_version=$mc"
            $text26 = $text26 -replace "(?m)^fabric_version=(.+)$", "fabric_version=$($spec.api)"
            $text26 = $text26 -replace "(?m)^loader_version=(.+)$", "loader_version=$($spec.loader)"
            $text26 = $text26 -replace "(?m)^loader_min_version=(.+)$", "loader_min_version=$($spec.loaderMin)"
            $text26 = $text26 -replace "(?m)^java_release=(.+)$", "java_release=$($spec.java)"
            $text26 = $text26 -replace "(?m)^modmenu_version=(.*)$", "modmenu_version=$($spec.modmenu)"
            [System.IO.File]::WriteAllText(
                $properties26,
                $text26,
                [System.Text.UTF8Encoding]::new($false)
            )
            Push-Location $root
            try {
                $wrapper = Join-Path $autobook "gradlew.bat"
                if ($SkipTests) {
                    & $wrapper -p $project26 clean build -x test --no-daemon
                } else {
                    & $wrapper -p $project26 clean build --no-daemon
                }
                if ($LASTEXITCODE -ne 0) {
                    throw "Gradle build failed for Minecraft $mc"
                }
                $built = Join-Path $project26 "build\libs\autobook-$version.jar"
            } finally {
                Pop-Location
            }
        } else {
            $text = $original -replace "(?m)^minecraft_version=(.+)$", "minecraft_version=$mc"
            $text = $text -replace "(?m)^fabric_version=(.+)$", "fabric_version=$($spec.api)"
            $text = $text -replace "(?m)^loader_version=(.+)$", "loader_version=$($spec.loader)"
            $text = $text -replace "(?m)^loader_min_version=(.+)$", "loader_min_version=$($spec.loaderMin)"
            $text = $text -replace "(?m)^java_release=(.+)$", "java_release=$($spec.java)"
            $text = $text -replace "(?m)^modmenu_version=(.*)$", "modmenu_version=$($spec.modmenu)"
            Write-Properties $text

            Push-Location $autobook
            try {
                if ($SkipTests) {
                    & .\gradlew.bat clean build -x test --no-daemon
                } else {
                    & .\gradlew.bat clean build --no-daemon
                }
                if ($LASTEXITCODE -ne 0) {
                    throw "Gradle build failed for Minecraft $mc"
                }
                $built = Join-Path $autobook "build\libs\autobook-$version.jar"
            } finally {
                Pop-Location
            }
        }

        if (-not (Test-Path $built)) {
            throw "Built jar not found: $built"
        }
        $target = Join-Path $dist "autobook-$version-mc$mc.jar"
        Copy-Item $built $target -Force
        Write-Host "staged: dist\autobook-$version-mc$mc.jar"
    }
} finally {
    Write-Properties $original
    [System.IO.File]::WriteAllText(
        $properties26,
        $original26,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "restored: $propertiesPath"
    Write-Host "restored: $properties26"
}

Write-Host "done. install the jar matching your Minecraft version into mods/"
