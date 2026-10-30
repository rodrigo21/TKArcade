# Artwork provider stays global

Status: rejected (2026-10-30). Decision record for the proposed per-game
artwork provider override.

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

A game's artwork download tries two providers, Steam's official CDN and
SteamGridDB, in the order set by the global preference
`[ui] artwork_source` (`Preferences.artwork_source`). Both the explicit
Fetch Artwork action and the background fetch read it.

The per-game `[artwork]` block has no provider key: it carries the three
manual file slots (`icon`, `cover`, `banner`), the `artwork_appid` of a
donor Steam app, and the `"cleared"` mark in the source AppID's
manifest. A single game whose art is better on the other provider
therefore forced either a global preference change, which affects every
game on its next fetch, or picking the files by hand.

## Decision

Keep the provider global. Do not add a per-game provider key.

The per-game escapes stay as they are:

- manual `icon`/`cover`/`banner` paths win over any download;
- `artwork_appid` borrows another Steam app's art, fetched with the
  global provider order;
- Clear removes the downloaded art and stops the background fetch until
  an explicit Fetch.

## Rationale

- The provider only chooses download order. Cached files, manual slots
  and the cleared mark do not depend on it, so a wrong global value never
  corrupts existing art.
- A truly mismatched game already has a precise per-game answer: pick
  the three files manually, or point `artwork_appid` at the app whose
  art is right. Both are rarer than a mixed provider need.
- A real key would touch the config whitelist, load/save, both fetch
  paths (`fetchArtwork` and the background worker), the Settings Artwork
  tab, translations and tests — steady surface for a rare case.
- SteamGridDB still needs the global API key, so a per-game `sgdb`
  choice cannot rescue a missing key; it only reorders the same two
  providers.
- A TOML-only key with no GUI control was rejected: current project
  policy keeps every config key reachable from the interface.

## Revisit if

Real reports accumulate where one game needs the other provider and
manual art is not good enough. The minimal shape would then be
`[artwork] provider = "" | "steam" | "sgdb"`, with `""` meaning "use the
global preference", resolved in both fetch paths and exposed as a combo
in the Artwork tab. It would still only affect downloads.
