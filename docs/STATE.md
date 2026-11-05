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
- Landed: nine batches. Prefix/config/winetricks guards, sanitized
  paths, background GUI probes (no freezes), custom `WINEDEBUG`,
  uppercase IDs, shared helpers and 9 redundant tests removed, the
  runtime version manager (`docs/decisions/runtime-manager.md`), and
  the tabbed Preferences window with its header button.
- Verified: `scripts/check.sh` 620 passed; `--qml` 620 passed; the five
  Preferences QML cases run in isolation; an offscreen screenshot round
  on the three tabs, the minimum width and the header row; venv
  refreshed after the merge.
- Next: fix the Manage Versions release combo (the desktop style paints
  `displayText` in its background, so the custom `contentItem` label
  double-paints it), then the hamburger rework that moves the library
  actions out of the menu, then name-based artwork for local games and
  the deferred research/release items.
- Open decisions: none blocking; the runtime manager landed with its
  decision record.
- Nothing blocking.
