# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean and in sync with `origin/main` at `e93bdc5`;
  the only dirty file is the `-git` PKGBUILD `pkgver`, left uncommitted
  on purpose.
- Last landed: the real-display pass and the two fixes it produced
  (`e93bdc5`, squashed from the `real-display-pass` branch, since
  deleted). All six items are `ok` in `docs/plans/real-display-checks.md`
  (Plasma Wayland, 2026-10-24), the runbook is marked passed, and the
  `TODO.md` entry that pointed at it is gone.
  - Settings labels stay beside their fields: `WidgetsFormLayout` pins
    `wideMode` (Kirigami dropped to one column whenever the dialog was
    narrower than the form's natural width, which the hidden `.exe` hint
    row inflated on the Launch tab), the hint label declares
    `Layout.preferredWidth: 0`, and `PrefsDialog.minimumWidth` fits its
    form. A QML case covers every settings tab at the default and
    minimum width, the hint row and the Preferences form.
  - The shell follows `preferences.language`: `main()` installs the
    bundled catalog before the engine loads, so the QML strings and the
    Python tray menu translate; `test_kirigami_app` boots `main()` out of
    process with `pt_BR` and asserts them.
- Verified on the merged tree: `scripts/check.sh` 405 passed,
  `scripts/check.sh --qml` 406 passed, ruff clean, the changed cases
  pass with `-p no:pytest-qt`, and the venv is refreshed
  (`0.0.0.post519.dev0+e93bdc5`) so the landed build can be tested.
- Next concrete step: the release pass — `Unreleased` now carries ten
  groups, the `-git` PKGBUILD, the `diff -r` against TKSteamLaunch and
  the package versions — waiting on the maintainer's version/tag
  decision. The runbook stays as the checklist for that release's
  real-display pass (`scripts/display-check.sh`).
- Open decisions: release numbering and signing are the maintainer's.
- Nothing blocking.
