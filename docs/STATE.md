# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main`. The tree is clean apart
  from the maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed: the taxonomy rename (`12a5ec0`: `[general] game_type` →
  `environment`, free `[general] platform` removed, Origin and Platform
  derived through `config.platform_for()` / `config.runner_label()`;
  library column 5 `Origin`, 7 `Platform`, 8 `Runner`), and docs only
  since then: the Faugus/Steam Linux Runtime design is parked as a
  detailed block in `TODO.md` (Deferred research), no code written.
- Verified: no code changed since the last run (fast suite 412 passed,
  1 deselected; ruff/format clean; offscreen screenshots of the library
  and Settings). The QML driver in this environment aborts or segfaults
  partway through a single run; one test per process gives 125 of 128,
  the three crashes being `test_header_sort_toggles_indicator_and_order`,
  `test_tier_double_click_opens_protondb` and
  `test_column_move_reorders_cells`. Venv at
  `0.0.0.post536.dev0+12a5ec0`.
- Next concrete step: implement that TODO block — `[runtime]
  steam_runtime` (`""|scout|soldier|sniper|steamrt4`) for Local + native,
  launched as `[umu-run, *argv]` with `PROTONPATH=umu-<name>` and
  `GAMEID=tkarcade-<appid>`; `runner_label()` already takes the origin.
- Then: the Preferences and Global Defaults content reviews (TODO).
- Open decisions: for the SLR item, (a) refuse when the runtime is not in
  `~/.local/share/umu/` (exit 14, keeps "nothing is downloaded") or let
  umu download it and document that; (b) label "Steam Runtime" or "Steam
  Runtime (sniper)". `UMU_NO_PROTON` is legacy: use `PROTONPATH` only.
- Nothing blocking.
