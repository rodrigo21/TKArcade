# Metadata provider registry: four providers, one client (proposal)

Status: proposal, not approved. C1 (the registry plus the Steam adapter)
landed as `docs/decisions/metadata-registry.md`, C2 (the action preview)
as `docs/decisions/metadata-preview.md`, C3 (the field locks) as
`docs/decisions/metadata-locks.md`, C4 (the VNDB fallback and the
candidate picker) as `docs/decisions/metadata-vndb.md`, C6 (the IGDB
adapter, the credentials and the provider menu) as
`docs/decisions/metadata-igdb.md`, and the earlier Steam `appdetails`
download as `docs/decisions/metadata-download.md`. C5 (PCGamingWiki)
was dropped: the site answers a plain HTTP client with a Cloudflare
interstitial, so its Cargo API is unreachable. The remaining consumers
below are still open. When the rest lands it belongs in
`docs/decisions/metadata-provider.md` with a landing banner, and this
file is deleted.

## Problem

`TODO.md` lists work that shares one missing piece: a provider registry
(service, credential, cache, rate limit, field locks) behind three
consumers: a local metadata download, provider artwork and online
categories. A single Steam client cannot answer a game without a Steam
AppID, and the manual fields would be retyped anyway.

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
| engine/requirements/fixes | no | no | no |

- **Steam** wraps the landed `storemeta.py`; no key.
- **IGDB** needs a Twitch app (client id/secret) and the Apicalypse query
  language; 4 req/s.
- **VNDB** has a public API with no key; title search, synopsis, brands
  and tags; ~1 req/s.
- **PCGamingWiki** is out: both its Cargo API and its `appid.php` helper
  answer a plain HTTP client with a Cloudflare interstitial (`403`,
  `Just a moment...`, tested 2026-11-11). A stdlib adapter cannot reach
  it, and its fields are a subset of IGDB's. Engine/requirements/fixes
  stay a separate feature if the site ever exposes them.

GameStoryLog was evaluated and dropped: a React SPA whose data comes
from an internal cache worker, with no public API. It is not a TODO
item; it comes back only if the site publishes an API or an export.

## Registry

- New `src/tkarcade/metadata.py`: a `PROVIDERS` registry; each entry
  declares `label`, `fields`, `needs_key`, `resolve(game, target)` and
  `fetch(game, target)`. `search(game)` arrives with the first
  name-based provider (VNDB). The UI menu and the Preferences key field
  derive from the registry, so a new provider is one module, one
  registry line and its tests.
- Cache: `app_cache_dir()/<provider cache dir>/<safe_stem(game_id)>.json`,
  30-day TTL, `target` and `saved` recorded, so a changed match reads as
  not cached. One namespace per provider keeps Steam and a store game
  apart; Steam keeps the landed `steam-meta` directory, which the
  Removed games cleanup already deletes.
- Rate gate per provider: IGDB 250 ms, VNDB 1 s, Steam none. Token
  cache for IGDB in the same dir, invalidated when the client id changes.
- Credential: `[ui] igdb_client_id` and `igdb_client_secret`, next to
  `sgdb_api_key`; only IGDB needs one.
- Failure policy: network error, 401 or a missing key return `None` and
  leave the cache alone, like `storemeta.py`.

## Download policy

- Explicit action only; nothing fetches on open, save or startup, and
  the work stays off the GUI thread (both landed rules stay).
- **Fill empty only** by default; a typed field survives.
- Preview before writing: a dialog lists `Field | Current | New` with a
  **Replace existing values** switch, off by default. Replacing a typed
  synopsis or genre is irreversible, so it never happens silently.
- **Field locks**: `[metadata] locked = "description,developer"` (CSV,
  normalized against the known field names). A label-side toggle in the
  game dialog marks a field; a locked field is never replaced. Locks
  cover description, developer, publisher, genre, series, age_ratings,
  region, status, tag, version and date; `steam_appid` is identity, not
  metadata.
- **Date becomes fillable** when empty (Steam included), which supersedes
  `docs/decisions/metadata-download.md` #7: the manual date already wins
  over the cached store date, so a filled empty field becomes the
  override instead of fighting it. Only values that pass
  `metadata_date_valid` are written.
- Ambiguous searches show a candidate picker, reusing the
  `artworkChoices` signal pattern; the pick saves in the provider's
  identity field (`[metadata] vndb_id` for VNDB, `[metadata] igdb_id`
  for IGDB).
- `age_ratings` is a list: fill-empty only when empty, replaced as a
  whole when the switch is on.

## Consumers and order

| # | Landing | Deliverable |
| --- | --- | --- |
| C1 | Registry + cache + rate gate + Steam adapter | landed (`decisions/metadata-registry.md`); no key, no UI change |
| C2 | Download Metadata preview dialog | landed (`decisions/metadata-preview.md`); the provider menu moved to C6, the candidate picker to C4 |
| C3 | Field locks (config + game dialog) | landed (`decisions/metadata-locks.md`); locks win over the replace switch, QML change |
| C4 | VNDB adapter + candidate picker | landed (`decisions/metadata-vndb.md`); no key, the visual-novel case |
| C5 | PCGamingWiki adapter | dropped: Cloudflare blocks a plain HTTP client; IGDB covers the fields |
| C6 | IGDB adapter + credential field + provider menu | landed (`decisions/metadata-igdb.md`) |
| C7 | IGDB artwork as a third source | landed (`decisions/artwork-igdb.md`) |
| C8 | Online categories/tags in bulk | last; taxonomy UX is its own risk |

The library format import and its enrichment follow as a separate theme;
the enrichment reuses C2's action in bulk.

## Open questions

- None block C7. A real-key IGDB smoke test waits on the maintainer's
  Twitch application; the adapter and its tests do not.
- PCGamingWiki engine/requirements/fixes stay out of metadata, and the
  site's Cloudflare challenge keeps them out of reach for now.

## Risks

- Four field mappings and two search shapes: the registry keeps the
  core small, but each adapter needs its fixtures.
- IGDB's Apicalypse query needs quote escaping; a title with quotes must
  not break the request.
- The preview dialog is a new QML surface; the fill-empty path must keep
  working without the switch.
- 1.0 grows by six landings before the library import. If the release
  tightens, C7 moves to 2.0 without touching VNDB or IGDB.
