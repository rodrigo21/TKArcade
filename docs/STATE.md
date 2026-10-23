# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked, and
opencode injects the difference when it changes. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean (`git log -1` for the tip; hashes here would
  churn a commit each time).
- Last landed: explicit game types plus local Wine/umu runtimes and
  graphics layers (squash of `game-types`), the flash-latest model pin,
  the state/handoff mechanism, the `AGENTS.md` split (QML rules in
  `docs/QML-NOTES.md`, policies in `docs/POLICIES.md`), cross-machine
  dev setup (`.opencode-model` versioned, `scripts/bootstrap.sh`
  rebuilds venv/install/hook in-tree), and combined graphics layers
  (squash of `graphics-toggles`): `[graphics] dxvk` (bool) plus
  `[graphics] vkd3d` (`""`/`proton`/`wine`), breaking, no shim.
- Verified on `main`: 378 tests (QML driver included), ruff check and
  format clean, offscreen screenshot of the Compatibility tab reviewed,
  `-git` rebuilt as `0.0.0.r490.g9d6f933-1` (its `check()` ran the same
  378).
- Next: pick from the open decisions below; no queued task.
- Open decisions: winetricks on a local backend, `runtime.prefix_name`.
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose.
  Design docs, when needed, go in `docs/plans/`; plan-mode scratch files
  under `$HOME` are per-machine and never relied on.
