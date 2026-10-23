# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked, and
opencode injects the difference when it changes. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `graphics-toggles` (feature complete, awaiting review; `main`
  untouched; `git log -1` for the tip, no hashes here).
- Last landed on `main`: explicit game types plus local Wine/umu runtimes
  and graphics layers (squash of the `game-types` branch), the
  flash-latest model pin, the state/handoff mechanism, the `AGENTS.md`
  split (QML rules in `docs/QML-NOTES.md`, policies in
  `docs/POLICIES.md`), and cross-machine dev setup (`.opencode-model`
  versioned, `scripts/bootstrap.sh` rebuilds venv/install/hook in-tree).
- This branch: DXVK and vkd3d-proton toggles combine. `[graphics] layer`
  became `dxvk` (bool) + `vkd3d` (`""`/`proton`/`wine`), overrides are
  composed per API, the prefix installs both layers, and the settings
  dialog shows a DXVK checkbox plus a D3D12 combo. Breaking, no shim.
- Verified on the branch: 378 tests (QML driver included), ruff check and
  format clean, offscreen screenshot of the Compatibility tab reviewed.
- Next: maintainer review, then `git merge --squash graphics-toggles`
  onto `main`, delete the branch locally/remote, rebuild `-git`.
- Open decisions: winetricks on a local backend, `runtime.prefix_name`.
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose.
  Design docs, when needed, go in `docs/plans/`; plan-mode scratch files
  under `$HOME` are per-machine and never relied on.
