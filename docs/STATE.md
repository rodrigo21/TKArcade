# Current state

Ambient instruction: `opencode.json` lists this file (and
`docs/README.md`, the document map) under `instructions`, so every
session reads them without being asked. Keep it short and factual —
history lives in `CHANGELOG.md` and git, deferred work in `TODO.md`,
document roles in `docs/README.md`. Refresh it with `/handoff` before
stopping mid-task.

- Branch: `main`, clean apart from the uncommitted documentation pass
  (corrections, `docs/decisions/`, `docs/runbooks/`, `docs/README.md`,
  and the doc-usage guard) plus the maintainer's `pkgver` churn in
  `packaging/arch/tkarcade-git/PKGBUILD` (never committed).
- Landed previously: the runtime axis is `[runtime] type` (library
  column and settings combo named `Runtime`); the library dropped its
  Category column. The venv was refreshed after that merge.
- The docs are now wired into every session: `opencode.json` injects
  `docs/STATE.md` and `docs/README.md`, `AGENTS.md` routes by trigger,
  and `tests/test_docs.py` (run by `--changed` for any doc edit) fails
  on a missing index entry, a finished `TODO.md` item, a lost decision
  banner or a link to the retired plans directory.
- Verified: full `scripts/check.sh` after the docs pass.
- Next: the open items in `TODO.md` — per-game metadata fields
  (`version`/`date`/`tag`), the artwork leftovers (cover consumer,
  provider override, "Artwork Cleared") and the categories details
  section.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
