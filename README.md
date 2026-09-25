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
- Custom command prefix (innermost wrapper, e.g. `zink-run`; missing binary aborts launch)
- Global defaults (`defaults.toml`) as a template: copied into new games on add/reset
- Feral `gamemoderun` + CachyOS `game-performance`
- `gamescope`, `mangohud` (config file picker sets `MANGOHUD_CONFIGFILE`)
- `ludusavi` via `wrap` (`--infer steam` or `--name`, `--no-restore`/`--no-backup`, `--gui`;
  real game exit code recovered through a sentinel file)
- Pre-launch/post-exit commands (executable + args, `shell=False`, with `run_in_shell` opt-in)
- Night Light: KDE via persistent `inhibit/uninhibit` holder, GNOME via `gsettings`

## Config (XDG)

`$XDG_CONFIG_HOME/tksteamlaunch/games/<appid>.toml` (e.g. `~/.config/...`),
storing each game's complete config. `defaults.toml` is only a template for
new games — editing it never changes existing games.
Per-game log at `$XDG_STATE_HOME/tksteamlaunch/games/<appid>.log` plus a
one-line entry per run in `$XDG_STATE_HOME/tksteamlaunch/launcher.log`.

## Deps and licenses

- `PySide6` (LGPLv3, fine with GPLv3 in the combined work) — GUI only
- `vdf` (MIT) — GUI/Steam reading only
- `jeepney` (MIT) — KDE NightLight holder
- External calls (`gamemode`, `gamescope`, `mangohud`, `ludusavi`, `qdbus6`) via subprocess, no linking.

## Dev without pip

No `pip` on the system (e.g. CachyOS): the launcher code uses stdlib only,
and dev tools come from system packages:

```bash
sudo pacman -S python-pytest ruff
python3 -m pytest tests/   # full suite (needs PySide6 for GUI smoke tests)
ruff check src/ tests/     # lint; see [tool.ruff] in pyproject.toml
PYTHONPATH=src python3 -m tksteamlaunch.launcher --help
```

The launcher itself stays dependency-free on purpose (it runs on every
game start); only the GUI needs PySide6 and helpers need vdf/jeepney.
Breaking config changes are recorded in `CHANGELOG.md`.

## AI assistance

This project is developed with AI assistance (OpenCode + Muse Spark),
reviewed by the maintainer. Every commit carries a `Co-Authored-By` trailer;
a local `commit-msg` hook (see `scripts/git-hooks/`, enabled via
`git config core.hooksPath scripts/git-hooks`) adds it automatically.
