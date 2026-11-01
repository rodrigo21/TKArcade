# External runtime versions stay per game and configured

Status: decided (2026-11-01).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: define how DXVK, vkd3d-proton and Proton versions from outside
the system installation are discovered and selected, without turning
TKArcade into a runtime downloader.

## Decision

- **Only configured directories are scanned.** DXVK and vkd3d-proton
  versions come from `[ui] dxvk_dirs` / `vkd3d_dirs` in Preferences.
  Lutris and Flatpak-Lutris default paths are not read: TKArcade does
  not depend on another launcher's layout.
- **The graphics layer version is per game.** Plain Wine games get
  `[graphics] dxvk_version` and `[graphics] vkd3d_version`. Empty means
  the newest installed version, so existing configs keep their
  behaviour. A missing selected version is an error for that layer;
  TKArcade never falls back to newest silently.
- **Proton stays read-only.** Local UMU builds come from Steam's
  `compatibilitytools.d`/`steamapps/common` plus `[ui] proton_dirs`;
  Steam games keep Steam's compat-tool mapping. A directory counts as
  Proton only when it holds the `proton` launcher, so anti-cheat
  runtime tools no longer appear as `PROTONPATH` choices.
- **No download or extraction.** Versions are installed by the user
  (distro, ProtonPlus/ProtonUp-Qt, manual unpacking). TKArcade only
  discovers and uses them. Archive support from a cache directory
  (option C) stays in `TODO.md`.

## Why

The old default paths made Lutris an implicit source even for users
who never chose it, and its versions won or lost by directory name
rather than by an explicit choice. Configured directories keep the
source of truth in Preferences. A per-game version is the same model
`graphics-layers.md` already uses for runtime builds: choose the build,
do not replace files inside it.

`runtimes.py` is imported by the stdlib-only launcher on every game
start, so it must stay read-only and cheap. Downloading, verifying and
unpacking archives there would add a network/package-manager surface
and make launches depend on remote availability.

## Behaviour today

| Case | Behaviour |
| --- | --- |
| Local Wine, DXVK/vkd3d on | The selected version (empty = newest) is copied into the prefix and selected through `WINEDLLOVERRIDES`. |
| Local Wine, selected version missing | The layer is not installed; launch and `--validate` warn, and the dialog marks the version as not installed. |
| Local umu / Steam Proton | `[graphics]` is ignored; the runtime ships its own DXVK/vkd3d (`graphics-layers.md`). |
| Local UMU Proton list | Only directories with the `proton` launcher; `proton_dirs` plus Steam roots. |
| Graphics directories | Only `dxvk_dirs` / `vkd3d_dirs` from Preferences. |
| Archives in a cache dir | Not supported; see `TODO.md`. |
| Steam Linux Runtime | Still a local-native choice; extending it to Wine/umu is a separate open item. |

## Rejected alternatives

- **Keep scanning Lutris defaults.** Convenient, but makes another
  launcher's layout an implicit dependency and hides which version was
  used.
- **Silent newest fallback for a missing selection.** Launches stop
  matching the saved config; the user cannot tell which layer ran.
- **Manage/download runtime versions.** Duplicates ProtonPlus/ProtonUp-Qt
  and the distro, and violates the read-only launcher policy.
- **Per-game Proton copies.** Already rejected in `graphics-layers.md`:
  gigabytes per game and shared-state writes into the runtime install.
