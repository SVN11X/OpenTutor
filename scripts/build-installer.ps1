# Builds dist\OpenTutorGuardian\ with PyInstaller, then the installer with Inno Setup.
# Run from the repository root in Windows PowerShell 5.1:  .\scripts\build-installer.ps1
# Use -SkipInstaller to stop after the PyInstaller folder. It signs nothing.
param([switch]$SkipInstaller)

$ErrorActionPreference = "Stop"
if (-not (Test-Path "src\guardian\desktop.py")) {
    Write-Error "Run this script from the repository root."
}

python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name OpenTutorGuardian `
    --paths src `
    --specpath build `
    --version-file (Resolve-Path scripts\installer\version_info.txt) `
    scripts\installer\guardian_entry.py
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed." }
if ($SkipInstaller) { exit 0 }

$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { Write-Error "Inno Setup 6 was not found. Install it from jrsoftware.org." }
& $iscc scripts\installer\guardian.iss
if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup failed." }
