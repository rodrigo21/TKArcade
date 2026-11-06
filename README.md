# TKArcade

Steam and local game launch wrapper (inspired by steamtinkerlaunch), in Python 3.12+.

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
`$XDG_STATE_HOME/tkarcade/games/<gameid>.log` (full) plus a one-line
entry per run in `launcher.log`.

## Local games

Games added with **Add → Local** keep their own origin. `[runtime] type`
says how the game runs: `native` (a Linux build), `wine` or `umu` for
local games; Steam games use `proton` (Steam's Proton) or `native`
(Steam Runtime). The library derives `Origin` (Steam/Local) and
`Platform` (Linux/Windows) from it, and the `Runtime` column shows a
compact runtime label (`Native`, `Wine`, `UMU`, `Steam Proton`, plus
`SLR` and `SLR 1.0`–`SLR 4.0` for the Steam Linux Runtimes); there is
no separate platform label. A Steam game with no configured
runtime prompts on launch to configure it: the settings open on the
Runtime tab with the type inferred from `%command%` preselected
(`proton` with Proton's `waitforexitandrun` or a `proton` binary,
`native` otherwise). Not now launches with that inferred type and saves
nothing, so the prompt returns next launch; the inference is also the
fallback when the settings cannot start. An unset or invalid pairing is
still refused for local games (exit 18): pick the runtime in the
settings dialog. The old `[general] environment` key is ignored.

Local Windows games never borrow Steam's Proton. `wine` runs the game
with the configured wine binary (or `wine` from PATH); `umu` runs
`umu-run` with `PROTONPATH` set to an installed Proton build. Proton
installs are discovered in Steam's `compatibilitytools.d` and
`steamapps/common` plus the extra directories in Preferences.
TKArcade only reads what is on disk: install and update Proton with
ProtonPlus/ProtonUp-Qt, Wine with the distro.

Prefixes live in `$XDG_DATA_HOME/tkarcade/prefixes/<name>` by default.
Preferences moves the base and a per-game `[runtime] prefix` overrides
it, but both are only the **base**: the WINEPREFIX of a local game is
always a subfolder of it. The subfolder is `[runtime] prefix_name` when
set (the GUI pins it from the game name on save, so renaming the game
never moves the prefix), else the normalised game name (`TK's
good-game_1` → `TKsGoodGame1`), else the AppID.
`[runtime] tool` overrides the global choice per game, and its meaning
follows `[runtime] type`: a Steam compat tool for `proton`, the
Wine binary for `wine`, the `PROTONPATH` install for `umu`. The same
applies to `[runtime] prefix`: Steam's compatdata dir for `proton` (used
as-is, no subfolder), the WINEPREFIX *base* for local games.
`[runtime] winetricks_verbs` runs the host
`winetricks` before launch against an existing prefix (`WINE` is the
chosen Wine binary, or the selected Proton's `files/bin/wine` for umu);
launch once first so the runtime creates the prefix. In the GUI,
`Add…` searches `winetricks list-all` and appends a verb to that field,
the Prefix section lists the verbs the prefix already has (from its
`winetricks.log`), and `Protontricks…`/`Winetricks…` opens the
interactive tool against the game's own prefix. A Steam game with a
custom `[runtime] prefix` uses `winetricks` too (protontricks only
targets Steam's own dir): the game's Proton supplies `WINE` and the
custom container's `pfx` is the `WINEPREFIX`.

`[runtime] steam_runtime` runs a **local Linux** game inside a Steam
Linux Runtime through `umu-run` (`scout`, `soldier`, `sniper` or
`steamrt4`; empty = the plain host). umu builds a passthrough
compatibility tool for native apps, so the launch only adds
`PROTONPATH=umu-<name>` and `GAMEID=tkarcade-<gameid>`: no WINEPREFIX and
no graphics layer. The field is ignored for Steam games (Steam picks
their runtime) and for Wine/umu games. Runtimes live in
`$XDG_DATA_HOME/umu/` and umu downloads a missing one on the first
launch that asks for it — the dialog says so and `--validate` prints a
`(note)`, never an issue; only a missing `umu-run` refuses (exit 14).

`[graphics] dxvk` and `[graphics] vkd3d` copy a matching build found in
the configured DXVK/vkd3d directories into the prefix at launch and
select it through `WINEDLLOVERRIDES`. The version is per game:
`dxvk_version` / `vkd3d_version`, with empty meaning the newest installed
version. Managed downloads land in `$XDG_DATA_HOME/tkarcade/runtimes`;
that directory and the ones set in Preferences are scanned, and
TKArcade does not read another launcher's default layout. Preferences
can download the latest DXVK/vkd3d-proton release, and archives dropped
into `$XDG_CACHE_HOME/tkarcade/archives` are extracted on the next GUI
scan. **Manage Versions…** lists the managed builds with where each came
from, installs any release (not only the latest) and a pasted archive URL,
and deletes managed versions; `dxvk_repo` / `vkd3d_repo` point a layer at
a GitHub fork such as DXVK-Sarek instead of the official repository. The
launcher never downloads or unpacks anything. DXVK covers
D3D9/10/11
and vkd3d-proton covers D3D12, so the two combine (`dxvk = true` plus
`vkd3d = "proton"`); `vkd3d = "wine"` keeps Wine's builtin vkd3d, which
has lower compatibility. A selected version that is no longer installed
is reported by the dialog and `--validate`; the layer falls back to
Wine's builtin instead of silently choosing another version. A marker
(`tkarcade-graphics.json`) records the copied files; **Remove from
prefix** deletes only those. Only a plain Wine prefix takes the layers:
`umu` and Steam's Proton ship their own DXVK/vkd3d, which own the DLL
search path, so the section is hidden for them and `[graphics]` is
ignored by design (`docs/decisions/graphics-layers.md`). To change those
versions, pick a different Proton build — the per-game compat tool in
Steam, or another runtime for a local umu game.

```toml
# Local Windows game under Wine, with the graphics layers.
[general]
gameid = "local-doom"

[runtime]
type = "wine"
tool = "/usr/bin/wine"
prefix_name = "DoomEternal"

[graphics]
dxvk = true
dxvk_version = "v2.6.2"   # empty = newest installed
vkd3d = "proton"
vkd3d_version = "v2.13"   # empty = newest installed
```

```toml
# Local Linux game inside a Steam Linux Runtime.
[general]
gameid = "local-openra"

[runtime]
type = "native"
steam_runtime = "sniper"
```

## GUI guide

**Main window** — filter by name/ID (or issues only), by source
(All Games/Steam/Local under the Origins section) or by a category in
the Categories section below it, which lists each category with its
icon and game count and keeps it at `(0)` until deleted in its editor
(games, icon, delete); drag
column headers to reorder, right-click them to show/hide columns;
right-click a row for Edit/Copy/Open/Validate/Clone/Remove (multi-select
works for Remove and Reset, multi shows only multi-game actions). Copy
Game ID copies the canonical ID; Steam games also offer Copy Steam AppID
for the numeric one. The Open actions follow the game's origin and
runtime: local games open their executable's folder (or `launch_cwd`),
only Wine/UMU games offer a prefix, and Steam adds ProtonDB and its
shader cache. Scan
Library batch-adds unconfigured Steam games; Remove Uninstalled Games
drops the configs whose Steam install entry or local executable is gone
(listed in a confirmation first); games with validation issues carry an
error or warning badge in the table, card and icon views, whose tooltip
lists them; Clear Shader Cache per
game; double-click the ProtonDB rating to open its page; the Played
column totals session history (clearable in Session History); the tray
icon lists recent games for quick launch through Steam.

The default table layout shows Release Date, Origin, Platform, Played,
Last Played and Installed after the game name; Runtime, Wine, ProtonDB,
Game ID and Install Dir start hidden (header menu or Configure
Columns). Release Date shows the manual `[metadata] date` first and
otherwise the Steam store release date, cached for 30 days; Installed
uses the `[general] installed_at` stamp written on the first save, or
the game's `.toml` birth time for older configs. Session History shows
the same installed value.

**Game dialog** — tabs for General (the game, optional `version`/`date`/
`tag` metadata shown as name suffixes, categories and launch settings),
Commands (variables, curated presets and the pre/post commands),
Runtime
(the runtime selector and tool, the Steam Linux Runtime of a local
native game, prefix with its installed and pending winetricks verbs plus
the interactive protontricks/winetricks window, Create for a missing
prefix — the Steam custom dir or a local WINEPREFIX, made only after a
confirmation, while Open never creates one — DXVK and vkd3d layers,
Proton debug switches), Performance
(GameMode, MangoHud, RT upscaler), Display (Gamescope, monitor mode),
System (notifications, idle suspend, network, night light, audio,
Ludusavi saves) and Artwork/Notes. The Artwork section picks the manual
icon/cover/banner files, an optional Artwork Source AppID (any Steam
AppID whose art overrides the game's own), the per-game download
provider (Steam first by default, SteamGridDB as fallback) and
Fetch/Clear; a local game without an AppID is looked up by name on
SteamGridDB and a stored choice keeps the same art across fetches. A
local game whose icon slot is still empty shows the icon embedded in its
executable, extracted once into the cache. Above the AppID row, framed
thumbnails (icon, banner, cover, shortest first) show what the list and
the cards draw, at the image's own size; clicking one picks that file and
the buttons under it download an image from a URL or clear the slot,
while the hover tooltip shows the picture larger with its origin. The
dialog opens at half the screen width and the full usable height. The
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

* `$XDG_CONFIG_HOME/tkarcade/games/<gameid>.toml` — per-game snapshot.
* `$XDG_CONFIG_HOME/tkarcade/profiles/<gameid>/<name>.toml` — profiles.
* `$XDG_CONFIG_HOME/tkarcade/defaults.toml` — new-game template only.
* `$XDG_DATA_HOME/tkarcade/prefixes/<name>/` — local Windows prefixes
  (default base; Preferences can move it, per-game `runtime.prefix` is
  the base, and the folder is `runtime.prefix_name`, else the
  normalised game name, else the Game ID).
* `$XDG_STATE_HOME/tkarcade/games/<gameid>.log` and `launcher.log`.
* `$XDG_CACHE_HOME/tkarcade/` — e.g. the ProtonDB tier cache.

Game IDs are origin-prefixed: Steam games use `steam-<appid>` and local
games `local-<slug>`, so a future store with numeric IDs cannot collide
with Steam AppIDs. Export/import everything with
`tkarcade --export FILE` / `--import FILE` (or the GUI buttons).
`tkarcade --migrate-ids` renames IDs written by older versions (bare
Steam AppIDs and the old local slug rules; the GUI and the launcher do
it on startup); the config, profiles, winetricks state, logs, history
and local artwork move together.

## Exit codes

0 ok (the game's own code when it runs); 10 AppID not resolved;
11 empty game command; 12 pre-launch hook failed; 13 game executable
not found; 14 custom prefix, wine/umu runtime or Proton install not
found; 15 display needed but missing; 16 export/import failed;
17 validation issues found; 18 runtime not set (local games) or invalid
for the game's origin.
See `tkarcade --help` and `man tkarcade` (man ships in the Arch packages).

## Troubleshooting

* **Game starts and quits instantly** — check the per-game log; a custom
  prefix or env var is the usual suspect. `--dry-run` prints the final
  command without running it.
* **Ludusavi does nothing** — the game must exist in Ludusavi (manifest
  or custom entry); use `Open Ludusavi...` in the Saves section (or the
  hamburger menu) and the `Check Coverage` button. The `wrap` exit code
  is always 0; the real game code is recovered internally and logged.
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
