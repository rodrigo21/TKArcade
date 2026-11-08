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
- Landed: thirty batches. The latest: a fix for the regression the Wine
  column change caused — the game dialog's Runtime field shows the compat
  tool name and its version again (`_row_wine` now takes `with_version`);
  the library column keeps the bare name. Before it: that Wine column
  shows the compat tool name only, so a distro build's epoch-prefixed
  version line no longer stretches it; artwork cache
  files keyed by the canonical game ID (`steam-<appid>`, `local-<slug>`)
  with the numeric-name migration, and the Removed games cleanup now
  covering cached art, ProtonDB and release date; the runtime manager
  keeps the three newest builds it installed per layer (default and game
  pins survive); `[ui] download_mirror` prepends an https prefix to
  GitHub asset downloads; the Compat Tool list reads the system Steam
  tree (`proton-cachyos-slr`); and the Proton default became a dialog
  preselection.
- Verified: the approved diff. 687 passed with the QML driver
  (`scripts/check.sh --qml`); the earlier Wine, Proton and DXVK manager
  screenshot passes still apply (images in `/tmp/opencode/`).
- Next: the fourth artwork kind (background/fanart, `TODO.md`), then the
  other game sources (Epic, GOG). The 1.0 visual pass, the packaging
  check, the compatibility-shim removal and the release pass wait for
  the maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
