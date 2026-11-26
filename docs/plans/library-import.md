# Plan: library format import (Lutris, Faugus)

Status: proposal, not approved. Awaiting the maintainer's review of
this file; when it lands it becomes `docs/decisions/library-import.md`
with a landing banner and this file is deleted.
Target: before 1.0, as the first item in `TODO.md`. The tag follow-ups
wait on it.
Created: 2026-11-26.

## Goal

Bring an installed Lutris or Faugus library into TKArcade without
writing to the other launcher's files. The import creates a live config
for a new game and saves a named profile for a game that already exists,
so nothing owned by TKArcade is overwritten. The user picks the games
from a checklist; nothing is written until the final Import.

## Evidence (checked 2026-11-26)

**Lutris** (0.5.x, installed locally):

- Library: `$XDG_DATA_HOME/lutris/pga.db` (SQLite). The Flatpak path is
  `~/.var/app/net.lutris.Lutris/data/lutris/pga.db`. A custom `pga_path`
  in `lutris.conf` wins.
- `games` columns used here: `name`, `runner`, `directory`, `installed`,
  `configpath`, `service`, `service_id`, plus the legacy `steamid`,
  `gogid` and `humblestoreid`. `executable` is usually NULL for Wine
  games: the exe lives only in the YAML.
- `categories` + `games_categories` carry the sidebar categories.
- Per-game YAML: `<config dir>/games/<configpath>.yml`. The config dir
  is `$XDG_CONFIG_HOME/lutris`, falling back to the data dir when it
  does not exist; Flatpak uses
  `~/.var/app/net.lutris.Lutris/config/lutris`. Relevant keys:
  `game.exe`, `game.args`, `game.working_dir`, `game.prefix`,
  `game.appid` (Steam and Linux entries), `system.env`,
  `system.mangohud`, `system.gamemode`,
  `system.prelaunch_command`, `system.postexit_command`,
  `system.prelaunch_wait`, `wine.version`. Lutris writes the file with
  `yaml.safe_dump`, so long scalars may wrap over several lines.
- Runners seen locally: `wine`, `linux`, `steam`, `dolphin`, `pcsx2`,
  `ppsspp`, `web`. Only the first three have a TKArcade launch path.
- Services seen locally: `gog`, `steam`, `xdg`, plus empty.
- `wine.version` names a Wine build under
  `<data dir>/runners/wine/<version>/bin/wine`, or `system` for PATH.
- Lutris keeps the prefix shared: several games may point at the same
  directory, and the prefix normally lives outside every TKArcade
  prefix base.

**Faugus** (1.x, installed locally; its `games.json` is empty here):

- Library: `$XDG_DATA_HOME/faugus-launcher/games.json` (JSON array).
  Flatpak: `~/.var/app/io.github.Faugus.faugus-launcher/data/faugus-launcher/games.json`.
- Fields: `title`, `gameid`, `path`, `prefix`, `runner`,
  `launch_arguments` (lines of `KEY=value`), `game_arguments`,
  `mangohud`, `gamemode`, `sdl_enabled`, `no_sleep`, `category`,
  `pre_launch`, `post_launch`.
- `runner` is a Proton path, `Linux-Native`, `Steam` (the `path` is the
  Steam AppID), `Default` (resolved through `config.json`
  `default-runner`) or a reserved label. Faugus runs Windows games
  through `umu-run` with `PROTONPATH` and `WINEPREFIX`, the same shape as
  TKArcade's `umu` runtime.
- `category` is a name or a list of names.

**Code to reuse:**

- `stl_import.py` is the reader pattern: stdlib, read-only on the other
  program's files, an allowlist map plus a report of what was dropped.
- `ImportDialog.qml` already has one page per source, a checkable list
  with Select All/None, and the `pressDefault` Enter list.
- `gui/model.py` already imports STL as a profile
  (`importStl`, `save_profile`) and creates local games with
  `new_local_id()`.
- `config.local_id_for_executable()` matches an executable to a local
  game; the name match must be added here because Lutris leaves
  `executable` NULL.

**Gap that blocks the import:** `prefix_dir()` and `prefix_target()`
always resolve a local WINEPREFIX to `<base>/<folder>`, and `prefix_stem`
normalizes the folder name (`TK's good-game_1` -> `TKsGoodGame1`).
Reusing an imported prefix through that rule would move the path and
lose the other launcher's saves.

## Decisions

1. **Both readers in the first batch.** Lutris and Faugus share the
   mapping and the UI; the second reader is a small addition.
2. **Exact prefixes.** New `[runtime] prefix_exact = true`: for a local
   wine/umu game, `[runtime] prefix` is the WINEPREFIX itself, not a
   base. `prefix_target()` returns it with `managed=False`, so the
   cleanup, Remove-game prefix deletion and the ID migration never move
   or delete it. `prefix_name` is ignored in that mode. Steam games keep
   their compatdata rule and ignore the key.
3. **Store identity.** New `[store] kind` and `[store] id` fields. A
   non-Steam store entry (GOG, Epic, ...) keeps a `local-<slug>` ID and
   records `kind` + service ID; a Steam entry targets the existing
   `steam-<appid>` and records no store. The section is inert until the
   2.0 origin work, but it makes a re-import idempotent.
4. **Existing games become profiles.** A matched game gets a
   `lutris`/`faugus` profile (same rule as the SteamTinkerLaunch
   import); its live config is untouched. A new game gets the live
   config. The profile name is the source, so a re-import replaces that
   one profile and never the user's own profiles.
5. **Categories, not metadata tags.** Lutris categories and Faugus
   `category` go to `[general] categories`, the same taxonomy the
   sidebar shows. `[metadata] tags` is provider/editing data and has no
   foreign source; the "Library import tag mapping" item in `TODO.md`
   is closed by this decision.
6. **PyYAML for Lutris.** Add `PyYAML>=6` (MIT) to the package
   dependencies; `library_import.py` imports it lazily, and the launcher
   never imports the module. A source install without it still starts
   the GUI and reports that Lutris YAML cannot be read. The native
   package adds `python-yaml`; the AppImage bundles the wheel.
7. **Selection is explicit.** A page lists every usable candidate:
   new games checked, already configured games unchecked, unsupported
   runners disabled with a reason. Select All/None and Enter import the
   checked rows only. Uninstalled Lutris entries and unsupported runners
   are not selectable.
8. **No network in the import.** New games get no automatic artwork or
   metadata download; the user runs those per game. The report lists
   what was skipped and why.

## Mapping

| Source | TKArcade |
| --- | --- |
| `name` / `title` | `[general] name` (new game); profile keeps the target's name |
| `game.exe` / `path` | `[general] custom_executable` |
| `game.args` / `game_arguments` | `[general] launch_args` |
| `game.working_dir` | `[general] launch_cwd` |
| `system.env` / `launch_arguments` `KEY=value` lines | `[env] vars` |
| `system.mangohud` / `mangohud` | `[mangohud] enable` |
| `system.gamemode` / `gamemode` | `[gamemode] feral_gamemode` |
| `prelaunch` / `pre_launch` | `[pre_post] pre_command`, `run_in_shell = true` |
| `postexit` / `post_launch` | `[pre_post] post_command`, `run_in_shell = true` |
| `no_sleep` | `[session] inhibit_idle` |
| `categories` / `category` | `[general] categories` |
| `wine` runner + `wine.version` | `[runtime] type = "wine"`, `tool` = resolved Wine binary, `prefix_exact` |
| Faugus Proton path / `runner` | `[runtime] type = "umu"`, `tool` = PROTONPATH, `prefix_exact` |
| `linux` / `Linux-Native` | `[runtime] type = "native"` |
| `steam` service / `Steam` runner | target `steam-<appid>`; profile only |
| `service`/`service_id` (non-Steam) | `[store] kind` + `[store] id` |

Values containing `$GAMEDIR`, `$HOME`, `$USER` or `~` are expanded
before use; a path is kept when it does not exist yet and reported. A
Lutris Wine version that cannot be resolved falls back to PATH Wine with
a note. Faugus `Default` is resolved through its `config.json`.

Anything outside the table is dropped and counted: `gamescope`,
`disable_runtime`, emulator/web runners, `addapp`, `lossless`,
`discord_rpc`, `protonfix`, `steamgriddb_id`, `prelaunch_wait` and the
like.

## Target matching and idempotency

1. A local config with the same `[store] kind` + `id`.
2. A Steam entry: `steam-<service_id>` (Lutris) or `steam-<path>`
   (Faugus), only when Steam lists it or a config exists.
3. A unique local config with the same resolved executable.
4. A unique local config with the same normalized name (NFC, strip,
   casefold).

A hit saves the profile. No hit creates a live config with
`new_local_id()`. An ambiguous match imports as a new game and says so
in the report; it never guesses. Re-importing the same source replaces
its own profile. Duplicate candidates (same exe or same target) are
merged before the list is shown.

## Reader boundaries

- `library_import.py` is GUI/helper-only: stdlib plus lazy `yaml`.
  Never imported by `launcher.py`.
- The Lutris DB is opened read-only through a `file:...?mode=ro` URI.
  Neither `pga.db` nor `games.json` is ever written.
- Missing or malformed files return no candidates plus a reason; they
  never raise into QML.
- Native and Flatpak locations are tried in order. A custom Lutris path
  comes from `lutris.conf`; a custom Faugus path is not supported in the
  first batch (report the path checked).

## UI

- `ImportDialog.qml`: the three source buttons become a `Flow` so five
  fit at the minimum width, then two pages (Lutris, Faugus), each with
  the STL page's scroll/checklist/Select All/None layout. Rows show the
  name, a short detail (exe or store ID) and the matched TKArcade game
  when one exists.
- `gameModel.libraryCandidates(source)` returns `{rows, hint}`;
  `gameModel.importLibrary(source, keys)` returns the report. Rows stay
  nested JS arrays, converted to a fresh array by the QML caller.
- Enter imports the current page through `pressDefault`; the list of
  default buttons gains the two new confirm names.
- `GameSettings.qml`: when `prefix_exact` is set, the prefix row reads
  as the WINEPREFIX itself, hides `prefix_name` and the prefix chooser,
  and a checkbox lets the user turn the mode off. Unchecking it restores
  the base/folder rule.

## Batches (one commit each)

### 0. This plan (main, docs only)

`docs/plans/library-import.md` plus the `docs/README.md` map entry.

### 1. Config and launch (branch)

- `config.py`: `StoreConfig`, `RuntimeConfig.prefix_exact`, section
  round-trip, `prefix_target()`, `_pin_prefix()`, defaults exclusions.
- `gui/model.py`: `_pin_prefix_name()`, `_keep_local_identity()`,
  `game_to_map`/`_apply_map` fields.
- `GameSettings.qml`: exact-prefix row.
- `pyproject.toml`, `packaging/arch/tkarcade-git/PKGBUILD` (depends hunk
  only), `docs/DEVELOPMENT.md`, `packaging/appimage/README.md`.
- `README.md` prefix section and `[store]` example; `CHANGELOG.md`.
- Tests: `test_config.py` round-trip and prefix target, `test_launcher.py`
  if the launch env is touched, migration test.

### 2. Reader

- New `src/tkarcade/library_import.py` and `tests/test_library_import.py`
  with SQLite/YAML/JSON fixtures: mapping, expansion, store identity,
  runners, categories, unsupported fields, malformed files.
- Read-only smoke check against the real Lutris library (counts only).

### 3. GUI and QML

- `gui/model.py` candidate/import slots and matching.
- `ImportDialog.qml` Flow + two pages.
- `tests/test_kirigami_model.py` import cases; QML flow case; offscreen
  screenshot of the dialog with five sources.
- `README.md` GUI guide and `CHANGELOG.md`.

### 4. Landing

- `docs/decisions/library-import.md` replaces this file; `TODO.md`
  loses the import item and the obsolete tag mapping; `docs/README.md`
  and `STATE.md` updated; squash to `main`.

## Verification

- Iterate on the code without running checks; run the smallest test for
  the changed module while implementing.
- On the approved diff: `scripts/check.sh --changed`, then
  `scripts/check.sh` and `scripts/check.sh --qml` once.
- Offscreen screenshot for the dialog layout.
- Refresh the venv after each commit on the branch and after the merge.
- No test uses the user's real Lutris/Faugus files; fixtures only, with
  one manual read-only count against the local library.

## Risks

- An exact prefix is external state: a wrong `managed` flag could let
  Remove-game cleanup delete another launcher's prefix. It stays
  `managed=False` and gets its own test.
- The ID migration moves local prefixes; it must skip exact ones.
- PyYAML enters the dependency set and the release package lists.
- Re-import overwrites the source's own profile, like the STL import.
- Five source buttons may not fit the minimum width; the screenshot
  check covers it.
- Some Lutris/Faugus fields have no equivalent; the report must say so
  instead of guessing.
