# Metadata provider registry

Status: landed (2026-11-15; the eight landings ran 2026-11-11 to
2026-11-15).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

Work sharing one missing piece: a provider registry (service,
credential, cache, rate limit, field locks) behind three consumers: a
local metadata download, provider artwork and online categories. A
single Steam client could not answer a game without a Steam AppID, and
the manual fields were retyped anyway.

## Providers

| Field | Steam | IGDB | VNDB |
| --- | --- | --- | --- |
| description | yes | yes | yes (synopsis) |
| developer | yes | yes | yes (brand) |
| publisher | yes | yes | no |
| genre | yes | yes | no (tags are not genres) |
| series | yes | yes (franchise) | no (relations are not a series) |
| age ratings | ESRB/PEGI/USK | ESRB/PEGI/USK | no |
| date | yes | yes | yes |
| tags | yes | yes | yes (rated 2.0 or more) |

- **Steam** wraps `storemeta.py`; no key.
- **IGDB** needs a Twitch app (client id/secret) and the Apicalypse
  query language; 4 req/s.
- **VNDB** has a public API with no key; title search, synopsis, brands
  and tags; ~1 req/s.
- **PCGamingWiki** is dropped: both its Cargo API and its `appid.php`
  helper answer a plain HTTP client with a Cloudflare interstitial
  (`403`, `Just a moment...`). A stdlib adapter cannot reach it, and its
  fields are a subset of IGDB's. Engine/requirements/fixes stay a
  separate feature if the site ever exposes them.

GameStoryLog was evaluated and dropped: a React SPA whose data comes
from an internal cache worker, with no public API.

## Registry

- `src/tkarcade/metadata.py` declares `PROVIDERS`; each `Provider` entry
  carries `label`, `cache_dir`, `fields`, `resolve(game, target)`,
  `fetch(game, target)`, `search(query)`, `needs_key` and
  `min_interval`. The UI menu and the Preferences key field derive from
  the registry, so a new provider is one module, one registry line and
  its tests.
- `FIELDS` is the shared field map, in preview order: description,
  developer, publisher, genre, series, age_ratings, date, tags. `tags`
  joined it with C8; VNDB declares the subset it can answer.
- Cache: `app_cache_dir()/<provider cache dir>/<safe_stem(game_id)>.json`,
  30-day TTL, with `version`, `target` and `saved` recorded: a changed
  match or a payload from an older build reads as not cached. One
  namespace per provider keeps Steam and a store game apart; Steam keeps
  the `steam-meta` directory the Removed games cleanup already deletes.
- Rate gate per provider: IGDB 250 ms, VNDB 1 s, Steam none. IGDB's app
  token is cached in `igdb-meta/.token.json` and renewed on expiry or a
  changed client id.
- Credential: `[ui] igdb_client_id` and `igdb_client_secret`, next to
  `sgdb_api_key`; only IGDB needs one.
- Failure policy: a network error, a 401 or a missing key returns
  `None` and leaves the cache alone. A failed or empty fetch falls back
  to the stale cache, so an expired entry still fills the preview
  offline.

## Download policy

- Explicit action only; nothing fetches on open, save or startup, and
  the work stays off the GUI thread.
- **Fill empty only** by default; a typed field survives.
- Preview before writing: a dialog lists `Field | Current | New` with a
  **Replace existing values** switch, off by default.
- **Field locks**: `[metadata] locked`, a CSV normalized against the
  known field names, with a row toggle in the game dialog and a button
  that locks every field at once. A locked field is never replaced, and
  the online tags list has its own lock. `steam_appid` is identity, not
  metadata.
- The date is fillable when empty, and only a value that passes
  `metadata_date_valid` is written; a filled empty field becomes the
  override the cached store date already respects.
- An ambiguous search shows a candidate picker that saves the choice in
  the provider's identity field (`[metadata] vndb_id`,
  `[metadata] igdb_id`).
- `age_ratings` is a list: fill-empty only when empty, replaced as a
  whole when the switch is on.

## Consumers

| # | Landing | Deliverable |
| --- | --- | --- |
| C1 | `decisions/metadata-registry.md` | Registry + cache + rate gate + Steam adapter |
| C2 | `decisions/metadata-preview.md` | Download Metadata preview dialog |
| C3 | `decisions/metadata-locks.md` | Field locks, config and game dialog |
| C4 | `decisions/metadata-vndb.md` | VNDB adapter + candidate picker |
| C5 | dropped | PCGamingWiki: Cloudflare blocks a plain HTTP client |
| C6 | `decisions/metadata-igdb.md` | IGDB adapter + credential field + provider menu |
| C7 | `decisions/artwork-igdb.md` | IGDB artwork as a third source |
| C8 | `decisions/online-tags.md` | Online tags via Download Metadata |

The library format import and its enrichment follow as a separate
theme; the enrichment reuses C2's action in bulk.

## Remaining

- A real-key IGDB smoke test waited on the maintainer's Twitch
  application; the adapter and its tests did not.
- PCGamingWiki engine/requirements/fixes stay out of metadata.
- The categories stay manual (`decisions/online-tags.md`).
