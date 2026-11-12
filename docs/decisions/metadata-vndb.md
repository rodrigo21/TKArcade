# VNDB metadata

Status: landed (2026-11-11).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The metadata registry (`decisions/metadata-registry.md`) and its preview
(`decisions/metadata-preview.md`) only answered for a Steam game or a
local game carrying a Steam store AppID. A local visual novel without
one had no online source at all, even though VNDB indexes it and needs
no key. A title does not identify a visual novel, though: ports, sequels
and remakes share a name, so the answer needs a candidate picker before
anything is written.

## Decision

1. `src/tkarcade/vndb.py` talks to the Kana API
   (`POST https://api.vndb.org/kana/vn`, stdlib `urllib`): `search()`
   ranks visual novels by title, `fetch()` reads one entry, `resolve()`
   maps a game to its VNDB id.
2. `[metadata] vndb_id` stores the pick (`v2002`; a bare `2002` and a
   `vndb.org` URL normalize too). It is identity like `steam_appid`, so
   it takes no lock, is not provider-filled and is ignored by a game
   that has a Steam AppID.
3. Download Metadata routes by source: a Steam game, or a local game
   with `[metadata] steam_appid`, reads Steam; otherwise a filled
   `vndb_id` is fetched directly, and an empty one searches VNDB by the
   dialog's title. The provider menu stays open until C6, so the Steam
   source wins whenever it exists.
4. A search with candidates shows the existing choice dialog
   (`artworkChoices` pattern, `askChoice`): the pick fills the VNDB
   field, then the fetch fills the same preview. An empty result is the
   landed `No Metadata Found.` status, no dialog.
5. The dialog field is part of the form: Save persists the pick, Cancel
   drops it. Editing or clearing the field and pressing the action again
   re-keys the cache; nothing else remembers the match.
6. VNDB fills description, developer and date. It has no publisher,
   series or age ratings, and its tags are a different taxonomy
   (content/sexual/technical, no genre class), so `genre` stays empty
   and tags are left to the online-categories work (C8).
7. The payload maps to plain text: BBCode is stripped, entities decoded.
   A release date is written only when it passes
   `metadata_date_valid`; `TBA` and a missing date become `""`.
8. Cache namespace `vndb-meta`, 30-day TTL, keyed by the game and
   recording the VNDB id: a changed `vndb_id` never reuses the previous
   visual novel's fields. Rate gate 1 s. The Removed games cleanup now
   derives its metadata namespaces from `metadata.cache_dirs()`.

## Rationale

- A stored id, not a remembered cache target, survives the cleanup and
  gives the user a way to change or clear the match; a cache-only pick
  would be permanent until the cache was deleted by hand.
- The title search and the picker belong together: VNDB's ranking is
  fuzzy and a wrong match would otherwise fill the preview silently.
- VNDB has no genre field; mapping tags would need a curated allowlist
  that ages badly, and C8 owns the tag taxonomy.
- Keeping the source automatic avoids the provider menu one landing
  early, and the field doubles as the manual override for the VNDB-only
  case.

## Consequences

- A local visual novel gets one more optional Details row: VNDB.
- A Steam game cannot use VNDB until C6 adds the provider menu; its
  `vndb_id` is ignored (and the row hidden).
- A search costs one request plus one fetch, gated 1 s apart; the
  documented VNDB limit is 200 requests per 5 minutes, which interactive
  use stays far below.
- The synopsis loses BBCode links (the text survives, the URL does not).

## Alternatives

- **Remember the pick in the cache only.** No cleanup survival, no way
  to choose another match without deleting files.
- **A `[metadata] vndb_url` free-form field.** Accepted shapes drift
  (URL, `v2002`, bare digits) and every caller would parse it again;
  normalization at load keeps one form.
- **Genre from content tags.** Includes themes (`Maid Heroine`,
  `Time Travel`) next to genres (`Mystery`); a curated allowlist would
  need maintenance for a field Steam already fills.
- **Auto-pick a single search result.** Skips the confirmation and
  leaves the id field empty, so the next press searches again.
