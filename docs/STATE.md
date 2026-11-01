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
- Landed: unconfigured Steam games now offer to be configured on
  launch. `tkarcade %command%` with no `[runtime] type` shows a
  first-run prompt (imported STL configs included); Configure opens the
  settings on the Runtime tab with `proton`/`native` inferred from the
  command preselected, and Save starts the game with the new config.
  Not now, or closing the prompt or settings, plays with the inference
  and saves nothing, so the prompt returns next launch. An unavailable
  or crashed editor falls back to the inference; local games keep exit
  18. `clean_gui_env` strips Steam overlay/library entries from
  `LD_PRELOAD` and a crashed child is reported as `crashed`.
- Verified: `scripts/check.sh --changed` 496 passed, full suite 496
  passed, `scripts/check.sh --qml` 497 passed (the batch aborts one QML
  case under load and the driver re-runs it isolated). Offscreen
  screenshots checked the prompt and the Runtime tab with proton and
  native preselected. Venv refreshed after the merge
  (`0.0.0.post600.dev0+6dc1449`). The maintainer has not yet repeated
  the real Steam launch to see the prompt.
- Next: plan mode for prefix safety. `prepare_fresh_prefix` wipes
  `STEAM_COMPAT_DATA_PATH`/the prefix, so a fresh-prefix option can
  destroy an existing one; audit it before the origin model (numeric
  Steam shortcuts vs `local-*` configs) and the remaining Steam-only
  audit findings.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
