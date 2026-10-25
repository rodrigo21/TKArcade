# TODO — deferred ideas

Where the work stands: `docs/STATE.md` (injected into every session
through `instructions` in `opencode.json`; refresh it with `/handoff`).
This file is the open list only: finished work lives in `CHANGELOG.md`
and git, and hard-won QML/toolkit rules in `docs/QML-NOTES.md`.

## Recurring

- Re-audit the environment presets against vendor docs on every release
  tag (Mesa/NVIDIA semantics drift; verify `vblank_mode` /
  `__GL_SYNC_TO_VBLANK` values). Last: 2026-10-19 — the vsync pair
  stands against Mesa's current driconf registry (plus the xmlconfig
  env-override test) and the 580.x NVIDIA README; both are
  OpenGL/GLX-only, so Vulkan needs its own present mode and the presets
  carry that in their `note`.

## Deferred research

- [ ] **Game taxonomy and terminology (priority).** Separate what a game
  is (Origin: Steam/Local; Platform: Linux/Windows; Type) from how it
  runs (Runner/Environment: Steam Runtime, Proton via Steam, Proton via
  UMU, plain Wine). Windows is one platform, not a Proton/Wine game type.
  Review how Lutris actually models and presents Source/Runner/Platform
  (not only the column names) and pick names for the library columns and
  filters from that. This decides what the current `game_type` becomes
  and how existing configs migrate.
- [ ] Faugus: how it lets native games (including local ones) select a
  runtime/environment, with Steam Runtime/soldier as the reference case
  for local native games. Follows from the taxonomy above.
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
