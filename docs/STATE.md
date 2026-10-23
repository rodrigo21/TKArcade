# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean and in sync with `origin/main`; the only dirty
  file is the `-git` PKGBUILD `pkgver`, left uncommitted on purpose.
- Last landed: the Add game flow (Game Type combo in the Add dialog,
  `.exe` hint with the Wine/Proton switch in Settings) and the
  capitalization audit (Title Case for labels, menus, titles, columns,
  status messages and the pt_BR catalog; tool names and flags verbatim).
  Both were short-lived branches, squashed and deleted.
- Verified on `main` after the squash: `scripts/check.sh` 383 passed,
  ruff check and format clean, `refresh-translations.sh` 0 untranslated
  (the branch tree ran 384 under `--qml`, same content), offscreen
  screenshots showed no clipped or overlapping text.
- Next: the "After game-types" item in `TODO.md` — a running indicator
  and a Terminate action in the GUI. The launcher writes per-game logs
  but keeps no PID state, so this starts with the process bookkeeping in
  the launcher/backends (stdlib-only invariant). New branch off `main`;
  read `docs/POLICIES.md` first.
- Open decisions: where the PID record lives (a file under the XDG state
  dir next to the logs, versus a lock/socket) and how it is cleaned when
  a game exits or the GUI restarts; whether Terminate signals the whole
  process group (wrappers such as `gamemoderun`/`gamescope` sit in
  between) and with which signal; and whether the indicator polls or
  reacts to the launcher's exit.
- Nothing blocking.
