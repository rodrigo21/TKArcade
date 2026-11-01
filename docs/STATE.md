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
- Landed: two batches. Copy Game ID (canonical) plus Steam-only Copy
  Steam AppID (numeric) in the library menu, and the settings Runtime
  tab offers Create for local Wine/UMU prefixes before they exist (Steam
  as before); Create always opens a confirm dialog and
  `ensurePrefix(appid, target)` creates exactly the dialog's target,
  while Open never creates anything. Then the terminology pass: the
  canonical ID reads Game ID in the library header, sort menu, header
  menu, Columns dialog, export header, Game tab and Prefix Base tooltip;
  the numeric value stays Steam AppID.
- Verified: full suite with the QML driver, 512 passed
  (`scripts/check.sh --changed` widened to it). The autofit test now
  asserts the width changed from its start value: Game ID measures
  exactly the default 90. Offscreen visual checks of the menu, the
  Create confirm window (directory absent until accepting) and every
  renamed label. pt_BR translated (638 finished). venv refreshed after
  the merge (`0.0.0.post610.dev0+e66294c`). No real-display or real
  Steam library test.
- Next: pass 2 of the ID terminology work, recorded in `TODO.md`:
  rename `[general] appid` to `gameid` and `--appid` to `--game-id`,
  with an alias and old-key read (breaking, lands alone). Then the
  DXVK/vkd3d design item in `TODO.md`.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
