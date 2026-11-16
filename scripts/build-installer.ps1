# Builds dist\OpenTutorGuardian\ with PyInstaller, then the installer with Inno Setup.
# Run from the repository root in Windows PowerShell 5.1:  .\scripts\build-installer.ps1
# Use -SkipInstaller to stop after the PyInstaller folder. It signs nothing.
# Native tools print progress on stderr, so errors are detected by exit code, not by stderr.
param([switch]$SkipInstaller)

if (-not (Test-Path "src\guardian\desktop.py")) {
    throw "Run this script from the repository root."
}

python -m pip install --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "pip failed." }

python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name OpenTutorGuardian `
    --paths src `
    --specpath build `
    --version-file (Resolve-Path scripts\installer\version_info.txt) `
    scripts\installer\guardian_entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
if ($SkipInstaller) { exit 0 }

$candidates = @(
    (Get-Command iscc -ErrorAction SilentlyContinue).Source,
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 was not found. Install it from jrsoftware.org." }

& $iscc scripts\installer\guardian.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
