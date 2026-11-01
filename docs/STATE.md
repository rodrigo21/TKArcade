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
- Landed: terminology pass 2. Saved configs write `[general] gameid`
  (was `appid`); old files still load because the identity is the
  filename, and are rewritten on the next save. The wrapper flag reads
  `--game-id`, with `--appid` as an alias until the 1.0 cleanup;
  copied local launch commands use `--game-id`. Internal
  `GeneralConfig.appid`, GUI row keys and `gui/edit.py`'s own
  `--appid` stay as before. `AGENTS.md` now needs an offscreen
  screenshot only when something renders differently, not for every
  GUI-touching change.
- Verified: full suite with the QML driver, 512 passed
  (`scripts/check.sh --changed` widened to it; targeted pass 2 run: 188).
  Translations 638 finished / 0 new. Offscreen clipboard check:
  `tkarcade --game-id local-doom` exact, no label regressions. venv
  refreshed after the merge (`0.0.0.post613.dev0+57e4a35`). No
  real-display or real Steam library test.
- Next: the DXVK/vkd3d design item in `TODO.md`.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
