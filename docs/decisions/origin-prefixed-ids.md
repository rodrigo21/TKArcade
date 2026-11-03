# Origin-prefixed game IDs

Status: implemented (2026-11-01).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: make a game's origin explicit in its ID instead of encoding it in
the ID's shape. A second numeric store (GOG, Epic, another service)
would otherwise collide with Steam AppIDs, and the Steam AppID currently
doubles as identity and as the external key for Steam APIs,
`compatdata`, Steam's config files and shortcuts.

## Evidence

**Lutris** (checked in 0.5.x) keeps identity and the store key apart:
`games.id` is the SQLite row id, `slug` is the stable identifier used by
`lutris:rungame/<slug>`, `service_id` holds the external store AppID and
`configpath` is the config-file key (`~/.config/lutris/games/<x>.yml`).
Config files are never named after the service ID.

**Faugus** (checked in 1.x) stores one `gameid` per entry in
`games.json`, a slugified title with `-2`, `-3` on collisions; it has no
origin and no external-ID separation, so two stores' numeric IDs could
not both be represented.

## Decision

The canonical ID is `<origin>-<body>`: `steam-570`, `local-doom`.
`[general] appid` stays the only identity key and holds the canonical
ID; the numeric Steam AppID is derived (`steam.steam_appid()`), never
stored twice. This matches Lutris's identity/service split without
Faugus's collision risk.

- `steam.origin(appid)` returns `steam` for `steam-<digits>` and for
  legacy bare digits, `local` otherwise; `is_steam_id()` delegates to
  it. `steam-<non-digits>` is not Steam (`steam_appid` returns `""`),
  so Steam-only actions refuse it.
- Every external Steam use derives the AppID: Steam API/web URLs,
  ProtonDB, SteamGridDB, `steam://rungameid/`, `compatdata`,
  `appmanifest_<n>.acf`, shader dirs, Steam's compat-tool config,
  protontricks and the fresh-prefix guard.
- Input boundaries canonicalize: `--appid`, the Steam environment
  variables (`STEAMAPPID`, `SteamAppId`, `STEAM_APP_ID`) and a numeric
  `STEAM_COMPAT_DATA_PATH` basename become `steam-<n>`; local IDs pass
  through, so a numeric shortcut keeps working.
- A non-Steam game added to Steam reaches the launcher through its
  numeric shortcut ID. When no `steam-<n>.toml` exists, the launcher
  reads `shortcuts.vdf` (read-only; `vdf` is a runtime dependency) and
  maps the shortcut's `Exe` to the single `local-*` config with that
  executable, so the local config applies. Unknown IDs, a missing
  executable or an ambiguous match keep the `steam-<n>` behaviour.
- Creation points emit canonical IDs: local games, `list_games`, STL
  import and the clone dialog.

## Migration

`config.migrate_ids()` runs at GUI startup, before a launcher target
loads, on `--migrate-ids` and after `--import`. A numeric config
(`570.toml`) becomes `steam-570.toml`, rewriting `general.appid` in the
live config and every profile; a legacy bare local ID becomes
`local-<slug>`. Profiles and the artwork directories, winetricks state,
the per-game log and history records move with the config; the artwork
cache keeps its existing numeric keys, so downloaded grids survive. The
pass is idempotent, skips games whose running record is alive, refuses
to overwrite an existing target (warn) and logs every rename. There is
no dual-read fallback: after migration only canonical files exist (the
project's no-shims policy).

## Rejected alternatives

- **Bare digit IDs plus an origin column in the config.** A second
  numeric origin collides with Steam AppIDs, and the origin would have
  to be written on every creation path and kept in sync with IDs already
  stored in shortcuts, history and logs.
- **A dual-read shim for legacy numeric files.** The project already
  refuses config shims pre-1.0; one rename at startup keeps a single
  code path.
