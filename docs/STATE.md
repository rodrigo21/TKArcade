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
- Landed: thirty batches. The latest maps a numeric Steam shortcut ID to
  the user's `local-*` config: when no `steam-<n>.toml` exists, the
  launcher reads `shortcuts.vdf` (read-only, packaged `vdf`) and applies
  the single local config with the same executable. The launcher
  invariant is now stdlib-first (`vdf` allowed). Earlier batches:
  `CHANGELOG.md`.
- Verified: targeted steam/config/launcher tests (201 pass), the full
  fast suite (573 pass) and the QML driver (574 pass; one batch aborted
  with rc=-11 and passed on isolated re-run). Venv refreshed after the
  merge. No real Steam userdata/`shortcuts.vdf` on this machine, so the
  end-to-end shortcut launch is covered only by fake-Steam fixtures; no
  real-display test.
- Next: the remaining `TODO.md` themes — name-based artwork for local
  games and prefix-resolution unification, then the deferred
  research/release items. The regex VDF fallbacks that `vdf` makes
  redundant are a separate cleanup.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
