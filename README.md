# TKSteamLaunch

Minimal Steam launch wrapper (inspired by steamtinkerlaunch), in Python 3.12+.

GPLv3-or-later (SPDX `GPL-3.0-or-later`).

## Install

Pick one:

```bash
# run as an isolated tool (needs uv once: https://astral.sh/uv/install.sh)
uv tool install git+https://github.com/rodrigo21/TKSteamLaunch

# or with pipx
pipx install git+https://github.com/rodrigo21/TKSteamLaunch.git

# or build the local Arch package (needs base-devel + depends in the PKGBUILD)
cd packaging/arch/tksteamlaunch && makepkg -si
```

This installs `tksteamlaunch`: the launcher for Steam Launch Options
(`tksteamlaunch %command%`) and, without arguments, the settings GUI
(`--gui` forces it, `--cli` forbids it). External helpers (GameMode,
Gamescope, MangoHud, Ludusavi, `protontricks`) are optional and come
from your distro.

## Steam usage

Set the game's Launch Options to one of:

```
tksteamlaunch %command%
tksteamlaunch --menu %command%     # pre-launch menu (Launch / Settings / Cancel)
```

The AppID resolves automatically from the Steam environment. Logs go to
`$XDG_STATE_HOME/tksteamlaunch/games/<appid>.log` (full) plus a one-line
entry per run in `launcher.log`.

## GUI guide

**Main window** — filter by name/App ID (or issues only); drag column
headers to reorder, right-click them to show/hide columns; right-click
a row for Edit/Copy/Open/Validate/Remove (multi-select works for Remove
and Reset); double-click the ProtonDB rating to open its page; the tray
icon lists recent games for quick launch through Steam.

**Game dialog** — tabs for General, Environment (variables + curated
presets), Pre/Post Commands, Performance, Display (Gamescope, MangoHud,
RT upscaler, monitor mode), Ludusavi, System, Wine/Proton and Notes.
The footer shows the live wrapper summary and a launch-command preview.

**Profiles** — named snapshots per game. Selecting one changes what
launches; saving with a profile active writes the profile (Game
Defaults stays pristine). `Save As...`/`Clone...` manage profiles.

**Global Defaults...** — template copied into new games and by
per-game `Reset to Global Defaults` (persists immediately, with
confirmation). Game files always store complete snapshots; unknown
keys are preserved. Files carry a `config_version` stamp; newer files
warn instead of silently resetting.

## Config files (XDG)

* `$XDG_CONFIG_HOME/tksteamlaunch/games/<appid>.toml` — per-game snapshot.
* `$XDG_CONFIG_HOME/tksteamlaunch/profiles/<appid>/<name>.toml` — profiles.
* `$XDG_CONFIG_HOME/tksteamlaunch/defaults.toml` — new-game template only.
* `$XDG_STATE_HOME/tksteamlaunch/games/<appid>.log` and `launcher.log`.
* `$XDG_CACHE_HOME/tksteamlaunch/` — e.g. the ProtonDB tier cache.

Export/import everything with `tksteamlaunch --export FILE` /
`--import FILE` (or the GUI buttons).

## Exit codes

0 ok (the game's own code when it runs); 10 AppID not resolved;
11 empty game command; 12 pre-launch hook failed; 13 game executable
not found; 14 custom prefix binary not found; 15 display needed but
missing; 16 export/import failed; 17 validation issues found.
See `tksteamlaunch --help` and `man tksteamlaunch` (man ships in the Arch packages).

## Troubleshooting

* **Game starts and quits instantly** — check the per-game log; a custom
  prefix or env var is the usual suspect. `--dry-run` prints the final
  command without running it.
* **Ludusavi does nothing** — the game must exist in Ludusavi (manifest
  or custom entry); use `Open Ludusavi...` and the `Check Coverage`
  button. The `wrap` exit code is always 0; the real game code is
  recovered internally and logged.
* **Night Light stuck off** — a leaked inhibitor holder may survive a
  crash: `pkill -f nightlight_holder`.
* **GUI looks unthemed under Steam** — the editor runs in a subprocess
  with Steam-runtime library paths filtered out; child stderr lands in
  the per-game log.
* **Dialog warns about unreadable settings** — the file has invalid TOML
  (or needs a newer app); defaults are shown and saving overwrites it.

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) (venv, tests, packaging,
AppImage, releases).
