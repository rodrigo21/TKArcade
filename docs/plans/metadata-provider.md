# Metadata provider: one client, four consumers (proposal)

Status: proposal, not approved. Step 1 (Steam `appdetails` metadata
download, no key) landed as `docs/decisions/metadata-download.md`; the
consumers below are still open. When the provider itself lands it belongs
in `docs/decisions/metadata-provider.md` with a landing banner, and this
file is deleted.

## Problem

`TODO.md` lists four items that look like separate features but share one
missing piece: a metadata provider client (service, credential, cache,
rate limit).

- Other artwork sources.
- Metadata download.
- Playnite-style metadata for local library import.
- Online categories/tags.

Nothing in `src/tkarcade` calls IGDB or any metadata service today
(`artwork.py` uses Steam's CDN and SteamGridDB only; `releasedate.py`
already reads Steam's `appdetails`).

## Shared core

One client for a metadata service (IGDB is the leading candidate; it is
also the source SGDB's own data is built around):

- credential: client id/secret, Twitch OAuth for IGDB (client-credentials
  token is enough for read-only lookups);
- cache: a JSON cache under the app cache dir, keyed like the existing
  per-game caches (`artwork._cache_key` shape) so Steam and local games do
  not collide;
- request budget: a small delay/backoff, as IGDB rate-limits per second;
- one decision record: service, credential storage (next to
  `[ui] sgdb_api_key`), cache TTL, field mapping, failure policy (same
  "silent on background fetch" rule as artwork).

This core is a dependency of the four consumers below, not a user-facing
feature on its own.

## Consumers

1. **Metadata download (Steam half) — landed.** `appdetails` supplies
   description, developer, publisher, genre, series, age ratings and
   release date; the action fills empty `[metadata]` fields for a Steam
   ID or a local game's `[metadata] steam_appid`, cached per game in
   `steam-meta`. See `docs/decisions/metadata-download.md`. The local
   half below still needs the provider.

2. **Metadata download (local half).** Same fields from the provider by
   name, plus a per-game "Download Metadata" action. Uses the shared
   client; per-field overwrite policy is a decision (fill empty only,
   overwrite, or preview-and-pick).

3. **Artwork from the metadata provider.** IGDB serves covers and
   artworks, so it can join `artwork.PROVIDERS` as a third provider
   without changing `ART_KINDS`. Different from "other artwork sources"
   in `TODO.md` only in which service is chosen.

4. **Playnite-style enrichment (Steam/Epic/GOG/PCGW/VNDB).** Blocked on
   the missing library-format import (Lutris/Playnite/Faugus). The
   enrichment reuses consumer 2; the import is its own theme.

5. **Online categories/tags.** Taxonomy (genres, keywords) applied in
   bulk to many games, not a per-game field. Different UX from consumer
   2; last, highest uncertainty.

## Ordering

1. ~~Steam `appdetails` metadata download (no key)~~ — landed.
2. Decision record + credential + client + cache.
3. Local metadata and provider artwork as consumers of the client.
4. Library import, then enrichment.
5. Online categories/tags.

Steps 2 and 3 can land as one batch; 4 and 5 stay separate themes. Step
4 depends on the library format import listed in `TODO.md`, not on the
client.

## Open questions

- Provider: IGDB only, or IGDB for both text and art plus PCGW for
  fixes? PCGW has no clean API.
- Does the provider need a user-supplied key in Preferences (like SGDB),
  or can a bundled credential work? IGDB/Twitch requires an app
  registration, so it is a user key at least for now.
- Overwrite policy for a field the user already filled by hand.
- One shared cache shape for text fields, or one file per game next to
  the existing artwork sidecar.
