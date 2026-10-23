# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked, and
opencode injects the difference when it changes. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean (`git log -1` for the tip; hashes here would
  churn a commit each time).
- Last landed: explicit game types plus local Wine/umu runtimes and
  graphics layers (squash of `game-types`), flash-latest model pin,
  state/handoff mechanism, the `AGENTS.md` split, cross-machine dev
  setup, combined graphics layers (`graphics.dxvk` bool +
  `graphics.vkd3d` `""`/`proton`/`wine`, breaking), and local
  winetricks (`[runtime] winetricks_verbs`, host `winetricks` against
  an existing prefix, Proton's `files/bin/wine` for umu), plus context
  hygiene: `tool_output` caps and compaction `keep.tokens` in
  `opencode.json`, and the rules in `AGENTS.md`.
- Verified on `main`: 382 tests (QML driver included), ruff check and
  format clean, offscreen screenshot of the Compatibility tab reviewed,
  `.venv` refreshed with `scripts/bootstrap.sh`, `-git` rebuilt as
  `0.0.0.r492.gd17421c-1` (its `check()` also ran 382; one QML batch
  aborted under load and its case passed re-run in isolation).
- Next: `runtime.prefix_name` (friendly prefix directory name) is the
  only open decision; no queued task.
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose.
  Design docs, when needed, go in `docs/plans/`; plan-mode scratch files
  under `$HOME` are per-machine and never relied on.
