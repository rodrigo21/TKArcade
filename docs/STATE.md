# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean and in sync with `origin/main` (the only dirty
  file is the `-git` PKGBUILD `pkgver`, left uncommitted on purpose).
  The short-lived branches `add-game-flow` and `casing-audit` landed as
  two squashed, signed commits and were deleted locally and on origin.
- Last landed: the Add game flow with the `.exe` hint, then the
  capitalization audit. `AddDialog` keeps `Steam Game` / `Local Game`
  and, for local games, a Game Type combo that preselects the same
  field in Settings; Settings warns when a Windows executable runs as
  Linux native and offers the Wine/Proton switch without blocking the
  save. Every label, button, menu entry, dialog title, checkbox, column
  and status message is Title Case, in the pt_BR catalog too; tool names
  (`wine`, `umu-run`, `winetricks`, `vkd3d-proton`, `logind`,
  `compatibilitytools.d`, `MangoHud`, `DXVK`) keep their spelling and
  flags/paths stay verbatim.
- Verified: 383 passed under `scripts/check.sh` on the squashed `main`
  (384 with `--qml` on the branch, same tree), ruff clean, translations
  complete (0 untranslated), offscreen screenshots showed no clipping.
- Next: the deferred item in `TODO.md` "After game-types" — a running
  indicator and a Terminate action in the GUI (the launcher writes
  per-game logs but keeps no PID state today). New session and branch
  off `main`; it touches the launcher/backends, so read
  `docs/POLICIES.md` first.
- Nothing blocking.
