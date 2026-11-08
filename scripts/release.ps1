param(
    # 发布构建：版本一致性校验 -> 测试 -> 多版本 jar + GUI 打包 -> 验收 -> dist/release 组包。
    [switch]$SkipTests,
    [switch]$SkipGui,
    [string[]]$Versions = @("1.21.5", "1.21.6", "1.21.7", "1.21.8", "1.21.11", "26.1", "26.1.1", "26.1.2", "26.2")
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# ---------- 1. 版本一致性 ----------

Write-Host "== 版本一致性校验 =="

function Get-ModVersion([string]$propertiesPath) {
    $match = [regex]::Match((Get-Content $propertiesPath -Raw -Encoding UTF8), "(?m)^mod_version=(.+)$")
    if (-not $match.Success) { throw "mod_version not found in $propertiesPath" }
    return $match.Groups[1].Value.Trim()
}

$autoVer = Get-ModVersion (Join-Path $root "autobook\gradle.properties")
$auto26Ver = Get-ModVersion (Join-Path $root "autobook-26\gradle.properties")
if ($auto26Ver -ne $autoVer) {
    throw "autobook-26 mod_version $auto26Ver != autobook $autoVer"
}

$bfInit = [regex]::Match((Get-Content (Join-Path $root "bookforge\bookforge\__init__.py") -Raw -Encoding UTF8), '__version__\s*=\s*"([^"]+)"').Groups[1].Value
$bfPy = [regex]::Match((Get-Content (Join-Path $root "bookforge\pyproject.toml") -Raw -Encoding UTF8), '(?m)^version\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $bfInit -or $bfPy -ne $bfInit) {
    throw "BookForge 版本不一致: __init__.py=$bfInit, pyproject.toml=$bfPy"
}
$bfVer = $bfInit

$readme = Get-Content (Join-Path $root "README.md") -Raw -Encoding UTF8
$readmeAuto = [regex]::Match($readme, 'AutoBook (\d+\.\d+\.\d+)').Groups[1].Value
$readmeBf = [regex]::Match($readme, 'BookForge (\d+\.\d+\.\d+)').Groups[1].Value
if ($readmeAuto -ne $autoVer) { throw "README AutoBook 版本 $readmeAuto != jar $autoVer" }
if ($readmeBf -ne $bfVer) { throw "README BookForge 版本 $readmeBf != $bfVer" }

$changelog = Get-Content (Join-Path $root "CHANGELOG.md") -Raw -Encoding UTF8
$autoVerEsc = [regex]::Escape($autoVer)
$bfVerEsc = [regex]::Escape($bfVer)
if ($changelog -notmatch "(?m)^## $autoVerEsc ") { throw "CHANGELOG 缺少 AutoBook $autoVer 条目" }
if ($changelog -notmatch "(?m)^## BookForge $bfVerEsc ") { throw "CHANGELOG 缺少 BookForge $bfVer 条目" }

Write-Host "AutoBook $autoVer / BookForge $bfVer (gradle/properties/init/pyproject/README/CHANGELOG 一致)"

# 压缩目录：用 .NET ZipFile（比 Compress-Archive 稳定），并对杀毒扫描等瞬时占用重试。
function Compress-Directory([string]$source, [string]$destination, [int]$attempts = 3) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path $destination) { Remove-Item $destination -Force }
    for ($i = 1; $i -le $attempts; $i++) {
        try {
            [System.IO.Compression.ZipFile]::CreateFromDirectory(
                $source, $destination, [System.IO.Compression.CompressionLevel]::Optimal, $true)
            return
        } catch {
            if ($i -eq $attempts) {
                throw "压缩失败（文件可能被其他进程占用）: $destination`n$($_.Exception.Message)"
            }
            Write-Host "压缩被占用，$($i)/$attempts 次重试..."
            Start-Sleep -Seconds 3
        }
    }
}

# ---------- 2. 测试 ----------

$bookforge = Join-Path $root "bookforge"
$python = Join-Path $bookforge ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

if (-not $SkipTests) {
    Write-Host "== BookForge pytest =="
    Push-Location $bookforge
    try {
        & $python -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
    } finally {
        Pop-Location
    }

    Write-Host "== AutoBook JUnit (1.21.8) =="
    Push-Location (Join-Path $root "autobook")
    try {
        & ".\gradlew.bat" test --no-daemon
        if ($LASTEXITCODE -ne 0) { throw "JUnit (1.21.8) failed" }
    } finally {
        Pop-Location
    }

    Write-Host "== AutoBook JUnit (26.1.2) =="
    Push-Location $root
    try {
        & (Join-Path $root "autobook\gradlew.bat") -p (Join-Path $root "autobook-26") test --no-daemon
        if ($LASTEXITCODE -ne 0) { throw "JUnit (26.1.2) failed" }
    } finally {
        Pop-Location
    }
}

# ---------- 3. 构建 ----------

Write-Host "== AutoBook 多版本构建 =="
& (Join-Path $PSScriptRoot "build-multi.ps1") -Versions $Versions -SkipTests

if (-not $SkipGui) {
    Write-Host "== BookForge GUI 打包 =="
    & (Join-Path $PSScriptRoot "build-gui.ps1")
}

# ---------- 4. 产物验收 ----------

Write-Host "== 产物验收 =="
Add-Type -AssemblyName System.IO.Compression.FileSystem

foreach ($mc in $Versions) {
    $jar = Join-Path $root "dist\autobook-$autoVer-mc$mc.jar"
    if (-not (Test-Path $jar)) { throw "jar not found: $jar" }
    $zip = [System.IO.Compression.ZipFile]::OpenRead($jar)
    try {
        $entry = $zip.GetEntry("fabric.mod.json")
        if ($null -eq $entry) { throw "fabric.mod.json missing in $jar" }
        $reader = New-Object System.IO.StreamReader($entry.Open())
        try {
            $meta = $reader.ReadToEnd() | ConvertFrom-Json
        } finally {
            $reader.Dispose()
        }
        if ($meta.version -ne $autoVer) {
            throw "jar 版本不一致: $($meta.version) != $autoVer ($jar)"
        }
        if ($meta.depends.minecraft -ne $mc) {
            throw "jar Minecraft 依赖不一致: $($meta.depends.minecraft) != $mc ($jar)"
        }
        # 帮助验收：游戏内帮助必须随 jar 发布
        if ($null -eq $zip.GetEntry("com/mcbookwriter/autobook/help/HelpText.class")) {
            throw "jar 缺少帮助类 HelpText.class ($jar)"
        }
        Write-Host "verified: autobook-$autoVer-mc$mc.jar (minecraft=$($meta.depends.minecraft), help=ok)"
    } finally {
        $zip.Dispose()
    }
}

# 帮助验收（BookForge）：GUI 帮助中心为离线内置内容
$helpContent = Join-Path $bookforge "bookforge\gui\help_content.py"
if (-not $SkipGui -and -not (Test-Path $helpContent)) {
    throw "缺少 GUI 帮助内容: $helpContent"
}

# ---------- 5. 密钥验收 ----------

Write-Host "== 密钥验收 =="

if (-not $SkipGui) {
    $guiKeys = Join-Path $root "dist\gui\BookForge\_internal\keys"
    $keyInGui = Join-Path $guiKeys "llm_api_key.txt"
    if ((Test-Path $keyInGui) -and ((Get-Item $keyInGui).Length -gt 0)) {
        throw "GUI 打包包含非空 API key: $keyInGui"
    }
    Write-Host "GUI 打包不含 API key（只带配置与术语表模板）"
}

$secretFile = Join-Path $bookforge "keys\llm_api_key.txt"
$secret = ""
if (Test-Path $secretFile) {
    $secret = (Get-Content $secretFile -Raw -Encoding UTF8).Trim()
}

# 收集所有可能承载 key 的文件：默认 key 文件 + llm_config.json 中 global/profiles 的 key_file
$secrets = @()
if ($secret) { $secrets += $secret }
$configPath = Join-Path $bookforge "keys\llm_config.json"
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $keyFiles = @()
    if ($config.key_file) { $keyFiles += $config.key_file }
    if ($config.profiles) {
        $config.profiles.PSObject.Properties | ForEach-Object {
            if ($_.Value.key_file) { $keyFiles += $_.Value.key_file }
        }
    }
    foreach ($kf in $keyFiles) {
        $path = $kf
        if (-not [System.IO.Path]::IsPathRooted($path)) { $path = Join-Path $bookforge $path }
        if ((Test-Path $path) -and -not (Test-Path $path -PathType Container)) {
            $value = (Get-Content $path -Raw -Encoding UTF8).Trim()
            if ($value) { $secrets += $value }
        }
    }
}
$secrets = $secrets | Select-Object -Unique

# ---------- 6. 组包 ----------

Write-Host "== 组包 =="

$releaseDir = Join-Path $root "dist\release"
$stage = Join-Path $releaseDir "MCBookWriter-$autoVer"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($mc in $Versions) {
    Copy-Item (Join-Path $root "dist\autobook-$autoVer-mc$mc.jar") $stage
}

if (-not $SkipGui) {
    Compress-Directory (Join-Path $root "dist\gui\BookForge") `
        (Join-Path $stage "BookForge-$bfVer-windows.zip")
}

New-Item -ItemType Directory -Force -Path (Join-Path $stage "docs") | Out-Null
foreach ($doc in @("usage.md", "job-schema.md", "redstone.md", "architecture.md", "release.md")) {
    $src = Join-Path $root "docs\$doc"
    if (Test-Path $src) { Copy-Item $src (Join-Path $stage "docs") }
}
Copy-Item (Join-Path $root "README.md") $stage
Copy-Item (Join-Path $root "CHANGELOG.md") $stage

New-Item -ItemType Directory -Force -Path (Join-Path $stage "examples") | Out-Null
Copy-Item (Join-Path $root "docs\examples\*") (Join-Path $stage "examples")

$jarLines = ($Versions | ForEach-Object {
    if ($_ -eq "26.1.2") {
        "   - 26.1.2：autobook-$autoVer-mc26.1.2.jar（需要 Java 25、Fabric Loader 0.20.1、Fabric API 0.155.3+26.1.2）"
    } else {
        "   - $_：autobook-$autoVer-mc$_.jar（需要 Java 21、Fabric Loader 0.16.14+、对应版本的 Fabric API）"
    }
}) -join "`r`n"

$install = @"
MCBookWriter 安装说明（AutoBook $autoVer / BookForge $bfVer）

== AutoBook（Minecraft 客户端模组）==

1. 按你的游戏版本选择 jar：
$jarLines
2. 把 jar 放进游戏目录的 mods\。
3. 启动一次游戏，自动生成 autobook\ 目录；把 job.json 放进 autobook\jobs\。
4. 游戏内输入 /autobook help 查看完整帮助；/autobook start <任务名> 开始写书。
5. 试跑：把 examples\sample_job.json 复制为 autobook\jobs\样例.json，准备 3 本空书和一份书与笔，
   执行 /autobook start 样例。预期约 3 本、每本约 5 页，日志出现 verified，无 CONFIRM/VERIFY 暂停。
   examples\sample_source.txt 是对应的源文本，可用 bookforge prepare 复现同一个 job。

== BookForge（书稿预处理）==

方式 A（免安装）：解压 BookForge-$bfVer-windows.zip，运行 BookForge.exe。
方式 B（源码）：cd bookforge && pip install -e ".[gui]"，然后 bookforge-gui 或 bookforge CLI。

LLM 核验为可选功能：在 GUI“配置”页或 bookforge key set 配置 API key。
详细使用见 docs\usage.md；校验和见 checksums-sha256.txt。
"@
[System.IO.File]::WriteAllText((Join-Path $stage "INSTALL.txt"), $install, [System.Text.UTF8Encoding]::new($true))

# 发布说明：提取 CHANGELOG 中当前版本段落
$sections = [regex]::Split($changelog, "(?m)^(?=## )") | Where-Object { $_ -match "^## " }
$notes = $sections | Where-Object {
    $_ -match "^## $autoVerEsc " -or $_ -match "^## BookForge $bfVerEsc "
}
$releaseNotes = "# MCBookWriter AutoBook $autoVer / BookForge $bfVer`r`n`r`n" + ($notes -join "`r`n")
[System.IO.File]::WriteAllText((Join-Path $stage "RELEASE_NOTES.md"), $releaseNotes, [System.Text.UTF8Encoding]::new($true))

# ---------- 7. 明文 key 扫描（发布包） ----------

if ($secrets.Count -gt 0) {
    Get-ChildItem $stage -Recurse -File | Where-Object { $_.Extension -in ".txt", ".md", ".json", ".xml" } | ForEach-Object {
        $content = Get-Content $_.FullName -Raw -Encoding UTF8
        foreach ($s in $secrets) {
            if ($content.Contains($s)) {
                throw "发布包包含明文 API key: $($_.FullName)"
            }
        }
    }
    Write-Host "发布包无明文 API key（扫描 $($secrets.Count) 个 key 来源）"
} else {
    Write-Host "源码中没有非空 key，跳过明文扫描"
}

# ---------- 8. 安装验收：从发布包跑通测试任务 ----------

Write-Host "== 安装验收 =="
$bfExe = Join-Path $bookforge ".venv\Scripts\bookforge.exe"
if (-not (Test-Path $bfExe)) { $bfExe = "bookforge" }
& $bfExe validate (Join-Path $stage "examples\sample_job.json")
if ($LASTEXITCODE -ne 0) { throw "发布包示例 job 校验失败" }
$sample = Get-Content (Join-Path $stage "examples\sample_job.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ($sample.segments.Count -lt 4) { throw "发布包示例 job 过简（少于 4 段）：应覆盖多章节与续本" }
$sampleSource = Join-Path $stage "examples\sample_source.txt"
if (Test-Path $sampleSource) {
    $sourceHash = (Get-FileHash $sampleSource -Algorithm SHA256).Hash.ToLower()
    if ($sourceHash -ne $sample.sourceHash) {
        throw "示例 job 的 sourceHash 与 sample_source.txt 不一致，请重新用 bookforge prepare 生成样例"
    }
    Write-Host "示例 sourceHash 与 sample_source.txt 一致（可用 prepare 复现）"
}
Write-Host "示例 job 通过 schema 校验（$($sample.titleBase)：$($sample.segments.Count) 段，pageLimit=$($sample.pageLimit)）"
Write-Host "游戏内测试任务与预期见 docs/release.md 验收清单"

# ---------- 9. 校验和 ----------

$checksums = Get-ChildItem $stage -Recurse -File | Sort-Object FullName | ForEach-Object {
    $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()
    $rel = $_.FullName.Substring($stage.Length + 1)
    "$hash  $rel"
}
[System.IO.File]::WriteAllLines((Join-Path $stage "checksums-sha256.txt"), $checksums, [System.Text.UTF8Encoding]::new($false))

$zipPath = Join-Path $releaseDir "MCBookWriter-$autoVer.zip"
Compress-Directory $stage $zipPath

Write-Host ""
Write-Host "发布包: $stage"
Write-Host "整包:   $zipPath"
Write-Host "下一步: 按 docs\release.md 创建 GitHub Release / Modrinth 版本，并核对验收清单"
