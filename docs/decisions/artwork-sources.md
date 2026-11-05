# Artwork sources: per-game provider, AppID field, name lookup

Status: decided (2026-11-05).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The provider order was global (`[ui] artwork_source`), so one game whose
art was better on the other source forced a preference change that
affected every game. A local game has no Steam AppID, so the only way to
download its art was to type another app's number in
`[artwork] artwork_appid`; the picker next to it listed installed games,
which made the field look like "borrow from a configured game" instead
of "any Steam AppID".

The icon was also resolved cover-first: after a fetch, the portrait
cover shadowed the freshly downloaded client icon. And when Steam only
served a 32x32 client icon `.jpg` (the `.ico` answers 404 for some
apps), that jpg beat SteamGridDB's official 256/512 square.

## Decision

1. `[artwork] provider` (`"" | "steam" | "sgdb"`) overrides the global
   order per game; `""` keeps the preference. The dialog exposes it as
   Download From, and its first entry names the global value it falls
   back to.
2. `[artwork] artwork_appid` stays as the Artwork Source AppID: any
   Steam AppID (installed or not), typed by hand, whose art the game
   uses. It is not tied to another configured game and it is not called
   a donor. A manual slot of the game itself still wins over it.
3. Target order for fetch and display: the typed AppID, then the game's
   own Steam AppID, then the SteamGridDB name lookup for a local game.
4. A local game without an AppID is looked up by name on SteamGridDB:
   the display name without its `[version]` bracket first, then the full
   name. An exact normalized match (case, accents and punctuation
   ignored) wins automatically; otherwise the first name's candidates go
   to the dialog, and the pick is downloaded.
5. The resolved SteamGridDB game id is stored in the game's cache
   sidecar (`grids/<id>.json`, key `sgdb`), not in the config. Clear
   keeps it, so Fetch restores the same art.
6. The icon chain is: official Steam client icon (`.ico` PNG frame
   when the app has one, otherwise its 32x32 `.jpg`) → SteamGridDB icon
   only when Steam has no icon at all. A cached icon whose provider is
   `sgdb` and that lacks the current chain marker came from the old
   order and is dropped once, then re-downloaded.
7. `artwork.resolve` asks for the icon before the cover; the cover is
   only the icon fallback when no square icon exists.

## Rationale

- The provider only chooses download order; caches, manual slots and the
  cleared mark do not depend on it, so a wrong choice never corrupts
  existing art.
- The typed AppID stays because it is the precise answer when a game's
  art lives under another Steam app; the field wins over the game's own
  art so what the user typed is what the views show.
- A name lookup gives a local game a real SteamGridDB entry without a
  hand-typed number, and the stored id survives renames of the display
  name.
- Steam's client icon is the only trustworthy square: a SteamGridDB
  entry tagged `official` is self-declared and can be a promotional
  banner at 256x256, which looks wrong everywhere an icon is drawn.
- The exact-match-first rule keeps the background fetch silent and safe;
  only an explicit Fetch can open the candidate list.

## Rejected alternatives

- **Remove the AppID field.** The maintainer still wants to type a Steam
  AppID for a game whose art lives elsewhere; only the installed-game
  picker was confusing.
- **Keep the Find… picker next to the field.** It listed installed and
  configured games, which is exactly what made the field look like a
  donor selector.
- **Store the chosen SteamGridDB id in the config.** It is cache state,
  not user intent; a config key would need a second UI field for a value
  the user never types.
- **Pick the first search result.** Name search answers with editions
  and sequels; a wrong automatic pick is worse than one extra click.
- **Prefer a SteamGridDB icon over Steam's 32x32 jpg.** That is how a
  promotional 256x256 image ended up as the icon; a small real icon
  beats a large wrong one.
