param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $PSScriptRoot
$dataPath = Join-Path $releaseRoot 'patcher\patch-data.zip'
if (-not (Test-Path -LiteralPath $dataPath)) { throw 'Build patch-data.zip first; see tools/build_patch_data.py.' }
Push-Location -LiteralPath $releaseRoot
$patcherPreviousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $releaseRoot 'patcher'
    & $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name 'Spikeout-Battle-Street-Kr-Patcher-v0.8' `
        --add-data "$dataPath;." --paths (Join-Path $releaseRoot 'patcher') `
        --distpath (Join-Path $releaseRoot 'dist') `
        --workpath (Join-Path $releaseRoot 'build\pyinstaller') `
        --specpath (Join-Path $releaseRoot 'build') `
        (Join-Path $releaseRoot 'patcher\patcher.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
} finally {
    $env:PYTHONPATH = $patcherPreviousPythonPath
    Pop-Location
}
