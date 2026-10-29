# Friendly prefix names (`runtime.prefix_name`)

Status: implemented. Decision record for the per-game prefix
directory name.

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

Local Windows games get `$XDG_DATA_HOME/tkarcade/prefixes/<appid>`
(or whatever `Preferences.prefix_base` points at). Reading the base is
easy only for the user who remembers which AppID belongs to which game,
and sharing one prefix between games meant typing the full path into
`runtime.prefix_dir`.

## Contract

```toml
[runtime]
prefix      = "/mnt/games/prefixes"  # base; empty = Preferences prefix_base
prefix_name = "Doom Eternal"         # folder under the base
```

Resolution (`config.prefix_dir(appid, per_game, base, name, game_name)`):

1. Base: `[runtime] prefix`, else `Preferences.prefix_base`, else the
   built-in XDG location.
2. Folder: `<safe prefix_name>`, else the normalised game name, else
   `<safe appid>`.
3. The local WINEPREFIX is always `<base>/<folder>`; no local key names
   the directory itself.

`safe_stem` sanitizes the name into one path component; a name that
sanitizes to nothing (`../`, `...`, blanks) falls back to the AppID
instead of escaping or creating `unknown`.

## Scope

Local Wine/UMU games only. Steam keeps `compatdata` (or the per-game
`[runtime] prefix`), which Steam itself manages and which the launcher
does not own.

## Behaviour

- Sharing a prefix is allowed on purpose: two games may name the same
  directory. Settings reports the other games using it ("Shared with:
  …") and the picker marks them, but Save never refuses the name.
- Changing the name is config-only. Nothing on disk is moved or deleted;
  the hint says whether the resolved directory already exists or will be
  created at launch. `Clear…` is the explicit destructive path: it
  deletes the resolved `<base>/<folder>` for this game (never a prefix
  another config still points at).
- The picker (`prefixChoices`) lists only directories that look like a
  Windows prefix (`drive_c/` plus `system.reg`) under the base,
  ignoring strays and files; `iter_prefixes` never raises.

## Surface

- `config.py`: field, load, `SECTION_KEYS["runtime"]`, `prefix_dir`
  parameter.
- `launcher.py` (`_runtime_paths`, the winetricks pre-pass) and
  `gui/model.py` (`runtimeOptions`, `graphicsState`, `removeGraphics`,
  `prefixNameState`, `prefixChoices`) resolve the same way.
- `xdg.py`: `is_wine_prefix`, `iter_prefixes`.
- `GameSettings.qml`: "Prefix name:" field with a `Choose…` dialog, the
  resolved-directory hint and `runtime_prefix_name` in `collect()`.
