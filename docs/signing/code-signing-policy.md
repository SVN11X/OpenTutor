# Code signing policy

Status: draft, publish only after SignPath approves the project.

Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org).

This wording and the section name "Code signing policy" follow https://signpath.org/terms. Put this page, or a link to it, on the project home page and on the download or release page.

## Scope

Only the OpenTutor Guardian Windows installer built from https://github.com/SVN11X/OpenTutor by the GitHub Actions workflow `.github/workflows/build-installer.yml` is signed. Nothing else is signed with this certificate.

## Team roles

The roles follow the three categories in the SignPath terms.

- Authors, trusted to change source code without extra review: TODO(owner) list GitHub handles
- Reviewers, who review every change from non-committers: TODO(owner) list GitHub handles
- Approvers, who approve each signing request and decide whether a release can be signed: TODO(owner) list GitHub handles

All team members use multi-factor authentication on SignPath and on GitHub.

## Release process

1. A tagged build runs in a public GitHub Actions workflow and uploads the unsigned installer.
2. The workflow submits a signing request to SignPath.
3. An approver reviews the request and approves it by hand. Every release needs manual approval.
4. The signed installer is uploaded as the build artifact.

## Privacy policy

This program will not transfer any information to other networked systems unless specifically requested.

Details are in the [privacy policy](https://github.com/SVN11X/OpenTutor/blob/main/docs/privacy.md). The only connection Guardian can make is to a local Ollama server on `127.0.0.1:11434`, and only if the user chooses it.
