# 0008. Versioned screenshot gallery

- Status: accepted
- Date: 2026-11-16
- Proposed by: Claude Code
- Accepted by: owner, through the answers given on 2026-11-16

## Context

The owner wants to see how Guardian looks to a user without opening it, and wants that gallery to live only in this repository. `scripts/gallery.py` captures the real windows. `docs/README.md` keeps generated build output out of `docs/`, so committing screenshots needs a written reason.

## Decision

- The gallery lives in `docs/gallery/`: one PNG per state and a `README.md` that GitHub renders as the gallery.
- `python scripts/gallery.py` regenerates it. By default it uses a sample bank made of the 10 backup questions in `src/guardian/questions.py`, so the images are the same on every machine and show no question from the owner's private bank.
- With `--bank`, the script uses a real bank and writes to `build/gallery/`, which git ignores, so real bank questions never reach the repository.
- The `gallery` workflow builds the gallery on every pull request and uploads it as an artifact, to prove the script still works.
- No copy outside the repository. The private page published on claude.ai was deleted at the owner's request.

## Alternatives considered

- Only an Actions artifact. Offered, and the owner chose versioned images that GitHub shows directly.
- Screenshots with the real bank. Rejected, because its questions would then be published in this public repository.
- A workflow that commits new images by itself. Rejected, because a bot commit would bypass the pull request and the owner's review.

## Consequences

- The repository grows by about 0.3 MB each time the images change. Regenerate them only when the interface changes.
- The images can fall behind the code if nobody regenerates them. The pull request template's "How to verify" is the place to say they were regenerated.
- To undo: delete `docs/gallery/` and set the script's default output back to `build/gallery/`.
