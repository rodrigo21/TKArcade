# Metadata merge policy

Status: landed (2026-11-18).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

Download Metadata kept the fill-empty/Replace rule for every field:
with **Replace existing values** off, a list the game already had was
left untouched. Two providers answer lists, so the rule made the sources
compete instead of combine: a game with Steam tags could not take VNDB's
visual-novel vocabulary without Replace discarding the store tags, and
typing the names in by hand was the only way to combine them. Age
ratings had the same problem one level deeper: the list mixes boards
(PEGI, ESRB, USK), and a game rated by Steam never took an IGDB rating
for another board. `TODO.md` carried the decision as the metadata merge
policy; `decisions/manual-tags.md` §5 recorded the old rule.

## Decision

1. The two list fields merge by default; **Replace existing values**
   stays the wholesale overwrite, and a lock blocks either write.
2. `tags`: Apply appends the accepted provider names to the game's list,
   in the game's order first, deduped case-insensitively (the first
   spelling wins). Replace swaps the whole list for the accepted set.
3. `age_ratings`: a provider value replaces the current value of its
   own board and leaves the boards it did not answer; the order is the
   current leftovers, then the provider values. Replace swaps the whole
   set. An unknown label counts as its own board, never as covered.
4. The preview's New column shows what Apply writes, not the provider
   answer: the Tags button's text and tooltip and the Age Ratings label
   show the merged result and follow the Replace switch and the current
   lists. The Tags picker still seeds and edits only the provider names;
   declining a name that the list already carries keeps it.
5. Scalar fields keep fill-empty/Replace. The automatic Steam fill when
   a game is added (`_fill_steam_metadata`) stays fill-empty: a write
   the user never previewed must not merge.
6. `genre` and `series` stay out: they are free-form strings, not lists.
   No other field has list semantics.
7. No new config key and no migration: an existing list is the merge
   target as it stands. The 30-day cache and `CACHE_VERSION` are
   untouched, since the merge happens at Apply, not at fetch.

`manual-tags.md` §5 described the fill-empty/Replace rule as it landed;
this record supersedes it.

## Rationale

- The preview is the contract: a write that silently merged would be a
  change the user did not see. Showing the merged result keeps Apply
  honest, and the picker keeps its job of accepting provider names.
- A union for age ratings would leave one board with two contradictory
  classifications (`PEGI 12` next to `PEGI 18`). Per-board replacement
  is the smallest rule that stays correct when two providers disagree.
- Merge only when the provider changes would need provenance per list;
  tags and ratings do not track it (`manual-tags.md` §6), and the tag
  manager already owns cleaning synonyms.

## Consequences

- A game's tag list can grow across providers. Synonyms from different
  vocabularies stay until the user edits the list or the manager merges
  them; a re-download can no longer remove a stale tag, because append
  only adds.
- A merged row counts as applied even when every provider name was
  already in the list, so the status line reports `Metadata Loaded.`
  rather than `Nothing to Fill.`
- Replace remains the only path to a clean provider vocabulary, and the
  lock the only way to keep a list from changing.
- The Details tab shows the merged list after Apply like any other
  draft; Save still writes the config.

## Alternatives

- **Union the age ratings too.** Simpler, but produces contradictory
  values for one board.
- **Merge only on a provider change.** Needs a stored provider per list
  and a migration; the provenance rule above argues against it.
- **A third switch state or per-value checkboxes for ratings.** More UI
  than the decision needs; the Replace switch already expresses the
  wholesale case.
- **Keep fill-empty/Replace.** Leaves a second provider's vocabulary
  reachable only by typing the names by hand.
