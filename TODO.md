# TODO — deferred ideas

Where the work stands: `docs/STATE.md` (injected into every session
through `instructions` in `opencode.json`; refresh it with `/handoff`).
This file is the open list only: finished work lives in `CHANGELOG.md`
and git, standing decisions in `docs/POLICIES.md`, and hard-won
QML/toolkit rules in `docs/QML-NOTES.md`. The document map is
`docs/README.md`.

## Deferred research

- [ ] **Other game sources (Epic, GOG).** The Add Game dialog picks the
  source (Steam, Local); a second store needs its own scan, a per-source
  import flow for a whole library and a decision record. The removed
  Scan dialog is the shape a per-source batch import can come back in.
- [ ] **Fourth artwork kind (background/fanart).** A wide backdrop for
  the game dialog/page: new entry in `artwork.ART_KINDS`, its cache name,
  provider fetch, manual slot and one more preview tile in the Artwork
  tab (the row already sizes each kind by its own box).
- [ ] **Other artwork sources.** Steam's CDN and SteamGridDB are the only
  providers today. A third source (IGDB, GiantBomb, a Playnite-style
  metadata service) would need its own key, cache and provider entry in
  the Download From list, plus a decision record.
- [ ] **Metadata download.** Fill description, developer, publisher,
  genre, series and age rating from a provider. Steam's store
  `appdetails` already supplies most fields for Steam games (the
  release-date lookup uses the same API); local games need an IGDB-style
  service and key. Needs a decision for the provider, cache and the
  per-game Download Metadata action.
- [ ] **ProtonDB for local games.** A local game may also exist on
  Steam. A per-game Steam AppID (separate from the Artwork Source AppID,
  which is art-only) would let the ProtonDB cache and the Details/table
  badge work; needs a decision and a cache key that does not collide
  with `local-<slug>`.
- [ ] Playnite plugin metadata (Steam/Epic/GOG/PCGW/VNDB) for the local
  library import of Lutris/Playnite/Faugus file formats. The format
  import itself is still pending (only tarball, SteamTinkerLaunch and
  predecessor configs import today); this is the metadata enrichment on
  top of it.
- [ ] Online sources à la Playnite for categories/tags (the per-game
  categories and the drawer filter shipped without them).

## Deferred release

Only when the maintainer opens the subject.

- [ ] **1.0 packaging: the new Python deps.** Confirm `icoextract` and
  `pefile` actually ship in the AppImage (the bundle must pick them up
  from the project dependencies) and depend on them in every package
  recipe before the release build. Same pass checks `zstandard` on 3.14.

- [ ] **1.0: drop every compatibility shim.** 1.0 should read only the
  current format; the compatibility promise starts after it. Remove
  `--migrate-ids` and the automatic rename plus numeric lookups for bare
  AppIDs (configs, profiles, logs, history, artwork), old numeric AppIDs
  in launch options, the `[general] appid` and `--appid` aliases once
  pass 2 lands, the legacy `environment` key that load ignores and save
  drops, and `move_legacy_prefix`. Keep the `config_version` newer-file
  warning and the third-party importers (they read other tools, not old
  TKArcade builds).
- [ ] **1.0: restore translations.** Translations are suspended until
  1.0 (2026-11-08): new QML strings ship in English,
  `tests/test_i18n.py` catalog tests are skipped and
  `scripts/refresh-translations.sh` is not run. At 1.0, run the script,
  translate every message, remove the skips and update
  `docs/DEVELOPMENT.md`.
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
