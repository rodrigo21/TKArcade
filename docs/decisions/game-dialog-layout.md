# Game dialog layout: Details and Execution

Status: landed.

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problems

1. `Launch` sat on the identity tab, apart from the runtime, prefix and
   graphics switches it is configured with.
2. The profile bar occupied a row above the tab bar on every page, even
   for players who never use profiles.
3. The identity tab had little content after `Launch` moved, while the
   ProtonDB rating and the optional game metadata lived only in the
   views or did not exist.

## Tabs

| Tab | Content |
| --- | --- |
| `Details` | Game ID, name, version, release date, state tag, categories, ProtonDB, and the Information section: description, developer, publisher, genre, series, age ratings, region and status |
| `Execution` | Launch (executable, command prefix, arguments, working directory, pre-launch menu, log), Runtime, Prefix, Graphics, Debug |
| `Commands` | Environment variables and the pre/post commands |
| `Performance` | GameMode, MangoHud, RT Upscaler |
| `Display` | Display mode and Gamescope |
| `System` | Notifications, idle suspend, network, night light, audio, Ludusavi |
| `Artwork/Notes` | Artwork and personal notes |

`General` was renamed `Details`; `Runtime` became `Execution` and now
leads with `Launch`. `Commands` moved behind it.

## Global Defaults

Execution stays enabled in the template because Launch holds the
pre-launch menu and timeout, which are template fields. The runtime,
prefix, graphics and debug sections hide there, as do the per-game
executable, working directory and log rows; a note below Launch says
where the per-game fields live. Previously the whole Runtime tab was
disabled and the Launch fields were unreachable in the template.

## Details fields

Identity remains in `[general]`: `name`, `categories`, `version`,
`date` and `tag` (the tag stays the single free-form name suffix).

New optional manual metadata lives in `[metadata]`:

| Key | Content |
| --- | --- |
| `description` | Multiline synopsis, distinct from the personal notes |
| `developer`, `publisher`, `series` | Free text |
| `genre` | Free text, comma-separated for several |
| `age_ratings` | List from `config.AGE_RATING_GROUPS`. The picker shows CERO, ClassInd, ESRB and PEGI by default; ACB, GRAC, IARC and USK sit behind a divider and the `Other Rating Boards` switch, and a saved hidden value stays hidden until expanded. The dialog opens tall enough for the primary boards and caps at the screen work area |
| `region` | `eu`, `jp`, `us` or `world`; empty means unset |
| `status` | `abandoned`, `beaten`, `completed`, `not_played`, `on_hold`, `plan_to_play`, `played` or `playing` |

Region and status store stable codes and display translated labels, so
changing the UI language never rewrites a config. Invalid codes load as
empty. A provider (Steam's store API for Steam games, IGDB-style for
local games) can fill the same keys later.

The tab keeps one column and one shared label width; each group is a
separate `SectionBox` (`Game`, `Information`).

## Status badges

The status appears in all three views. The list name cell and the icon
view use the same 16 px colored disc with a Unicode glyph and a tooltip;
the card keeps a wider pill with the translated label. Empty status
hides the badge; unknown codes fall back to neutral.

| Status | Glyph |
| --- | --- |
| abandoned | `✕` |
| beaten | `✓` |
| completed | `★` |
| not_played | `○` |
| on_hold | `Ⅱ` |
| plan_to_play | `◷` |
| played | `◐` |
| playing | `▶` |

The glyph font comes from `gameModel.symbolFontFamily()`: the first
installed of Noto Sans Symbols 2, Noto Sans Symbols, DejaVu Sans,
Segoe UI Symbol, Apple Symbols or Symbola, falling back to the default
font and Qt's own glyph fallback.

## Profile bar

The bar remains a whole-config preset strip above the tabs. A footer
switch (`Show Profile Bar`, before `Diff vs Defaults`) hides it and
persists `[ui] show_profile_bar` (default true). The switch is hidden
in Global Defaults, which has no profiles.

## ProtonDB

Details shows a compact, left-aligned ProtonDB pill for Steam games,
filled from the existing 30-day cache and linking to the ProtonDB page.
It is not stored in the game config. Local games have no AppID, so the row stays hidden;
a future per-game Steam AppID is recorded in `TODO.md`.

## Rejected alternatives

- **Two-column Details form.** `docs/QML-NOTES.md` requires one label
  column per tab; two columns would also break the field alignment
  across sections.
- **A single Details section.** Fifteen rows in one frame; two
  `SectionBox` groups keep the tab scannable.
- **A table column for status.** The badge keeps the row compact and
  works in cards and icons; sorting and filtering can come later.
- **Reusing `tag` for status.** The single state tag stays a free-form
  name suffix (`Demo`, `Beta`), separate from the fixed lifecycle.
- **Features, multi-tags and Sorting Name.** Out of scope: each needs
  its own store or sorting plumbing.
- **Migrating translations now.** Suspended until 1.0
  (`tests/test_i18n.py` catalog tests are skipped); new strings ship in
  English and the pt_BR catalog is restored in the release pass.
