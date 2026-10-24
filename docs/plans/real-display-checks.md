# Real-display checks

Status: prepared (2026-10-24), awaiting the maintainer's pass on a real
compositor. Runbook for the items offscreen tests cannot verdict.

The QML suite asserts geometry, state and dispatch on `QT_QPA_PLATFORM=
offscreen`. That cannot answer "does the tray menu appear under the
icon on Plasma Wayland", "are the settings rows really on one line",
"does the pt_BR catalog fit in the buttons". Those need one look each.

## Running the pass

```sh
scripts/display-check.sh                 # English, 3 seeded games
scripts/display-check.sh --lang pt_BR    # item 5
scripts/display-check.sh --keep          # reuse the profile afterwards
```

The script builds a throwaway profile (`XDG_CONFIG_HOME` and friends
inside it, `TMPDIR` too, so the single-instance socket is its own) and
seeds three games: `check-native`, `check-wine` (game type Wine) and
`check-category` (category `Testing`, platform `PC`, a real PNG cover
and banner). Your `~/.config/tkarcade` is never read or written.

`TKARCADE_OPEN=<surface>` opens one dialog at launch instead of hunting
through the menus:

| value | opens |
| --- | --- |
| `settings` | game settings for the selected row |
| `settings:<appid>` | game settings for that game |
| `artwork:<appid>` | the same window on the Artwork/Notes tab |
| `defaults` | the Global Defaults editor |
| `add` | the Add Game dialog |
| `category` | the category filter |
| `prefs` | Preferences |
| `about` | About |

Record each result in the table at the end. Screenshot **only on
failure**, attached to the follow-up item; a passing pass needs no
artifacts.

## 1. Tray menu

Highest risk: it is the one path with no offscreen substitute for the
host's own behaviour.

Preparo: default profile (`tray_enable` on), Plasma Wayland.

1. Launch; the icon appears in the tray.
2. Left click: the window toggles (hidden → shown and raised, shown →
   hidden).
3. Right click: the menu appears **under the icon**, not at the cursor
   corner, not on another monitor.
4. Entries: recent launches (up to five, most recent first), Preferences…,
   Global Defaults, About…, Quit.
5. Keyboard: the menu takes focus; arrows move, Enter activates, Esc
   dismisses.
6. Click outside: dismisses, no stray window left behind.
7. Reopen after playing nothing: the recents list is rebuilt on every
   open (`aboutToShow`), not stale.
8. Quit exits the process (not just hides the window).

Accept: menu positioned under the icon, focus and keyboard navigation
work, dismissal clean, labels translated in the pt_BR pass (item 5).

Fails if: the menu opens at (0,0) or under the wrong monitor, right
click does nothing, the recents are stale, or Quit leaves the process
alive.

Where: `gui/tray.py` (the `QMenu`, `setContextMenu`, `aboutToShow`),
`kirigami_app.py:_tray_callbacks`, `gui/model.py` (`trayAction`,
`trayRecentGames`). The native menu is deliberate: Plasma's SNI host
never delivers `activated(Context)` without an exported context menu,
so the earlier QML menu could not open at all.

Next if it fails: the QML-popup fallback is already ruled out by that
measurement; fix the native path (placement from `QCursor.pos()`,
rebuilt entries) in its own branch, and keep the offscreen coverage in
`tests/test_tray.py` unchanged.

## 2. Settings window layout

Preparo: `TKARCADE_OPEN=settings:check-native`.

1. Every tab, top to bottom: General, Launch, Environment, Compatibility,
   Performance, Display, System, Artwork/Notes.
2. Rows read label left, field right, on one line — the same shape as
   the widgets `QFormLayout` the QML replaced.
3. Resize the window narrower and taller: no clipped labels, no field
   running past the edge.
4. Long lists (Proton versions, wine tools, profiles) scroll inside the
   window instead of growing it past the screen.
5. Footer preview starts collapsed; expanding it does not push the tabs
   out of reach.

Accept: one line per row, aligned columns, window height follows the
current tab.

Fails if: a label sits above its field, fields start at different x
positions across rows, or the window opens taller than the screen.

Where: `qml/WidgetsFormLayout.qml`, `qml/GameSettings.qml` (TabBar at
`settingsTabs`).

## 3. Table and header

Preparo: the seeded profile; `check-category` carries a category and a
platform so those columns have content.

1. Columns Source, Category, Platform and Version show their values.
2. Drag a header title past the threshold: the column moves; a plain tap
   still sorts by it.
3. Drag a header edge: the column resizes; double-click autofits.
4. Restart: column order, widths and hidden columns survive (they live
   in `preferences.toml` as `column_order`, `column_widths`,
   `hidden_columns`).
5. Columns dialog: toggling a column takes effect immediately.

Accept: reorder/resize/autofit feel like the widgets header, taps still
sort, everything persists.

Fails if: a drag also fires the sort, a resize jumps on release, or the
order resets after a restart.

Where: `qml/MainPage.qml` (header, `MouseArea` drag), `qml/ColumnsDialog.qml`,
`gui/model.py` (column order/width slots).

## 4. Category and Artwork dialogs

Preparo: `TKARCADE_OPEN=category`, then `TKARCADE_OPEN=artwork:check-category`.

1. Category: the radio list shows All and `Testing`; picking one closes
   the dialog and filters the table.
2. Artwork: the seeded cover and banner render as images (not a broken
   icon placeholder), with their Clear buttons and "Reuse Artwork From…".
3. The dialog is sized to the window, not a fixed rectangle; a long
   category list scrolls.

Accept: images render at the right aspect, the filter applies, no
placeholder for the seeded art.

Fails if: thumbnails stay empty (path resolution), or the dialog opens
at the wrong size on a scaled display.

Where: `qml/CategoryDialog.qml`, `qml/GameSettings.qml` (artwork tab;
`SETTINGS_TAB_ARTWORK` in `gui/kirigami_app.py` must match the TabBar
index — currently 7).

## 5. pt_BR catalog in situ

Preparo: `scripts/display-check.sh --lang pt_BR` (the language comes from
`preferences.language`, not from `LANG`).

1. Main window: header, drawer, context menus, empty-state text.
2. Settings: every tab label and every field label.
3. Dialogs: Add, Category, Artwork, Preferences, About.
4. Tray menu (Python `TrayMenu` context).

Accept: no truncated or ellipsised button text, accents and casing
correct, English only where it is a proper noun or tool name (`wine`,
`umu-run`, `winetricks`, `vkBasalt`, `MangoHud`, `DXVK`).

Fails if: a label clips, a string stayed English that should not, or a
`%1`-style placeholder is missing from the translation.

Where: `src/tkarcade/translations/tkarcade_pt_BR.ts`,
`scripts/refresh-translations.sh` (refuses to write a `.qm` while a
message stays flagged unfinished).

## 6. Audio sink picker

Preparo: Settings → System, with PipeWire or PulseAudio running.

1. Open the output-sink combo.
2. The entries show human descriptions, with the node name as fallback
   when the server reports no description.
3. Selecting one saves the node name (check `[audio] sink` in the game
   TOML) and the launch routes to it.

Accept: descriptions in the list, node name in the config.

Fails if: the list shows raw node names only, or the saved value is the
description.

Where: `backends/audio.py` (`list_sinks`, long-form parse),
`qml/GameSettings.qml` (audio combo).

## Results

| # | Item | Date | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | Tray menu | | | |
| 2 | Settings layout | | | |
| 3 | Table and header | | | |
| 4 | Category/Artwork | | | |
| 5 | pt_BR in situ | | | |
| 6 | Audio sink picker | | | |

Fill Result with `ok` or `failed`; a failure gets its own `TODO.md` item
(or branch) with the screenshot attached. When the pass is clean, delete
the "Real-display checks" section from `TODO.md` and keep this document
as the runbook for the next release.
