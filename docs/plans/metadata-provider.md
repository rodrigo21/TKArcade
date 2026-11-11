# Metadata provider registry: four providers, one client (proposal)

Status: proposal, not approved. C1 (the registry plus the Steam adapter)
landed as `docs/decisions/metadata-registry.md`, C2 (the action preview)
as `docs/decisions/metadata-preview.md`, C3 (the field locks) as
`docs/decisions/metadata-locks.md`, and the earlier Steam `appdetails`
download as `docs/decisions/metadata-download.md`; the adapters below
are still open. When the rest lands it belongs in
`docs/decisions/metadata-provider.md` with a landing banner, and this
file is deleted.

## Problem

`TODO.md` lists work that shares one missing piece: a provider registry
(service, credential, cache, rate limit, field locks) behind three
consumers: a local metadata download, provider artwork and online
categories. A single Steam client cannot answer a game without a Steam
AppID, and the manual fields would be retyped anyway.

## Providers

| Field | Steam | IGDB | VNDB | PCGamingWiki |
| --- | --- | --- | --- | --- |
| description | yes | yes | yes (synopsis) | no |
| developer | yes | yes | yes (brand) | yes |
| publisher | yes | yes | no | yes |
| genre | yes | yes | tags (genre-class only) | yes |
| series | yes | yes (franchise) | no (relations are not a series) | yes |
| age ratings | ESRB/PEGI/USK | ESRB/PEGI/USK | no | ESRB/PEGI/CERO |
| date | yes | yes | yes | yes |
| engine/requirements/fixes | no | no | no | yes, separate feature |

- **Steam** wraps the landed `storemeta.py`; no key.
- **IGDB** needs a Twitch app (client id/secret) and the Apicalypse query
  language; 4 req/s.
- **VNDB** has a public API with no key; title search, synopsis, brands
  and tags; ~1 req/s.
- **PCGamingWiki** uses the MediaWiki Cargo query (`action=cargoquery`);
  no key and no API contract, so the adapter tolerates missing columns;
  ~1 req/s.

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
- Rate gate per provider: IGDB 250 ms, VNDB and PCGamingWiki 1 s, Steam
  none. Token cache for IGDB in the same dir, invalidated when the
  client id changes.
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
  `artworkChoices` signal pattern; the pick is remembered as the cached
  `target`.
- `age_ratings` is a list: fill-empty only when empty, replaced as a
  whole when the switch is on.

## Consumers and order

| # | Landing | Deliverable |
| --- | --- | --- |
| C1 | Registry + cache + rate gate + Steam adapter | landed (`decisions/metadata-registry.md`); no key, no UI change |
| C2 | Download Metadata preview dialog | landed (`decisions/metadata-preview.md`); the provider menu moved to C6, the candidate picker to C4 |
| C3 | Field locks (config + game dialog) | landed (`decisions/metadata-locks.md`); locks win over the replace switch, QML change |
| C4 | VNDB adapter + candidate picker | no key; the visual-novel case |
| C5 | PCGamingWiki adapter | publisher, series, ratings |
| C6 | IGDB adapter + credential field + provider menu | waits on the maintainer's Twitch app |
| C7 | IGDB artwork as a third source | joins `artwork.PROVIDERS` |
| C8 | Online categories/tags in bulk | last; taxonomy UX is its own risk |

The library format import and its enrichment follow as a separate theme;
the enrichment reuses C2's action in bulk.

## Open questions

- None block C1. C6 waits on the maintainer registering a Twitch
  application (client id/secret).
- PCGamingWiki engine/requirements/fixes are a separate feature, not
  metadata.
- VNDB tags: only genre-class tags feed `genre`; theme tags are dropped.

## Risks

- Four field mappings and three search shapes: the registry keeps the
  core small, but each adapter needs its fixtures.
- PCGamingWiki has no API contract; a renamed Cargo column must degrade
  to a missing field, not a crash.
- IGDB's Apicalypse query needs quote escaping; a title with quotes must
  not break the request.
- The preview dialog is a new QML surface; the fill-empty path must keep
  working without the switch.
- 1.0 grows by eight landings before the library import. If the release
  tightens, C5 and C7 move to 2.0 without touching VNDB.
