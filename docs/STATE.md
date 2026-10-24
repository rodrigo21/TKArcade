# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `real-display-pass` (off `main` at `fbad6ea`), one commit: the
  fixes the real-display pass found, plus the filled runbook and the
  `TODO.md` entry it retires. `main` untouched and in sync with
  `origin/main`; the only dirty file there is the `-git` PKGBUILD
  `pkgver`, uncommitted on purpose.
- The pass itself (`docs/plans/real-display-checks.md`, table at the
  end): all six items `ok` on Plasma Wayland, 2026-10-24. Two failures
  came out of it and both are fixed in this branch:
  - Settings stacked labels above fields on the Launch tab only:
    Kirigami's `FormLayout` drops to one column when the form is
    narrower than its *natural* width, and the hidden `.exe` hint row
    (a wrapped sentence at full line width) inflated that width.
    `WidgetsFormLayout` now pins `wideMode`, the hint label declares
    `Layout.preferredWidth: 0`, and `PrefsDialog.minimumWidth` rose to
    the width its form needs (`gridUnit * 23`, the widgets dialog's
    420). QML cases cover every settings tab at the default and minimum
    width, and the Preferences form at its minimum.
  - The shell never installed the translation catalog (only
    `gui/edit.py` did), so `preferences.language` and the picker had no
    effect on the QML window or the tray menu. `main()` installs it
    before the engine loads; `test_kirigami_app` boots `main()`
    out of process with `pt_BR` and asserts the translated strings.
- Verified: `scripts/check.sh --qml` 406 passed (fast suite included),
  ruff clean, and the two changed cases pass with `-p no:pytest-qt`.
  Venv refreshed on this branch.
- Next concrete step: review and land `real-display-pass` (`git merge
  --squash` on `main`, then delete the branch locally and on the
  remote), then a release pass — Unreleased has ten groups, `-git`
  PKGBUILD, `diff -r` against TKSteamLaunch, package versions — waiting
  for the maintainer's version/tag decision.
- Deferred by the maintainer (2026-10-23): the vkBasalt successor item
  stays out of scope; do not pick it up without a new request.
- Open decisions: release numbering and signing are the maintainer's.
- Nothing blocking.
