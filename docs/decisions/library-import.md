# Library import (Lutris, Faugus)

Status: implemented (2026-11-26).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: bring an installed Lutris or Faugus library into TKArcade
without writing to the other launcher's files. A new game gets a live
config, a game already in the library gets a named profile, and the
user picks the rows from a checklist.

## Evidence

**Lutris** keeps the library in `$XDG_DATA_HOME/lutris/pga.db` (Flatpak:
`~/.var/app/net.lutris.Lutris/data/lutris/pga.db`) and one YAML per game
under the config dir (`games/<configpath>.yml`, falling back to the data
dir). The DB has `name`, `runner`, `installed`, `configpath`, `service`,
`service_id` and the legacy `steamid`/`gogid`/`humblestoreid` columns;
`executable` is usually NULL for Wine games, so the exe and prefix come
from the YAML (`game.exe`, `game.args`, `game.working_dir`,
`game.prefix`, `game.appid`, `system.env`, `system.mangohud`,
`system.gamemode`, the hooks and `wine.version`). Categories live in
`categories` + `games_categories`. Lutris writes the YAML with
`yaml.safe_dump`, so long scalars may wrap.

**Faugus** keeps `$XDG_DATA_HOME/faugus-launcher/games.json` (Flatpak
path under `~/.var/app/io.github.Faugus.faugus-launcher/data/`), with
`title`, `gameid`, `path`, `prefix`, `runner`, `launch_arguments`,
`game_arguments`, `mangohud`, `gamemode`, `no_sleep`, `category`,
`pre_launch` and `post_launch`. A Windows game runs through `umu-run`
with `PROTONPATH` and `WINEPREFIX`, like TKArcade's `umu` runtime.

**The prefix gap.** `prefix_dir()`/`prefix_target()` always resolve a
local WINEPREFIX to `<base>/<folder>` and normalise the folder name.
Reusing a foreign prefix through that rule would move the path and lose
the other launcher's saves.

## Decisions

1. **One module, two readers.** `library_import.py` is GUI/helper-only:
   stdlib plus a lazy `PyYAML` import for the Lutris YAML. The launcher
   never imports it. The Lutris DB is opened with a read-only URI;
   neither `pga.db` nor `games.json` is written.
2. **Exact prefixes.** `[runtime] prefix_exact = true` makes `prefix`
   the WINEPREFIX itself. `prefix_target()` returns it with
   `managed=False`, so cleanup, Remove-game prefix deletion and the ID
   migration never move or delete it. `prefix_name` is ignored there.
   Steam games keep the compatdata rule.
3. **Store identity.** A non-Steam store entry keeps its `local-<slug>`
   ID and records `[store] kind` + `[store] id`. A Steam entry targets
   the existing `steam-<appid>` and records no store. The section is
   inert until the 2.0 origin work, but makes a re-import idempotent.
4. **Existing games become profiles.** A matched game gets a
   `lutris`/`faugus` profile, the same rule as the SteamTinkerLaunch
   import; its live config is untouched. A new game gets the live
   config. Re-importing replaces only that source's profile.
5. **Categories, not metadata tags.** Lutris categories and Faugus
   `category` go to `[general] categories`, the sidebar taxonomy.
   `[metadata] tags` is provider/editing data and has no foreign
   source, so the "Library import tag mapping" item is closed.
6. **PyYAML.** `PyYAML>=6` (MIT) is a declared dependency, imported
   only by the reader. A source tree without it still starts the GUI
   and reports that Lutris configs cannot be read.
7. **The selection is explicit.** The page lists every usable row: new
   games checked, already configured games unchecked and marked
   `In Library` with an information icon, unsupported runners disabled
   with a warning icon, the `Unavailable` label and the reason in the
   tooltip. Select All/None and Enter act on the checked rows only.
   Uninstalled Lutris entries do not appear.
8. **No network in the import.** New games get no automatic artwork or
   metadata download; the report lists what was skipped and why.
9. **No stat on foreign paths.** Matching compares paths as text
   (`expanduser` + `normpath`), never `resolve()`/`exists()`: a stat on
   an automounted external drive can block the process in `D` state.
   `/proc/self/mountinfo` detects an autofs mount that is still waiting
   for its filesystem, and the row is disabled with a warning and a
   tooltip ("External drive not connected"). The reader and the import
   run on a worker thread, so a slow library never freezes the window.

## Mapping

`name`/`title`, `exe`/`path`, args, working directory, env, MangoHud,
GameMode, hooks (shell mode), `no_sleep` -> `[session] inhibit_idle`,
categories, and the runtime: Lutris `wine` -> `wine` with the resolved
Lutris Wine binary, Faugus Proton path -> `umu` with `PROTONPATH`,
`linux`/`Linux-Native` -> `native`, Steam entries -> `steam-<appid>`.
Values containing `$GAMEDIR`, `$HOME`, `$USER` or `~` are expanded; a
missing path is kept and reported. Everything else is dropped and
counted: emulator/web runners, `gamescope`, `disable_runtime`, `addapp`,
`lossless`, `discord_rpc`, `protonfix`, `steamgriddb_id`,
`prelaunch_wait` and the like.

## Matching and idempotency

Order: a local config with the same `[store] kind` + `id`; a Steam
target (`steam-<service_id>`/`steam-<path>`) that Steam lists or that has
a config; a unique local config with the same resolved executable; a
unique local config with the same normalised name. An ambiguous match
imports as a new game and says so; it never guesses. Duplicate
candidates are merged before the list is shown.

## Rejected alternatives

- **A hand-written YAML subset parser.** The Lutris writer wraps long
  scalars and quotes values; a subset parser would silently misread
  paths. PyYAML is small, MIT and used only by the GUI reader.
- **Importing without the prefix.** The game would launch into a new
  prefix and lose the other launcher's saves.
- **Overwriting an existing live config.** A profile is reversible and
  keeps the user's own settings.
- **Mapping foreign categories into `tags.toml`.** Tags are the online
  metadata list, not the sidebar taxonomy.
- **A silent all-or-nothing import.** The checklist and the report make
  the skipped rows visible.

## Consequences

- The prefix stays shared with the other launcher; running both at once
  is the user's call, as with any shared WINEPREFIX.
- Re-import overwrites the source's own profile.
- PyYAML is part of the package and the AppImage.
- The dialog now has five source buttons; the offscreen screenshot and
  the QML case cover the layout.
