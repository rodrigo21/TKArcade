# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `fix/artwork-donor-find`, based on `main` (`9dc4538`), 9
  commits, not merged. `main` is otherwise in sync with `origin/main`,
  and the maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD` is still in the tree.
- Landed the artwork pipeline, end to end:
  - `fix(artwork)`: every SteamGridDB call was failing with Cloudflare
    `403 error code: 1010` (urllib sends no `User-Agent`), hidden in
    `log.debug`. Now UA on every request, failures logged and returned
    as tokens, and downloads keep the file's real suffix.
  - `feat(artwork)`: official Steam assets first (client icon
    `library_600x900`, `library_hero`), no key needed. The client `.ico`
    is multi-size; Qt reads its 16x16 frame, so the biggest PNG frame is
    unwrapped and stored (games without one fall back to the 32x32 jpg,
    then `header.jpg`). `fetch_best` tries the preferred provider first
    and only fills the gaps from the second; SteamGridDB entries prefer
    `style == "official"`, pick by shape and skip `.ico` submissions.
    Cache sidecar `grids/<appid>.json` records the provider, and
    `ICommunityService/GetApps` validates the AppID (`5406300` answers a
    bare appid: it is a SteamGridDB page id, not a Steam AppID).
  - `feat(config)`: `[ui] artwork_source` (`steam` default, `sgdb`).
  - `feat(gui)`: `Fetch Artwork` forces a re-download (that is what
    makes a provider change take effect), `artworkFetched(appid, status,
    provider)` feeds a Status row that names the provider and explains
    failures, the dialog reads the AppID from the field before Save, the
    list icon cell crops with `PreserveAspectCrop`, and Preferences has
    the "Artwork Source" combo.
- Verified with the real network (temp cache): `2399420` (Le Mans
  Ultimate, the game the maintainer was after) downloads 600x900 cover,
  1920x620 banner and the 32x32 jpg icon from Steam; `620` (Portal 2)
  gives a 256x256 PNG icon; provider `sgdb` with the real key gives
  community art and the manifest says `sgdb`. Fast suite 438 passed,
  1 deselected; prefs and artwork QML cases pass; offscreen screenshots
  at 756/612 px show the Status row and the Prefs combo fitting.
- Landed after the maintainer's first real test: `Clear…` in
  Artwork/Notes removes the artwork downloaded for the Artwork Source
  AppID (shared by every game pointing there, manual picks untouched)
  behind a confirm, and writes `"cleared": true` in the cache sidecar so
  the background fetch stops filling it back; `Fetch Artwork` (forced)
  drops the mark. The section's buttons share `artButtonWidth`
  (`gridUnit * 6`, 108 px) with a spacer on the AppID row and two button
  columns, so all four fields line up. Verified: 442 passed, and the
  offscreen check at 756/612 px shows five 108 px buttons in two columns
  with 8 px of slack inside the section.
- Next concrete step: `TODO.md` in order — Winetricks UI, Ludusavi
  default name, the icons/cards views. The artwork work is done except
  the per-game provider override idea and showing "Artwork Cleared" in
  the Status row.
- Open decisions: whether a single game needs its own provider override
  (the preference is global); the Status row wraps mid-sentence at the
  612 px minimum; the Environment tab name collision; the Steam Linux
  Runtime item — (a) refuse when the runtime is missing from
  `~/.local/share/umu/` (exit 14) or let umu download it, (b) label
  "Steam Runtime" or "Steam Runtime (sniper)"; Steam shortcuts created
  before the AppID migration still pass the old AppID.
- Nothing blocking.
