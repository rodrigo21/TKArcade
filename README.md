# TKArcade

Minimal Steam launch wrapper (inspired by steamtinkerlaunch), in Python 3.12+.

GPLv3-or-later (SPDX `GPL-3.0-or-later`).

## Install

Pick one:

```bash
# run as an isolated tool (needs uv once: https://astral.sh/uv/install.sh)
uv tool install git+https://github.com/rodrigo21/TKArcade

# or with pipx
pipx install git+https://github.com/rodrigo21/TKArcade.git

# or build the local Arch package (needs base-devel + depends in the PKGBUILD)
cd packaging/arch/tkarcade && makepkg -si
```

This installs `tkarcade`: the launcher for Steam Launch Options
(`tkarcade %command%`) and, without arguments, the settings GUI
(`--gui` forces it, `--cli` forbids it). External helpers (GameMode,
Gamescope, MangoHud, Ludusavi, `protontricks`) are optional and come
from your distro.

The GUI needs PySide6 (Qt) 6.12 or newer: 6.12.0 carries the fixes for
CVE-2026-8168 (SVG), CVE-2026-105923 (VectorImage) and CVE-2026-15037
(QDom). Tool and AppImage installs resolve it from PyPI; the Arch
package already ships 6.12.

## Steam usage

Set the game's Launch Options to one of:

```
tkarcade %command%
tkarcade --menu %command%     # pre-launch menu (Launch / Settings / Cancel)
```

The AppID resolves automatically from the Steam environment. Logs go to
`$XDG_STATE_HOME/tkarcade/games/<appid>.log` (full) plus a one-line
entry per run in `launcher.log`.

## Local games

Games added with **Add → Local** keep their own origin. `[general]
environment` says how the game runs: `native` (a Linux build), `wine`
or `umu` for local games; Steam games use `proton` (Steam's Proton) or
`native` (Steam Runtime). The library derives `Origin` (Steam/Local)
and `Platform` (Linux/Windows) from that, and `Runner` names the
environment; there is no separate platform label. A missing or legacy
`auto` value is refused (exit 18): pick the environment in the settings
dialog, there is no detection.

Local Windows games never borrow Steam's Proton. `wine` runs the game
with the configured wine binary (or `wine` from PATH); `umu` runs
`umu-run` with `PROTONPATH` set to an installed Proton build. Proton
installs are discovered in Steam's `compatibilitytools.d` and
`steamapps/common` plus the extra directories in Preferences.
TKArcade only reads what is on disk: install and update Proton with
ProtonPlus/ProtonUp-Qt, Wine with the distro.

Prefixes live in `$XDG_DATA_HOME/tkarcade/prefixes/<appid>` by default.
Preferences moves the base, and a per-game `[runtime] prefix_dir` wins;
`[runtime] prefix_name` uses a readable directory name instead of the
game id (sanitized, still under the base).
`[runtime] wine_binary` and `[runtime] proton_path` override the global
choices per game. `[runtime] winetricks_verbs` runs the host
`winetricks` before launch against an existing prefix (`WINE` is the
chosen Wine binary, or the selected Proton's `files/bin/wine` for umu);
launch once first so the runtime creates the prefix.

`[graphics] dxvk` and `[graphics] vkd3d` copy the newest matching builds
found in the configured DXVK/vkd3d directories into the prefix at launch
and select them through `WINEDLLOVERRIDES`. DXVK covers D3D9/10/11 and
vkd3d-proton covers D3D12, so the two combine (`dxvk = true` plus
`vkd3d = "proton"`); `vkd3d = "wine"` keeps Wine's builtin vkd3d, which
has lower compatibility. A marker (`tkarcade-graphics.json`) records the
copied files; **Remove from prefix** deletes only those.

```toml
[general]
appid = "local-doom"
environment = "umu"

[runtime]
proton_path = "/home/user/GE-Proton10-25"

[graphics]
dxvk = true
vkd3d = "proton"
```

## GUI guide

**Main window** — filter by name/App ID (or issues only); drag column
headers to reorder, right-click them to show/hide columns; right-click
a row for Edit/Copy/Open/Validate/Clone/Remove (multi-select works for
Remove and Reset, multi shows only multi-game actions); Scan Library
batch-adds unconfigured Steam games; Clear Shader Cache per game;
double-click the ProtonDB rating to open its page; the Played column
totals session history (clearable in Session History); the tray
icon lists recent games for quick launch through Steam.

**Game dialog** — tabs for General, Launch (executable, prefix, extra
args, working directory, pre-launch menu, pre/post commands),
Environment (variables + curated presets), Compatibility (Steam Proton
settings, or the Windows runtime for local games: Wine binary or umu
Proton, prefix, DXVK and vkd3d layers), Performance (GameMode, MangoHud, RT
upscaler), Display (Gamescope, monitor mode), System (notifications,
idle suspend, night light, audio, Ludusavi saves) and Artwork/Notes. The
footer shows the live wrapper summary and a launch-command preview.

**Profiles** — named snapshots per game. Selecting one changes what
launches; saving with a profile active writes the profile (Game
Defaults stays pristine). `Save As...`/`Clone...` manage profiles.

**Global Defaults...** — template copied into new games and by
per-game `Reset to Global Defaults` (persists immediately, with
confirmation). Game files always store complete snapshots; unknown
keys are preserved. Files carry a `config_version` stamp; newer files
warn instead of silently resetting.

## Config files (XDG)

* `$XDG_CONFIG_HOME/tkarcade/games/<appid>.toml` — per-game snapshot.
* `$XDG_CONFIG_HOME/tkarcade/profiles/<appid>/<name>.toml` — profiles.
* `$XDG_CONFIG_HOME/tkarcade/defaults.toml` — new-game template only.
* `$XDG_DATA_HOME/tkarcade/prefixes/<appid>/` — local Windows prefixes
  (default base; Preferences can move it, per-game `runtime.prefix_dir`
  wins, `runtime.prefix_name` picks a readable directory name).
* `$XDG_STATE_HOME/tkarcade/games/<appid>.log` and `launcher.log`.
* `$XDG_CACHE_HOME/tkarcade/` — e.g. the ProtonDB tier cache.

Export/import everything with `tkarcade --export FILE` /
`--import FILE` (or the GUI buttons). `tkarcade --migrate-ids` renames
local AppIDs written by older versions of the slug rules (the GUI does
it on startup); the config, profiles and artwork move together.

## Exit codes

0 ok (the game's own code when it runs); 10 AppID not resolved;
11 empty game command; 12 pre-launch hook failed; 13 game executable
not found; 14 custom prefix, wine/umu runtime or Proton install not
found; 15 display needed but missing; 16 export/import failed;
17 validation issues found; 18 environment not set (or invalid for the
game's origin).
See `tkarcade --help` and `man tkarcade` (man ships in the Arch packages).

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
