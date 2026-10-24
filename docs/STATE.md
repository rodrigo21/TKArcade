# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`. Landed: the real-display pass, its two fixes and the
  vkBasalt removal — runbook items all `ok`
  (`docs/plans/real-display-checks.md`, Plasma Wayland, 2026-10-24),
  document marked passed.
- Landed on 2026-10-24: `TODO.md` pruned from 324 lines to the open list
  (the recurring env-preset re-audit and the two deferred-research
  lines: Playnite plugin metadata and online sources à la Playnite).
  Nothing lost: the Qt 6.11 landmines (including the real,
  `selectedIds`-as-source-of-truth selection model behind a write-only
  TableView mirror, and the cards view's `MouseArea`), the per-test
  `XDG_CACHE_HOME` rule, the tray measurements (native `QMenu` skips
  invisible actions, `aboutToShow` rebuilds, the zero-QtWidgets options,
  the `{expr}` lupdate placeholder) are now in `docs/QML-NOTES.md`, and
  the three code comments that pointed at `TODO.md` for them point
  there instead (`gui/tray.py`, `gui/kirigami_app.py`,
  `tests/conftest.py`).
- Verified after that change: `scripts/check.sh` 405 passed
  (1 QML case deselected), ruff clean; `scripts/check.sh --changed` 28
  passed for the touched files. Docs and comments only, no QML or tests
  touched, so no `--qml` run was needed. Venv refreshed.
- Next concrete step: the release pass (ten `Unreleased` groups, the
  `-git` PKGBUILD, the `diff -r` against TKSteamLaunch, package
  versions), with `scripts/display-check.sh` as its checklist — waiting
  on the maintainer's version/tag decision.
- Open decisions: release numbering and signing are the maintainer's;
  whether the closed widgets-parity audit stays anywhere at all (its
  text is in `CHANGELOG.md`/git, nothing in the tree links to it).
- Uncommitted, the maintainer's: `pkgver` bump in
  `packaging/arch/tkarcade-git/PKGBUILD` (`r356` → `r513`).
- Nothing blocking.
