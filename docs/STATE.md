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
- Landed: thirty-four batches. The latest drops the Qoder-specific
  agent rules (back on OpenCode): the plan-mode section naming
  `/plan`, `EnterPlanMode` and `ExitPlanMode` is gone, `.qoder/` left
  `.gitignore` and `docs/STATE.md`, and the approval, landing and git
  safety gates stayed. The removed state is archived in the annotated,
  SSH-signed tag `qoder-2026-11-03` (points at the commit before the
  cleanup). Previous batch: runtime archives — Preferences downloads
  the latest official DXVK/vkd3d-proton release (sha256 verified when
  the API provides it), archives in the cache dir are extracted
  automatically on GUI scans into `$XDG_DATA_HOME/tkarcade/runtimes`,
  launcher discovery stays read-only, and zstd uses the 3.14 stdlib
  module with a lazy `zstandard` fallback below it. Earlier batches:
  `CHANGELOG.md`.
- Verified: docs-only change, so only `tests/test_docs.py` (6 pass) and
  the venv refresh ran; no code or test touched. The tag verifies with
  `git tag -v` and both `main` and the tag are on the remote. The
  runtime-archive batch before it: targeted runtime/model tests (132
  pass), full fast suite (595 pass), QML driver (596 pass; the known
  Qt/pytest-qt segmentations re-run in isolation), an offscreen
  screenshot of the Preferences Runtime rows, and translations with 0
  unfinished strings. No live GitHub download (the manual check stays
  pending) and no real-display test.
- Next: the `TODO.md` design-review items — the runtime version
  manager, then name-based artwork for local games, then the deferred
  research/release items.
- Nothing blocking.
