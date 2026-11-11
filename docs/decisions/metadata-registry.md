# Metadata provider registry

Status: landed (2026-11-11).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

C1 of `docs/plans/metadata-provider.md` needed one place where a
metadata source declares what it can fill and how to reach it. C2 will
add the action UI, and each later adapter (VNDB, PCGamingWiki, IGDB)
must not repeat the cache, the target keying or the rate limit. The
Steam download already worked, with its cache and payload mapping in
`storemeta.py`, and that mixed two layers.

## Decision

1. `src/tkarcade/metadata.py` owns the registry: `FIELDS` (description,
   developer, publisher, genre, series, age_ratings, date) and
   `PROVIDERS`, where each `Provider` declares `label`, `cache_dir`,
   `fields`, `resolve(game_id, target)`, `fetch(game_id, target)`,
   `needs_key` and `min_interval`. `search(game)` arrives with the first
   name-based provider (VNDB, C4).
2. `storemeta.py` keeps only the Steam payload layer: `resolve` (the
   explicit store link wins over the AppID a Steam ID derives),
   `normalize` and `fetch`. It no longer writes a cache.
3. Cache: `app_cache_dir()/<provider cache dir>/<safe_stem(game_id)>.json`,
   30-day TTL, recording `saved` and the resolved `target`, so a changed
   store link or match reads as not cached. Steam keeps the landed
   `steam-meta` namespace: the Removed games cleanup already deletes it
   and `decisions/metadata-download.md` stays correct.
4. Rate gate: `Provider.min_interval` per provider, in memory, based on
   `time.monotonic` and a lock. Steam declares no interval and never
   waits.
5. `download(provider, game_id, target)` is the one entry point: fresh
   cache first, one provider call otherwise, cache written only when the
   call answered. A network error, a 401 or a missing key returns `None`
   and leaves the cache alone.
6. Steam now extracts the release date as well (`release_date` through
   `releasedate.parse_date`), so the adapter fills every field in
   `FIELDS`. Nothing writes it yet: the action UI and the field locks
   come with C2 and C3.
7. No UI change. The model's Download Metadata worker calls
   `metadata.download("steam", ...)` and the QML keeps filling only the
   fields it maps; an unknown `date` key is ignored.

## Rationale

- One cache implementation and one failure policy replace a copy per
  adapter; a provider module only maps a payload to the shared fields.
- Keeping the Steam cache directory avoids a migration and keeps the
  orphan cleanup honest.
- The rate gate is per provider because the limits differ by an order
  of magnitude, and Steam needs none.

## Consequences

- A new provider is one module, one registry line and its tests.
- The `[ui]` credential fields and the provider menu stay open; only
  IGDB will need a key.
- The date field is fetched but unwritten until C2.

## Alternatives

- **Keep the cache inside `storemeta.py` and let the registry delegate.**
  Copies the cache into every adapter, which is the duplication the
  registry exists to prevent.
- **Move the Steam cache to `metadata/steam/`.** Needs a migration and
  rewrites the cleanup and a landed decision for no user gain.
- **A registry entry with `search()` now.** Nothing calls it before the
  name-based providers; it would be untested service code.
