# Kirigami/QML rules (hard-won, do not regress)

Rules learnt the hard way while building the Kirigami shell. Read the
relevant entries before touching QML; every one of them fixed a real
failure. `AGENTS.md` links here.

- Repeater models must stay JS arrays end to end: a QVariantList
  injected from Python (e.g. via setProperty) lays out at zero
  width on Qt 6.11. All QML writers build fresh JS arrays.
- Row clicks need modifiers (Ctrl/Shift multi-select): QEventPoint
  carries none, so rows use MouseArea (below the content, accepted
  Left|Right) instead of TapHandler.
- QML tests: never walk childItems() blindly (aborts on dead
  pooled/delegate wrappers) and never use findChildren for
  Repeater-nested items (QObject tree misses them). Navigate known
  structure only (objectName'd column roots + direct cells),
  match cells by parent modelData, and pump frames until delegates
  settle (Repeater columns instantiate asynchronously).
- Addon table cells do not wrap for tests: assert through the
  selectionModel, header component props and measured metrics
  (contentHeight/rowCount), never through delegate objects.
- Table delegates bind the Loader-provided `model` roles directly
  (`model.gameIcon`, never `rowData(row)` which desyncs on sort);
  `model` is null transiently, so every dereference needs optional
  chaining plus fallback (`model?.gameIcon ?? ""`).
- `selectedIds` is the only source of truth for selection. The TableView
  is a write-only mirror: hiding it drops its selection and it clears the
  selection again when it comes back (measured), so `onViewModeChanged`
  re-applies `selectedIds` through `applySelectionToTable` with
  `Qt.callLater` once the view has settled, and nothing reads the
  selection model back. The icons → cards → list switches all pass
  through it; the widgets had a single view, so there is no reference
  behaviour to copy (found while giving the views keyboard navigation).
- `Kirigami.Card.clicked()` carries no mouse event and exposes no
  `acceptedButtons`: the cards view keeps plain selection on `clicked()`
  and takes the context menu plus Ctrl/Shift clicks from a `MouseArea`
  that claims only those presses (`onPressed: mouse.accepted = ...`),
  leaving plain presses to the card and the footer's Play action. A full
  cover swallows Play (guarded by `test_card_play_button_clickable`),
  and anchoring that MouseArea above the footer is not an option: Qt
  refuses anchors to a non-sibling item and `z: -1` lands under the card
  background, which eats the press.
- `Controls.ScrollView` manages its content x/y itself: never position
  content with `x` or anchors (silently reset, no warning) — wrap in a
  plain Item and center inside that instead. Scrolling needs the
  content's **implicit** size: the wrapper must carry `implicitHeight`
  (a plain Item has none), else the ScrollView sizes the content to the
  viewport, `contentHeight` stays -1 and nothing scrolls at all.
- Dialog windows are sized, never a fixed rectangle: the width follows
  the widgets reference (r240, measured off the system install) and the
  height the body content plus the body margins, with lists capped so a
  long list scrolls instead of growing the window; a stacked page reads
  the **current** page's implicit height (a `StackLayout` reports its
  tallest child, so the backup-file page would stay as tall as an STL
  list loaded earlier). A height that follows Repeater-built content
  means the ScrollView syncs its content size a layout pass **after**
  the window is mapped: tests wait (`QTest.qWait`) before asserting
  `contentHeight`.
- Dialog bodies use `Kirigami.Units.smallSpacing * 3` (12px) as the
  layout margin, matching the widgets `QDialog`/`QMessageBox` (10px
  under Breeze, 11px offscreen). Do not "fix" it back to `largeSpacing`
  or `smallSpacing * 2`: both are 8px in this Kirigami (`gridUnit` 18).
- A layout item's maximum size defaults to its implicit size, so a
  collapsed `SectionBox` (frame hidden, title checkbox the only visible
  child) shrinks to the checkbox unless the maximum hint is widened:
  the component sets `Layout.maximumWidth: Number.POSITIVE_INFINITY`
  itself, hosts still ask for `Layout.fillWidth: true`.
- QQC2 `onToggled` fires on user interaction only (unlike QWidgets):
  react to programmatic `setProperty("checked", ...)` (tests included)
  with `onCheckedChanged` instead.
- QQC2 menu entries keep their layout height when `visible: false` (the
  menu skips nothing): collapse conditional entries with
  `height: visible ? implicitHeight : 0` or the menu paints blank rows
  (29px per item, separator 3px, measured offscreen).
- A QML binding that calls a model method is evaluated once, before the
  shell registers its callbacks, and never updates: re-read such state in
  the popup's `onAboutToShow` (where the dynamic entries are rebuilt).
- QML tests wait with `QTest.qWait`, not bare `processEvents()` loops:
  layout passes need wall-clock time, and a few hundred tight iterations
  can all run inside one millisecond on an idle machine while starving
  under load (a case flaked inside `makepkg`'s check).
- `XDG_CACHE_HOME` is isolated per test (`tests/conftest.py`) so the QML
  disk cache never leaks between cases — but never disable the disk
  cache itself: layout breaks without it.
- A test that runs `edit.main()` or `kirigami_app.main()` in process
  pins `QT_QUICK_CONTROLS_STYLE` in `os.environ` for the rest of the
  session (the QML driver's children then inherit the desktop style and
  style-sensitive cases flip inside the full suite) — save/restore the
  variable explicitly in an autouse fixture; `monkeypatch.delenv` on an
  already-absent var registers no undo and does not undo `main()`'s write.
- `Kirigami.Dialog` overlays never finish their enter fade offscreen
  (they render invisible): synthetic clicks don't reach their buttons —
  open them via clicks and drive accepts with direct calls instead.
  After `close()`, assert `opened` (not `visible`, which lingers
  through the exit transition), and never click the next control right
  away: the fading overlay swallows the click silently and the failure
  surfaces in an unrelated assertion. `_click()` in
  `tests/kirigami_qml_cases.py` polls the window hit test (walking
  `childAt` down the tree, it only reports one level) until the control
  is the visible target, then clicks — use it in settings/dialog cases.
- `StackLayout` children do not auto-fill: every tab needs explicit
  `Layout.fillWidth/Height`, else it collapses to implicit size.
- Settings and dialogs mirror the widgets QDialog layout in pure QML
  (`SectionBox` gives the QGroupBox look: centered title above a framed
  panel, `checkable` mirrors `setCheckable`; each panel computes its own
  right-aligned label column through `WidgetsFormLayout`; section
  checkboxes are centered; the button box keeps Diff/Reset on the left,
  accept/cancel on the right). QQC2's `Controls.GroupBox` in the desktop
  style puts the title inside the frame at the top-left — not the
  widgets look. Layout rule, not a toolkit one: QtWidgets stays out of
  the tree (`tests/test_no_widgets.py` defines the allowed names).
- The reference for that layout is the retired QtWidgets shell, archived
  at tag `widgets-2026-10-06`; the dialog metrics were measured against
  the maintainer's r240 build, which lives outside the repo. Read the
  archived code instead of trusting memory or a copy pasted into a note:
  `git show widgets-2026-10-06:src/tkarcade/gui/main_window.py`.
- Every dialog button row copies the KDE `QDialogButtonBox` layout:
  Help/Reset/action buttons lead, the accept button then the reject come
  last, and the whole cluster is right-aligned (spacer first) with the
  accept button `highlighted`. Check the real layout with a
  `QDialogButtonBox` under `QT_QPA_PLATFORMTHEME=kde` before guessing —
  the offscreen default lays the same roles out differently.
- Every widgets-style form is a `WidgetsFormLayout`, never a plain
  `KirigamiLayouts.FormLayout`: Kirigami sizes its grid to the form's
  natural width and centers it, so a wide dialog shows a hole left of
  the labels and fields stuck at their implicit width. Our subclass
  binds the implicit width to the actual one, so the field column takes
  the remaining space (a widgets QFormLayout) and `Layout.fillWidth`
  fields reach the panel edge.
- Pushed pages slide in: QML tests must `QTest.qWait` for the PageRow
  transition before synthetic clicks, or clicks land mid-slide.
- Separate modal windows outlive their test's main window by event
  rounds: `_load_main` closes straggler top-levels so title lookups
  (`topLevelWindows()`) never match a foreign window.
- Fixed bottom blocks shrink `StackLayout` tabs: if tab content grows
  past the window, `ScrollView` clip swallows synthetic clicks silently
  (identical geometry, no warnings). Keep the default window tall enough
  that tab controls stay above the fold offscreen.
- Content windows (settings and friends) are separate modal `Window`s
  (`WindowModal`, transient on the main window): resizable, no PageRow
  tiling surprises. Tests drive them through `topLevelWindows()` by
  title, clicking on the window itself.
- The shell builds a `QApplication`, on purpose: on Plasma the platform
  theme supplies the tray icon through a `KStatusNotifierItem`, whose
  constructor creates a `QMenu` — a `QWidget` — so a `QGuiApplication`
  aborts the process inside `QSystemTrayIcon.show()` ("Cannot create a
  QWidget without `QApplication`"). Do not "clean" it back. The tray
  context menu is a native `QMenu` in `gui/tray.py`: the Plasma SNI host
  only shows a menu the app exports through `setContextMenu()` and never
  delivers `activated(Context)` without one, so a QML menu could not be
  opened from the tray at all. `QSystemTrayIcon` and `QMenu` in
  `gui/tray.py`, plus `QApplication` in `gui/kirigami_app.py`, are the
  only QtWidgets names the tree may import (`tests/test_no_widgets.py`
  defines done). The native menu skips invisible actions outright, so
  conditional entries (recents separators, Global Defaults) are simply
  left out — the blank-row collapse QQC2 needs does not apply here.
  Recents and Global Defaults rebuild on `aboutToShow`; the host
  positions the menu under the icon, so no `geometry()`/`QCursor.pos()`
  plumbing to `popup()`. Zero QtWidgets would need a hand-rolled
  StatusNotifierItem + `com.canonical.dbusmenu` (~400 lines, no new
  dependency); PyKF6's `KStatusNotifierItem` still wants `QMenu` and a
  `QApplication`, so it is dominated and adds an ABI-matched runtime
  dependency. Qt documents `QSystemTrayIcon` on Linux as a
  StatusNotifierItem client, so both land in the same place on the
  desktop; only the hand-rolled one buys module purity. Its labels are
  the only Python-translatable strings, in a `TrayMenu` context: system
  `lupdate6` reads Python natively and writes `{expr}` placeholders
  where the retired `pylupdate6` wrote `{}` — adjust by hand, the
  extraction itself is clean.
- Kirigami's ApplicationWindow ships a built-in Quit action bound to
  the quit sequence that calls `close()` (not quit): clear
  `quitAction.shortcut` at startup or Ctrl+Q closes-to-tray instead
  of quitting.
- The shell is single-instance: `kirigami_app.single_instance()` listens
  on `$TMPDIR/tkarcade-gui-<uid>` (QtNetwork) and a second launch pings
  "show" and exits 0 before building any UI; `show_requested()` brings
  the window back from the tray. Do not add a second window path.
- A `Window` declared inside another one never shows while the
  enclosing window is hidden (`visible = true` and `show()` both no-op,
  Qt 6.12). The standalone editor (`Editor.qml`) therefore creates its
  windows with `createObject(null)` and keeps them in JS properties
  (no QObject parent); the shell's own windows are nested and only ever
  shown while the main window is visible.

## Test driver

`tests/test_kirigami_qml.py` runs `kirigami_qml_cases.py` in short-lived
`pytest` subprocesses (the whole file aborts in one process on Qt 6.12
GC teardown); a batch that aborts re-runs its swallowed cases in
isolation, and a case counts as passed once its `PASSED` line printed
(a teardown segfault after it is expected).

- Fast loop without QML (~17s): `pytest tests/ -q -m "not qml"`, which
  `scripts/check.sh` runs. Full run (~90s): `pytest tests/ -q`. The
  marker covers exactly one node, `test_qml_suite_isolated`, so a check
  run ends with "1 deselected" — expected, not a skipped case: that node
  is the driver that runs every QML case in subprocesses.
- Knobs: `TKARCADE_QML_BATCH` (cases per subprocess; default 8 serial,
  4 up to four workers, 2 above) and `TKARCADE_QML_WORKERS` (default one
  per CPU, capped at 8). Parallel runs can flake timing-sensitive cases
  under load: set `TKARCADE_QML_WORKERS=1` to force serial.
- `pytest -v -rP tests/test_kirigami_qml.py` prints one line per
  finished batch with its wall time; the `-git` PKGBUILD runs it that
  way so a slow build names the culprit (plus `--show-capture=stdout`:
  plain `-rP` also dumps the captured log/stderr of every passing
  test).
- Failures are bounded: the assertion shows a tail per case and the
  `/tmp/tkarcade-qml-fail-*.log` path with the full output.
- Single case:
  `pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"`.
