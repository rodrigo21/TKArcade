# VNDB release picker

Status: landed (2026-11-19).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The VNDB provider (`decisions/metadata-vndb.md`) answered one
visual-novel date and no publisher: `/vn` exposes the earliest
`released` date and the developers, while the date and the producers
belong to a release. A visual novel has several releases (platforms,
regions, fan translations), and a publisher is not a developer. The
choice had to survive the next download without turning into a second
manual field.

## Decision

1. `src/tkarcade/vndb.py` adds `releases()` on the Kana `/release`
   endpoint, filtered by the visual novel
   (`["vn", "=", ["id", "=", "v2002"]]`): title, alternative title,
   date, platforms, languages, the official flag, the link type and the
   producers. Rows are `{"id", "name", "detail", "langs"}`; the name is
   the combo label (title, date, platform and language codes), the
   detail is the tooltip, `langs` feeds the client-side filter. Every
   linked release is listed, in date order, including unofficial and
   non-complete entries; the label marks `unofficial`, `trial` and
   `partial`. A release whose link does not name the queried visual
   novel is dropped.
2. `[metadata] vndb_release` stores the pick (`r1234`; a bare `1234`
   and a `vndb.org/r1234` URL normalize too). It is identity like
   `vndb_id`: no lock, not provider-filled, ignored and dropped when
   the visual-novel id is empty.
3. `vndb.fetch(game_id, target, timeout, release)` reads the visual
   novel first and then the picked release. The release must still link
   that visual novel. Its `released` replaces the date and the
   producers flagged `publisher` fill the Publisher row; the visual
   novel's developers stay the developer. A missing or failed release
   returns `None`, so the stale cache may answer instead of a payload
   silently missing the pick.
4. The registry carries the release as its own argument: `Provider`
   gains `releases` and `resolve_release`, and `cached()`/`download()`
   take `release`. The effective release is the explicit pick; an
   explicit target with an empty release means no release (so clearing
   the pick wins over the config); a call with no target reads
   `[metadata] vndb_release`. The cache payload records the release
   next to the target and compares both. `CACHE_VERSION` stays 3: an
   old payload without the key reads as no release and still answers a
   no-release download.
5. There is no default release. Without a pick the download keeps the
   visual-novel date and an empty publisher; nothing is preselected or
   written for the user.
6. Search Data shows the release list under the VNDB identity, with a
   **Language:** filter built from the fetched rows (codes and release
   counts). The filter is window state, resets on open and on an
   identity change, and is not saved. The current pick stays visible,
   marked `outside filter` or `not in VNDB`, when the filter or a
   deleted entry hides it. Picking refetches through the existing
   preview, so fill-empty, the Replace switch and the locks keep
   working. Details shows `VNDB v2002/r1234`.
7. The list is fetched off-thread once per visual-novel id and window
   open, with no disk cache. New strings ship in English: translations
   stay suspended until 1.0.

## Rationale

- The date and the publisher belong to the release; the developer list
  belongs to the visual novel and stays there.
- A stored `vndb_release` survives the cache cleanup, gives the next
  download the same pick and gives the user a way to clear it; a
  cache-only pick would be permanent until the files were deleted.
- A release argument beats composing the id into the cache target:
  clearing the pick is expressible without a sentinel, and the cache
  key stays readable.
- The language filter reads data already fetched, so it costs no
  request and works offline inside the dialog; the API `lang` filter
  remains the upgrade path if the row cap ever hides a language.
- Listing every linked release is the point of the feature: a user who
  runs a fan translation needs that release, not only the official
  Japanese one. The markers keep the choice informed.

## Consequences

- A game with a VNDB identity gets two optional rows on Search Data
  (Language and Release) and one more key in the config.
- A pick costs up to three VNDB requests: the list, the visual novel
  and the release. The existing 1 s gate spaces the registry calls; the
  visual novel and its release are two requests inside one gated call.
- The release list stops at 100 rows; pagination waits for a visual
  novel that exceeds it.
- A fan release's publisher is the fan group; a release with no
  publisher-flagged producer leaves Publisher empty.
- A release deleted on VNDB fails until the user clears the pick.
- Every window open that shows the row refetches the list; the list is
  not cached on disk.
- Publisher already obeyed the field lock, fill-empty default and
  Replace switch; the release pick adds no new write path.

## Alternatives

- **Compose the release into the target (`v2002@r1234`).** Reuses the
  old signature, but clearing the pick needs a sentinel because an
  empty release would fall back to the stored config value.
- **Preselect the earliest official release.** Fills Publisher without
  a user action, but chooses a region and a release for the user and
  silently changes today's date.
- **List official releases only.** Shorter, but hides the release a
  fan-translation user actually runs.
- **Server-side language filter (`["lang","=","en"]`).** Reaches
  releases beyond the first page and returns shorter lists, at one
  request per language change and more window state.
- **Store date and publisher at pick time only.** Loses the pick on the
  next download and gives no way to change it.
- **Derive Publisher from the visual novel's developers.** The
  developer is not the publisher; VNDB keeps them apart on the release.
