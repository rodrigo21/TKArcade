# Plan: Epic and GOG game sources

Status: proposal, not approved. Awaiting the maintainer's decisions
below; when it lands it becomes `docs/decisions/game-sources.md` with a
landing banner and this file is deleted.
Created: 2026-11-11. Read `TODO.md` "Other game sources" and
`docs/STATE.md` "Next" for the current snapshot.

## Goal

Add Epic and GOG as game origins: discover installed games, import them
into the library, and launch them. The smallest complete change reuses
the local launch path: a store game is local for execution
(wine/umu/native, its own prefix, TKArcade env/presets) and differs only
in discovery, origin label and store metadata.

## Evidence (checked 2026-11-11)

**Origin is binary today.**
- `steam.origin()` (`src/tkarcade/steam.py:21`) returns `steam`/`local`
  from the ID prefix; `is_steam_id()` delegates; no value registry.
- Hard-coded binary branches: runtime matrix `launcher.py:69-82`,
  prefix target `config.py:904`, Play `gui/model.py:4779`,
  source filter `gui/model.py:5373`, counts `gui/model.py:424`,
  sidebar `qml/main.qml:237-266`, Add Game source combo
  `qml/AddDialog.qml:118-139`, runtime combo `qml/GameSettings.qml:283`,
  context-action matrix in `gui/model.py`.
- About 30 branch points total; `origin-runtime-actions.md` and
  `game-taxonomy.md` document the current axis.

**Heroic is installed locally and is the cheapest discovery source**
(pure JSON, stdlib):
- `~/.config/heroic/gog_store/installed.json`: `appName`,
  `install_path`, `executable`, `platform`, `version`.
- `~/.config/heroic/store_cache/gog_install_info.json` (5 KB): title and
  build per app, keyed `<appName>_<platform>_...`.
- Epic: `~/.config/heroic/legendaryConfig/legendary/installed.json` is
  absent here (no Epic game installed), so the Epic path cannot be
  validated on this machine.
- Amazon (`nile_store`) and Heroic sideload apps follow the same shape.

**GOG executable gap.** `installed.json` carries an empty `executable`
for some games (one of the two GOG games installed here). A Windows GOG
game's exe is described by `goggame-*.info` inside the install dir; a
Linux build sometimes needs guessing. The import must therefore allow an
empty exe and let the user fill it in the game settings, instead of
refusing the import.

**Store games have no Steam AppID.** ProtonDB, Steam artwork CDN, the
Steam page link and compatdata are unavailable; SGDB-by-name, the icon
fallback chain and ProtonDB-via-`[metadata] steam_appid` still apply.

## Decisions required before the first batch

1. Scope: GOG first (validatable here) then Epic, both, or GOG only.
   Recommendation: GOG first.
2. Discovery source: Heroic configs (recommended, zero new deps),
   legendary/gogdl standalone (not present here), both, or no discovery
   (manual Add only).
3. Launch: direct exe with TKArcade wine/umu (recommended, keeps env,
   presets, prefix and runtime selection), handoff to Heroic, or direct
   with Heroic fallback.
4. Import UI: Add Game for one game plus an ImportDialog batch page
   (recommended), Add Game only, or ImportDialog only.

## Batches (one commit each)

### 1. Origin foundation, no UI

- `steam.py`: a small origin registry (`steam`, `local`, `epic`, `gog`),
  `origin()` parsing `<origin>-<body>`, `is_local_family()`.
- `launcher.py`: `runtime_problem()` allows native|wine|umu for the
  local family (epic/gog), proton only for steam; error messages keep
  naming valid choices.
- `config.py`: prefix target treats epic/gog as managed local prefixes;
  `new_game_id(origin, name)` generalizes `new_local_id()`.
- Tests: origin parsing, runtime matrix, ID creation, prefix target.

### 2. Discovery module

- New `src/tkarcade/heroic.py`, stdlib `json` only:
  - read GOG installed games from `gog_store/installed.json`;
  - resolve title from `gog_install_info.json`;
  - resolve exe: `installed.json` -> `goggame-*.info` (playTasks) ->
    empty (user fills it);
  - return a candidate dataclass (origin, store app name, title, install
    path, exe, platform).
- Cache like `steam.py` does, cleared on Reload.
- Epic support behind the same reader if its file exists; no validation
  claim until a real Epic game is installed.
- Tests: fixtures for both JSON shapes, empty exe, missing files.

### 3. Import flow

- Add Game dialog: source combo gains GOG (and Epic); picking one lists
  installed candidates, creates the config with origin ID
  `gog-<appName>`, name from the store title, runtime `umu` first.
- ImportDialog: a batch page listing installed store games not yet in
  the library, with per-row selection, following the removed Scan dialog
  shape.
- `gui/model.py`: candidate slots, create/save, refresh.
- QML tests plus an offscreen screenshot check.

### 4. Presentation and docs

- Origin labels (GOG, Epic), sidebar Sources entries with counts,
  source filter, card origin line, column values.
- Guards: Steam-only actions hidden/refused for store origins.
- `docs/decisions/game-sources.md`: axis, discovery source, launch
  choice, exe fallback, rejected alternatives.
- `README.md`, `CHANGELOG.md`, `TODO.md` (remove the finished item),
  `docs/README.md` map entry, `tests/test_docs.py` expectations.

## Verification

- Batch 1-2: `pytest tests/test_steam.py tests/test_heroic.py`,
  `scripts/check.sh --changed`.
- Batch 3: QML cases plus `scripts/check.sh --qml` once, offscreen
  screenshot.
- Before each commit: full `scripts/check.sh` on the approved diff.
- Batch 3-4 needs a real GOG launch test: the two games installed here,
  one with a known exe and one with the empty-exe fallback.

## Risks

- The exe gap may make some GOG Linux builds unlaunchable until the user
  fills the path; the import must accept that calmly.
- About 30 binary origin branches: a missed one leaks a Steam action into
  a store game. An origin registry plus a test that walks every
  `is_steam_id` call site's behaviour for a store ID mitigates it.
- Epic cannot be validated here; shipping it means relying on fixtures
  and Heroic's documented layout until a real install exists.
- Importing a whole library creates many configs at once; the batch page
  must default to a safe selection and never overwrite an existing ID.
