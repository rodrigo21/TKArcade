# TODO — deferred ideas

Where the work stands: `docs/STATE.md` (injected into every session
through `instructions` in `opencode.json`; refresh it with `/handoff`).
This file is the open list only: finished work lives in `CHANGELOG.md`
and git, and hard-won QML/toolkit rules in `docs/QML-NOTES.md`.

## Deferred research

- [ ] **Game taxonomy and terminology (priority).** Separate what a game
  is (Origin: Steam/Local; Platform: Linux/Windows; Type) from how it
  runs (Runner/Environment: Steam Runtime, Proton via Steam, Proton via
  UMU, plain Wine). Windows is one platform, not a Proton/Wine game type.
  Review how Lutris actually models and presents Source/Runner/Platform
  (not only the column names) and pick names for the library columns and
  filters from that. This decides what the current `game_type` becomes
  and how existing configs migrate.
- [ ] **Faugus / Steam Linux Runtime for local Linux games.** Let a local
  Linux game (`environment = "native"`, origin Local) pick a Steam Linux
  Runtime (scout/soldier/sniper/steamrt4) and run inside it through
  `umu-run`, like the Faugus `runtime` combo; Steam games already get the
  SLR from Steam. Follows from the taxonomy above.
  - Field stays orthogonal to `environment`: `[runtime] steam_runtime =
    ""|scout|soldier|sniper|steamrt4`, only for Local + `native` (ignored
    otherwise), configured, no migration, not breaking. Needs
    `normalize_steam_runtime()`, `SECTION_KEYS["runtime"]`, parse next to
    `proton_path` and serialize in `gui/model.py`.
  - Launch: after `swap_native_executable`, wrap `[umu-run, *argv]` at the
    same level as `_wrap_local_runtime`, with `PROTONPATH=umu-<name>` and
    `GAMEID=tkarcade-<appid>` (no `WINEPREFIX`, no DXVK/vkd3d); missing
    `umu-run` raises exit 14 with an SLR-specific message; the doctor
    checks `umu-run` and `~/.local/share/umu/<name>`; `_launch_summary`
    reports the configured runtime (`proton.py::native_runtime` only knows
    Steam paths).
  - Presentation: `runner_label(environment, is_steam, steam_runtime="")`
    returns "Steam Runtime" for Local+Native+SLR; Settings gains a "Steam
    Runtime:" combo (`Disabled` + the four), serialized as
    `runtime_steam_runtime`. Origin/Platform derive as today.
  - Verified against the umu installed here (2026-10-27):
    `PROTONPATH=umu-soldier|umu-sniper|umu-steamrt4` builds a passthrough
    compat tool for native apps (`umu_proton.py::_get_umu_runtime_tool`,
    layer `umu-passthrough`, entry point `exec "$@"`); `umu-scout` is not
    a shim but a real tool downloaded from `loathingKernel/umu-scout`;
    `GAMEID` only names the prefix dir; runtimes live in
    `~/.local/share/umu/<steamrt2|steamrt3|steamrt4>` and a missing one is
    downloaded by umu on first use. `UMU_NO_PROTON=1` is the legacy
    "container only, no Proton" switch (`RUNTIMEPATH` maps to
    `umu-soldier`/`umu-sniper`/`umu-steamrt4`, and `umu_run()` forces
    `umu-<runtime>`), so set `PROTONPATH` only and leave it alone.
  - Open decisions: (a) missing runtime → refuse with exit 14 (keeps
    "nothing is downloaded") or let umu download it and document that;
    (b) label "Steam Runtime" (version only in Settings) or "Steam Runtime
    (sniper)".
  - Files/tests: `config.py`, `launcher.py`, `gui/model.py`,
    `GameSettings.qml`, README, CHANGELOG, pt_BR catalog, man page;
    `test_config.py` (round-trip, normalizer, `runner_label`),
    `test_backends.py` (argv/env, missing `umu-run`, doctor) and one QML
    case. Verify with `scripts/check.sh [--changed]`, the QML driver and an
    offscreen screenshot.
- [ ] Playnite plugin metadata (Steam/Epic/GOG/PCGW/VNDB) for the local
  library import of Lutris/Playnite/Faugus file formats. The import
  itself shipped; this is the metadata enrichment on top of it.
- [ ] Online sources à la Playnite for categories/tags (the per-game
  categories and the drawer filter shipped without them).

## Settings and metadata (sessions ahead)

Order: (1) local AppID slug + migration — landed; (2) settings reorg;
(3) game metadata fields and categories.

- [ ] Settings reorg (option B: break config keys where it helps).
  Landed on the `settings-reorg` branch, awaiting the maintainer's
  review:
  - `Game` and `Launch` merge on General; Pre/Post moves to the
    Environment tab (which now holds the env vars too).
  - One `[runtime]` section: `prefix` (Steam compatdata dir or local
    `WINEPREFIX`) and `tool` (compat tool / Wine binary / `PROTONPATH`)
    replace the duplicated `[proton]`/`[runtime]` stores; `[proton]` is
    gone and old keys stay as ignored extras.
  - `Compatibility` becomes `Runtime` (environment, tool, prefix,
    verbs, graphics layers, debug) and `System` orders Night Light
    before Network.
  - Deferred: rename the `Environment` tab (its name still collides
    with the `[general] environment` runtime choice, now on Runtime).
- [x] Winetricks/Protontricks inside the Runtime tab (`Prefix` section).
  - Landed: `Add…` opens a searchable `winetricks list-all` picker
    (cached per process) that appends to the verbs field; the section
    lists the prefix's own `winetricks.log` verbs and the field's
    pending ones apart; `Protontricks…`/`Winetricks…` opens the
    interactive tool (`protontricks --gui <appid>`, or `winetricks
    --gui` with the resolved `WINEPREFIX`/`WINE`) and the list refreshes
    when it exits. Missing binary, prefix not created yet and a Steam
    game with a custom `[runtime] prefix` are refused with a message.
  - Deferred: a Steam game whose `[runtime] prefix` moves the compatdata
    dir cannot use `protontricks --gui` (it always targets Steam's own).
    The fallback is to resolve the game's Proton (compat mapping +
    `runtimes.find_proton`) and run `winetricks --gui` with
    `WINEPREFIX=<custom>/pfx` and that `files/bin/wine`.
- [ ] Ludusavi name for local games. Without `[ludusavi] name_override`
  Ludusavi resolves the game by Steam AppID, and a local game has none
  (its id is `local-*`), so `wrap` finds nothing. Default the name to
  `[general] name` when the game is not a Steam id and the override is
  empty, and keep the explicit override winning. In the GUI the field
  placeholder should read `Empty = <game name>` for local games, and
  the coverage check should use the same fallback. Files/tests:
  `launcher.py` (wrap args), `gui/model.py` (fields/coverage),
  `backends/ludusavi.py` possibly unchanged, backend argv tests for a
  local game (name present) and a Steam game (absent).
- [ ] Artwork Source AppID: landed (renamed from Donor AppID, official
  Steam assets first without a key, SteamGridDB as the fallback or
  first with the "Artwork Source" preference, per-shape download, cache
  sidecar recording the provider, Status row, forced `Fetch Artwork`).
  Left: the per-game `[artwork]` block has no way to override the
  *provider* for one game (the preference is global); decide if a rare
  mismatched game needs it. A cleared AppID keeps its `"cleared": true`
  mark in `grids/<appid>.json` with no visible trace in the UI — if the
  art stops coming back and nobody remembers the Clear, that file is the
  answer (consider showing "Artwork Cleared" in the Status row).
- [ ] Views beyond the list (icons and cards): the list is the current
  focus. Give the Cover slot a consumer — the card's `Kirigami.Card`
  banner reads `gameIcon`, which falls back to the source AppID's icon,
  not to the cover — and review the card banner framing. `cover` is
  written, cleared and migrated today but nothing renders it. Also: the
  Status row's long text wraps mid-sentence at the 612 px minimum
  ("…Use Fetch / Artwork."), next to a button with the same words.
- [ ] Categories redesign: how categories work and how they are added.
  - Drop the Category column from the library list; show the game's
    categories in the right-hand details section instead. The column
    currently looks broken.
- [ ] Per-game metadata fields (all optional), rendered as name suffixes
  in the library list and the other views, never inside the AppID:
  - `version`: free-form for local games; shown as `Name [version]`
    (space before the bracket). On save a trailing `[x]` in the name
    moves into the field: `Jogo Bom [v0.3.5]` → name `Jogo Bom`,
    version `v0.3.5` (the `v` is not required).
  - `date`: `YYYY-MM-DD`, also accepting `YYYY-MM` and `YYYY`
    (Playnite-style, richer than Lutris' year).
  - `tag`: free-form state label, shown as `Name [version] (TAG)`
    with a space before the parenthesis.
  - Applies to Steam and local games; the list column/views layout is
    part of the work.
- [ ] Steam shortcuts created before an AppID migration still cache
  `tkarcade <old-appid>` in their launch options: decide whether to
  rewrite `shortcuts.vdf` or keep the manual warning.

## Deferred design review

- [ ] **DXVK/vkd3d inside UMU/Proton prefixes.** umu and Steam's Proton
  ship their own DXVK and vkd3d, so `[graphics]` is hidden and ignored
  for them (an old install is only neutralised). Decide whether
  overriding the runtime's versions should be possible at all, how (copy
  into the prefix vs. the runtime's own layer dir), which selector the
  dialog needs, and what happens when Proton updates.
- [ ] **External runtime versions.** Like Lutris, allow several DXVK,
  vkd3d-proton and Proton versions from arbitrary locations, not only
  what is installed system-wide. Audit what `[ui] dxvk_dirs`,
  `vkd3d_dirs` and `proton_dirs` already cover, what is missing (e.g.
  per-game overrides, archives in the cache dir, Steam Linux Runtime
  picks) and how the GUI should present it.
- [ ] Preferences content: decide what is truly global (e.g. Proton/DXVK
  directories, prefix base, SteamGridDB key) versus per-game, and whether
  the window should be split into tabs/sections. The current form mixes
  both and some rows are only meaningful with the tray enabled.
- [ ] Global Defaults content: audit which fields belong in the template.
  Per-game identity/artwork and paths that only make sense for one game
  should not be there.

## Deferred release

Only when the maintainer opens the subject.

- [ ] Release pass: group the `Unreleased` entries, update the `-git`
  PKGBUILD, `diff -r` against TKSteamLaunch, check package versions and
  run `scripts/display-check.sh`. Numbering/tag and signing are the
  maintainer's decision.
- [ ] Re-audit the environment presets against vendor docs on every
  release tag (Mesa/NVIDIA semantics drift; verify `vblank_mode` /
  `__GL_SYNC_TO_VBLANK` values). Last: 2026-10-19 — the vsync pair
  stands against Mesa's current driconf registry (plus the xmlconfig
  env-override test) and the 580.x NVIDIA README; both are
  OpenGL/GLX-only, so Vulkan needs its own present mode and the presets
  carry that in their `note`.
