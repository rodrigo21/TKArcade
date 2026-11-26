# Import mapping onto native options

Status: landed (2026-11-26).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The first library import (`decisions/library-import.md`) moved Lutris and
Faugus entries into live configs, but four mappings were wrong:

- A trailing `[version]` in the source name stayed in the name. The GUI
  only splits it when the game is saved, so an imported game showed
  `Game [v1.2]` until its dialog was opened and saved.
- `to_gameconfig()` started from a blank `GameConfig`, not Global
  Defaults, and then wrote `False` over every launcher toggle: new games
  arrived without the default MangoHud, Gamescope, Gamemode, session and
  env settings.
- Lutris `gamescope` and its options were ignored, so 80 of the sampled
  games lost their compositor settings.
- `MANGOHUD`, `MANGOHUD_DLSYM` and `MANGOHUD_CONFIGFILE` stayed as
  `[env]` vars although the app has native `[mangohud]` options; a
  per-game MangoHud configuration never reached the picker.

## Decision

1. **The name splits at read time.** `LibraryGame.version` holds the
   trailing `[version]`; the plain name then drives matching, the new
   `local-*` ID and the config, and `[metadata] version` is written for a
   new game. Lutris and Faugus are both split.
2. **The base is the user's config, not a blank object.** A new game
   starts from Global Defaults (`load_defaults()`); a profile for an
   existing game starts from that game's live config.
3. **The source only adds.** The imported value wins for its own fields,
   but a launcher toggle turns a setting on, never off: `mangohud`,
   `gamemode`, `gamescope`, `session.inhibit_idle` and `run_in_shell`
   only become true, and `[env]` merges (imported names win). A source
   without a value keeps the default or the live value.
4. **Gamescope maps onto `[gamescope]`.** `enable` from the Lutris toggle
   and `args` composed like Lutris passes them: window mode, game
   resolution (`-w`/`-h`), output resolution (`-W`/`-H`), `-r` FPS
   limiter, `gamescope_flags` verbatim, `--force-grab-cursor` and
   `--hdr-enabled`. FSR sharpness stays out: it needs the `-F` option
   detection Lutris does at runtime.
5. **MangoHud env vars with an option move to it.** `MANGOHUD=1` enables
   the wrapper, `MANGOHUD_DLSYM=1` adds `--dlsym` to `[mangohud] args`,
   and `MANGOHUD_CONFIGFILE` becomes `[mangohud] config_file` when the
   file lives in `$XDG_CONFIG_HOME/MangoHud` (a filename there); a config
   file elsewhere has no native equivalent and stays in `[env]`. The
   mapped names are removed from `[env]`.
6. **No option, no mapping.** `ENABLE_VKBASALT`, `VKBASALT_CONFIG_FILE`,
   `DXVK_HUD`, `DXVK_CONFIG`, `SDL_VIDEODRIVER`, `DISPLAY`, `RADV_DEBUG`,
   `MESA_LOADER_DRIVER_OVERRIDE`, `PROTON_*` and `LSFG_*` stay env vars
   until the app grows the matching feature.
7. **Already imported games are not rewritten.** Re-importing after
   removing them is the fix; a "refresh from the library" action stays
   future work.

## Consequences

- An imported game now behaves like one added by hand: Global Defaults
  apply, and the source's own values sit on top.
- A source that explicitly disabled MangoHud or Gamescope does not turn
  the default off. The per-game dialog remains the way to disable one.
- A profile created by the import carries the live game's settings, so
  applying it no longer resets the game to built-in defaults.
- The version split changes the new game's ID for a name that carried
  `[version]`; no migration is needed because no such config existed
  before the fix.
