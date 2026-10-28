# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `settings-reorg`, two commits on top of `main` at `3be695c`,
  pushed for review; `main` untouched. The venv was refreshed from the
  branch so the maintainer can test it before landing.
- Landed on the branch: the settings reorg, option B. `[proton]` is
  gone; `[runtime]` now holds `fresh_prefix`, `winetricks_verbs`,
  `prefix` (Steam compatdata dir / local `WINEPREFIX`), `prefix_name`
  and `tool` (Steam compat tool / Wine binary / umu `PROTONPATH`), all
  interpreted by `[general] environment`. The game dialog has 7 tabs:
  General (Game, Profile, Launch), Environment (env vars + Pre/Post,
  name kept — the rename is deferred), Runtime (environment selector,
  tool, prefix, verbs, DXVK/vkd3d, Proton debug), Performance, Display,
  System, Artwork/Notes. Old keys survive as ignored unknown entries; no shim.
  CHANGELOG carries the BREAKING note, README and the man page use the
  new keys, and the design is `docs/plans/settings-reorg.md`.
- Second commit on the branch (from the review): Pre/Post moved next to
  the env vars on Environment (General keeps Game/Profile/Launch), System
  lists Night Light before Network, and the executable row is labelled
  "Game Executable:" for local games / "Custom Executable (Override):"
  for Steam. `TODO.md` gained the three follow-ups from the review:
  Winetricks/Protontricks UI with installed verbs and a verb picker;
  Ludusavi defaulting to the game name for local games; Donor AppID
  (diagnose the empty Find list before changing its behaviour).
- Verified on the branch: `scripts/check.sh --qml` 422 passed (the full
  QML driver ran to completion in this environment this time);
  ruff/format clean. Offscreen screenshots at 756 and 1000 px: the 7
  tabs fit without eliding, General carries the whole old Launch
  section, Runtime is populated for Wine and Steam, and the graphics
  status row no longer pushes "Remove from Prefix" out of the frame. At
  the 612 px minimum width Artwork/Notes elides and a few full-width
  rows still clip — the pre-existing missing `columnSpan` on those
  rows, untouched here. A second offscreen pass checked the merged
  Environment tab at the default size, 1000x700 and the 612 px minimum:
  the env table keeps ~10 rows of room, the Pre/Post box fits whole, and
  the System order is Night Light then Network.
- Next concrete step: the maintainer reviews and tests the branch, then
  `git merge --squash` into `main`, delete the local and remote branch
  and refresh the venv again. After that, session 3: per-game metadata
  fields (version/date/tag as name suffixes) and the categories
  redesign (drop the Category column from the library list).
- Open decisions: none for the reorg. Still open from before: the Steam
  Linux Runtime item — (a) refuse when the runtime is missing from
  `~/.local/share/umu/` (exit 14) or let umu download it, (b) label
  "Steam Runtime" or "Steam Runtime (sniper)"; whether to rename the
  Environment tab later; Steam shortcuts created before the AppID
  migration still pass the old AppID.
- Nothing blocking.
