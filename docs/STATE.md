# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean and in sync with `origin/main`.
- Landed: the real-display pass, its two fixes and the vkBasalt removal.
  All six runbook items are `ok` (`docs/plans/real-display-checks.md`,
  Plasma Wayland, 2026-10-24) and the document is marked passed.
  - Settings keep labels beside fields: `WidgetsFormLayout` pins
    `wideMode` (Kirigami dropped to one column when the dialog was
    narrower than the form's natural width, inflated by the hidden
    `.exe` hint row on Launch), the hint label declares
    `Layout.preferredWidth: 0`, and `PrefsDialog.minimumWidth` fits its
    form. QML cases cover every settings tab at the default and minimum
    width, the hint row and the Preferences form.
  - The shell follows `preferences.language`: `main()` installs the
    catalog before the engine loads, covering QML and the Python tray
    menu; `test_kirigami_app` boots `main()` out of process with `pt_BR`.
  - vkBasalt is out of scope (a successor would be a separate project):
    no TODO item, no docs mention, and the SteamTinkerLaunch importer
    carries no `VKBASALT_*` variables and does not count its toggles.
- Verified after the last code change: `scripts/check.sh` 405 passed
  (1 QML case deselected), ruff clean; `scripts/check.sh --qml` 406
  passed on the same tree minus that importer change (no QML or test
  touched since). Venv refreshed.
- Next concrete step: prune `TODO.md` (327 lines, 45 `[x]` blocks and
  the closed widgets audit whose text is already in `CHANGELOG.md`/git,
  down to the open list: the recurring env-preset re-audit and the two
  deferred-research lines). Move the Qt 6.11 landmines and the tray
  measurements into `docs/QML-NOTES.md` first, so nothing is lost.
  Approved, not started; docs-only, may commit on `main`.
- After that: the release pass (ten `Unreleased` groups, the `-git`
  PKGBUILD, the `diff -r` against TKSteamLaunch, package versions), with
  `scripts/display-check.sh` as its checklist — waiting on the
  maintainer's version/tag decision.
- Open decisions: release numbering and signing are the maintainer's;
  whether the closed widgets-parity audit stays anywhere at all.
- Nothing blocking.
