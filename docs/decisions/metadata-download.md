# Store metadata download

Status: landed (2026-11-10).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The Details metadata fields (`[metadata]` description, developer,
publisher, genre, series, age ratings) were manual, although Steam's
store `appdetails` response carries almost all of them and the
release-date lookup already calls the same endpoint. Since a local game
can now hold its own store link, the same source fits it too, and the
manual fields meant retyping what the store already answers.

## Decision

1. The provider is Steam's `appdetails` only. A Steam ID derives its
   AppID; a local game uses `[metadata] steam_appid`, through the same
   resolver as ProtonDB. A local game without a link keeps the action
   disabled; an IGDB-style provider stays a separate future change.
2. An explicit **Download Metadata** action closes the Details Game
   section, beside the Steam AppID and ProtonDB rows it depends on.
   Nothing downloads automatically: no fetch on open, save or startup.
3. The action fills **empty** fields only. A typed synopsis, studio,
   genre or rating set survives, and the status line says whether every
   field was filled, some were kept, or the store answered nothing.
   Changed 2026-11-11: the answer opens a preview first, and a
   **Replace existing values** switch opts into overwriting typed
   fields; see `docs/decisions/metadata-preview.md`.
4. The download runs off the GUI thread (the house `threading.Thread`
   plus signal pattern) and returns the fields to the dialog; Save is
   still what writes the config.
5. Cache: `$XDG_CACHE_HOME/tkarcade/steam-meta/<gameid>.json`, 30-day
   TTL, keyed by the canonical game ID, with the AppID it was fetched
   for recorded in the payload. A changed store link reads as not
   cached; a fresh cache answers the click without a network call.
   The Removed games cleanup counts and deletes it like the ProtonDB and
   release-date caches.
6. Field mapping: `description` is `short_description` with HTML
   entities unescaped (`detailed_description` is HTML and is not used);
   `developer`/`publisher` join the store lists with `", "`; `genre`
   joins the genre names; `series` uses `franchise` when the store sends
   it (often absent); `age_ratings` maps only ESRB, PEGI and USK, the
   boards whose codes match `config.AGE_RATINGS`.
7. The manual `[metadata] date` is not downloaded: the Release Date
   column already shows the cached store date for a Steam ID, and a
   second writer of the same date would fight it. Changed 2026-11-11:
   the provider registry fills an empty date and locks it per field; see
   `docs/plans/metadata-provider.md`.

## Rationale

- Same endpoint, no API key, and the payload is already trusted for the
  release date.
- Fill-empty-only makes the action safe to press on a curated library; a
  destructive refresh would need a confirmation and a second command.
- Keying the cache by game ID keeps the cleanup working and the numeric
  cache migration away, the same reasoning as the ProtonDB cache.

## Consequences

- A store payload with no fields leaves the dialog untouched and says so.
- Store text can change; within the 30-day window the action returns the
  cached answer. Replacing edited text stays manual.
- A local game without a Steam link still needs its own provider.
- `franchise` is absent from many payloads, so series remains a manual
  field in practice.

## Alternatives

- **Overwrite every field on click.** Loses hand-edited synopses; would
  need a confirmation for little gain.
- **Download automatically on open or save.** Surprising network traffic
  and a slow dialog on a cold cache.
- **`detailed_description`.** Carries HTML markup and links; the
  synopsis field is plain text.
- **Use `[artwork] artwork_appid` as the store link.** The field is
  art-only and may point at another edition.
- **IGDB now.** Needs a key, a second provider and a decision of its
  own; Steam covers Steam IDs and linked local games already.
