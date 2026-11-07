# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `runtime-sources`, three commits ahead of `main`, not pushed.
  The redesign waits for the landing approval. The working tree carries
  only the maintainer's packaging churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed.
- Landed: twenty-two batches. The latest three redesign the runtime
  sources (`docs/decisions/runtime-sources.md`): the Wine builds are a
  list with one default, the Prefix Base gained a folder picker; the
  Proton installs are discovered (system tree first, then every Steam
  library from `libraryfolders.vdf`) with a read-only list and a
  ProtonPlus/ProtonUp-Qt button; DXVK and vkd3d-proton download from a
  preset or custom source chosen inside the manager, register outside
  folders in `runtimes/.external.json`, and mark one default. The old
  `wine_binary`, `proton_dirs`, `dxvk_dirs`, `vkd3d_dirs`,
  `dxvk_repo` and `vkd3d_repo` keys are migrated and dropped on save.
  Before it: the running marker in the list view, the QML suite cost and
  isolation work, and the Steam compat mapping preselection.
- Verified: the branch, on the verify machine. 670 passed for the fast
  suite and 671 with the QML driver (148 cases, 56.6s). The Wine,
  Proton and graphics dialogs went through offscreen screenshots, where
  two real defects were found and fixed (the labels an attached form
  property never rendered, and a column that shifted when a row had no
  Delete button). The screenshots of the Wine manager and the Preferences
  Runtime tab are in `/tmp/opencode/` (`wine-dialog-final*.png`,
  `proton-*.png`, `gfx-*.png`).
- Next: land `runtime-sources` into `main` when the maintainer approves
  (squash commit, branch deleted, venv refreshed), then work through the
  correction list the maintainer is holding for this redesign. After
  that: the fourth artwork kind (background/fanart, `TODO.md`), then
  the other game sources (Epic, GOG) and the 1.0 packaging check.
- Known gaps from the redesign: the Proton default only preselects the
  game dialog (the launcher does not inject it), `protonup-qt` installed
  as a Flatpak is not found by the manager button, and a registered
  graphics folder is listed as versions but the dialog cannot tell which
  version came from which folder.
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
