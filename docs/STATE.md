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
- Landed: fresh-prefix safety. `[runtime] fresh_prefix` now wipes only
  this game's own `compatdata/<appid>` prefix: the configured
  `[runtime] prefix` when set, else `STEAM_COMPAT_DATA_PATH`, with the
  folder basename required to equal the AppID and `compatdata` in the
  path; symlinks and mismatched folders are refused and the toggle stays
  armed. The wipe runs only for the `proton` runtime (other runtimes log
  a warning and keep the flag), and a successful disarm writes
  `fresh_prefix=false` to the active profile when present instead of
  saving the profile snapshot over the live config.
- Verified: targeted fresh-prefix tests 10 passed; `scripts/check.sh
  --changed` and the full fast suite 503 passed. No QML changed, so
  `--qml` and the screenshot check did not apply. Venv refreshed after
  the merge (`0.0.0.post602.dev0+da5d0ee`). No real Steam wipe was run
  (destructive); the tests cover target selection and refusals.
- Next: plan mode for the origin model. Origin is currently "the AppID
  is numeric" (`steammod.is_steam_id`), which also drives the runtime
  matrix, exit 18 and prefix rules; audit every Steam-only assumption
  behind that test (numeric Steam shortcut IDs vs `local-*` configs)
  before changing it. After it: the remaining Steam-only audit findings,
  then the origin × runtime action matrix recorded in `TODO.md`
  (context menu actions per combination).
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
