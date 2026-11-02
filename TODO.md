# TODO — deferred ideas

Where the work stands: `docs/STATE.md` (injected into every session
through `instructions` in `opencode.json`; refresh it with `/handoff`).
This file is the open list only: finished work lives in `CHANGELOG.md`
and git, standing decisions in `docs/POLICIES.md`, and hard-won
QML/toolkit rules in `docs/QML-NOTES.md`. The document map is
`docs/README.md`.

## Deferred research

- [ ] Playnite plugin metadata (Steam/Epic/GOG/PCGW/VNDB) for the local
  library import of Lutris/Playnite/Faugus file formats. The format
  import itself is still pending (only tarball, SteamTinkerLaunch and
  predecessor configs import today); this is the metadata enrichment on
  top of it.
- [ ] Online sources à la Playnite for categories/tags (the per-game
  categories and the drawer filter shipped without them).

## Deferred design review

- [ ] **Runtime archives in a cache dir.** Downloads and archive
  extraction were deferred when per-game DXVK/vkd3d versions landed
  (`docs/decisions/external-runtimes.md`): the launcher is stdlib-only,
  extraction needs a safe format story, and the cache needs a lifecycle.
  Versions today come from the Preferences directories only.
- [ ] **Steam Linux Runtime pick for local Wine/umu games.** A local
  native game already picks one; a local Wine or umu game still runs
  outside a container, so umu's own runtime selection is not exposed.
- [ ] **Issue badge in the card and icon views.** The table's
  error/warning badge and its tooltip are table-only; `GameCard` and
  `GameIconDelegate` need the same when those views are revisited.
- [ ] **Unify prefix resolution.** `prefixDir`, `_prefix_users`,
  `_resolved_prefix`, `installedVerbs`, `openWinetricksGui` and
  `_prefix_to_clear` each resolve a game's Wine prefix on their own;
  folding them into one resolver is a no-behavior-change refactor
  across the model and the launcher, deferred to a session with a
  dedicated verification budget.

## Deferred release

Only when the maintainer opens the subject.

- [ ] **1.0: drop every compatibility shim.** 1.0 should read only the
  current format; the compatibility promise starts after it. Remove
  `--migrate-ids` and the automatic rename plus numeric lookups for bare
  AppIDs (configs, profiles, logs, history, artwork), old numeric AppIDs
  in launch options, the `[general] appid` and `--appid` aliases once
  pass 2 lands, the legacy `environment` key that load ignores and save
  drops, and `move_legacy_prefix`. Keep the `config_version` newer-file
  warning and the third-party importers (they read other tools, not old
  TKArcade builds).
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
