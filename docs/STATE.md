# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `fix/gui-review-batch` off `main` (commits `80a8a7a` code,
  `863cfd4` docs/TODO, `e657230` history header rules, `a1b1ee3` docs).
  Not merged: awaiting the maintainer's review. `main` is untouched; the
  maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD` is left alone.
- Landed: the GUI review batch. Header sorting now calls
  `gameTable.forceLayout()` after the proxy sort (TableView did not
  re-request rows, so the view stayed one order behind). Library columns
  6–11 render their role data, with tooltips for Install Dir/Category.
  The Steam scan window measures the longest `name [appid]` and scrolls
  horizontally at the screen cap; Preferences opens at 30/34 grid units
  (minimum/default). Session History uses the games-table header bar,
  vertical rules between columns, and row/header columns were aligned
  (same spacing and a fixed 3-unit Clear column). Validate Game shows the
  game name in the title and strips the `appid:` prefixes. Tools → Clean
  Up Leftovers removes profiles, session log, Proton logs and history
  lines, plus an optional prefix (unchecked; `compatdata` and prefixes
  shared with a live game are never deleted). TODO gained the
  taxonomy/Lutris/Faugus research plus the Preferences and Global
  Defaults content reviews.
- Verified after the last code change: `scripts/check.sh --changed`
  (full suite + QML driver) 411 passed, ruff/format clean. Offscreen
  visual check passed for columns, sort repaint, scan width, prefs and
  Validate; the History header offset it found was fixed, re-measured
  (header and row cells now share the same x/width) and the vertical
  column rules were added on the maintainer's request. Venv refreshed
  after the code commits.
- Next concrete step: maintainer review of the branch; merge with
  `git merge --squash` when approved, then the release pass (ten
  `Unreleased` groups, the `-git` PKGBUILD, the `diff -r` against
  TKSteamLaunch, package versions), with `scripts/display-check.sh` as
  its checklist.
- Open decisions: taxonomy terms (Origin/Platform/Runner) are in TODO,
  pending the Lutris/Faugus analysis; release numbering and signing are
  the maintainer's.
- Nothing blocking.
