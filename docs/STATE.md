# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main`; the tree is clean apart
  from the maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed: the right-side header buttons (view, Columns,
  hamburger/Preferences) no longer vanish in pt_BR. Above 1600px the
  four title buttons show text, and the filter cap came from a fixed
  380px guess; wider translated labels made the row overrun and Kirigami
  hid the actions row. The cap now lives on the `titleDelegate` row and
  measures the real button widths (its ids are not visible at page
  scope). `test_toolbar_survives_translated_labels` boots the shell out
  of process with the desktop style, pt_BR and an 11pt font at the
  maximized 1440p/1.5 width (1700px) and checks the three items are
  visible inside the window.
- Verified after the last code change: `scripts/check.sh --changed`
  (full suite + QML driver) 407 passed, ruff clean; `scripts/check.sh`
  406 passed, 1 deselected (the QML driver banner). Offscreen shot at
  1700px in pt_BR: `/tmp/tkarcade-toolbar-pt.png`. Venv refreshed at
  `post527.dev0+716fe8b`, before the merge and again after it.
- Next concrete step: the maintainer's next round of fixes, then the
  release pass (ten `Unreleased` groups, the `-git` PKGBUILD, the
  `diff -r` against TKSteamLaunch, package versions), with
  `scripts/display-check.sh` as its checklist.
- Open decisions: release numbering and signing are the maintainer's.
- Nothing blocking.
