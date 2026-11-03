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
- Landed: twenty-five batches. The latest adds the hidden-by-default
  Release Date (manual `[metadata] date`, else cached Steam store date)
  and Installed (`[general] installed_at`, else the `.toml` birth time)
  columns, both also in History where applicable; the Configure Columns
  dialog now follows the table order; compact `SLR`/`SLR 1.0`–`SLR 4.0`
  runtime labels in the table; and the Wine column shows `—` for native
  games and the Proton install name for local UMU games. Earlier
  batches: `CHANGELOG.md`.
- Verified: full fast suite and the QML driver (568 pass), the targeted
  column/dialog/history QML cases, `tests/test_i18n.py` (4 pass) and
  offscreen screenshots (table with both columns enabled, Configure
  Columns after Move Up, History Installed column). Venv refreshed
  after the merge. No real-display or real Steam library test.
- Next: the `TODO.md` "Deferred design review" items — runtime archives
  in a cache dir, the Steam Linux Runtime pick for local Wine/umu games,
  the issue badge in the card/icon views, name-based artwork for local
  games, numeric shortcut mapping and prefix-resolution unification.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
