# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's packaging churn in `packaging/arch/tkarcade-git/`
  (`PKGBUILD` `pkgver`, `optdepends` indentation and a lenient
  `check()`, plus an untracked `.SRCINFO`, never committed); `.qoder/`
  is git-ignored.
- Landed: thirty-two batches. The latest unifies prefix resolution:
  `config.prefix_target` returns the container, the WINEPREFIX and
  whether TKArcade owns it, and the GUI model and launcher all use it;
  a Steam custom prefix with `~` now expands in the settings' Open
  button. Earlier batches: `CHANGELOG.md`.
- Verified: targeted config/model tests (208 pass), the full fast suite
  (574 pass) and the QML driver (575 pass). The first run of each suite
  hit the known Qt/pytest-qt segfault and passed on rerun; the QML
  driver re-ran its aborted batches in isolation. Venv refreshed after
  the merge. No real-display test. The real-device shortcut check was
  closed by the maintainer on 2026-11-03 without a run; VDF coverage
  stays fixture-based.
- Next: the remaining `TODO.md` themes — name-based artwork for local
  games, the runtime-archives design, then the deferred
  research/release items.
- Nothing blocking.
