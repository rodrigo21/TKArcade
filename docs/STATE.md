# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's packaging churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed; `.qoder/`
  is git-ignored.
- Landed: thirty-three batches. The latest adds runtime archives:
  Preferences downloads the latest official DXVK/vkd3d-proton release
  (sha256 verified when the API provides it), archives in the cache
  dir are extracted automatically on GUI scans into
  `$XDG_DATA_HOME/tkarcade/runtimes`, launcher discovery stays
  read-only, and zstd uses the 3.14 stdlib module with a lazy
  `zstandard` fallback below it. A docs commit records the deferred
  Lutris-like version manager (unofficial builds such as DXVK-Sarek,
  per-game choice). Earlier batches: `CHANGELOG.md`.
- Verified: targeted runtime/model tests (132 pass), the full fast
  suite (595 pass) and the QML driver (596 pass; the known Qt/pytest-qt
  segmentations were re-run in isolation), an offscreen screenshot of
  the Preferences Runtime rows, and translations with 0 unfinished
  strings. Venv refreshed after the merge. No live GitHub download (the
  manual check stays pending) and no real-display test.
- Next: the `TODO.md` design-review items — the runtime version
  manager, then name-based artwork for local games, then the deferred
  research/release items.
- Nothing blocking.
