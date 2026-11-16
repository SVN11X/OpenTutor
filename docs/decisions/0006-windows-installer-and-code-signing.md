# 0006. Windows installer and code signing

- Status: accepted. Signing on hold since 2026-11-16, see Update.
- Date: 2026-11-15
- Proposed by: Claude Code
- Accepted by: owner

## Context
Guardian runs from source. Users need an installer, and Windows shows "Unknown publisher" for unsigned programs.

## Decision
- Freeze the app with PyInstaller 6.22.3 in `--onedir` mode. One-file builds trigger more antivirus false positives.
- Build a per-user installer with Inno Setup 6. No administrator rights, a normal uninstaller that also removes the autostart value.
- Sign with SignPath Foundation, which is free for open source projects. Signing runs from a public GitHub Actions build. It is added after SignPath approves the project, so the first installers are unsigned.
- PyInstaller and Inno Setup are build tools only. The app still has no runtime dependency. Scripts live in `scripts/installer/` and `scripts/build-installer.ps1`. No new top-level folder.
- A frozen build starts its own executable with `--hidden` for autostart.

## Alternatives considered
- Nuitka: fewer false positives in some reports, but a C compiler is required and builds are slower. Not tried here.
- A paid certificate or Azure Trusted Signing: costs money and identity checks. Kept as a fallback if SignPath declines.
- A self-signed certificate: Windows and antivirus tools still warn, so it does not help.

## Consequences
- Windows may still warn until the file gains reputation. A signature does not guarantee silence from every antivirus.
- SignPath requires a public build and a download page that says the project uses SignPath Foundation. That page is written only after approval.
- To undo: delete `scripts/installer/`, `scripts/build-installer.ps1`, `requirements-build.txt` and the build workflow.

## Update 2026-11-16: signing on hold

The owner put code signing on hold. The SignPath Foundation terms (https://signpath.org/terms) sign a modified version of another project only when the upstream project publishes signed builds, and this repository is a GitHub fork. The installer stays unsigned, and each release publishes its SHA-256 in `SHA256SUMS.txt`. The preparation (checklist, policy page and a guarded signing step) is kept in the closed pull request #33, branch `docs/signpath-prep`, to reopen if Guardian moves to its own repository or the fork rule is met.
