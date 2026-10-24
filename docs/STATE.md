# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean and in sync with `origin/main`; the only dirty
  file is the `-git` PKGBUILD `pkgver`, left uncommitted on purpose.
- Last landed on `main`: Block Internet per game (`[network]
  block_internet`). The launcher wraps the game innermost in
  `unshare -Urn -- <game>`; hosts that forbid unprivileged user
  namespaces are refused (exit 14, `--validate` 17) instead of going
  online. Option in Settings → System → Network; risk matrix in
  `docs/plans/network-isolation.md`. Also landed earlier: the running
  indicator and Terminate action (`docs/plans/running-indicator.md`),
  the Add game flow and the `.exe` hint.
- Verified on the current tree: `scripts/check.sh --qml` 401 passed,
  ruff check and format clean, `refresh-translations.sh` 0 untranslated,
  offscreen screenshots of the Network section and of its
  unavailable-hint variant showed no clipping, overlap or QML warnings.
- Next concrete step: pt_BR catalog hygiene. `translations/tkarcade_pt_BR.ts`
  has 31 entries marked `type="unfinished"` that already carry text;
  clear the flag on those, recompile, and make
  `scripts/refresh-translations.sh` report unfinished-with-text (its
  `untranslated: 0` hides them today). Small, no behaviour change.
- After that: the "Real-display checks" list in `TODO.md` needs the
  maintainer on a real compositor (tray menu, `WidgetsFormLayout`,
  table/header gestures, category/artwork dialogs, pt_BR in situ, audio
  picker); a release pass (Unreleased has nine groups, `-git` PKGBUILD,
  `diff -r` against TKSteamLaunch, package versions) waits for the
  maintainer's version/tag decision.
- Deferred by the maintainer (2026-10-23): the vkBasalt successor item
  stays out of scope; do not pick it up without a new request.
- Open decisions: none for the running indicator or block_internet;
  release numbering and signing are the maintainer's.
- Nothing blocking.
