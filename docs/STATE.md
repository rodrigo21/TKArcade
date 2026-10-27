# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` at `9be5a22`. The tree is
  clean apart from the maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`. Venv at
  `0.0.0.post538.dev0+f08313b` (source at `f08313b`, the STATE commit does not change it).
- Landed: `f08313b` — local AppIDs use a real slug (`config.local_slug`,
  `local_id_base`, hash fallback `local_name_hash` for names with no
  ASCII letters) and `config.migrate_local_ids()` renames the old ones
  once, at GUI startup or through `tkarcade --migrate-ids`. It moves
  config, profiles, artwork, grids, per-game log, winetricks state,
  history lines and `donor_appid` refs and pins an existing prefix via
  `[runtime] prefix_name`; only slug-dirty IDs are touched, so Steam IDs,
  clone targets and running games keep theirs. Steam shortcuts created
  before the rename still pass the old AppID (TODO item).
- Verified: fast suite 421 passed, 1 deselected; ruff/format clean; one
  QML case (`test_columns_menu_hides_app_id`) passes. The full QML
  driver in this environment aborts or segfaults partway through a single
  run; one test per process gave 125 of 128 last time it was measured
  (crashes: `test_header_sort_toggles_indicator_and_order`,
  `test_tier_double_click_opens_protondb`,
  `test_column_move_reorders_cells`). The maintainer tested the
  migration on the real config before the merge.
- Next concrete step: session 2 of the "Settings and metadata" TODO
  block — settings reorg, option B (breaking keys are fine): merge the
  `Game` and `Launch` tabs, unify `[proton]`/`[runtime]`
  (`winetricks_verbs`, prefix override, tool selection), rename the
  `Environment` tab (collides with `[general] environment`), rework
  `Compatibility`/`System`. Old configs lose moved keys (no shims
  pre-1.0) — CHANGELOG must say so.
- Then: session 3 — metadata fields (version/date/tag, suffixes
  `Name [version] (TAG)`, never in the AppID), categories redesign and
  dropping the Category column from the library list.
- Open decisions: none for the slug work. Still open from before: for the
  Steam Linux Runtime item, (a) refuse when the runtime is not in
  `~/.local/share/umu/` (exit 14) or let umu download it; (b) label
  "Steam Runtime" or "Steam Runtime (sniper)".
- Nothing blocking.
