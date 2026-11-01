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
- Landed: origin/runtime-aware context menu. `GameListModel.contextActions()`
  is the single table (Steam proton/native, local native/wine/umu) that
  the QML menu binds to; the stale `/^\d+$/` Steam test is gone, so
  Steam games have Copy Launch Options, Open ProtonDB and shader cache
  again with canonical IDs. Local games gained Open Install Folder (the
  executable's folder, `launch_cwd` wins, reusing `launcher.local_run_cwd`).
  The prefix entry is Steam-proton-or-existing / local wine-UMU only, is
  hidden for native games, and reads Open Prefix Folder; an applicable
  but not yet created prefix stays visible and disabled. Decision record:
  `docs/decisions/origin-runtime-actions.md`.
- Verified: full suite with the QML driver, 512 passed
  (`scripts/check.sh --changed` widened to it). Offscreen visual check of
  both popups: items and labels correct (Qt 6.12 QQC2 keeps space for
  hidden menu items, a pre-existing menu quirk). venv refreshed after the
  merge (`0.0.0.post606.dev0+9ee3e5e`). No real-display or real Steam
  library test.
- Next: plan the two menu/settings follow-ups deferred by this batch: a
  separate Copy Steam AppID (numeric) action plus renaming Copy App ID
  (which copies the canonical ID), and opening/clearing the local
  Wine/UMU prefix from the settings dialog (today those buttons are
  Steam-custom-prefix only). Then the DXVK/vkd3d design item in
  `TODO.md`.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
