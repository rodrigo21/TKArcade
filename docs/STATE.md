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
- Landed: twenty-nine batches. The latest: the library's Wine column
  shows the compat tool name only, so a distro build's epoch-prefixed
  version line no longer stretches it; the version stays in the game
  dialog, the pre-launch menu and notifications. Before it: artwork cache
  files keyed by the canonical game ID (`steam-<appid>`, `local-<slug>`)
  with the numeric-name migration, and the Removed games cleanup now
  covering cached art, ProtonDB and release date; the runtime manager
  keeps the three newest builds it installed per layer (default and game
  pins survive); `[ui] download_mirror` prepends an https prefix to
  GitHub asset downloads; the Compat Tool list reads the system Steam
  tree (`proton-cachyos-slr`); and the Proton default became a dialog
  preselection.
- Verified: the approved diff. 685 passed for the fast suite; the QML
  driver last ran on the three-batch diff (686, 149 cases). The new
  Preferences mirror row is covered by the runtime-graphics QML case; the
  earlier Wine, Proton and DXVK manager screenshot passes still apply
  (images in `/tmp/opencode/`).
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
