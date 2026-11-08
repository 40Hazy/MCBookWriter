param(
    [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$bookforge = Join-Path $root "bookforge"
$python = Join-Path $bookforge ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if ($InstallDeps) {
    & $python -m pip install -e "$bookforge[gui,package]"
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 未安装。请先运行: pip install -e `".[gui,package]`""
}

$out = Join-Path $root "dist\gui"
$work = Join-Path $bookforge "build\pyinstaller"
& $python -m PyInstaller `
    --noconfirm --clean `
    --distpath $out `
    --workpath $work `
    (Join-Path $bookforge "BookForge.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed (exit $LASTEXITCODE). Close any running BookForge.exe and retry."
}

Write-Host "built: $(Join-Path $out 'BookForge\BookForge.exe')"
Write-Host "keys: put llm_api_key.txt into $(Join-Path $out 'BookForge\_internal\keys')"
