# Development launcher for OpenTutor Guardian (Windows PowerShell 5.1).
# Run from the repository root.
# Usage:  .\scriptsun-dev.ps1            tests, then start the panel
#         .\scriptsun-dev.ps1 -Hidden    start minimized to the tray
#         .\scriptsun-dev.ps1 -TestsOnly
# It never changes the execution policy, never sets up autostart and never installs anything.
param([switch]$Hidden, [switch]$TestsOnly, [switch]$Demo)

$ErrorActionPreference = "Stop"
if (-not (Test-Path "src\guardian\desktop.py")) {
    Write-Error "Run this script from the repository root (the folder that contains src)."
}
$env:PYTHONPATH = "src"

python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { Write-Warning "Some tests failed. See the output above." }
if ($TestsOnly) { exit $LASTEXITCODE }

$guardianArgs = @()
if ($Hidden) { $guardianArgs += "--hidden" }
if ($Demo) { $guardianArgs += "--demo" }
python -m guardian.desktop @guardianArgs
