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
- Landed: eight batches. Prefix/config/winetricks guards, sanitized
  paths, background GUI probes (no freezes), custom `WINEDEBUG`,
  uppercase IDs, shared helpers and 9 redundant tests removed, and the
  runtime version manager (`docs/decisions/runtime-manager.md`).
- Verified: `scripts/check.sh` 620 passed; `--qml` 620 passed; two
  offscreen screenshot rounds on the Preferences runtime rows and the
  new manager dialog; venv refreshed after the merge.
- Next: the `TODO.md` design-review items — a tabbed Preferences window,
  then name-based artwork for local games, then the deferred
  research/release items.
- Open decisions: none blocking; the runtime manager landed with its
  decision record.
- Nothing blocking.
