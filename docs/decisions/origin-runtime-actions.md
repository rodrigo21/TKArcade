# Origin/runtime-aware context menu

Status: implemented (2026-11-01).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: the game-list context menu should offer only the actions that fit
a game's origin and configured runtime, and the rules should live in one
place instead of scattered checks in QML. Canonical IDs made the old
`/^\d+$/` Steam test always false, so Steam games lost their menu items
and showed the local ones.

## Decision

`GameListModel.contextActions(appid)` is the single table. It returns
`is_steam`, `install`, `prefix`, `prefix_applicable`, `shader` and
`shader_size`; `MainPage.qml` binds its menu items to those values and
keeps no origin test of its own.

| Game | Copy | ProtonDB | Install Folder | Prefix Folder | Shader Cache |
| --- | --- | --- | --- | --- | --- |
| Steam · proton | Launch Options | yes | Steam install dir (if installed) | compatdata/custom when it exists; visible disabled until then | Steam cache |
| Steam · native | Launch Options | yes | Steam install dir | hidden unless a prefix exists | Steam cache |
| Local · native (± Steam Runtime) | Launch Command | no | exe folder (`launch_cwd` wins) | hidden | hidden |
| Local · wine | Launch Command | no | exe folder (`launch_cwd` wins) | WINEPREFIX when created; visible disabled before that | hidden |
| Local · umu | Launch Command | no | exe folder (`launch_cwd` wins) | WINEPREFIX when created; visible disabled before that | hidden |

Play, Edit, Validate, Clear History, Clone, Remove, Reset and Categories
stay for every game; Terminate stays running-only.

## Install folder

A local game's install folder is the directory a launch uses as its
working directory: `launcher.local_run_cwd()` (`launch_cwd` when it is a
directory, else the executable's folder, `""` when the executable is
missing). The menu reuses that function instead of reimplementing the
rule, so the folder it opens is the folder the game runs from.

## Prefix applicability

- Steam: visible when the configured runtime is `proton` or a prefix
  already exists. That keeps a native game with a leftover `compatdata`
  openable while a native game without one has no dead entry.
- Local: visible only for `wine` and `umu`; a native game never offers
  it, even if an old prefix directory remains.
- The path is passed through `os.path.expanduser()` and must be a
  directory to enable the action. An applicable but not yet created
  prefix stays visible and disabled, so the user can see that the game
  will get one.
- The label is `Open Prefix Folder`, covering Steam's `compatdata` (or
  custom dir) and a local `WINEPREFIX` alike.

`prefixDir()`, `shaderDir()` and `shaderSize()` stay as they are: the
settings dialog and the runtime table still call them directly.

## Rejected alternatives

- **Origin checks in QML.** They drift from the model and cannot be
  unit-tested: the regex left behind by the ID change silently inverted
  the Steam rows. One model table keeps the matrix testable.
- **Disabling instead of hiding.** A disabled entry for an action a game
  can never use (shader cache on a local game) is noise; hide those.
  Applicable-but-not-ready actions (a prefix not created yet) are the
  exception and stay visible.
- **Duplicating the launch working-directory rule in the menu.** Two
  copies would disagree after a change; reusing `local_run_cwd()` keeps
  menu and launch aligned.
