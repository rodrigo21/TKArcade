# Changelog

All notable changes to TKSteamLaunch are documented here.
Breaking config changes are called out explicitly under `Changed`.

## [Unreleased]

### Added
- pytest suite (`tests/`, 36 tests) and ruff config in `pyproject.toml`.
- `Co-Authored-By` trailer policy + `scripts/git-hooks/commit-msg` hook.

### Changed
- **BREAKING:** `nightlight.provider = "kde"` no longer recognized
  (renamed to `"plasma"`); unknown values fall back to auto-detect.
- **BREAKING:** legacy ludusavi keys (`enable_restore`, `enable_backup`,
  `use_gui_progress`) no longer honored; affected games load with
  ludusavi off.
- **BREAKING:** no config migration machinery remains; sparse/unknown
  files load as-is with built-in defaults for missing keys.

### Fixed
- Pre/post hooks with `run_in_shell` now receive the game's env vars
  (previously dropped).

## [0.1.0] - 2026-09-23

First tagged baseline: launcher pipeline, PySide6 GUI, ludusavi `wrap`,
per-game snapshots, night light holder.
