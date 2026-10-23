# Friendly prefix names (`runtime.prefix_name`)

Status: implemented. Decision record for the per-game prefix
directory name.

## Problem

Local Windows games get `$XDG_DATA_HOME/tkarcade/prefixes/<appid>`
(or whatever `Preferences.prefix_base` points at). Reading the base is
easy only for the user who remembers which AppID belongs to which game,
and sharing one prefix between games meant typing the full path into
`runtime.prefix_dir`.

## Contract

```toml
[runtime]
prefix_name = "Doom Eternal"  # friendly directory under the prefix base
prefix_dir  = ""              # full path; wins over prefix_name
```

Resolution (`config.prefix_dir(appid, per_game, base, name)`):

1. `prefix_dir`, when set, is used verbatim (as before).
2. Otherwise `<base>/<safe prefix_name>`, base being
   `Preferences.prefix_base` or the built-in XDG location.
3. Otherwise `<base>/<safe appid>` — the previous behaviour, so existing
   configs and their directories keep working (no migration).

`safe_stem` sanitizes the name into one path component; a name that
sanitizes to nothing (`../`, `...`, blanks) falls back to the AppID
instead of escaping or creating `unknown`.

## Scope

Local Wine/UMU games only. Steam keeps `compatdata` (or
`proton.wine_prefix`), which Steam itself manages and which the launcher
does not own.

## Behaviour

- Sharing a prefix is allowed on purpose: two games may name the same
  directory. Settings reports the other games using it ("Shared with:
  …") and the picker marks them, but Save never refuses the name.
- Changing the name is config-only. Nothing on disk is moved or deleted;
  the hint says whether the resolved directory already exists or will be
  created at launch. The existing `Clear…` action remains the explicit
  destructive path for a full path override.
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
