# TODO — open work

Where the work stands: `docs/STATE.md` (injected into every session
through `instructions` in `opencode.json`; refresh it with `/handoff`).
This file is the open list only: finished work lives in `CHANGELOG.md`
and git, standing decisions in `docs/POLICIES.md`, and hard-won
QML/toolkit rules in `docs/QML-NOTES.md`. The document map is
`docs/README.md`. The order:

1. The 1.0 gate on the maintainer's release call: visual pass, shim
   removal, translations, release pass.
2. Epic and GOG as origins in 2.0: the 1.0 gate removes the rename
   machinery a new ID prefix would need, so a store game records its
   store in a `[store]` field and keeps a `local` ID.
3. Playnite in 3.0, only if the project supports another operating
   system: its library import, its plugin metadata and its tag mapping.

## Before 1.0

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

## Tags follow-up

- [ ] **Tag display polish.** Chips, autocomplete, manual order and
  colors; only if use shows the need.

## Artwork follow-up

- [ ] **VNDB release cover variants.** The release `images` list
  (`pkgfront`, language filter) can offer another cover when the
  visual novel's main image is missing or poor. Only if use shows the
  need.

## 2.0

- [ ] **Epic and GOG game sources.** The Add Game dialog picks the source
  (Steam, Local); a second store needs its own scan, a per-source import
  flow for a whole library and a decision record. The removed Scan dialog
  is the shape a per-source batch import can come back in.
  Design: `docs/plans/epic-gog-sources.md`.
- [ ] **IGDB without a per-user key.** Every user registers a Twitch
  application and pastes `[ui] igdb_client_id` / `igdb_client_secret`,
  and the Twitch console requires an OAuth redirect URL the app never
  uses. Playnite hides the setup behind its own backend service, which
  owns the Twitch keys. Decide at 2.0: project-hosted proxy (hosting,
  uptime, IGDB redistribution terms) against a key embedded in the
  package (public secret, Twitch confidentiality expectation) against
  dropping IGDB. No plan yet; a design lands before any code. A
  real-key smoke test of the adapter still waits on the maintainer's
  Twitch application.

## 3.0

Only if the project supports another operating system. Playnite is
Windows-only, so its formats wait for that decision.

- [ ] **Playnite library import.** A per-format reader for Playnite's
  library file, the ID/name mapping onto existing games and an
  ImportDialog page; an imported store game records its store in a
  `[store]` field and keeps a `local` ID. Design: a plan lands before
  the reader.
- [ ] **Playnite plugin metadata** (Steam/Epic/GOG/PCGW/VNDB) on top of
  the Playnite import: the enrichment reads the imported entries and
  fills the manual metadata fields through the registry. The bulk
  action needs its own plan.
- [ ] **Playnite tag mapping.** Map Playnite tags into `tags.toml` when
  the import lands.
