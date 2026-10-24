# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean and in sync with `origin/main`; the only dirty
  file is the `-git` PKGBUILD `pkgver`, left uncommitted on purpose.
- Last landed on `main`: the real-display check runbook
  (`docs/plans/real-display-checks.md`), `scripts/display-check.sh` and
  `TKARCADE_OPEN` in `gui/kirigami_app.py` (commit `b2c87de`). The
  script launches the shell against a throwaway profile (own `XDG_*` and
  `TMPDIR`) seeded with native, Wine and category/artwork games; the env
  var opens one dialog at launch (`settings[:appid]`, `artwork[:appid]`,
  `defaults`, `add`, `category`, `prefs`, `about`) and a bad name only
  logs. The runbook carries the per-item steps, acceptance criteria,
  failure symptoms and the results table; `TODO.md` now points at it
  instead of repeating the prose, and the tray entry no longer describes
  the ruled-out QML popup (the menu is a native `QMenu`).
- Verified on the merged tree: `scripts/check.sh` 404 passed,
  `scripts/check.sh --qml` 405 passed, ruff check and format clean, and
  an offscreen smoke against the real QML opened all six surfaces
  (`artwork:` lands on tab 7); full boot with
  `TKARCADE_OPEN=artwork:check-category` returns 0 with only the settings
  window visible. Venv refreshed after the merge.
- Next concrete step: the pass itself, on a real compositor —
  `scripts/display-check.sh` (then `--lang pt_BR`), filling the table at
  the end of the runbook; failures become their own item or branch. A
  release pass (Unreleased has nine groups, `-git` PKGBUILD, `diff -r`
  against TKSteamLaunch, package versions) waits for the maintainer's
  version/tag decision.
- Deferred by the maintainer (2026-10-23): the vkBasalt successor item
  stays out of scope; do not pick it up without a new request.
- Open decisions: none for the runbook or the diagnostic surface;
  release numbering and signing are the maintainer's.
- Nothing blocking.
