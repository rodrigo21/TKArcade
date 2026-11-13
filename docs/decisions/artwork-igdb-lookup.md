# IGDB artwork without a prior metadata download

Status: landed (2026-11-13).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

Fetch Artwork with IGDB failed until the user ran Download Metadata for
that game. Steam art uses the existing AppID and SteamGridDB has a name
autocomplete, so both worked on their own; IGDB's art endpoint only takes
a numeric game id, and the artwork path only read the
`[metadata] igdb_id` that Download Metadata stores. The dialog draft
added later only helped after a candidate was already picked. IGDB does
have a title search, so the dependency was an artefact of the original
artwork design, not of the provider.

## Decision

1. `artwork._igdb_lookup` resolves the id in this order: the dialog draft
   or stored `[metadata] igdb_id`, then the id a previous search or pick
   left in the cache, then an IGDB title search.
2. The title search tries the same names as SteamGridDB (the display name
   without its `[version]` bracket first, then the full name). An exact
   normalized title wins automatically, ignoring the `(YYYY)` release
   suffix IGDB appends to search labels. Otherwise the first name's rows
   come back as candidates tagged `provider: "igdb"`.
3. A Steam game without an IGDB id searches its official Steam name; a
   local game searches its configured name. The chosen provider still
   runs first, and the other providers only fill kinds IGDB cannot
   (the square icon).
4. `artworkChoices` rows carry `provider` (`sgdb` or `igdb`).
   `fetchArtworkGame(appid, id, provider, source)` dispatches:
   SteamGridDB keeps its existing download and sidecar, IGDB fetches with
   the picked id as the draft id. IGDB needs the Twitch credentials; the
   SteamGridDB key is only needed for the icon fill and is not a
   prerequisite.
5. An explicit Fetch or pick writes the resolved id to
   `[metadata] igdb_id` (normalized). The id is also cached in the game's
   manifest under the `igdb` key, like the SteamGridDB choice, so the
   silent startup pass can reuse it without another search.
   `clear_fetched()` keeps both. The config/draft id wins over the cached
   one. A target that comes from an Artwork Source AppID is not written:
   that IGDB game belongs to the source AppID, not to the local game.
6. `igdbResolved(appid, id)` tells the open dialog the id; the QML writes
   it into the `igdbIdField`, so a later Save cannot overwrite the stored
   value with an empty draft.
7. When a title search returns candidates and no art exists yet, the
   fetch status is `choose` and the dialog says "Pick the Matching Game
   Below."; the provider-specific "no exact match" wording is gone.

## Rationale

- IGDB has the same shape as SteamGridDB once a title lookup exists: a
  search, a pick and a remembered game id.
- Steam keeps its AppID in the config and SteamGridDB keeps its game id
  in the cache; the IGDB id is a metadata identity, so the explicit
  action stores it where Details and Download Metadata can see it.
  The sidecar remains the silent-pass fallback, not the visible owner.
- Exact-match-first matches the SteamGridDB rule and keeps a unique title
  from costing a click.
- Requiring the SteamGridDB key for an IGDB fetch would couple two
  independent credentials; the icon is a fill, not a prerequisite.

## Consequences

- The first IGDB Fetch for a game costs one or two extra IGDB search
  queries; later fetches use the stored id.
- Details shows the resolved IGDB id in its "Matches:" line and Search
  Data reuses it; the dialog draft is updated by the signal.
- The startup/Save background pass still does not rewrite metadata; only
  an explicit Fetch or a pick does.
- A cached IGDB id survives Clear, so a cleared game restores the same
  game's art instead of asking again.
- The old `artwork-igdb.md` alternative "IGDB name search inside the
  artwork dialog" is superseded by this record; it was rejected when the
  provider chain was new, not because IGDB lacked a search.
- A wrong exact title match is possible where IGDB lists two games with
  the same title and year; the picker appears whenever the normalized
  title is not exact.

## Alternatives

- **Cache only, never write `[metadata] igdb_id`.** Keeps artwork purely
  a cache action, but Details and Download Metadata stay blind to the
  resolved game and the user has to run Search Data anyway.
- **Always show the picker.** Simpler, but a unique title would pay a
  click that SteamGridDB does not charge.
- **Map a Steam AppID to IGDB through `external_games`.** More precise
  for Steam games, but a second API shape; the official Steam name is
  enough for the title search that local games already need.
