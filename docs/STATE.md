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
- Landed: seven batches. Prefix/config/winetricks guards, sanitized
  paths, background GUI probes (no freezes), custom `WINEDEBUG`,
  uppercase IDs, shared helpers and 9 redundant tests removed.
- Verified: `scripts/check.sh` 598 passed; `--qml` 599 passed; venv
  refreshed. Docs-only change since.
- Next: the `TODO.md` design-review items — the runtime version
  manager, then name-based artwork for local games, then the deferred
  research/release items.
- Open decisions: `docs/decisions/runtime-archives.md` is still a
  proposal; the runtime version manager needs a design before code.
- Nothing blocking.
