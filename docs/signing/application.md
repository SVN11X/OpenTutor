# SignPath Foundation application checklist

For the owner. Everything here happens on SignPath's side or needs your identity. Claude prepared the repository side only. Nothing was submitted, no account was created and no token exists.

Decision record: `docs/decisions/0006-windows-installer-and-code-signing.md`.

## Read this first: the fork risk

The SignPath terms say a fork may be signed only if the upstream project publishes signed builds, the fork is visible as a fork, and release branches are based on usually signed upstream branches. This repository is a fork of OpenTutor and the MIT license names the upstream author. Check these points before you apply:

- [ ] Does the upstream project publish signed builds? If not, the fork condition fails.
- [ ] Can you show that your team maintains all source files and build scripts of Guardian?
- [ ] Decide how to explain this in the application. SignPath decides at its own discretion and gives no appeal.

## Eligibility, with answers from this repository

| Requirement (terms page) | Answer |
| --- | --- |
| OSI-approved license, no commercial dual licensing | MIT, file `LICENSE` |
| No malware or potentially unwanted programs | Guardian is local only, see `docs/privacy.md` |
| No proprietary component | None. The app has no runtime dependency. Build tools are PyInstaller and Inno Setup |
| Actively maintained | Releases 0.4.0 and 0.5.0 exist. The latest commit is a release commit |
| Released in the form to be signed | TODO(owner): publish an unsigned installer as a GitHub release first |
| Functionality described on the download page | TODO(owner): the release page or README must describe it |
| Own team, own binaries | See the fork risk above |
| No hacking tools | Guardian only asks study quizzes. See the non-goals in `docs/goals.md` |
| Privacy | Sends nothing over the network. Policy in `docs/privacy.md` |
| System changes announced | The installer adds an autostart value for the current user and the uninstaller removes it |
| Uninstaller provided | Inno Setup uninstaller, per user, no administrator rights |

## Facts to prefill in the application

- Repository: https://github.com/SVN11X/OpenTutor
- License: MIT
- Build workflow: `.github/workflows/build-installer.yml`, runs on `windows-latest` from a public repository
- Build script: `scripts/build-installer.ps1`, which runs PyInstaller (onedir) and then Inno Setup 6
- Installer contents: the frozen Guardian app folder `OpenTutorGuardian` with its icon, the Spanish locale file and a fallback content file. File name `OpenTutorGuardian-Setup-<version>.exe`
- Product name in file metadata: `OpenTutor Guardian`. The terms require it to match the project name and the version to be the same in each build. Sources: `scripts/installer/version_info.txt` and `scripts/installer/guardian.iss`
- Privacy statement: https://github.com/SVN11X/OpenTutor/blob/main/docs/privacy.md

## Steps for the owner

1. [ ] Turn on multi-factor authentication on your GitHub account and on every team member's account. The terms require it for the repository and for SignPath.
2. [ ] Decide the roles in `docs/signing/code-signing-policy.md` (authors, reviewers, approvers). Fill the TODO(owner) lines with real GitHub handles.
3. [ ] Publish an unsigned release and make sure the download page describes what Guardian does.
4. [ ] Open https://signpath.org/apply and apply in your own name. Accept the terms yourself. The form fields could not be read here, so check what it asks and copy answers from the table above.
5. [ ] Wait for SignPath's decision. Do not publish the policy page before approval.
6. [ ] After approval, publish the code signing policy. Copy `docs/signing/code-signing-policy.md` to the home page or release page and remove the draft line. Use the term "Code signing policy".
7. [ ] In SignPath, add the predefined "GitHub.com" trusted build system to the organization and link it to the Guardian project.
8. [ ] In SignPath, create the artifact configuration. The uploaded artifact is a ZIP, so the root element must be `<zip-file>`. Set and enforce file metadata restrictions (product name `OpenTutor Guardian`, one product version per build).
9. [ ] In SignPath, create a signing policy and require manual approval for every release.
10. [ ] In SignPath, create an API token for a user with submitter permission on that project and policy.
11. [ ] In GitHub, repository Settings, Secrets and variables, Actions: store the token as the secret `SIGNPATH_API_TOKEN`. Do this yourself. Never paste it in a file or chat.
12. [ ] On the same page add these repository variables: `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_SIGNING_POLICY_SLUG`. Optional: `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG`.
13. [ ] Run the workflow `build-installer` by hand. Approve the request in SignPath. Check that the `installer-signed` artifact exists and that Windows shows the publisher on the installer.
14. [ ] Optional: install the SignPath GitHub App. The docs say it is only needed for audit log evaluation.
15. [ ] After a successful signed release, update decision 0006 and the download text in the README.

## What the workflow does

The signing steps in `.github/workflows/build-installer.yml` run only when the variable `SIGNPATH_ORGANIZATION_ID` and the secret `SIGNPATH_API_TOKEN` both exist. Before approval the workflow behaves as before and only uploads `installer-unsigned`.

The action is pinned to the commit of tag `v3.0` of `SignPath/github-action-submit-signing-request`. SignPath's documentation shows `@v3`. Update the pin yourself when you review a newer release.

## Sources

Fetched in this task:

- https://signpath.org/terms (eligibility, conditions, roles, MFA, website wording)
- https://signpath.org/apply (the fetched text had no form details)
- https://signpath.org/projects/archi/ (example project listing, no policy text)
- https://docs.signpath.io/trusted-build-systems/github (GitHub setup, secret name, ZIP root element)
- https://github.com/SignPath/github-action-submit-signing-request (action repository, tag `v3.0`)
- https://raw.githubusercontent.com/SignPath/github-action-submit-signing-request/main/action.yml (inputs and outputs)

Not verified: the application form fields and the exact review steps. The fetched apply page did not show them.
