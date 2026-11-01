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
- Landed: four batches. External runtime versions
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
- Verified: `scripts/check.sh --qml` 520 passed on the branch (one QML
  batch abort re-ran in isolation, known Qt teardown); offscreen
  screenshots covered the Graphics rows, runtime order and the empty
  versions state at both widths (tooltip popup not hovered); translations
  0 unfinished; venv refreshed after the merge. No real-display or real
  Steam library test.
- Next: the `TODO.md` "Deferred design review" items — runtime archives
  in a cache dir (option C) and the Steam Linux Runtime pick for local
  Wine/umu games.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
