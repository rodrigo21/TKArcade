# Changelog

All notable changes to TKArcade are documented here.
Breaking config changes are called out explicitly under `Changed`.

## [Unreleased]

### Fixed
- Drawer header is a plain Item so the drawer-edge separator runs full
  height and meets the header lines (a ToolBar header makes Kirigami
  inset it around the header zone); status text steps right off the
  divider tip.
- Table frame hugs the list flush with rounded corners (TKS look); no
  margins, so its top edge never reads as a second header separator.
- Drawer Library bar shares the Kirigami global toolbar height, so its
  separator meets the Games header line; header heights locked by test.
- Header titles are centered TKS-style with a small ▲/▼ mark overlaid
  at the top right corner (the frame and dividers mark the columns).
- View button is icon-only like Dolphin (icons per mode plus
  Ctrl+1/2/3); menu button uses the existing overflow-menu icon;
  geometry dump behind TKARCADE_DEBUG_GEOMETRY=1.
- Header strip shares the body x origin (stray outer margins had
  shifted every title and divider away from its column); header
  geometry locked by test.
- Number gutter frames rows like the widgets vertical header
  (Button set, follows selection highlight).
- Selected rows paint highlightColor behind highlightedTextColor
  text (tier badge joins the highlight); selection state lives on
  the delegate via selectedIds, no row index involved.
- Row clicks pass the page explicitly (QML ids are file-scoped, so
  the bare `gamesPage` reference inside RowClickHandler.qml resolved
  to nothing and every click died silent: no selection, no
  highlight, no multi-select).
- List view migrated from Addons ListTableView to plain QtQuick
  TableView with a custom Button-set header bar (full-bleed
  background, centered bold titles, sort indicators, tap-to-sort
  and right-click column menu). The proxy is now a real 6-column
  table model with order/visibility mapping, so icons and cells
  always track their rows through sorts.
- Header actions (Play/Add/Edit/Remove, search, views, columns,
  hamburger) live in the window header like plasma-systemmonitor,
  buttons centered with symmetric spacers.
- Header bar borrows the toolbar background (full-bleed Button
  set, bold titles) and the table sits flush under the window
  toolbar, like plasma-systemmonitor. The delegate carries its
  own implicit size (zero-size collapse hid text and background).
- Hamburger menu no longer overlaps (popup at cursor); header
  titles use the toolbar Button set, semibold off; selected rows
  use highlighted text; icons and tooltips track rows through sorts.
- Invented row dividers removed again; alternating tint stays off.
- Kirigami count properties live on the QMetaObject (drawer and
  status counts rendered `undefined` before); Steam play validates
  the AppID and drops the menu skip when the handoff fails.

### Added
- View switcher with per-view icons and Ctrl+1/2/3 shortcuts;
  menu button uses the vertical ellipsis.
- Single-row toolbar (title, centered actions, search, views,
  columns gear, hamburger); Tools lives in the hamburger with a
  persisted Drawer Mode section; Configure Columns dialog
  (show/hide + Up/Down) plus header right-click.
- List is a native table (Addons ListTableView): real header with
  relief, centered titles and sort indicator, row selection with
  highlight, gutter numbers; needs kirigami-addons at runtime.
- Movable data columns (Move left/right menu, Reset Columns) with
  order and visibility persisted to prefs; Game stays first.
- Tools menu (Scan Steam Library, History viewer, Ludusavi, Logs,
  Clean Profiles, Reload, Preferences, About, Quit), issues-only
  filter, shown count in the footer, 3-button empty state, and
  background ProtonDB/artwork refresh with an offline kill-switch.
- Drawer options below a separator (sources stay on top) and
  window geometry: 1280x720 default, last size/maximized restored
  and persisted debounced.
- Multi-selection (Ctrl toggles, Shift extends, single tap resets)
  with toolbar Play/Add/Edit/Remove, per-game context menu (copies,
  install/prefix folders, shader cache, ProtonDB, validate, clear
  history, remove with profile cleanup), footer notices.
- List matches the widgets table: plain left-aligned headers over
  the data, single-line names (no played sub-line), row numbers in
  an outside gutter, played hover tooltip, tier badge opens ProtonDB
  on double-click, `gamePlayedTip` role and `openProtonDB` slot.
- Gallery-style drawer modes (Overlay/Sidebar/Collapsible Sidebar
  with collapse header) and gallery-style views: details list,
  icons grid and cards (Kirigami CardsLayout) behind a split-button
  view switcher (button cycles, arrow opens the Zoom/Sort panel);
  uniform delegate selection overlay across views, `idAt` proxy
  slot so keyboard navigation follows the highlight.
- List view selection (tap + arrow keys + highlight), positional
  `#` column, Columns menu (App ID/Played/ProtonDB/Source driven
  by proxy flags), styled header with sort indicators.
- Main-window UI parity in Kirigami: source drawer with counts,
  search field, rich rows (name, ID · played, tier badge), status
  counts. Filtering runs through a proxy model (tested in Python).
- List view like the widgets table (Game/App ID/Played/ProtonDB/
  Source, clickable headers, per-view row height).
- Async native file picker: Browse never freezes the UI (worker
  thread + result signal); `TKARCADE_VERBOSE=1` (or `--verbose`)
  shows portal handshake debug lines.
- Native file picker: the Add dialog uses the desktop's own picker
  via xdg-desktop-portal (jeepney) instead of the Qt fallback.
- Kirigami spike (branch only): QtWidgets parked under `widgets/`
  as reference, new Kirigami list/add/launch UI in `gui/` reusing
  the stdlib core untouched; `--gui` opens it, `--edit`/`--menu`
  report unavailable until its settings UI lands.

### Added
- New application icon: arcade cabinet with TK screen and play
  triangle (monochrome outline variant for the tray).
- Double-click plays the game, middle-click opens its settings
  (ProtonDB column still opens the page).
- Centered main toolbar actions; window opens at 1280x720 and
  remembers its size across runs (floored at 640x480).
- View menu with a Main Toolbar toggle; toolbar buttons show icon
  beside text.
- `TKARCADE_NO_NOTIFY` kill-switch: the test suite sets it, so test
  runs (and PKGBUILD checks) never pop desktop notifications.
- Main window restores maximized state across runs (size kept
  separately, never overwritten while maximized).
- Dependency Status hides Steam-only entries for local games.
- Display modes load on first opening the Display tab (Refresh and
  provider/output edits still re-query).

### Fixed
- Diff vs Defaults ignores identity fields (appid, name) and the
  profile selection memory.

### Added
- Source sidebar: All/Steam/Local filter list with counts beside
  the games table (future sources appear there on their own).
- TKSteamLaunch import: one click copies games/profiles/defaults/
  preferences from the predecessor XDG dirs (missing files only,
  never overwrites) — do it early, formats still match.
- Menu bar + slim toolbar replace the Games/Tools/Application button
  rows (File/Game/Tools/Settings/Help; Play/Add/Edit/Remove up front).
  Copy Launch Options and the rest of the per-game actions live only
  in the row menu now, shown per source (no ProtonDB page for local
  games); Validate/Clone guard empty selections.
- Single Add Game entry: a source chooser (Steam / Local Linux)
  replaces the per-source buttons; room for Wine and UMU later.
- Local native Linux games: Add Local... (name + executable, unique
  `local-<slug>` ID), direct Play (detached, same logs/history/menu
  skip as Steam), Copy Launch Command, and exe-dir working directory.
  Settings show the editable name and hide Steam-only bits; clone and
  validation accept local IDs (missing custom executables flagged).
- Game identity groundwork for local (non-Steam) games: string IDs
  (`local-<slug>` alongside numeric Steam AppIDs), per-game display
  names, and a Source column (Steam/Local) in the games list.
  Steam-only lookups (ProtonDB, artwork) skip local rows.

### Changed
- TKArcade starts here as a standalone repo renamed from
  TKSteamLaunch 1.1.1 (full history preserved, new remote).
  **BREAKING**: config/state/cache now live under the `tkarcade`
  XDG directories, so no settings carry over automatically.
- Pre-0.1: `-git` is the only Arch package (normal PKGBUILD
  returns with the 0.1.0 release); third-party recipes under
  `packaging/arch/` stay in sync with TKSteamLaunch until this
  project supplants it.
- AppImage release asset now carries the version
  (`TKArcade-<version>.AppImage`).

## [1.1.1] - 2026-10-05

### Fixed
- Profile Delete asks first and Save/Clone ask before overwriting an
  existing profile.
- Save and Reset over a newer-version config need an explicit Ok, so a
  loud fallback can no longer be silently downgraded.
- Steam quick-launch rejects non-numeric App IDs, and a failed Steam
  handoff no longer plants a menu skip that would eat the next menu.
- Game add/clone pickers reject non-numeric App IDs instead of writing
  garbage configs.
- Mode list no longer queries on dialog open (Refresh/provider/output
  only) and rapid Refresh never stacks workers.
- `summarize().last` is the newest stamp, not file order.
- Launch-without-save now persists just the profile selection, so the
  launcher resolves the profile shown in the dialog (never overwriting
  an unreadable live file on this path).
- Unreadable (not just invalid) config files fall back to defaults
  everywhere instead of crashing dialogs.
- Display mode no longer gets stuck on the dip mode when the target
  apply fails or the launch is interrupted: the original mode is
  recorded after the first apply and restored best-effort.
- xrandr mode lines keep every refresh rate (e.g. `164.96*+ 60.00`),
  so same-resolution dips avoid a resolution flicker.
- Shipped Qt translations actually load from installed packages: the
  catalog dir is a real package with an explicit wheel rule (previously
  English-only outside a source checkout), and repeat installs on one
  process no longer skip a second app.

## [1.1.0] - 2026-10-05

### Added
- Play button (Games row) and Play in the context menu for launching
  through the client; Play uses the real selection. Launching from
  the program (button, tray, menu) skips the pre-launch menu once
  via a fresh sentinel, even with show-menu enabled.
- Backup now includes preferences.toml; context menu order mirrors
  the button rows, with Copy Launch Options leading the copies group.
- In-app language option (Preferences): system default, English, or
  shipped locales — restart to apply, games unaffected (no LC_ALL leak).
- Display dip delay slider (3-15 s, per game, default 8 s) for the
  same-mode VRAM clock workaround; slider and note show only for
  the current mode.
- Display same-mode workaround for the AMD VRAM clock bug: requesting
  the current mode dips one mode down and back before the game starts
  (same resolution, closest lower refresh; logged, never aborts).
- Mode picker shows backend numbers and the current mode, keeps manual
  entry valid, and warns that same-mode requests dip first.
- Export/import now carries profiles (whitelist extended, traversal
  still rejected), and games clone live config plus profiles to
  another AppID ("Clone Settings To...", picking from the Steam
  game list, with overwrite confirm).
- Display mode picker lists detected modes (manual entry kept) with
  a Refresh button; apply/restore log values and failures loudly.
- Per-game history clearing: exact token match, atomic rewrite, in
  the History dialog (Clear Selected) and the game context menu.
- System tab grouped (Notifications / Idle Suspend / Night Light)
  with the night-light toggle named; PT-BR strings included.

### Fixed
- Pre-launch menu shows the active profile's wrappers (it rendered
  the live file while launching the profile).
- Display mode goes through kscreen numeric mode IDs (the WxH@rate
  string form is silently ignored) and the picker lists offered
  modes sorted by resolution then rate, descending.
- Mode list fills in a worker thread (a wedged kscreen-doctor once
  hung dialog construction); dialog open performs zero backend
  queries, and worker threads stop cleanly on accept/reject.
- Crafted AppIDs can no longer escape the log/proton-log dirs
  (`safe_stem` centralized in xdg, applied to every AppID path).
- Validate and the pre-launch countdown check the effective
  (profile-resolved) config, not just live.
- Clone replaces (not merges) destination profiles; export skips
  hand-placed nested profile junk the importer would refuse.

## [1.0.0] - 2026-10-04

### Added
- GUI translations via Qt Linguist, starting with PT-BR (351 strings;
  CLI stays English). New UI strings require `tr()` (enforced by test).

### Added
- Display dip delay slider (3-15 s, per game) for the same-mode
  VRAM clock workaround.
- Display same-mode workaround for the AMD VRAM clock bug: requesting
  the current mode dips one mode down and back before the game starts
  (same resolution, closest lower refresh; logged, never aborts).
- Mode picker shows backend numbers and the current mode, keeps manual
  entry valid, and warns that same-mode requests dip first.
- Mode picker shows backend numbers and the current mode, keeps manual
  entry valid, and warns that same-mode requests dip first.
- Export/import now carries profiles (whitelist extended, traversal
  still rejected), and games clone live config plus profiles to
  another AppID ("Clone Settings To...", picking from the Steam
  game list, with overwrite confirm).
- Display mode picker lists detected modes (manual entry kept) with
  a Refresh button; apply/restore log values and failures loudly.
- Per-game history clearing: exact token match, atomic rewrite, in
  the History dialog (Clear Selected) and the game context menu.

### Fixed
- Pre-launch menu shows the active profile's wrappers (it rendered
  the live file while launching the profile).
- Display mode goes through kscreen numeric mode IDs (the WxH@rate
  string form is silently ignored) and the picker lists offered
  modes sorted by resolution then rate, descending.
- Dip slider (default 8 s) and note show only for the current mode;
  worker threads stop on dialog close (close() bypasses reject,
  which once aborted suite teardown).
- Mode list fills in a worker thread (a wedged kscreen-doctor once
  hung dialog construction); dialog open performs zero backend
  queries, and worker threads stop cleanly on accept/reject.
- Crafted AppIDs can no longer escape the log/proton-log dirs
  (`safe_stem` centralized in xdg, applied to every AppID path).
- Validate and the pre-launch countdown check the effective
  (profile-resolved) config, not just live.
- Clone replaces (not merges) destination profiles; export skips
  hand-placed nested profile junk the importer would refuse.

## [0.9.0] - 2026-10-04

### Added
- Single binary: bare `tksteamlaunch` (or `--gui`) opens the settings
  GUI, `--cli` guarantees launcher mode; the `tksteamlaunch-gui` and
  `tksteamlaunch-appimage` entry points are gone (BREAKING for direct
  callers; the desktop file and AppImage use `tksteamlaunch` now).
- Gear-and-play app icon (font-free paths, gray gear + orange play),
  also wired as the AppImage icon.
- Scan Library batch-add for Steam games without a config, and
  per-game Clear Shader Cache (with size) in the context menu.
- User-focused README (uv tool/pipx/local package installs) with dev
  docs split into docs/DEVELOPMENT.md; new man page installed by both
  Arch packages; single-entry AppImage recipe in packaging/appimage/.
- FPS Limit (DXVK) now uses `DXVK_CONFIG="dxgi.maxFrameRate = 60;
  d3d9.maxFrameRate = 60"`: the `DXVK_FRAME_RATE` env var was removed
  upstream (doitsujin/dxvk#5331); DX9/10/11 only.
- Tray quick-launch: recent games section (steam:// URLs, 1-10
  configurable) with Preferences toggle and count.

### Changed
- Config files carry a `config_version` stamp (current: 1). Files from
  the future fail loudly (dialog warning, launcher fallback with an
  error, validate issue) instead of silently resetting; pre-stamp
  files load as before.

## [0.8.1] - 2026-10-04

### Added
- Movable game-list columns (drag the header) with a header context
  menu to show/hide columns (Game always on) and reset to the
  Game | App ID | Played | ProtonDB default; layout persists.

## [0.8.0] - 2026-10-04

### Changed
- **BREAKING**: selecting a profile now affects the launch: the
  launcher runs the active profile's content, falling back to the
  live config (with a warning) when the selection is missing or
  unreadable. Saving with a profile active writes the profile file
  and keeps only the selection in the live file, so Game Defaults
  stays pristine; `--validate` reports dangling selections.
- Reset to Global Defaults persists immediately (with confirmation):
  no more staged reset silently discarded by Cancel. Profiles are
  never touched by Reset.
- Fixed populate clobbering: live preview collects no longer overwrite
  the config mid-populate, which left late fields (Ludusavi, Wine /
  Proton, notes) stale on Reset and profile switches — looking like
  "nothing changed".

### Added
- Per-game display mode (phase 1: Plasma via kscreen-doctor, X11 via
  xrandr): optional output + WIDTHxHEIGHT[@RATE], applied on launch
  and restored on exit, failures warn without aborting. Empty mode
  disables it; GNOME/wlroots detect but warn as phase 2.
- Main window Played column (total time, sorts by seconds) fed by the
  session log; History dialog gained Clear History with confirmation.
- FPS Limit (DXVK) env preset (`DXVK_FRAME_RATE=60`, DX9/10/11 only).
- Proton Wayland env preset (`PROTON_ENABLE_WAYLAND=1` for GE,
  CachyOS and DW builds); No Esync and Disable D3D9 presets note
  where the toggle is a known no-op.
- Right-click context menu on the game list: Edit, Copy App ID /
  Game Name / Launch Options, Open Install Folder / Proton Prefix /
  ProtonDB Page, Validate, Remove (entries disable when N/A).
- Multi-select (Ctrl/Shift+click) for Remove and Reset to Global
  Defaults, with one confirmation listing the games; removing offers
  to clean up leftover profiles via a checkbox table.
- Context menu shows only multi-game actions on multiple selection;
  Tools row has Clean Profiles for orphaned profiles anytime, Games
  row has Reset, and empty Remove/Reset hint at selecting first.

### Added
- Opening the game dialog on a config file that cannot be parsed warns
  that defaults are shown (and will be written on save) instead of
  silently switching to them. The same warning fires when switching to
  an unreadable profile or back to an unreadable live file, and
  unreadable (not just invalid) files no longer crash the dialog open.

### Fixed
- Config writer escapes control characters (CR, ESC, NUL, …) and quotes
  exotic keys: a pasted line break can no longer produce an unreadable
  TOML file that resets the game to defaults on the next load.
- Config saves (games, profiles, defaults, preferences) are atomic
  (temp file + rename): a crash mid-write no longer truncates the file.
- Atomic saves sweep stale temp files left by a previous crash.
- Saving with a profile active writes the profile file and keeps
  only the selection in the live file (see Changed above); edits no
  longer revert on reopen and Game Defaults stays pristine.
- Game list App ID column sorts numerically (9, 80, 1044620) instead
  of lexicographically.

## [0.7.0] - 2026-09-30

### Added
- Guided empty state on the main window (Add / Import / Copy Launch
  Options) when no games are configured.
- Game list filter by name or App ID plus "With issues only" (same
  checks as `--validate`), with a "N shown" status suffix.
- Live "Will launch with: ..." wrappers summary in the game dialog
  footer, updated on every field change.
- Advanced tabs (Environment, Pre/Post Commands, Wine / Proton) hidden
  behind an "Advanced" footer toggle; auto-expanded when the game
  already uses them.
- Broken custom-executable/hook paths surface as live Dependency
  Status warnings with an "Open folder" link when the parent exists.
- New presets: DXVK Sarek for pre-1.3 Vulkan GPUs, D7VK switch for
  GE-Proton.

### Fixed
- SteamTinkerLaunch importer drops default-off (`"0"`/`"none"`) flags
  via allowlist (numeric scales and unknown keys kept) and reports
  pre/post hooks or custom executables missing on disk (cross-PC paths).
- Env preset applicability audited against current Valve/CachyOS/GE
  docs and the installed Proton scripts: CachyOS-only vars no longer
  offered on Valve/GE, GE-only `PROTON_NO_NTSYNC` no longer offered
  elsewhere, DW-Proton recognized as its own flavor.

## [0.6.0] - 2026-09-30

### Added
- Profile selection persists per game; Clone confirms before copying
  live settings; profile list refreshes on dialog focus.
- Profile combo starts with `(Game Defaults)` to reload the saved game
  settings; switching (or deleting the active) profile with unsaved
  edits asks Save / Discard / Cancel.
- SteamTinkerLaunch importer: common settings land in a
  `steamtinkerlaunch` profile (live config untouched), with usage
  notice; profile Clone button.

## [0.5.0] - 2026-09-28

### Added
- Proton log capture per game (off by default, warning in notification).
- WINEDEBUG selector per game (Off/-all/+err/+warn,+err).
- VSync disable presets for Mesa and NVIDIA (verified against docs).
- Idle suspend inhibitor per game (logind idle lock only).
- Proton prefix fresh-start toggle (deletes compatdata before launch).
- Winetricks verbs per game via protontricks (unattended, skips repeats).
- Config diff viewer (game vs global defaults).
- SteamGridDB artwork fallback (API key in Preferences, own cache).
- RT upscaler support (linux-rt-upscaler wrap, XWayland enforced).
- Richer pre-launch menu: centered buttons with icons, landscape game
  art, `Name (AppID)` header, playtime and active wrappers, optional
  auto-launch countdown (`menu_timeout`).
- Compat preset catalog (FSR4, sync, D3D fallbacks, locale, HDR...) with
  GPU/Proton applicability tags and mismatch confirm.

### Changed
- Settings dialog regrouped: Environment, System and Display tabs;
  status box in two columns with blanks packed last; collapsible
  3-line command preview.
- Main window and dialogs center on the available area; game list
  sorts A-Z by default with clickable headers.

### Fixed
- SteamGridDB single-object game responses handled (artwork works).

## [0.4.0] - 2026-09-28

### Added
- Dynamic versioning from git tags (`uv-dynamic-versioning`); releases
  are cut by tagging. PKGBUILD derives `pkgver()` the same way.
- Real pre-launch menu dialog (Launch / Settings / Cancel) for `--menu`.
- Status tray icon (normal/monochrome) with menu, minimize/close to
  tray and a Preferences dialog (`preferences.toml`).
- Bundled application icons and freedesktop desktop entry.

### Changed
- **BREAKING:** `show_preview` moved from `defaults.toml [ui]` to
  `preferences.toml`; old key ignored.
- LICENSE file removed (SPDX common license covers GPL-3.0-or-later);
  nightlight-holder console script removed (use `python -m`).

### Fixed
- Minimize-to-tray deferred past the state-change event.
- Reload rescans Steam games again (per-process cache is cleared).
- GUI test suite hermetic to pytest-qt presence.

### Added
- Live launch-command preview box in dialogs (global `[ui] show_preview`
  toggle); tool toggles disable when their binaries are missing.
- Per-game config profiles (switch/save-as/delete, in-memory until Save).
- ProtonDB tier column in the main window (30-day cache, background
  refresh; double-click opens the game page).
- Session history dialog (last played, sessions, total time, failures).
- Steam launch-options verifier (dialog status + `--validate` input).
- Gamescope option presets (1080p144, 1440p165, 4K60, borderless, Deck).
- Per-game notes tab.
- Config export/import tarballs (`--export`/`--import`, GUI buttons).
- MangoHud starter templates (minimal, fps-cap, full) in New Configuration.
- Env presets (FSR, RADV shaders, SDL Wayland) via Add Preset.
- pytest suite (`tests/`, 41 tests) and ruff config in `pyproject.toml`.
- `Co-Authored-By` trailer policy + `scripts/git-hooks/commit-msg` hook.
- "Preview Command" button in the game dialog (dry-run parity).
- `tksteamlaunch --list` prints configured and detected games.
- Per-game logs rotate at 1 MiB (3 backups).
- Desktop `notify-send` alerts on hook failures and launch blockers.
- Transient game-start notification (per-game `[notifications]` toggle,
  game icon, Proton version lookup).
- Session-end notification with playtime.
- Detected Proton runtime shown read-only in the game dialog.
- Ludusavi coverage check (manifest entry + local saves via preview).
- Pre-launch menu: `--menu` flag and per-game `show_menu` setting
  (Launch / Settings / Cancel, display fallback launches directly).
- `--edit` accepts a positional AppID and shows a game picker when
  no AppID is given.

### Changed
- "Preview Command..." button removed (replaced by the live preview box);
  ludusavi shown by bare name in previews, like other wrappers.
- Build backend setuptools → hatchling; local install via
  `uv venv --system-site-packages` + `uv pip install --no-deps .`.
- `--help` documents the exit-code contract.
- **BREAKING:** `nightlight.provider = "kde"` no longer recognized
  (renamed to `"plasma"`); unknown values fall back to auto-detect.
- **BREAKING:** legacy ludusavi keys (`enable_restore`, `enable_backup`,
  `use_gui_progress`) no longer honored; affected games load with
  ludusavi off.
- **BREAKING:** no config migration machinery remains; sparse/unknown
  files load as-is with built-in defaults for missing keys.

### Fixed
- Minimize-to-tray deferred past the state-change event.
- Ctrl+Q quits the app; closing without close-to-tray drops the tray
  icon so the app really exits.
- Single GUI instance: followers raise the open window and exit.
- Status tray rebuilt safely: persistent menu reference, update in
  place instead of delete/recreate, guarded teardown.
- Steam launch-options check now parses real `localconfig.vdf` files
  (lowercase `apps` node, nested blocks); venv paths with flags match.
- Command preview uses `%command%` instead of `<game-command>`.
- Start notification folds runtime and wrappers into one line and uses
  the same Proton tool display as the game dialog (no more lone
  "Proton" when only the tool mapping exists).
- Dialog buttons ordered Launch | Save | Save & Launch with theme
  icons; "Launch" runs with the saved configuration, discarding
  unsaved edits.
- Settings dialogs opened from Steam no longer fall back to the Fusion
  style: the editor runs in a subprocess with Steam-runtime library
  paths filtered out of `LD_LIBRARY_PATH`.
- `--menu` flag no longer opens the pre-launch menu twice.
- Qt/desktop environment logged per run to diagnose GUI theming.
- NightLight holder spawned twice per launch, leaking an inhibitor;
  single spawn with idempotent start().
- Empty game command executed a bare prefix stack; now skipped with
  a log line, and "Save && Launch" hides when nothing can launch.
- Unbalanced quotes in prefix/args fields no longer crash launch,
  validation or Save (whitespace fallback).
- String booleans in TOML (`"false"`) now parse correctly.
- Ludusavi coverage tolerates non-integer `bytes` values.
- GameMode/CachyOS conflict resolved on dialog load (Feral wins).
- Add Game ignores blank names instead of writing `unknown.toml`.
- Copy Launch Options handles missing clipboard (headless).
- Command preview never kills the dialog on unexpected errors.
- Ludusavi coverage check runs off the UI thread; worker threads
  always joined (terminate fallback) before their owners close.
- "Check Coverage" button hidden in Global Defaults (per-game only).
- Pre/post hooks with `run_in_shell` now receive the game's env vars
  (previously dropped).

## [0.1.0] - 2026-09-23

First tagged baseline: launcher pipeline, PySide6 GUI, ludusavi `wrap`,
per-game snapshots, night light holder.
