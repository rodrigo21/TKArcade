# VNDB artwork

Status: landed (2026-11-27).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

Fetch Artwork had three sources. Steam supplies official art for a
numeric AppID, SteamGridDB and IGDB cover the community art, and a
visual novel still had no source that recognized it as one. VNDB
already held the cover, the screenshots and the identity the Metadata
tab used, and its Kana API needs no credential.

## Decision

1. VNDB joins the per-game provider chain (`steam`, `sgdb`, `igdb`,
   `vndb`) and the global Artwork Source preference. It fills `cover`
   with the visual novel's `image` and `banner` with its least flagged
   screenshot; the views crop the wide art. The square `icon` stays
   with the other providers.
2. The id resolves in this order: the dialog draft or stored
   `[metadata] vndb_id`, then the id cached in the sidecar, then a VNDB
   title search. An exact normalized title or alternative title wins
   automatically; otherwise the rows reach the existing
   provider-tagged picker. A pick writes `[metadata] vndb_id` and
   clears `vndb_release` when the visual novel changes. The sidecar
   keeps the id across Clear.
3. An Artwork Source AppID's resolved id is not written to the game's
   metadata, matching the IGDB ownership rule.
4. The picker only asks when the fetch downloaded nothing. Candidates
   from the SteamGridDB icon fill used to open it after the chosen
   provider had stored the cover and banner, and picking one would
   replace that art. The fix applies to IGDB too.
5. `[ui] hide_explicit_artwork` is off by default. When on, it drops
   VNDB images whose `sexual` or `violence` average is at least 1.5 and
   SteamGridDB entries marked `nsfw`. It changes downloads and the
   picker only; stored art stays and nothing is deleted. IGDB and Steam
   carry no flags.
6. VNDB release `images` (`pkgfront`, language variants) are not read;
   `TODO.md` carries the follow-up.

## Rationale

- VNDB has the same shape as IGDB once an identity exists: a title
  search, a remembered id and two kinds. Mirroring the IGDB pass keeps
  one chain and one picker.
- A key would only add setup for a source that needs none.
- The switch is opt-in because the maintainer asked for no curation by
  default; filtering by provider flag keeps the rule honest, and the
  tooltip names the providers it cannot reach.
- Suppressing the picker protects the art that was just downloaded; an
  empty icon already falls back to the executable's icon for a local
  game.

## Consequences

- The first VNDB Fetch for a game without an id costs one search; later
  fetches use the stored or cached id.
- A visual novel without a screenshot keeps the cover only; a game
  without a clean image under the switch falls back to the other
  providers.
- VNDB image flags are average votes: a freshly uploaded image can read
  0 and pass the switch.
- Clear keeps the resolved VNDB id, so the next Fetch restores the same
  novel's art.

## Alternatives

- **A credential-gated VNDB source.** VNDB needs none, and asking for a
  key would only add setup.
- **A separate `background` download.** The backdrop follows the banner
  by design (`artwork-background.md`).
- **Filtering by default or deleting cached explicit art.** Rejected:
  opt-in only, and the cache is never rewritten.
- **A picker labelled by source.** Naming the missing icon's provider
  in the dialog would explain the interruption instead of removing it;
  the smaller change is not to interrupt.
