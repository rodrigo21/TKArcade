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
- Landed: origin-prefixed game IDs. Steam games are `steam-<appid>` and
  local games `local-<slug>`; `[general] appid` stays the only identity
  key and the numeric Steam AppID is derived (`steam.steam_appid()`).
  Input boundaries canonicalize (`--appid`, Steam env vars, a numeric
  `STEAM_COMPAT_DATA_PATH` basename), creation points emit canonical
  IDs, and `config.migrate_ids()` renames legacy bare Steam AppIDs and
  old local IDs together with profiles, winetricks state, logs, history
  and local artwork (idempotent, skips running games, refuses an
  existing target). Steam services, compatdata, shaders and protontricks
  receive the derived numeric AppID; the artwork cache keeps its numeric
  keys. **BREAKING** in `CHANGELOG.md`: numeric `--appid` values and old
  launch options keep working, but scripts reading `games/<number>.toml`
  must use `steam-<appid>`.
- Verified: full fast suite 510 passed; `scripts/check.sh --qml` 511
  passed; venv refreshed after the merge
  (`0.0.0.post604.dev0+89d7424`). No real configuration was migrated
  (tests cover the rename); no manual display check, since the change
  has no visual surface.
- Next: the remaining Steam-only audit findings, then the origin ×
  runtime action matrix recorded in `TODO.md` (context menu actions per
  combination). Before testing the new build on the real machine, run
  `tkarcade --export`: the first launch renames the live configs,
  profiles and logs.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
