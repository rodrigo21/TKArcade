# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` after the GUI-review merge
  (`4b92f43`, squashed from `fix/gui-review-batch`; the branch was
  deleted locally and on the remote). The tree is clean apart from the
  maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed: the GUI review batch. Header sorting forces the table layout
  after the proxy sort (the view used to stay one order behind); library
  columns 6–11 render their values; the Steam scan window measures the
  longest `name [appid]` and scrolls at the screen cap; Preferences
  opens at 30/34 grid units; Session History has the games-table header
  bar, vertical rules and aligned cells; Validate Game shows the game
  name without the AppID prefixes; Tools → Clean Up Leftovers removes
  profiles, session log, Proton logs and history lines, with an optional
  prefix (never Steam `compatdata` or a shared prefix). TODO carries the
  taxonomy/Lutris/Faugus research and the Preferences/Global Defaults
  content reviews.
- Verified on the merged tree: `scripts/check.sh` 410 passed, 1
  deselected; the branch run had `scripts/check.sh --changed` (full
  suite + QML driver) 411 passed and ruff/format clean. Offscreen visual
  check passed; the History header offset it found was fixed and the
  vertical rules re-checked by pixels. Venv refreshed after the merge at
  `0.0.0.post529.dev0+4b92f43`.
- Next concrete step: the release pass (ten `Unreleased` groups, the
  `-git` PKGBUILD, the `diff -r` against TKSteamLaunch, package
  versions), with `scripts/display-check.sh` as its checklist. Release
  numbering and signing are the maintainer's decision, so they come
  first.
- Open decisions: release number/tag and signing; the taxonomy terms
  (Origin/Platform/Runner) wait for the Lutris/Faugus analysis in TODO.
- Nothing blocking.
