# Artwork cache keys and deleted-game cleanup

Status: decided (2026-11-07).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

`decisions/origin-prefixed-ids.md` deliberately kept the artwork cache
keyed by the bare Steam AppID, so downloaded grids survived the ID
migration. Every other per-game store moved to `<origin>-<body>`: the
config, profiles, logs, ProtonDB and release-date caches. The result was
two naming schemes in the cache directory and, worse, cached art for
games removed from the library stayed forever: the Removed games cleanup
only looked at profiles, logs and history, so a game that left nothing
but art never appeared as a leftover.

## Decision

1. The cache name is the canonical game ID: `steam-<appid>` for Steam,
   the local ID otherwise (`artwork._cache_key`). A bare numeric input
   still resolves to the same name; that normalization is the pre-1.0
   shim and goes away with the other shims.
2. `artwork.migrate_cache_keys()` runs at GUI startup next to
   `config.migrate_ids()`: every cache entry whose name starts with the
   bare digits (grids, sidecar, executable icon, manual artwork
   directory, ProtonDB and release-date files) is renamed to
   `steam-<name>`. A target that already exists is left alone, so the
   pass never overwrites and is idempotent.
3. The Removed games cleanup covers the cache:
   `artwork.cache_keys()` feeds the leftover candidates, a cache-only
   game shows up in the dialog with its artwork file count, and
   `cleanLeftovers` deletes grids, sidecar, executable icon, manual
   slots, the ProtonDB entry and the release-date entry.
4. Deletion stays manual and per game, inside the existing confirmation
   dialog. Nothing prunes the cache on its own: a removed game's art is
   still the only copy of a URL-pasted image.

## Rejected alternatives

- **Keep the numeric key and only prune.** Consistent cleanup, two
  naming schemes forever, and the 1.0 shim would have to keep rewriting
  bare AppIDs in artwork lookups.
- **Rename on read, without a migration.** The first run after the
  change would miss every cached grid and re-download the whole library.
- **Prune the cache automatically.** Downloads are cheap to fetch again,
  but URL-pasted art is not: deleting it belongs in the explicit
  cleanup, next to the prefix option.
