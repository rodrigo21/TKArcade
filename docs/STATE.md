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
- Landed: twenty-three batches; the second bug-hunt pass is complete.
  The last eight: Global Defaults reaches new Local games (template
  seed, identity-preserving reset), Open Ludusavi... in the Saves
  section, the inline Steam list in Add Game, the category picker Add
  button, `--dry-run` is read-only again, the running badge/Terminate
  fixes, the Steam cache/prefix/migrated-profile fixes and the
  history/playtime/record robustness batch. Earlier batches:
  `CHANGELOG.md`.
- Verified: `scripts/check.sh --changed` widened to the full fast suite
  and the QML driver (552 pass); targeted cases cover dry-run,
  terminate escalation, the running badge, cache reload, profile
  migration, signal exits, the playtime boundary, live History and the
  cleared selection. Venv refreshed after each merge. No real-display
  or real Steam library test.
- Next: the `TODO.md` "Deferred design review" items — runtime archives
  in a cache dir, the Steam Linux Runtime pick for local Wine/umu games,
  the issue badge in the card/icon views, name-based artwork for local
  games, numeric shortcut mapping and prefix-resolution unification.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
