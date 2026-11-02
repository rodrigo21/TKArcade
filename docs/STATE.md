# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's packaging churn in `packaging/arch/tkarcade-git/`
  (`PKGBUILD` `pkgver`, `optdepends` indentation and a lenient
  `check()`, plus an untracked `.SRCINFO`, never committed); `.qoder/`
  is git-ignored.
- Landed: twenty-four batches. The latest pairs the Saves (Ludusavi)
  buttons on one row with no side labels, refining the Open Ludusavi...
  button; before it the second bug-hunt pass, whose last eight landed
  Global Defaults for new Local games, the inline Steam list in Add
  Game, the category picker Add button, `--dry-run` read-only, the
  running badge/Terminate fixes, the Steam cache/prefix/migrated-profile
  fixes and the history/playtime/record robustness batch. Earlier
  batches: `CHANGELOG.md`.
- Verified: for the Saves row, the targeted QML case (same row, hidden
  in Defaults), `tests/test_i18n.py` (4 pass) and an offscreen
  screenshot (buttons aligned with the field column, no leftover
  labels); `scripts/check.sh --changed` ran the full fast suite and the
  QML driver (552 pass). Venv refreshed after the merge. No
  real-display or real Steam library test.
- Next: the `TODO.md` "Deferred design review" items — runtime archives
  in a cache dir, the Steam Linux Runtime pick for local Wine/umu games,
  the issue badge in the card/icon views, name-based artwork for local
  games, numeric shortcut mapping and prefix-resolution unification.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
