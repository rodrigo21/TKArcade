# Changelog

All notable changes to TKSteamLaunch are documented here.
Breaking config changes are called out explicitly under `Changed`.

## [Unreleased]

### Added
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
- **BREAKING:** `nightlight.provider = "kde"` no longer recognized
  (renamed to `"plasma"`); unknown values fall back to auto-detect.
- **BREAKING:** legacy ludusavi keys (`enable_restore`, `enable_backup`,
  `use_gui_progress`) no longer honored; affected games load with
  ludusavi off.
- **BREAKING:** no config migration machinery remains; sparse/unknown
  files load as-is with built-in defaults for missing keys.

### Fixed
- NightLight holder spawned twice per launch, leaking an inhibitor;
  single spawn with idempotent start().
- "Check Coverage" button hidden in Global Defaults (per-game only).
- Pre/post hooks with `run_in_shell` now receive the game's env vars
  (previously dropped).

## [0.1.0] - 2026-09-23

First tagged baseline: launcher pipeline, PySide6 GUI, ludusavi `wrap`,
per-game snapshots, night light holder.
