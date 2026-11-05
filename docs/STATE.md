# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's packaging churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed.
- Landed: eleven batches. Prefix/config/winetricks guards, sanitized
  paths, background GUI probes (no freezes), custom `WINEDEBUG`,
  uppercase IDs, shared helpers and 9 redundant tests removed, the
  runtime version manager (`docs/decisions/runtime-manager.md`), the
  tabbed Preferences window with its header button, the Manage Versions
  release combo fix, and the hamburger rework (grouped menu, Global
  Defaults header button, issues checkbox beside the filter, title row
  on one width budget).
- Verified: `scripts/check.sh` 619 passed (the QML node deselected) and
  the full QML suite passed on the rebased branch before the landing;
  offscreen screenshot rounds on the header at 800/1280/1600/1920, the
  Preferences tabs and the release combo; venv refreshed after the
  merge.
- Next: name-based artwork for local games (`TODO.md`), then the
  deferred research and release items.
- Open decisions: none blocking; the runtime manager and the settings
  placement records cover the recent work, the Preferences tabs carry a
  **Reversed** note in `docs/decisions/settings-placement.md`.
- Nothing blocking.
