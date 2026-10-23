# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked, and
opencode injects the difference when it changes. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean (`git log -1` for the tip; hashes here would
  churn a commit each time).
- Last landed: explicit game types plus local Wine/umu runtimes and
  graphics layers (squash of the `game-types` branch), the flash-latest
  model pin, the state/handoff mechanism, the `AGENTS.md` split
  (Kirigami/QML rules now in `docs/QML-NOTES.md`, policies in
  `docs/POLICIES.md`, `AGENTS.md` keeps a short index), and
  cross-machine dev setup: `.opencode-model` is versioned and
  `scripts/bootstrap.sh` rebuilds the venv/install/hook in-tree.
- Verified: 377 tests (QML driver included) at the `game-types` merge,
  ruff clean, `-git` rebuilt as `0.0.0.r485.g9cfb001-1`. The setup
  change ran 376 non-QML tests plus a real `bootstrap.sh` pass.
- Next: pick from the open decisions below; no queued task.
- Open decisions: combined DXVK + vkd3d toggles, winetricks on a local
  backend, `runtime.prefix_name`.
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose.
  Design docs, when needed, go in `docs/plans/`; plan-mode scratch files
  under `$HOME` are per-machine and never relied on.
