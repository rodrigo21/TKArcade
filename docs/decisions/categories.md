# Categories in the library sidebar

Status: implemented (2026-10-30).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: categories should behave the way they do in Lutris — free-form
category entities with icons, a section in the library sidebar listing
every category with its game count, and a click on one filters the game
list.

## Evidence

**Lutris** (checked locally in 0.5.x, revisited for the second batch)
keeps categories as entities with a folder icon by default: its sidebar
carries a Categories section with one row per category, its icon and
game count, and a click filters the list. A category stays listed as
`(0)` after the last game drops it; each category has an `Edit Games`
entry that assigns it across several games and is also where it is
deleted, and the icon can be changed through the KDE icon picker
(`org.kde.iconthemes.IconDialog`, the dialog Dolphin uses for folders).
Assignment is a checkable list, not a comma-separated text field.

## Decisions

**Categories are stored, not derived.** The first batch derived the
sidebar from the tags found on configs, so the section vanished with the
last tag. `categories.toml` in the config directory (`[categories]`
name → icon, stdlib TOML, atomic write) now holds every category ever
created; any tag found on a config during a refresh is registered there,
so hand-edited configs still surface, and removing a category from its
last game leaves a `(0)` row. Only the explicit Delete drops an entry.

**The section replaces the filter dialog.** The single
`Category: All/<category>` drawer row and `CategoryDialog.qml` (a radio
list) are gone; the drawer section lists the categories directly, as
Lutris does. It is a `Kirigami.Action` with `expandible: true` whose
children are rebuilt from `allCategories()` whenever the model refreshes;
the GlobalDrawer paints the header plus the entries inline and turns
them into a popup when the drawer is collapsed. A separator action
divides it from the Origins section above, so the source filter and the
categories read as separate blocks. The section stays visible while the
store has an entry.

**All Categories is the first entry, with the library count.** Lutris
has no explicit "all" row, but re-clicking a checked category also
clears the filter here, and the row keeps the old dialog's discoverable
way out. It is counted like the other rows (`All Categories (N)`, N the
full library), and every category row shows its icon and game count
(`Action (2)`).

**Sources get their own named section.** The three source rows sit
under an `Origins` expandible action with an icon, mirroring the
taxonomy's Origin axis; a separator follows it, and the categories
section below carries the Categories header with its own icon. Origins
uses the game-library folder (`folder-games`, falling back to the
gamepad logo) and Categories a tag (`tag-symbolic`/`tag`), so the
headers read as a library and as labels rather than as a deck of cards.
Each source row also carries an icon (a grid for All Games, the Steam
logo, a computer for Local), matching the iconed category entries.

**Editing a category.** A gear action labeled `Edit Categories` is the
first row of the section, directly under the title, so a long category
list cannot bury it below the fold. Two separator actions frame it, so
the row reads as the section's control rather than as another entry.
It opens `CategoryManagerDialog`,
because the drawer's delegates have no context menu, clicking an action
with children pushes a submenu page, and the GlobalDrawer paints header
rows without a trailing action slot: the action cannot sit beside the
Categories title, so it is a regular labeled row (icon plus text, the
theme's action font), and the drawer scrolls it along with the title.
The manager lists every stored category with its icon and count;
each row's Edit opens `CategoryEditorDialog`, which checks the games
that carry the category (accept writes exactly that set through
`setCategoryGames`), carries the icon button that opens
`org.kde.iconthemes.IconDialog` (the icon defaults to the folder), and
owns Delete behind a confirmation, which strips the category from every
game and from the store. This is where Lutris's `Edit Games` lives,
renamed because the dialog edits the category, not its games.

**Assignment stays replace-based, but checkable.** The Set Categories
dialog lists the categories in use as checkboxes (partially checked when
only some of the selected games carry one) and keeps a field for new
categories. Accepting writes checked + typed categories to every
selected game, which is the dialog's previous semantics. The same
`CategoryPicker.qml` opens from the Add button beside the Categories
field on the General tab (the field moved to the end of the Game
section); there it writes the picked names back into the comma field,
which remains the per-game text path and still saves them. The category
editor is a second checkable list, keyed by game instead of by category.

**Unchecking removes.** The picker rows are plain JS objects; a
Repeater's `modelData` is a copy, so writing `modelData.state` left the
owner array untouched and the category survived Accept. Delegates carry
`index` and write `catRows[index].state`; a test clicks the checkbox for
real (`onToggled` is user-only) and asserts the config loses the
category.

**Categories are normalized at the boundaries.** `normalize_categories()`
trims, drops empties and dedupes case-insensitively, keeping the first
spelling; config load, `_apply_map`, `setCategories`, `allCategories()`
and the store all use it, and the filter compares lowercased. The
sidebar therefore lists one entry per category even when hand-edited
configs disagree on case. The UI calls them categories throughout;
"tag" is reserved for the separate state tag of a game.

**The comma limitation is unchanged.** `setCategories` takes a
comma-joined string, so a category containing a comma cannot round-trip
through the Set Categories field or the settings field; the checkable
list sends the categories it displays through the same slot. The
category editor writes names into the config array directly, so it is
the one path that can carry a comma.

**`TKARCADE_OPEN=category` expands the sidebar.** The real-display check
needed a programmatic way to show the filter; with the dialog gone the
surface reveals the section instead of opening a window.
