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
Execution tab with the type inferred from `%command%` preselected
(`proton` with Proton's `waitforexitandrun` or a `proton` binary,
`native` otherwise). Not now launches with that inferred type and saves
nothing, so the prompt returns next launch; the inference is also the
fallback when the settings cannot start. An unset or invalid pairing is
still refused for local games (exit 18): pick the runtime in the
settings dialog. The old `[general] environment` key is ignored.

Local Windows games never borrow Steam's Proton. `wine` runs the game
with the Wine build the game selects, else the default build from
Preferences, else `wine` from PATH; `umu` runs `umu-run` with
`PROTONPATH` set to an installed Proton build. Proton installs are
discovered, never configured: the distro tree
(`/usr/share/steam/compatibilitytools.d`, first), then every Steam
library listed in `libraryfolders.vdf` (its `compatibilitytools.d` and
`steamapps/common/Proton*`). Preferences lists what was found and one
button opens ProtonPlus (or ProtonUp-Qt); one build can be marked as
the preselection for the game dialog (a Steam game keeps Steam's own
compat choice). TKArcade only reads what is on disk:
install and update Proton with ProtonPlus/ProtonUp-Qt, Wine with the
distro.

Preferences keeps the Wine builds in one list (`[ui] wine_versions`,
`name=path` entries) with one marked as the default (`wine_default`,
empty = PATH). The builds stay in their system location: nothing is
copied or symlinked, and the first row of the manager is always `wine`
from PATH. The game dialog picks from that list.

Prefixes live in `$XDG_DATA_HOME/tkarcade/prefixes/<name>` by default.
Preferences moves the base and a per-game `[runtime] prefix` overrides
it, but both are only the **base**: the WINEPREFIX of a local game is
always a subfolder of it. The subfolder is `[runtime] prefix_name` when
set (the GUI pins it from the game name on save, so renaming the game
never moves the prefix), else the normalised game name (`TK's
good-game_1` → `TKsGoodGame1`), else the AppID.
`[runtime] tool` overrides the global choice per game, and its meaning
follows `[runtime] type`: a Steam compat tool for `proton`, the Wine
build name from Preferences (a raw path still resolves) for `wine`, the
`PROTONPATH` install for `umu`. The same
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

`[graphics] dxvk` and `[graphics] vkd3d` copy a matching build into the
prefix at launch and select it through `WINEDLLOVERRIDES`. The version is
per game: `dxvk_version` / `vkd3d_version`, with empty meaning the layer
default (`dxvk_default` / `vkd3d_default` in the preferences, itself
empty = newest installed). Builds live in
`$XDG_DATA_HOME/tkarcade/runtimes/<layer>`, one directory per version,
plus the distro trees when they exist (`/usr/share/dxvk` and the
`vkd3d-proton` equivalent, read-only and labelled "System Version") and
any folder registered with **Manage Versions… → Add Folder…** (stored in
`runtimes/.external.json`; the files stay where they are).
Archives dropped into `$XDG_CACHE_HOME/tkarcade/archives` are extracted
on the next GUI scan. The manager lists every build with where each came
from, marks one as the default, installs any release of the chosen
source and a pasted archive URL, and deletes managed versions. After an
install, and on every scan, it keeps the three newest builds it installed
per layer: the default build and any version pinned by a game are never
pruned, and a build dropped into the archive cache, an external folder or
the distro tree is left alone. An `[ui] download_mirror`
(Preferences → Runtime → Download Mirror) is an `https://` prefix
prepended to the GitHub asset URLs, ghproxy style; empty downloads
direct, and a pasted archive URL is never rewritten. The
source is a preset per layer — official (the default), DXVK-Sarek or the
discontinued DXVK-GPLAsync for DXVK — or a custom `owner/repo`.
TKArcade does not read another launcher's default layout, and the
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
shader cache. Remove Uninstalled Games
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

**Game dialog** — six tabs: Details (the game, optional `version`/`date`/
`tag` metadata shown as name suffixes, categories, the identity line, a
ProtonDB rating linking to its page — a local game gets a search
button beside it — one banner artwork preview and the
Notes box at the end), Execution, Commands,
Performance, Display and System.
Developer, publisher, genre, series, age ratings (CERO/ClassInd/ESRB/PEGI
first, the other boards behind a divider and switch), region, status,
description and Notes stay manual, with a lock toggle on each row that
keeps that field out of every download, and a lock button beside the
Game title that locks every field at once. An icon button next to
the Information title opens a window with two tabs. **Metadata** picks
the source (Steam, VNDB or IGDB) and holds the Steam AppID,
VNDB and IGDB identity fields: a known Steam AppID — a Steam game's own,
or a local game's store link — is looked up as the window opens and
leaves no query row, while a local game without one searches the Steam
store by title. A stored VNDB or IGDB id fills the query, an id typed
in place of a title goes straight to the provider, and a title lists
candidates. The answer arrives as preview rows (Apply fills empty
fields, a switch replaces typed ones, the locks win) and writes the
dialog draft; Save persists it. Details shows the identities back as a
"Matches:" line, and a newly added Steam game fills its own store entry
on save: empty fields only, locks respected, tags and release date
included. IGDB needs a free Twitch application (client
id and secret in Preferences); the Twitch console asks for an OAuth
redirect URL, where any public HTTPS address works, because the
download uses the client-credentials grant and never redirects. The
preview also carries a **Tags** row:
Apply writes the online tags into `[metadata] tags`, where Steam
contributes genres, store features and the franchise, IGDB its genres,
franchise, themes and keywords, and VNDB its non-spoiler tags rated 2.0
or more (top 20). Tags are not categories: they stay out of the sidebar
and the category store, and Details lists them next to Series with a
Clear button that empties the list on Save and its own lock.
Execution (launch settings first, then the runtime selector and tool,
the Steam Linux Runtime of a local native game, prefix with its
installed and pending
winetricks verbs plus the interactive protontricks/winetricks window,
Create for a missing prefix — the Steam custom dir or a local WINEPREFIX,
made only after a confirmation, while Open never creates one — DXVK and
vkd3d layers, Proton debug switches), Commands (variables, curated
presets and the pre/post commands), Performance
(GameMode, MangoHud, RT upscaler), Display (Gamescope, monitor mode),
System (notifications, idle suspend, network, night light, audio,
Ludusavi saves). The Description box on Details
fills the space the other sections leave, shrinks to five lines with
the window and scrolls longer text inside its frame. The window's
**Artwork** tab picks the manual
icon/cover/banner/background files, an optional Artwork Source AppID (any
Steam AppID whose art overrides the game's own), the per-game download
provider (Steam, SteamGridDB or IGDB; Steam first by default) and
Fetch/Clear; a local game without an AppID is looked up by name on
SteamGridDB and a stored choice keeps the same art across fetches. IGDB
needs a Twitch application and the IGDB ID that Search Data
saves; it fills the cover and the banner, and its square icon slot
stays with the other providers. The
`background` slot is a wide backdrop with no download of its own: it
falls back to the banner art when empty, and clearing it never removes
the banner. A local game whose icon slot is still empty shows the icon
embedded in its executable, extracted once into the cache. Clear empties
the tile for real: a cleared kind, and every slot of a cleared game,
shows no art — not even Steam's own or the executable's icon — until
Fetch Artwork. Above the
AppID row, framed thumbnails (icon, banner, background, cover) show what
the list and the cards draw, at the image's own size; a filled frame
hugs the loaded picture with an equal margin on every side, so the art
never touches the rounded corner, and the backdrop's preview matches the
banner's while it has no art of its own. Clicking one picks that file
and the buttons under it download an image from a URL or clear the slot,
while the hover tooltip names the kind and shows the picture larger with
its origin. The
dialog opens at half the screen width and the full usable height. The
footer shows the live wrapper summary and a launch-command preview. The
chosen status also appears as a colored disc in the list and icons and a
pill on cards.

**Profiles** — named snapshots per game. Selecting one changes what
launches; saving with a profile active writes the profile (Game
Defaults stays pristine). `Save As...`/`Clone...` manage profiles. The
game dialog footer switch hides the profile bar; the choice persists in
`[ui] show_profile_bar`.

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
