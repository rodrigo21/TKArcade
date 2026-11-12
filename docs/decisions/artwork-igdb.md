# IGDB artwork

Status: landed (2026-11-12).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

C7 of `docs/plans/metadata-provider.md` wanted the IGDB adapter from
`decisions/metadata-igdb.md` behind artwork too. A local game without a
Steam AppID had one community source (SteamGridDB), and the IGDB entry
already carries a cover and promo art. Joining meant more than one
registry line: `artwork.PROVIDERS` ordered its fallback by reversing the
tuple, which only works with two sources, and a name-based game had a
single lookup path hard-wired to SteamGridDB.

## Decision

1. `artwork.PROVIDERS` becomes `("steam", "sgdb", "igdb")`. The chain
   starts with the chosen provider and keeps the others in that order,
   so a third source cannot land before the choice.
2. `igdb.art()` queries `cover.url,artworks.url,screenshots.url` for the
   stored `[metadata] igdb_id` and returns absolute CDN URLs: the cover
   at `t_720p`, the banner from the first artwork (a screenshot when
   there is none) at `t_1080p`. Error tokens: `no-igdb-key`, `no-id`,
   `not-found`.
3. `artwork.fetch_igdb()` stores those two kinds and records the
   provider in the per-kind manifest. IGDB has no square icon, so `icon`
   is never filled there and the other providers keep it.
4. A numeric AppID runs the full chain (choice first, the rest in
   `PROVIDERS` order). A local game with IGDB chosen runs IGDB first and
   then the existing SteamGridDB name lookup for the kinds still
   missing; SteamGridDB also keeps its candidate picker, which IGDB does
   not use.
5. `[ui] artwork_source` and the per-game `[artwork] provider` accept
   `igdb`; the Preferences combo, the per-game Download From combo, the
   cached-origin label (`cache:igdb`) and the status messages follow.
   A missing credential reports `IGDB Needs a Client ID and Secret in
   Preferences.`; a missing id reports `IGDB Needs an IGDB ID: Run
   Download Metadata With IGDB.`
6. The cache and the manifest stay the landed ones: IGDB art is keyed by
   the same game slot and cleaned up by the same paths.

## Rationale

- IGDB's game id is already saved by the metadata download (C6), so the
  artwork needs no second identity or name-search shape.
- A square icon is not in IGDB's payload; cropping a cover would lie
  about the aspect and look soft at icon size, so the slot stays with
  Steam and SteamGridDB.
- The banner box is wide by design and already crops SteamGridDB heroes;
  a 16:9 IGDB artwork crops the same way instead of needing a new kind.
- Fixing the chain order was required for three sources and closes a
  latent bug in the two-source version.

## Consequences

- A local game needs one Download Metadata (IGDB) before IGDB art; the
  status line says so.
- The IGDB pass costs one config read in the chain even when the id is
  empty, and a stale token inside its 60-day window still answers.
- A fetched IGDB banner is 1920x1080 cropped to the 460:215 preview, not
  authored at that ratio.
- `decisions/artwork-sources.md` stays correct for the two providers it
  named; this record adds the third.

## Alternatives

- **IGDB name search inside the artwork dialog.** A second search shape
  and a provider tag on the candidate picker, for a game that already
  has an IGDB id one action away.
- **Steam AppID to IGDB through `external_games.uid`.** Automatic for
  Steam games, but Steam's own art already wins there; the extra query
  serves the case that needs it least.
- **Crop the IGDB cover into an icon.** The square slot would show a
  portrait detail at low resolution.
- **A separate `background` download.** The landed backdrop has no asset
  of its own and follows the banner.
