# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, clean. The working tree carries only the maintainer's
  packaging churn in `packaging/arch/tkarcade-git/` (`PKGBUILD`
  `pkgver` and an untracked `.SRCINFO`, never committed); `.qoder/` is
  git-ignored.
- Landed: the Steam overlay crash fix. Steam injects
  `gameoverlayrenderer.so` through `LD_PRELOAD` for `tkarcade
  %command%`; the 64-bit renderer aborted Qt Quick's OpenGL context
  (SIGABRT), the editor child died and the game was skipped.
  `clean_gui_env` now strips Steam library and overlay entries from
  `LD_PRELOAD` too, `run_editor_menu` reports `crashed` instead of
  `cancelled`, the config-triggered menu falls back to a direct
  launch, `--edit` exits 15 on a crash and `--menu` launches directly.
- Verified: the maintainer ran a real Steam launch through the venv
  build and confirmed it works. `scripts/check.sh --changed` 70 passed,
  full suite 486 passed, `--qml` 487 passed (one QML case aborted in
  the batch and passed isolated). Venv refreshed after the merge
  (`0.0.0.post598.dev0+2bea15f`).
- Next: plan mode for the runtime batch. Unconfigured Steam games exit
  18 because `defaults.toml` has no `[runtime] type`; infer it from
  `%command%` (proton when it carries `waitforexitandrun`/Proton, else
  native) without persisting, and cover imported (STL) games too.
  After it: prefix safety (`prepare_fresh_prefix` wipes
  `STEAM_COMPAT_DATA_PATH`), the origin model (numeric Steam shortcuts
  vs `local-*` configs), then the remaining Steam-only audit findings.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-fix).
- Nothing blocking.
