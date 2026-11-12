# IGDB metadata

Status: landed (2026-11-11).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

C6 of `docs/plans/metadata-provider.md` needed a general provider: VNDB
answers visual novels only, and a local game without a Steam store link
had no source for publisher, series or age ratings. IGDB indexes every
game and needs a Twitch application (client id and secret), so the
credential is the user's, not a shipped one. C5 (PCGamingWiki) was
planned first and dropped: the site answers a plain HTTP client with a
Cloudflare interstitial (`403`, `Just a moment...`), so a stdlib
adapter cannot reach either its Cargo API or its `appid.php` helper. Its
fields are a subset of IGDB's.

## Decision

1. `src/tkarcade/igdb.py` talks to `https://api.igdb.com/v4/games` with
   the Apicalypse query language (stdlib `urllib`): `search()` ranks
   games by title, `fetch()` reads one entry, `resolve()` maps a game to
   its numeric IGDB id, `credentials()` reads the Twitch application.
2. An app access token comes from
   `POST https://id.twitch.tv/oauth2/token` (`client_credentials`) and
   is cached in `app_cache_dir()/igdb-meta/.token.json` with the client
   id and the expiry. It renews on expiry or a changed client id; the
   leading dot keeps the file apart from a per-game cache named
   `safe_stem(game_id)`.
3. `[ui] igdb_client_id` and `igdb_client_secret` live next to the
   SteamGridDB key. Preferences shows them in a new **Metadata** section
   on the Artwork tab, the secret masked. A missing pair, a 401 or a
   network error returns `None` and leaves the cache alone.
4. `[metadata] igdb_id` stores the pick (digits only). It is identity
   like `steam_appid` and `vndb_id`: no lock, not provider-filled.
5. Details gains a **Metadata Source** menu (Steam, VNDB, IGDB) next to
   Download Metadata. The default preserves the previous routing: the
   stored identity wins, then Steam when the game links an AppID, then
   VNDB. Steam needs a Steam AppID; an empty VNDB/IGDB id searches by
   the dialog title and the existing picker asks which game it is.
   IGDB without credentials reports `IGDB Needs a Client ID and Secret
   in Preferences.` instead of a failed download.
6. The VNDB and IGDB identity rows show for every game, the VNDB row no
   longer hidden behind "a Steam game cannot use VNDB" (the C4 note that
   waited on this menu).
7. The payload fills every field in `metadata.FIELDS`: `summary` →
   description, `involved_companies` split by its developer/publisher
   flags, `genres.name` → genre, `franchises.name` → series,
   `age_ratings.rating` → `config.AGE_RATINGS` (the IGDB enum is global,
   not per board; EC, GRAC_TESTING and ACB_RC have no label and are
   dropped), and `first_release_date` only when it passes
   `metadata_date_valid`.
8. Cache namespace `igdb-meta`, 30-day TTL, keyed by the game and
   recording the IGDB id; the Removed games cleanup picks the namespace up
   through `metadata.cache_dirs()`. Rate gate 250 ms (4 req/s).

## Rationale

- One menu, three providers: routing inside the dialog would keep
  growing per adapter, and the user needs a way to pick a source for a
  game that exists in more than one database.
- Preserving the old default keeps the VNDB visual-novel flow working
  without a choice; IGDB is one click away.
- A token cache avoids a Twitch request per search and keeps the
  credential out of every call; the token is short-lived and app-scoped,
  never the user's password.
- IGDB is the only planned source with description, publisher, series
  and ratings together, which is why it replaces the blocked C5 instead
  of adding a fourth adapter with fewer fields.

## Consequences

- A second credential pair in Preferences; without it IGDB reports the
  missing key and VNDB still works.
- IGDB needs the network on the first fetch and every 60 days for a
  token; a stale token inside the cache window is reused.
- The provider menu makes the previous "Steam wins whenever it exists"
  rule configurable, and the preview, the replace switch and the locks
  are unchanged.
- A searched title costs one request plus one fetch, gated 250 ms.

## Alternatives

- **Keep PCGamingWiki with a browser-impersonating client or a
  Cloudflare-solving proxy.** A third-party dependency on the launch-free
  path, brittle against the next challenge change, and against the
  stdlib-first rule.
- **Always IGDB for a local game.** Changes the landed VNDB default
  silently; the menu makes the choice explicit instead.
- **Identify a Steam game through `external_games.uid`.** Fewer title
  searches, but a second mapping to maintain; the picker already
  resolves the name.
- **Store the token in the preferences file.** A short-lived app token
  next to a long-lived secret gains nothing.
