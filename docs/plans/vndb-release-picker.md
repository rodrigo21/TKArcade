# Plan: VNDB release picker

Status: proposal, not approved. Awaiting the maintainer's review of this
text; when it lands it becomes `docs/decisions/metadata-vndb-release.md`
with a landing banner and this file is deleted.
Target: before 1.0, extending the landed VNDB provider
(`docs/decisions/metadata-vndb.md`).
Created: 2026-11-19. Read `TODO.md` "Before 1.0" and `docs/STATE.md`
"Next" for the current snapshot.

## Goal

A visual novel has several releases, and each carries its own date and
producers: a publisher is not the developer, and a later localized or
fan-translated release has another date. The VNDB source should list the
releases linked to the chosen visual novel, and the pick should drive the
preview's Date and Publisher rows. The pick is stored in
`[metadata] vndb_release`, survives the cache cleanup and is used by the
next download.

## Maintainer decisions (2026-11-19)

1. **No default release.** Without an explicit pick the download keeps
   the visual-novel-level date and an empty publisher. Nothing is written
   or preselected for the user.
2. **All linked releases.** The list carries official, unofficial
   (fan-translation/patched) and non-complete releases. Labels mark
   `unofficial`, `trial` and `partial`; the picker is the place where the
   user decides. A fan release's publisher is the fan group, by design.
3. **Explicit `release` parameter.** The registry carries the release as
   its own argument instead of composing it into the cache target. The
   cache compares the visual novel and the release separately, and
   clearing a pick needs no sentinel.
4. **Language filter, client-side.** The release combo gains a
   **Language:** filter built from the rows already fetched. It narrows
   the choices without another request and resets to any language. A
   server-side `lang` filter is the alternative if the 100-row cap ever
   hides a language.

## Evidence (checked 2026-11-19)

**The adapter has no release layer.**
- `src/tkarcade/vndb.py:23` posts only to `/vn`; `fetch()` maps
  description, developer, date and tags, and hard-codes
  `"publisher": ""` (`vndb.py:154-162`). The provider declares no
  publisher (`metadata.py:70-78`).
- `/vn` exposes one `released` date and the `developers` list; it has no
  release list. The Kana `/release` endpoint has a `vn` filter and the
  `producers.publisher` flag, and allows 100 results per page.

**The registry passes one target and caches one string.**
- `Provider` (`metadata.py:47-58`) declares `resolve` and `fetch` with
  `(game_id, target)`; `cached()`/`download()` (`metadata.py:105-198`)
  record the resolved target in the cache payload and compare it. A
  changed target re-keys the entry.
- `CACHE_VERSION = 3` (`metadata.py:44`); an entry written by an older
  build reads as cold, so a new payload shape needs a version bump only
  when old data is wrong for the new shape.

**The Search Data form owns the identities.**
- The VNDB ID row sits in `GameSettings.qml:5358-5372`; the load and
  collect paths write `vndb_id` (`:1073`, `:1195`), the fetch passes the
  field as the target (`:2080-2093`), and the Details "Matches:" line
  lists the identities (`:1974-1988`).
- `model.py:84` normalizes the form map, `model.py:1107` builds it from
  the config, and `fetchMetadata`/`_metadata_worker` (`model.py:5049-5073`)
  run the provider call off-thread.

**Storage and cleanup.**
- `[metadata] vndb_id` is declared at `config.py:249`, normalized at
  `config.py:278-285`, listed in the known keys at `config.py:1109` and
  loaded at `config.py:1359`. An unknown key is preserved by older
  builds; the cache cleanup derives its namespaces from
  `metadata.cache_dirs()`.

## Design

### Adapter calls

`vndb.releases(vn_id)` posts to `/release` and returns picker rows:

```json
{
  "filters": ["vn", "=", ["id", "=", "v2002"]],
  "fields": "id,title,alttitle,released,platforms,languages.lang,official,vns.id,vns.rtype,producers.name,producers.developer,producers.publisher",
  "sort": "released",
  "results": 100
}
```

Each row becomes
`{"id": "r1234", "name": ..., "detail": ..., "langs": [...]}`:
- `name` is the short combo label: title, its date or `TBA`, platform
  codes and language codes, then the markers (`unofficial`, `trial`,
  `partial`) that apply.
- `detail` is the tooltip: alternative title, the full platform and
  language lists, the release type and the producer names with their
  roles.
- `langs` is the language-code list the client-side filter counts and
  matches. It is not stored in the config.
- The release type comes from the `vns` entry whose id is the queried
  visual novel, not from another visual novel in a bundle.
- A release without a matching visual-novel link is dropped. An empty
  id skips the network; a failed request returns `[]`.

`vndb.fetch(game_id, target="", timeout=15, release="")` keeps the
current `/vn` request. With a release it makes a second request:

```json
{
  "filters": ["id", "=", "r1234"],
  "fields": "id,released,producers.name,producers.publisher,vns.id",
  "results": 1
}
```

- The release must link the queried visual novel; otherwise the fetch
  returns `None`, so a stale or hand-edited id cannot borrow another
  game's date.
- The release's `released` replaces the visual novel's date (still gated
  by `metadata_date_valid`; `TBA` or a missing date becomes `""`).
- Publisher joins the release producers whose `publisher` flag is true,
  deduplicated like the developers; the release's `developer` flag does
  not touch the visual novel's `developer` field.
- A failed release request returns `None`; `download()` may still answer
  from the stale cache. No silent fallback to the visual-novel payload,
  which would cache one release's key with another shape.

### Registry channel

- `Provider` gains `releases: Callable[[str], list[dict]] | None` and
  `resolve_release: Callable[[str, str, str], str] | None`.
- `metadata.releases(provider, target)` mirrors `search()`: empty target
  or provider without the hook returns `[]`; the call passes the rate
  gate and is failure-tolerant.
- `cached()` and `download()` gain `release=""`. The effective release is
  resolved before the cache lookup:
  - an explicit release wins;
  - an explicit target with an empty release means **no release**, so
    clearing the pick in the window works even when the config stores
    one;
  - no target at all asks the adapter for the stored
    `[metadata] vndb_release` (a VNDB id must exist).
- The cache payload records the effective release next to the target and
  compares both. An old payload without the key reads as `""`; no
  `CACHE_VERSION` bump is needed because a no-release download still
  matches its old entry.
- `fetch` receives the release by keyword. Steam and IGDB accept and
  ignore the argument; VNDB uses it.

### Config key

- `Metadata.vndb_release` (`config.py`) holds `r1234`.
  `normalize_vndb_release()` accepts `r1234`, `1234` and a
  `vndb.org/r1234` URL, lowercases the prefix and returns `""` for
  anything else.
- The key joins the metadata known-key set, loads through the same
  normalizer, and is dropped when `vndb_id` is empty.
- It is identity, not a provider-filled field: no lock. Older builds
  preserve it as an unknown key.

### Search Data UI

- A **Release:** row sits below the VNDB ID row, visible when the source
  is VNDB and the id is not empty, with the **Language:** filter in the
  row above the combo.
- The combo starts with an empty entry ("Earliest Release (Visual
  Novel)") that means no release. The other entries are the provider
  rows. The tooltip shows `detail`.
- The list loads when the id is set: window open with a stored id,
  candidate pick, an id typed and confirmed, and a source switch to
  VNDB. It is not loaded for a Steam/IGDB source.
- A changed `vndb_id` clears the draft and reloads the list. A draft not
  present in the answer (release deleted on VNDB) stays visible with a
  `not in VNDB` marker so the user can clear it.
- Picking a release refetches through the current path with the draft
  release; the preview's Date and Publisher rows follow the landed
  fill-empty/Replace/lock rules.
- An empty or failed list hides nothing else: the combo keeps the empty
  entry and the visual-novel-level download still works.
- Save writes `vndb_release`; Cancel drops it, like the identities.
- Details shows `VNDB v2002/r1234` when a release is stored.
- New strings are English only: translations stay suspended until 1.0.

### Language filter

- A **Language:** combo sits in the Release block, above the combo, and
  follows the same visibility. Entries: "Any Language", then the codes
  present in the fetched rows with their release counts (`en (12)`).
- The filter is client-side: it reads `langs` from the rows. A release
  with several languages matches any of them and counts once per
  language. No extra `/release` request; the API `lang` filter stays
  unused in this batch.
- Window state only: it resets to any language when the window opens
  and when the VN changes, and it is not saved in the config.
- A selected release stays in the combo when the filter excludes it,
  marked `outside filter`, so the pick that drives Date and Publisher is
  never hidden.
- Codes only (`ja`, `en`, `pt-br`), matching the release labels. Readable
  names need a schema fetch or a local map; both wait for a use case.
- The 100-row cap bounds the filter: a language that appears only beyond
  the first page cannot be reached.

### Model

- `fetchMetadata(appid, provider, target, release)` passes the release
  to `metadata.download` in the worker.
- `fetchReleases(appid, provider, target)` runs
  `metadata.releases` off-thread and emits
  `metadataReleases(appid, rows)`. It respects
  `TKARCADE_NO_BG_FETCH` like the other fetchers.

### Cache and request budget

- Worst case three requests per pick (release list, visual novel,
  release), spaced by the existing 1 s gate.
- The release list has no disk cache in this batch: every window open
  that shows the row refetches it. Add one only if use shows the need.
- The language filter adds no request; it narrows the rows already in
  memory.
- The 100-row cap gets a `shortcut:` comment; pagination waits for a
  visual novel that exceeds it.
- A release deleted on VNDB leaves the stored pick failing until the
  user clears it; no automatic rewrite.

## Batches (one commit each)

1. **This plan.** `docs/plans/vndb-release-picker.md`, the
   `docs/README.md` map entry and the `docs/STATE.md` next step.
2. **Adapter, config and registry.** `src/tkarcade/vndb.py`,
   `src/tkarcade/config.py`, `src/tkarcade/metadata.py`; unit tests in
   `tests/test_vndb.py`, `tests/test_config.py`,
   `tests/test_metadata.py`.
3. **Model and UI.** `src/tkarcade/gui/model.py`,
   `src/tkarcade/gui/qml/GameSettings.qml`, QML cases in
   `tests/kirigami_qml_cases.py` (release row, language filter,
   clearing), model coverage in `tests/test_kirigami_model.py`, plus the
   offscreen screenshot.
4. **Landing docs.** `docs/decisions/metadata-vndb-release.md`, the map
   entry, `README.md` (Search Data paragraph), `CHANGELOG.md`, the
   finished `TODO.md` item and `/handoff`.

## Verification

- Batch 2: `pytest tests/test_vndb.py tests/test_metadata.py
  tests/test_config.py`.
- Batch 3: the single QML case with
  `pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"`
  plus `scripts/check.sh --qml` once; an offscreen screenshot of the new
  rows.
- On the approved diff: the full `scripts/check.sh --qml`, before the
  commit and again after the merge per `docs/GIT.md`.
- A real API smoke (`vndb.releases("v2002")` and one pick) is manual,
  read-only and network-dependent; tests keep stubbing `urlopen`.

## Risks

- The "all releases" scope makes the combo long and can surface a fan
  translation's date and publisher; the markers and the tooltip are the
  only guard.
- The 100-row cap can truncate an unusually large release list; the
  shortcut comment records the limit. A language that appears only
  beyond the first page stays unreachable through the client-side
  filter.
- Bilingual releases count in every language they carry; the counts are
  per release, not per language edition.
- Codes instead of language names are shorter but less readable for a
  user who does not know them.
- A release can list several publishers for different regions; the
  joined list loses that distinction, matching the single Publisher
  field.
- Three requests per pick with a 1 s gate feels slow inside the dialog;
  the list request and the metadata fetch are independent, so the wait
  stays bounded.
- A stored release deleted upstream fails until cleared.
- Publisher is a locked manual field today; the release pick must obey
  the same lock and fill-empty rules or a download overwrites typed
  text.

## Alternatives

- **Compose the release into the target (`v2002@r1234`).** Reuses the
  current signature, but clearing the pick needs a sentinel because an
  empty release would fall back to the stored config value.
- **Preselect the earliest official release.** Fills publisher without
  a user action, but chooses a region and a release for the user and
  changes today's date silently.
- **List official releases only.** Shorter list, but hides the release a
  fan-translation user actually runs.
- **Server-side language filter (`["lang","=","en"]`).** Reaches releases
  beyond the first page and returns shorter lists, at one request per
  language change and more window state; the client-side filter covers
  the common case.
- **Store date and publisher at pick time only.** Loses the pick on the
  next download and gives no way to change it later.
- **Derive publisher from the visual novel's developers.** The developer
  is not the publisher; VNDB keeps them apart on the release.
