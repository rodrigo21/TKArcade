# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` at `5785af3` (this STATE
  refresh is the only commit after it). The tree is clean apart from the
  maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`, and the venv was refreshed
  from this commit.
- Landed `5785af3` (squash of `settings-reorg`): the settings reorg,
  option B. `[proton]` is gone; `[runtime]` holds `fresh_prefix`,
  `winetricks_verbs`, `prefix` (Steam compatdata dir / local
  `WINEPREFIX`), `prefix_name` and `tool` (Steam compat tool / Wine
  binary / umu `PROTONPATH`), interpreted by `[general] environment`.
  The dialog has 7 tabs: General (Game, Profile, Launch),
  Environment (env vars, presets, pre/post commands), Runtime
  (environment, tool, prefix, verbs, DXVK/vkd3d, Proton debug),
  Performance, Display, System (Night Light before Network) and
  Artwork/Notes. The executable row reads "Game Executable:" for local
  games and "Custom Executable (Override):" for Steam. Old keys stay in
  the files as ignored extras (no shim); CHANGELOG has the BREAKING
  note and `docs/plans/settings-reorg.md` the design. README and the
  man page use the new keys.
- Verified on the merged tree: `scripts/check.sh --qml` 422 passed (the
  full QML driver ran to completion here); ruff/format clean. Offscreen
  screenshots at the default size, 1000x700 and the 612 px minimum: 7
  tabs fit, General carries the whole old Launch, Runtime is populated
  for Wine/Steam, the Environment tab keeps room for ~10 env rows with
  the Pre/Post box whole, and "Remove from Prefix" no longer overflows.
  At 612 px Artwork/Notes elides and a few full-width rows still clip
  (pre-existing missing `columnSpan`, untouched).
- Next concrete step: the three review follow-ups added to `TODO.md`,
  in this order — (1) Donor AppID diagnosis first (bug: `Find…` reported
  empty with 14 games; reproduce with a QML case before changing the
  behaviour, then make the donor cover icon/cover/banner); (2)
  Winetricks/Protontricks UI with installed verbs from `winetricks.log`
  and a searchable verb picker; (3) Ludusavi defaulting to
  `[general] name` for local games. After them, session 3 of the
  metadata block: version/date/tag name suffixes and the categories
  redesign (drop the Category column).
- Open decisions: whether to rename the Environment tab (env vars +
  pre/post; the collision with `[general] environment` is now only in
  the name). Still open from before: the Steam Linux Runtime item —
  (a) refuse when the runtime is missing from `~/.local/share/umu/`
  (exit 14) or let umu download it, (b) label "Steam Runtime" or
  "Steam Runtime (sniper)"; Steam shortcuts created before the AppID
  migration still pass the old AppID.
- Nothing blocking.
