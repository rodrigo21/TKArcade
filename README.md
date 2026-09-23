# TKSteamLaunch

Minimal Steam launch wrapper (inspired by steamtinkerlaunch), in Python 3.12+.

GPLv3-or-later. See `LICENSE`.

## Steam usage

Game Launch Options:

```
tksteamlaunch %command%
```

## MVP features

- Per-game env vars (table + bulk edit)
- Custom executable (Proton prefix swap or native argv[0], auto-detected)
- Global defaults (`defaults.toml`) with per-game sparse overrides
- Feral `gamemoderun` + CachyOS `game-performance`
- `gamescope`, `mangohud` (config file picker sets `MANGOHUD_CONFIGFILE`)
- `ludusavi` via `wrap` (`--infer steam` or `--name`, `--no-restore`/`--no-backup`, `--gui`)
- Pre-launch/post-exit commands (executable + args, `shell=False`, with `run_in_shell` opt-in)
- Night Light: KDE via persistent `inhibit/uninhibit` holder, GNOME via `gsettings`

## Config (XDG)

`$XDG_CONFIG_HOME/tksteamlaunch/games/<appid>.toml` (e.g. `~/.config/...`),
storing only values that differ from `defaults.toml`.
Per-game log at `$XDG_STATE_HOME/tksteamlaunch/games/<appid>.log` plus a
one-line entry per run in `$XDG_STATE_HOME/tksteamlaunch/launcher.log`.

## Deps and licenses

- `PySide6` (LGPLv3, fine with GPLv3 in the combined work) — GUI only
- `vdf` (MIT) — GUI/Steam reading only
- `jeepney` (MIT) — KDE NightLight holder
- External calls (`gamemode`, `gamescope`, `mangohud`, `ludusavi`, `qdbus6`) via subprocess, no linking.

## Dev without pip

No `pip` on the system (e.g. CachyOS): the launcher code uses stdlib only.
Tests: `python3 -m py_compile` + `PYTHONPATH=src python3 -m tksteamlaunch.launcher --help`.
