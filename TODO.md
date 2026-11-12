# TODO — open work

Where the work stands: `docs/STATE.md` (injected into every session
through `instructions` in `opencode.json`; refresh it with `/handoff`).
This file is the open list only: finished work lives in `CHANGELOG.md`
and git, standing decisions in `docs/POLICIES.md`, and hard-won
QML/toolkit rules in `docs/QML-NOTES.md`. The document map is
`docs/README.md`. The order:

1. Metadata provider registry first: Steam, VNDB and IGDB (the
   PCGamingWiki adapter is dropped: Cloudflare blocks a plain HTTP
   client); the local metadata download, the provider artwork source
   and the online categories all consume it. IGDB landed last inside the
   phase because it needs a Twitch app key.
2. Library import second: the Playnite-style enrichment reuses the
   provider, and the provider has nothing to enrich before the import
   exists.
3. The 1.0 gate on the maintainer's release call: visual pass, shim
   removal, translations, release pass.
4. Epic and GOG as origins in 2.0: the 1.0 gate removes the rename
   machinery a new ID prefix would need, so a store game records its
   store in a `[store]` field and keeps a `local` ID.

## Before 1.0

- [ ] **Metadata provider registry (Steam, VNDB, IGDB).**
  One client behind the local metadata download, the provider artwork
  source and the online categories: per-provider adapters, cache, rate
  limit, a preview before writing and per-field locks. It covers a game
  without a Steam AppID. PCGamingWiki is out: Cloudflare blocks a plain
  HTTP client, and IGDB carries the fields it would have added.
  Design: `docs/plans/metadata-provider.md`.
- [ ] **Other artwork sources.** Steam's CDN, SteamGridDB and IGDB are
  the providers today; IGDB serves cover and banner only (no square
  icon) and needs the IGDB ID from Download Metadata.
  Design: `docs/plans/metadata-provider.md`.
- [ ] **Library format import (Lutris, Playnite, Faugus).** Only tarball,
  SteamTinkerLaunch and predecessor configs import today. A foreign
  library file needs a per-format reader, the ID/name mapping onto
  existing games and an ImportDialog page. An imported store game records
  its store in a `[store]` field and keeps a `local` ID.
  Design: a plan lands before the first reader.
- [ ] Playnite plugin metadata (Steam/Epic/GOG/PCGW/VNDB) on top of the
  library format import above: the enrichment reads the imported
  entries and fills the manual metadata fields through the registry.
  Design: `docs/plans/metadata-provider.md`.
- [ ] **Online tags follow-up.** Download Metadata fills `[metadata]
  tags` from Steam, IGDB and VNDB, and Details shows them read-only.
  After the library import, decide whether the sidebar categories derive
  from them, whether they get their own filter and editor, and whether a
  bulk download is worth it.
  Design: `docs/decisions/online-tags.md`.

Release, only when the maintainer opens the subject:

- [ ] **1.0: drop every compatibility shim.** 1.0 should read only the
  current format; the compatibility promise starts after it. Remove
  `--migrate-ids` and the automatic rename plus numeric lookups for bare
  AppIDs (configs, profiles, logs, history, artwork), old numeric AppIDs
  in launch options, the `--appid` alias, the legacy `environment` key
  that load ignores and save drops, and `move_legacy_prefix`. Keep the
  `config_version` newer-file warning and the third-party importers (they
  read other tools, not old TKArcade builds).
- [ ] **1.0: restore translations.** Translations are suspended until
  1.0 (2026-11-08): new QML strings ship in English,
  `tests/test_i18n.py` catalog tests are skipped and
  `scripts/refresh-translations.sh` is not run. At 1.0, run the script,
  translate every message, remove the skips and update
  `docs/DEVELOPMENT.md`.
- [ ] Release pass: group the `Unreleased` entries, update the `-git`
  PKGBUILD, `diff -r` against TKSteamLaunch, check package versions,
  confirm `icoextract` and `pefile` ship in the AppImage bundle and run
  `scripts/display-check.sh`. Numbering/tag and signing are the
  maintainer's decision.
- [ ] Re-audit the environment presets against vendor docs on every
  release tag (Mesa/NVIDIA semantics drift; verify `vblank_mode` /
  `__GL_SYNC_TO_VBLANK` values). Last: 2026-10-19 — the vsync pair
  stands against Mesa's current driconf registry (plus the xmlconfig
  env-override test) and the 580.x NVIDIA README; both are
  OpenGL/GLX-only, so Vulkan needs its own present mode and the presets
  carry that in their `note`.

## 2.0

- [ ] **Epic and GOG game sources.** The Add Game dialog picks the source
  (Steam, Local); a second store needs its own scan, a per-source import
  flow for a whole library and a decision record. The removed Scan dialog
  is the shape a per-source batch import can come back in.
  Design: `docs/plans/epic-gog-sources.md`.
