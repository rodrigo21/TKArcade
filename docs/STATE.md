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
- Landed: thirty-one batches. The latest drops the regex VDF fallbacks
  for libraryfolders, appmanifest, launch options and the compat-tool
  mapping: `vdf` is a runtime dependency, and unreadable files now
  yield no information instead of a regex guess. Earlier batches:
  `CHANGELOG.md`.
- Verified: targeted steam/backends tests (91 pass), the full fast suite
  (572 pass) and the QML driver (573 pass; one batch aborted with
  rc=-11 and passed on isolated re-run). Venv refreshed after the
  merge. No real-display test. The real-device shortcut check was
  closed by the maintainer on 2026-11-03 without a run; VDF coverage
  stays fixture-based.
- Next: the remaining `TODO.md` themes — name-based artwork for local
  games and prefix-resolution unification, then the deferred
  research/release items.
- Nothing blocking.
