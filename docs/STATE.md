# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` after the game taxonomy
  merge (`12a5ec0`, squashed from `feat/game-taxonomy`; the branch was
  deleted locally and on the remote). The tree is clean apart from the
  maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed: the taxonomy design (`docs/plans/game-taxonomy.md`, from the
  Lutris/Faugus analysis) and the rename it decided —
  `[general] game_type` → `environment`, the free `[general] platform`
  label removed, origin (Steam/Local) and platform (Linux/Windows)
  derived through `config.platform_for()` and `config.runner_label()`.
  Library column 5 is `Origin`, 7 `Platform`, 8 `Runner` (Steam Proton,
  Steam Runtime, Native, Wine, Proton (UMU)); Settings says
  "Environment" and has no Platform field. pt_BR catalog refreshed.
- Verified: fast suite 412 passed, 1 deselected; ruff/format clean;
  offscreen screenshot of the library and Settings with the new labels
  and no stray "Source"/"PC". The QML driver in this environment
  aborts or segfaults partway through a single run (three cases also
  segfault on the pre-merge tree); one test per process gives 125 of
  128, the three crashes being
  `test_header_sort_toggles_indicator_and_order`,
  `test_tier_double_click_opens_protondb` and
  `test_column_move_reorders_cells`. Venv refreshed after the merge at
  `0.0.0.post536.dev0+12a5ec0`.
- Next concrete step: the Faugus item — Steam Linux Runtime
  (soldier/scout/sniper/steamrt4 via `umu-run`) for local Linux games,
  in its own commit; `runner_label()` already takes the origin.
- Then: the Preferences and Global Defaults content reviews (TODO).
- Open decisions: none on the taxonomy; the terms are Origin / Platform
  / Environment (Runner).
- Nothing blocking.
