# Search Data window and Steam auto-fill

Status: landed (2026-11-12).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`). Supersedes
the Details-side parts of `metadata-preview.md`, `metadata-vndb.md` and
`metadata-igdb.md`, and the Artwork tab of `artwork-sources.md`.

## Problem

Metadata and artwork were spread over the Details tab and a seventh tab,
every identity (Steam AppID, VNDB id, IGDB id) was a raw field in the
form, and Download Metadata was a button inside the Information box that
opened a small preview, with a name search and a candidate picker living
outside it. Four entry points for one job, two hidden identity fields,
artwork parked in the last tab, and a Steam game needed a manual click
before its store entry existed.

## Decision

1. **Steam fills its metadata on add.** `_fetch_on_save` asks for
   `enrich=True`; `_fetch_worker` hands each game to `_fetch_game`, which
   calls `_enrich_steam` for a Steam id. `_fill_steam_metadata` writes
   the empty fields from the store payload (description, developer,
   publisher, genre, series, age ratings, date, tags): fill-empty only, a
   locked field stays out even when empty, and a value typed before Save
   wins. Background and silent, cached for 30 days, and a failed fetch
   changes nothing. `backgroundDone` refreshes the list.
2. **One window, two tabs.** `Search Data` is a modal child of the game
   dialog, opened from a button on the **Information** title line (new
   `SectionBox.actions` slot). It works on the dialog draft: Apply writes
   the draft, Save persists it.
   - **Metadata** tab: source combo (Steam, VNDB, IGDB, ProtonDB), one
     query field prefilled with the clean name, candidate buttons, a
     `Matches:` line, the Field | Current | New preview, the Replace
     switch and the status line; the window stays open after Apply so
     the result is readable.
   - The query answers an id directly (`v2002`, digits for IGDB or a
     Steam AppID), otherwise it searches the provider. A pick writes the
     identity field in the same window.
   - **ProtonDB** is a source without a name search: AppID, Check, tier
     and Open Page.
   - **Artwork** tab: the four slots, Artwork Source AppID, Download
     From, Fetch and Clear Downloaded; cache writes, not draft edits.
3. **Identity moved off the form**, not out of the config: the same
   `[metadata] steam_appid`, `vndb_id` and `igdb_id` keys are edited in
   the window, and Details shows them back as a `Matches:` line.
4. **Artwork left the dialog.** The seventh tab is gone (six tabs
   remain); Notes moved to the end of Details, and a strip of the four
   effective previews in the Game section opens the window on its
   Artwork tab. The `artwork:` surface (`TKARCADE_OPEN`) opens the same
   tab through `openSearchDataArtwork()`.
5. `searchStatus` replaces `metadataStatus`; `metadataRows` stays the
   preview model and `metadataReplaceBox` still starts unchecked per
   answer.

## Rationale

- One intent, one entry point: the source, the identity, the search and
  the preview belong together, and the draft contract (Apply then Save)
  stays exactly what the preview already did.
- The id-as-query rule removes a mode switch: a stored id is a paste,
  a new game is a search.
- Steam is the only source that can fill without a human decision about
  which game it is, which is why only a Steam id is enriched silently.
- Artwork is a cache, not a field: keeping its actions immediate avoids
  a second draft concept.
- The window needs 36 grid units at minimum: at the old 34 the Artwork
  tab clipped the last button and part of the status line.

## Consequences

- No config migration; the identities keep their keys and the cache
  identity.
- The QML suite's settings helpers changed: `SETTINGS_TAB_TITLES` has six
  entries, the art and metadata controls are driven through
  `_search_window()`, and candidate buttons are counted through the
  Repeater (their delegates are visual children, not object children).
- Detail's Description box now competes with Notes for the leftover
  height, so its stretch check runs on a taller window.
- IGDB still needs a per-user Twitch application; the credential review
  is parked in `TODO.md` under 2.0.
- Translations stay suspended: the new strings ship in English.

## Alternatives

- Keep the preview and add a search field on Details: fewer moves, but
  the four entry points and hidden ids stay.
- Two windows (metadata, artwork): clearer separation, two modal flows
  for one intent.
- Auto-fill local games too: a VNDB/IGDB match is a decision, and a wrong
  match would write a stranger's fields.
