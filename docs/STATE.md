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
- Landed: twenty-three batches. The latest landed the runtime-source
  redesign as one squash (`docs/decisions/runtime-sources.md`): the Wine
  builds are a managed list with one default and a PATH row, Proton
  installs are discovered (system tree first, then every Steam library
  from `libraryfolders.vdf`) with a read-only list and a
  ProtonPlus/ProtonUp-Qt button, DXVK and vkd3d-proton download from a
  preset or custom source inside the manager, register outside folders in
  `runtimes/.external.json`, pick up the distro trees
  (`/usr/share/dxvk`) and mark one default. The six old `[ui]` path keys
  are migrated and dropped on save. The follow-up fixed the source
  change not reloading releases, removed the redundant "Download
  Release…" button, added the system builds and gave the managers a
  name column measured from the longest label with the window sized to
  fit the paths. Before it: the running marker, the QML suite cost and
  isolation work, and the Steam compat mapping preselection.
- Verified: the approved diff. 671 passed for the fast suite and 672
  with the QML driver (149 cases, 60s). The Wine, Proton and DXVK
  managers went through several offscreen screenshot passes; the last
  one measured the path column x (identical per dialog), the gaps, the
  scroll-bar clearance and the widths. Images in `/tmp/opencode/`
  (`col2-*.png` is the final layout).
- Next: the maintainer wants a **visual pass over the whole program
  before 1.0** ("ainda feio, mas ok"); that is the standing next theme,
  not started. After it: the fourth artwork kind (background/fanart,
  `TODO.md`), the other game sources (Epic, GOG) and the 1.0 packaging
  check.
- Known gaps from the redesign: the Proton default only preselects the
  game dialog (the launcher does not inject it); a `protonup-qt` Flatpak
  is not found by the manager button; `vkd3d-proton-git` on Arch ships
  only native `.so` files, so there is no system vkd3d-proton for the
  layer list (Wine's builtin `d3d12.dll` is the `vkd3d = "wine"` path);
  the path column leaves a wider gap after short names, and a path wider
  than 90 gridUnits elides in the middle.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
