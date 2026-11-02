# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, clean. The working tree carries only the maintainer's
  packaging churn in `packaging/arch/tkarcade-git/` (`PKGBUILD`
  `pkgver`, `optdepends` indentation and a lenient `check()`, plus an
  untracked `.SRCINFO`, never committed); `.qoder/` is git-ignored.
- Landed: fifteen batches; the audit-remediation series is complete.
  The latest fixes the library's play statistics: the two-second poll
  compares the launcher log signature and refreshes the rows when a
  finished session lands, so Played, Last Played and the session
  tooltip update without reopening the GUI. Before it: docs plus the
  Flatpak Ludusavi warning wording, the internal name-map/origin
  consolidation and the GUI local-game correctness pass. Earlier
  batches: `CHANGELOG.md`.
- Verified: `--changed` widened to the fast suite (539) plus the full
  QML driver (540, one batch abort re-ran green); a targeted test covers
  the new refresh path and its no-change no-reset case. Venv refreshed
  after the commit. No real-display or real Steam library test.
- Next: the remaining bug reports from the maintainer's pass, then the
  `TODO.md` "Deferred design review" items — runtime archives in a
  cache dir, the Steam Linux Runtime pick for local Wine/umu games, the
  issue badge in the card/icon views, name-based artwork for local
  games, numeric shortcut mapping and prefix-resolution unification.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
