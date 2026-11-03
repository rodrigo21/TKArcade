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
- Landed: twenty-nine batches. The latest shows the validation badge
  (error/warning icon and tooltip) on cards and icon cells too, matching
  the table. The two docs batches froze the runtime-archives design
  (`docs/decisions/runtime-archives.md`, not implemented) and dropped
  the Steam Linux Runtime pick item (upstream-blocked). Earlier
  batches: `CHANGELOG.md`.
- Verified: full fast suite and the QML driver (568 pass) on the badge
  branch, the targeted badge QML cases, and offscreen screenshots
  (table/cards/icons badges, no layout shift). One one-off
  `test_header_divider_drag_resizes_and_persists` flake passed on
  re-run. Venv refreshed after the merge. No real-display or real
  Steam library test.
- Next: the remaining `TODO.md` themes — name-based artwork for local
  games, numeric shortcut mapping (discussion in progress: using the
  packaged `vdf` in the launcher) and prefix-resolution unification,
  then the deferred research/release items.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
