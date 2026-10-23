# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked, and
opencode injects the difference when it changes. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `local-winetricks` (feature complete, awaiting review; `main`
  untouched; `git log -1` for the tip, no hashes here).
- Last landed on `main`: explicit game types plus local Wine/umu runtimes
  and graphics layers (squash of `game-types`), flash-latest model pin,
  state/handoff mechanism, the `AGENTS.md` split, cross-machine dev
  setup, and combined graphics layers (`graphics.dxvk` bool +
  `graphics.vkd3d` `""`/`proton`/`wine`, breaking).
- This branch: winetricks for local games. `[runtime] winetricks_verbs`
  runs the host `winetricks` against the prefix before launch, with
  `WINE` set to the chosen Wine binary or the selected Proton's
  `files/bin/wine` for umu; the prefix must already exist (launch once).
  State records prefix+verbs, failures only warn, and the Compatibility
  "Windows runtime" section has the field.
- Verified on the branch: 382 tests (QML driver included), ruff clean,
  offscreen screenshot of the Compatibility tab reviewed.
- Next: maintainer review, then squash onto `main`, delete the branch
  locally/remote, rebuild `-git`.
- Open decisions: `runtime.prefix_name` (friendly prefix directory name).
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose.
  Design docs, when needed, go in `docs/plans/`; plan-mode scratch files
  under `$HOME` are per-machine and never relied on.
