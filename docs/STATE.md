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
- Landed: fourteen batches; the audit-remediation series is complete.
  The latest is docs plus one warning wording: `RuntimeConfig`
  documents `[runtime] prefix` as the local prefix base, the decision
  docs record the accepted behaviors (lenient runtime/origin load,
  Proton-only `fresh_prefix`, importer runtime default, Steam Runtime
  label, `detectedRuntime`, `native_runtime` sniff), the Flatpak
  Ludusavi warning says Wine/Proton prefixes, and `TODO.md` gains the
  name-based artwork and numeric-shortcut mapping items. Before it: the
  internal name-map/origin consolidation (no behavior change), the
  Proton-only preset check for local games and the GUI local-game
  correctness pass. Earlier batches: `CHANGELOG.md`.
- Verified: B8 targeted tests (192), `--changed` with the full QML
  driver (539, one batch abort re-ran in isolation green), translations
  650 finished and 0 pending; B7 fast suite (538); B6 (95/538/539); B5
  full QML driver green and offscreen screenshots; B4 (244/533); B3
  (85/530); B2 (90/529); B1 (185/526). Venv refreshed after each merge.
  No real-display or real Steam library test.
- Next: the `TODO.md` "Deferred design review" items — runtime archives
  in a cache dir, the Steam Linux Runtime pick for local Wine/umu games,
  the issue badge in the card/icon views, name-based artwork for local
  games, numeric shortcut mapping and prefix-resolution unification.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
