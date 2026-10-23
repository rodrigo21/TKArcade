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
  model pin, the state/handoff mechanism, and the `AGENTS.md` split
  (Kirigami/QML rules now in `docs/QML-NOTES.md`, policies in
  `docs/POLICIES.md`, `AGENTS.md` keeps a short index).
- Verified at the `game-types` merge: 377 tests (QML driver included),
  ruff clean, `-git` rebuilt as `0.0.0.r485.g9cfb001-1`. The
  `AGENTS.md` split is docs-only and touched no code.
- Next: pick from the open decisions below; no queued task.
- Open decisions: combined DXVK + vkd3d toggles, winetricks on a local
  backend, `runtime.prefix_name`.
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose.
