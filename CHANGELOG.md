# Changelog

All notable changes to TKSteamLaunch are documented here.
Breaking config changes are called out explicitly under `Changed`.

## [Unreleased]

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
