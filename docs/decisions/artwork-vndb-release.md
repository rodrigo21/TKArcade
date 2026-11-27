# VNDB release cover

Status: landed (2026-11-27).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

VNDB's artwork side read only the visual novel's own image. After the
release picker landed (`decisions/metadata-vndb-release.md`), a user who
selected a release still got the visual novel's main image as the only
cover, even though that release carries its own packaging front
(`pkgfront`). For a visual novel whose main image is missing or poor,
the picked release was the obvious source of another cover, and the
chooser had no way to offer it.

## Decision

1. `src/tkarcade/vndb.py` adds `RELEASE_ART_FIELDS`
   (`images{id,type,url,dims,sexual,violence,photo}` plus the link
   fields) and lets `_release()` take the field list, so the release
   read keeps its "must still link this visual novel" check.
2. `art_options()` takes an optional `release`. When it is set, the
   picked release's `pkgfront` images are appended to the cover
   candidates, after the visual novel's image, labelled **Release
   Cover**. Other image types (`pkgback`, `pkgcontent`…) stay out.
3. The visual novel's image stays the automatic pick whenever it
   exists. A release cover only becomes automatic when there is no main
   image, so the silent Fetch and the chain fill keep the old result for
   every game with an image.
4. The usual filters apply: `[ui] hide_explicit_artwork` drops flagged
   release covers, and a URL equal to the main image is not repeated.
5. `src/tkarcade/artwork.py` reads `[metadata] vndb_release` from the
   game's config for the chooser and passes it to `art_options()`. The
   automatic `vndb.art()` path takes no release and is unchanged.
6. No language filter and no whole-release scan: only the release the
   user already picked is read, with one request.

## Rationale

- The release is a deliberate pick, so its packaging front is worth
  offering; the main image is still the canonical VN cover, so it keeps
  the automatic slot.
- One extra request only when a release is picked: no cost for every
  other game, and the chooser stays a candidate list, not a download.
- `pkgfront` is the box front; the other package types are artwork of
  the box at angles or extras and make poor library covers.
- A shared URL (VNDB often reuses the main image as a release cover)
  would show twice in the chooser and download once anyway; deduping
  keeps the list honest.

## Alternatives

- **A language filter over every linked release.** It would surface
  covers from releases the user never picked, at the cost of a second
  list, window state and several requests. Deferred until use shows the
  need; the deferred item lived in `TODO.md` under "Artwork follow-up".
- **Releasing picking the cover automatically.** It would silently
  change art for every game with a stored release. Rejected: a
  packaging front carries store logos and stickers, and the automatic
  pick must stay the image the provider always used.
