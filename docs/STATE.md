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
- Landed: five batches. Missing installs: `launcher.missing_install()`
  flags a Steam game whose appmanifest/install folder is gone (only when
  a Steam root exists) and a local game whose configured executable
  vanished, so the issues-only filter, Validate Game and `--validate`
  (exit 17) report it; the hamburger's "Remove Uninstalled Games..."
  lists those configs in a confirmation, deletes only their configs and
  offers the usual leftover cleanup. Before it: external runtime versions
  (`docs/decisions/external-runtimes.md`): DXVK/vkd3d come only from the
  Preferences directories (the Lutris and Flatpak-Lutris defaults are
  gone), each local Wine game picks `[graphics] dxvk_version` /
  `vkd3d_version` (empty = newest, a missing selection warns instead of
  falling back), and Proton installs require the `proton` launcher. Its
  settings follow-up reads Native, UMU, Wine, keys the Runtime rows on
  the kind (no Proton path leaking into the Wine field, no Detected
  Runtime row for Wine) and turns D3D12 into two mutually exclusive
  checkboxes with the version picker shown only while its layer is on.
  Earlier: the graphics-layers and settings-placement decisions and the
  Compat Tool filter (details in `CHANGELOG.md`).
- Verified: `scripts/check.sh --qml` 524 passed on the branch (one QML
  batch abort re-ran in isolation, known Qt teardown); offscreen
  screenshots covered the hamburger entry and the Remove Uninstalled
  confirmation (plural/singular, default and minimum width, empty-state
  notice), no QML warnings; venv refreshed after the merge. No
  real-display or real Steam library test.
- Next: the approved issue-badge batch on `feat/issue-badge` — severity
  levels (error/warning) from `launcher.validate_issues()`, a badge at
  the end of the table's name cell with the issues in its tooltip, and a
  `TODO.md` item for the card/icon views.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
