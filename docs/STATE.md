# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean and in sync with `origin/main`; the only dirty
  file is the `-git` PKGBUILD `pkgver`, left uncommitted on purpose.
- Last landed on `main`: pt_BR catalog hygiene (`chore(i18n)`). The 31
  messages that carried `type="unfinished"` despite having text are
  clean; `scripts/refresh-translations.sh` now lists unfinished entries
  and runs `lrelease6 -fail-on-unfinished`, so it refuses to write a
  `.qm` while a message is flagged; `test_ts_has_no_unfinished` checks
  the attribute, not only the text. `.qm` came out byte-identical: no
  behaviour change. Also landed earlier: Block Internet per game
  (`docs/plans/network-isolation.md`), the running indicator and
  Terminate action (`docs/plans/running-indicator.md`), the Add game
  flow and the `.exe` hint.
- Verified on the current tree: `scripts/check.sh --qml` 401 passed,
  ruff check and format clean, `refresh-translations.sh` reports
  `untranslated: 0` / `unfinished: 0` with 537 finished translations.
  One earlier `--qml` run aborted with a Qt offscreen crash (SIGSEGV
  inside libpython) and a plain rerun passed; treat it as a flake of
  the QML driver, not as a failure of the change under test.
- Next concrete step: the "Real-display checks" list in `TODO.md` needs
  the maintainer on a real compositor (tray menu, `WidgetsFormLayout`,
  table/header gestures, category/artwork dialogs, pt_BR in situ, audio
  picker); a release pass (Unreleased has nine groups, `-git` PKGBUILD,
  `diff -r` against TKSteamLaunch, package versions) waits for the
  maintainer's version/tag decision.
- Deferred by the maintainer (2026-10-23): the vkBasalt successor item
  stays out of scope; do not pick it up without a new request.
- Open decisions: none for the catalog, running indicator or
  block_internet; release numbering and signing are the maintainer's.
- Nothing blocking.
