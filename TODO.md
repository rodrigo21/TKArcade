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

## Deferred design review

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
