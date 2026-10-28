# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` at `3577594` (the squash of
  the winetricks/prefix branch). The tree is clean apart from the
  maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed `3577594` (squash of 4 feature/fix commits plus STATES):
  - Winetricks UI (Runtime → Prefix): `In the Prefix:` reads the
    prefix's `winetricks.log` against the field's draft ("… — Pending at
    Launch: …"); `Add…` searches `winetricks list-all` (parsed once per
    process, keyed by binary path+mtime) and appends without duplicating;
    `Protontricks…`/`Winetricks…` opens the tool (`start_new_session`),
    its output lands in `games/<appid>-winetricks.log`, and a non-zero
    exit is reported with that path. Refusals: missing binary, no wine,
    prefix not created yet, Steam + custom prefix, Steam without
    compatdata ("installed and launched once").
  - Local prefix layout (**BREAKING**): `[runtime] prefix` and the
    Preferences base are the base; the WINEPREFIX is always
    `<base>/<folder>`. Folder = `prefix_name` (the GUI pins it from the
    game name on save, so renaming never moves the prefix) → game name
    via `xdg.folder_stem` (`TK's good-game_1` → `TKsGoodGame1`) → AppID.
    A prefix sitting at the base is folded into the subfolder before the
    launch; an occupied target exits 14. `Create` makes the subfolder,
    `Clear…` deletes only it and refuses a shared one. Field label:
    `Wine Prefix:`. Steam's compatdata dir keeps its own layout.
  - Play on a local game runs the build the GUI runs from
    (`sys.executable -m tkarcade.launcher`), not `tkarcade` from PATH
    (the system package here is post533 and used to refuse with exit 18);
    the Steam launch-options row names the PATH binary with its version
    and warns when it differs (`steam-stale`) or is missing.
  - Graphics (DXVK/vkd3d) is Wine-only: hidden and ignored for umu and
    Proton (they ship both), an older install is neutralised at launch,
    `--validate` no longer reports missing versions there.
  - `AGENTS.md`: refresh the venv after every change, before committing.
- Verified: `scripts/check.sh --qml` → 460 passed, ruff clean; QML cases
  `test_settings_winetricks_verbs_ui`, `test_settings_local_runtime_flow`;
  `.venv` at `post545.dev0+3577594` (the GUI's Play path runs this build).
- Next concrete step: `TODO.md` in order — Ludusavi defaulting to
  `[general] name` for local games, then the icons/cards views (the list
  is done). Small artwork leftovers in the TODO: per-game provider
  override and showing "Artwork Cleared" in the Status row.
- Open decisions: the Environment tab name collision; the Steam Linux
  Runtime item — (a) refuse when the runtime is missing from
  `~/.local/share/umu/` (exit 14) or let umu download it, (b) label
  "Steam Runtime" or "Steam Runtime (sniper)"; Steam shortcuts created
  before the AppID migration still pass the old AppID. Deferred: the
  winetricks fallback for a Steam game with a custom prefix (resolve its
  Proton and run `winetricks --gui` on `<custom>/pfx`).
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533, and Steam expands
  `tkarcade %command%` through PATH (the dialog now warns about it).
- Nothing blocking.
