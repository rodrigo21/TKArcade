# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` at `1cc7cbc` (the squash of
  the artwork branch; this STATE refresh is the only commit after it).
  The tree is clean apart from the maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed `1cc7cbc` (squash of 13 commits): the artwork pipeline, tested
  by the maintainer in the real window.
  - `[artwork] donor_appid` → `artwork_appid`, "Artwork Source AppID":
    the Steam AppID whose art a game uses, installed or not.
  - SteamGridDB was unreachable from the app (no `User-Agent` → Cloudflare
    `403 error code: 1010`, swallowed by `log.debug`); requests carry a UA
    and failures surface as tokens.
  - Official Steam art first, no key: client icon (multi-size `.ico`
    unwrapped to its 256x256 PNG, because Qt reads the 16x16 frame),
    `library_600x900`, `library_hero`. SteamGridDB is the fallback, or
    first with Preferences → "Artwork Source" (`[ui] artwork_source`).
  - Per-kind resolution through the source AppID; cache records the
    provider in `grids/<appid>.json`; `ICommunityService/GetApps`
    validates the AppID (a SteamGridDB page id answers no name).
  - Dialog: `Fetch Artwork` (forced re-download), `Clear…` (removes the
    source AppID's shared cache and marks it so the background fetch
    stops filling it back), a Status row naming the provider, and one
    button width (`gridUnit * 6`) across the section.
  - List icon cell crops (`PreserveAspectCrop`) instead of letterboxing.
- Verified: fast suite 442 passed, 1 deselected, ruff clean; the artwork
  and prefs QML cases; offscreen geometry at 756/612 px (five 108 px
  buttons in two columns, fields equal, 8 px slack); real-network smoke
  in a temp cache (`620` → 256x256 PNG icon, `2399420` → 32x32 jpg icon
  plus 600x900 and 1920x620).
- Next concrete step: `TODO.md` in order — Winetricks/Protontricks UI
  with installed verbs from `winetricks.log`, Ludusavi defaulting to
  `[general] name` for local games, then the icons/cards views (the list
  is done). Small artwork leftovers in the TODO: per-game provider
  override and showing "Artwork Cleared" in the Status row.
- Open decisions: the Environment tab name collision; the Steam Linux
  Runtime item — (a) refuse when the runtime is missing from
  `~/.local/share/umu/` (exit 14) or let umu download it, (b) label
  "Steam Runtime" or "Steam Runtime (sniper)"; Steam shortcuts created
  before the AppID migration still pass the old AppID.
- Nothing blocking.
