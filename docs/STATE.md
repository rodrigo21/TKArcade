# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` (two landings this session
  plus this STATE refresh). The tree is clean apart from the maintainer's
  uncommitted `pkgver` in `packaging/arch/tkarcade-git/PKGBUILD`, plus
  the `.SRCINFO`/src `.tar.gz` build leftovers next to it. The venv was
  refreshed from this commit.
- Landed the squash of `feature/ludusavi-local-name`: Ludusavi resolves
  a local game by its name. `effective_name(appid, name_override,
  game_name)` in `backends/ludusavi.py` is the single rule — the explicit
  override wins, a numeric AppID keeps `--infer steam`, and a `local-*`
  id falls back to `[general] name` (before, `--infer steam` could never
  match, so nothing was restored or backed up). The wrap
  (`launcher._apply_wrappers`), the launch preview and the coverage check
  (`gui/model._coverage_worker`) all call it. `checkCoverage` takes the
  dialog's name as a third argument, so a rename is reflected before the
  Save, falling back to the saved name when it is empty. The `luName`
  placeholder reads `Empty = <name>` for local games. CHANGELOG under
  Unreleased, no **BREAKING** note (no config key changed).
- Landed `fix(gui): stop recentering the list on every row click`: the
  table centred the clicked row on every selection (plain/Ctrl/Shift), so
  the row slid out from under the cursor and a double-click's second
  click hit another game (visible from the rows below the viewport's
  middle, plain from the 11th with the default height). The mouse paths
  never scroll now; `ensureTableRowVisible()` (MainPage, next to
  `tableSelectAndReveal`) reveals the current row by the least amount for
  the keyboard (arrows, Page, Home/End) — the `QTableView::scrollTo`
  rule. `test_table_click_never_scrolls` fails on the old code.
- Verified: `scripts/check.sh` → 463 passed, `--qml` → 464 passed, ruff
  check/format clean. No visual change in either landing (the QML only
  gained an argument and the scroll helpers), so the earlier offscreen
  screenshot checks still hold.
- Next concrete step: `TODO.md` in order — the icons/cards views (the
  list is done); then the artwork leftovers: per-game provider override
  and "Artwork Cleared" in the Status row.
- Open decisions: the Environment tab name collision; the Steam Linux
  Runtime item — (a) refuse when the runtime is missing from
  `~/.local/share/umu/` (exit 14) or let umu download it, (b) label
  "Steam Runtime" or "Steam Runtime (sniper)"; Steam shortcuts created
  before the AppID migration still pass the old AppID. Deferred: the
  winetricks fallback for a Steam game with a custom prefix (resolve its
  Proton and run `winetricks --gui` on `<custom>/pfx`).
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533, and Steam expands
  `tkarcade %command%` through PATH (the dialog now warns about it).
- Nothing blocking.
