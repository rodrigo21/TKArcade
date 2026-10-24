# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main`; the tree is clean apart
  from the maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed: `TODO.md` pruned from 324 lines to the open list (the
  recurring env-preset re-audit and the two deferred-research lines:
  Playnite plugin metadata, online sources à la Playnite). The notes that
  were still load-bearing moved to `docs/QML-NOTES.md`: the
  `selectedIds`-as-source-of-truth selection behind a write-only
  TableView mirror, the cards view's `MouseArea`, the per-test
  `XDG_CACHE_HOME` rule that forbids disabling the disk cache, and the
  tray measurements (native `QMenu` skips invisible actions,
  `aboutToShow` rebuilds, the zero-QtWidgets options, the `{expr}`
  lupdate placeholder). Three code comments repointed
  (`gui/tray.py`, `gui/kirigami_app.py`, `tests/conftest.py`).
- Landed: the widgets-parity audit stays nowhere — its outcomes are in
  `CHANGELOG.md`, its rules in `QML-NOTES.md`, and no second copy is to
  be added. QML-NOTES now names the archived QtWidgets shell, tag
  `widgets-2026-10-06`, as the reference to read (the r240 build the
  dialogs were measured against lives outside the repo).
- Landed: "1 deselected" is explained where it is seen — the
  `scripts/check.sh` banner says the `qml` suite driver is the excluded
  node, QML-NOTES' driver section says the same, and the deselected node
  is `test_qml_suite_isolated` (it runs every QML case in subprocesses
  and only `--qml` includes it).
- Verified after the last code change: `scripts/check.sh` 405 passed,
  ruff clean; only docs, comments and the check banner changed since, so
  `--qml` was not re-run (last full number: 406 with the driver). Venv
  refreshed at `post525.dev0+4c4ab79`.
- Next concrete step: the release pass (ten `Unreleased` groups, the
  `-git` PKGBUILD, the `diff -r` against TKSteamLaunch, package
  versions), with `scripts/display-check.sh` as its checklist — waiting
  on the maintainer's version/tag decision.
- Open decisions: release numbering and signing are the maintainer's.
- Nothing blocking.
