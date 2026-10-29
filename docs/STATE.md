# Current state

Ambient instruction: `opencode.json` lists this file (and
`docs/README.md`, the document map) under `instructions`, so every
session reads them without being asked. Keep it short and factual —
history lives in `CHANGELOG.md` and git, deferred work in `TODO.md`,
document roles in `docs/README.md`. Refresh it with `/handoff` before
stopping mid-task.

- Branch: `feature/game-metadata` off `main`, holding the uncommitted
  per-game metadata work; `main` is pushed and clean apart from the
  maintainer's `pkgver` churn in `packaging/arch/tkarcade-git/PKGBUILD`
  (never committed). `.qoder/` is git-ignored.
- Metadata landed on the branch: `[metadata] version`/`date`/`tag`
  with `split_name_version()`, `game_display_name()` and
  `metadata_date_valid()` in `config.py`; the library shows the
  `Name [version] (TAG)` suffix in every view (the saved name stays
  plain); a trailing `[x]` typed in the name moves into `version` on
  save; the Game tab gained the three fields and refuses a malformed
  release date. i18n, README and CHANGELOG updated.
- Before it, on `main`: the documentation pass (map, guard, decisions/
  runbooks split) and earlier the `[runtime] type` axis and the dropped
  Category column.
- Verified: full suite with the QML driver (`scripts/check.sh
  --changed`, 481 passed).
- Next: review and land this branch (squash to `main`), then the open
  `TODO.md` items — the artwork leftovers (cover consumer, provider
  override, "Artwork Cleared") and the categories details section.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
