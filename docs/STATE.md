# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean, in sync with `origin/main`.
- Last landed: friendly prefix names — `[runtime] prefix_name` puts a
  local Windows game under the prefix base as a readable directory
  (`prefix_dir` still wins; empty/unsanitizable names fall back to the
  AppID, no migration), the launcher and the GUI resolve it through the
  same `config.prefix_dir`, Settings gained the name field, a resolved
  path/sharing hint and a picker of complete Wine prefixes
  (`xdg.iter_prefixes`, `drive_c` + `system.reg`). Sharing a prefix is
  allowed and reported; renaming never moves files. Design:
  `docs/plans/prefix-name.md`. Also landed: the venv-refresh rule in
  `AGENTS.md`.
- Verified: 383 tests fast and 384 with the QML driver via
  `scripts/check.sh --qml`, ruff check and format clean; the full QML
  driver passed on a rerun (one offscreen batch segfault, unrelated
  geometry case). `.venv` reinstalled after the merge.
- Next: the Add game flow (TODO "Add game flow and casing") — two
  sources, `Steam Game`/`Local Game`, a `Game Type` combo for local
  games, then the `.exe`-as-native hint and the capitalization audit.
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose
  and is never committed as part of a work-state update.
