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
- Landed: twenty-six batches. The latest changes the library's default
  column layout: Release Date, Origin, Platform, Played, Last Played
  and Installed show after `#` and Game; Runtime, Wine, ProtonDB, Game
  ID and Install Dir start hidden. A new `column_layout_version`
  preference resets saved order/visibility once to these defaults and
  keeps fitted widths. Earlier batches: `CHANGELOG.md`.
- Verified: `tests/test_config.py` + `tests/test_kirigami_model.py`
  (205 pass), full fast suite and the QML driver (568 pass), the
  targeted column/header QML cases, and offscreen screenshots (default
  table with readable Release Date/Installed cells, Configure Columns,
  migrated old prefs). Venv refreshed after the merge. No real-display
  or real Steam library test.
- Next: the `TODO.md` "Deferred design review" items — runtime archives
  in a cache dir (design frozen in `docs/decisions/runtime-archives.md`,
  not implemented), the issue badge in the card/icon views, name-based
  artwork for local games, numeric shortcut mapping and prefix-resolution
  unification.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
