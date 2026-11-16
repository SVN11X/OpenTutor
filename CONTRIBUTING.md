# Contributing

Guardian is a small Python desktop app with no third-party dependencies.

1. Branch from `main`. Do not push to `main`.
2. Run the tests from the repository root (Windows PowerShell):
   `python -m unittest discover -s tests` with `PYTHONPATH=src`
3. Keep it local-first: no telemetry, no paid services, no hidden control.
4. Never let unverified questions or unreviewed work grant credit.
5. Write code, comments, docs and commits in English.
6. Open a pull request that says what you ran and what you could not test.

## This repository is a fork

`origin` is `SVN11X/OpenTutor`, a fork of `zijinz456/OpenTutor`. A plain `gh pr create` can open the pull request on the upstream repository, where it is public and cannot be deleted. Always name the target:

```
gh pr create --repo SVN11X/OpenTutor --base main --head <branch>
```

The same applies to every `gh` command that writes, such as issues, comments and merges. To make it the default for this folder, run `gh repo set-default SVN11X/OpenTutor`.
