# TODO — deferred ideas

- [x] Kirigami game settings shell (General/Notes in a modal
  `Window` like the widgets QDialog — resizable, `WindowModal`,
  transient on the main window; TabBar, load/save/profile slots,
  profile-name prompt; Edit and Add open it)
- [x] Point 2 in the same mold: `PrefsDialog`, `HistoryView` and
  `ScanDialog` as modal windows (`open()` shim keeps call sites;
  scan list scrolls); confirms/about/utilities stay small dialogs
- [x] Remaining settings tabs (all nine), Clone/Reset/Global Defaults,
  Steam add flow with picker, AddSource chooser.
- [x] Kirigami File Export/Import (tarball, SteamTinkerLaunch,
  predecessor copy; local library import from Lutris/Playnite/Faugus
  file formats stays for the library phase). Scan Steam Library already exists.
  Playnite plugin metadata (Steam/Epic/GOG/PCGW/VNDB, incl. VNDB)
  is deferred research for when the import work starts.
- [x] System tray with recent games (`QGuiApplication` + QML menu now;
  tray prefs already existed; Global Defaults entry waits for the
  defaults UI)
- [x] Column drag-reorder in the QML header (title drag past a
  threshold; taps still sort, Move left/right menu stays)
- [x] QML i18n catalog (pt_BR for the strings added since the
  Kirigami work started; QML `qsTr` calls are in place; deferred
  for now, after the rest).
- [x] Manual artwork per game (icon, cover, banner), for non-Steam
  and Steam (local override); non-Steam games may reuse Steam art
  via name search or a donor AppID.
- [x] More columns, Lutris parity (candidates: last played, total
  time, platform, runner, version/wine, install dir, category);
  define the data source per column (manual, history, auto-detect,
  ProtonDB).
- [x] Categories/tags (multiple per game, drawer filter, bulk edit);
  online sources à la Playnite are deferred research.
- [x] Windows game management: prefix per game (point/create/clear),
  version selector (system Wine, Proton, custom path), runner
  (native/Wine/Proton) + args/cwd, winetricks per prefix.

- [x] Per-game display mode: save current resolution/refresh, apply the
  game's, restore afterwards (same save/restore pattern as nightlight).
  Providers with auto-detect: Plasma (`kscreen-doctor`), GNOME
  (`org.gnome.Mutter.DisplayConfig` over D-Bus), wlroots
  (`wlr-randr`/`kanshi`), X11 (`xrandr`), `off`.
- [x] Per-game audio output: route to a chosen sink via `pactl`/`pw-cli`
  on launch, restore on exit.
- [ ] Audio sink labels: `list_sinks` promises `(name, description)` but
  returns `(name, name)` — the description is never queried, the second
  item is dead end to end (`audioSinks` re-duplicates it, the QML only
  reads `[0]`), so the combo shows the raw node name
  (`alsa_output.pci-…analog-stereo`). Either parse `pactl list sinks`
  for real `Description:` labels (QML shows it, stores the name) or drop
  the pair. Deferred pending real-display review of the audio picker.
- [x] Review env presets against vendor docs (Mesa/NVIDIA semantics drift;
  verify `vblank_mode` / `__GL_SYNC_TO_VBLANK` values). Recurring: re-audit
  on every release tag (last: 2026-09-30 + installed-build checks).
- [ ] Block Internet per game (net namespace, unprivileged). DEFERRED for
  now: not cheap enough (LAN/achievements/Proton-under-userns risk matrix).
  Lighter alternative already shipped: `WINE_BLOCK_HOSTS` preset.
- [ ] vkBasalt successor: vkBasalt is unmaintained; evaluate forks or
  ReShade-on-Linux successors when mature (out for now).
- [x] FPS cap field (MangoHud `fps_limit`, per-game setting + MANGOHUD_CONFIG).
- [x] libstrangle wrapper option for DX12 titles without overlay
  (automatic fallback when fps_limit is set but MangoHud is off).
- [ ] Lint expansion (decided 2026-10-06, after the first Kirigami GUI
  steps): enable the full Ruff rule set and fix everything it reports.
  Known first case: `stl_import.map_to_gameconfig` (mccabe 26 — rewrite
  as a table-driven mapping). Strong candidates: `C90`, `RET`, `A`, `N`,
  `SIM` (minus `SIM105`, our best-effort `try/except: pass` is deliberate),
  `LOG`, `ERA`, `FLY`, `RUF022`, `TCH`. Deliberately off (documented in
  `pyproject.toml`): `PLC0415` (lazy PySide imports isolate the launcher),
  `S` (subprocess is the whole project), `EM`/`TRY` (readable raise style),
  `T201` (print is the CLI interface), `SLF` (tests touch privates),
  `D`/`ANN` (churn, much later).

## Kirigami parity (widgets → Kirigami, branch `kirigami`)

Goal: visual consistency with the widgets version, then drop widgets.
Rule: always prefer the Kirigami/Addons equivalent, never reinvent.
Parity order (agreed, i18n last): pickers+tabs → settings →
export/import → PromptDialog → tray → drag-reorder.
Status: list/icons/cards views, drawer modes, toolbar Play/Add/Edit/Remove,
game context menu, Tools menu, prefs/about/history/scan dialogs,
issues-only filter, geometry + column prefs, movable columns — all pushed
to `kirigami` (see git log). Two modes only: overlay + collapsible
sidebar (plain sidebar removed); drawer header has the gamepad
toggle and a centered Library.

### Equivalence map (audit 2026-10-07)
- [x] QMainWindow → ApplicationWindow
- [x] QListWidget sources → GlobalDrawer actions
- [x] QMenu/QToolBar → title row (buttons + centered filter) + actions
  row (view icons pinned right); per-row Play removed (play via
  double-click, toolbar or menu); header separators drag-resize and
  double-click autofits the column (measured on the model, persisted
  per column); fresh/reset starts fitted capped at 300px; filter
  clamps to 600–1200px; narrow windows shrink columns, then scroll
  with the header following; hairlines + header/footer rules.
- [x] QDialog+ButtonBox → Kirigami.Dialog
- [x] QComboBox/Spin/Slider/Check/LineEdit → QQC2 direct
- [x] QTableWidget+QHeaderView → plain QtQuick TableView + custom
  header (manual x tiling: positioners do not reschedule on child
  width edits) and kirigami-addons FormCard for prefs; keep game*
  roles, sort through existing sortBy, selectionModel replaces
  selectedIds. Never KTableView (its inner TableView spins the
  offscreen event loop forever).
- [x] QShortcut Quit → QML Shortcut (Ctrl+Q)
- [x] QMessageBox → Kirigami.PromptDialog (remove/cleanup/shader/
  history/validate; cleanup checklist via mainItem, actions fired
  with trigger())
- [x] QFormLayout (prefs) → Addons FormCard (API key row stays
  plain: FormTextFieldDelegate needs a KLocalizedContext)
- [x] QTabWidget (future settings UI) → pageStack pages + TabBar
- [x] QFileDialog/QInputDialog → portal picker / Dialog+ComboBox (with config UI)
- [x] QSystemTrayIcon → migrated to QGuiApplication + a QML context
  menu (tray controller with recents, model dispatches the entries)

### Widgets removal: done (survey 2026-10-15)

Goal reached: `src/tkarcade/widgets/` and `tests/gui_widgets_reference.py`
are deleted, the ruff `exclude` is gone, and `tests/test_no_widgets.py`
allows exactly one QtWidgets name (`QSystemTrayIcon`, from
`gui/tray.py`) while still failing on `QMenu` or any other widget class.
No module imports the widgets package.

Chosen: option 1 (`QGuiApplication` + `QSystemTrayIcon` + QML `Menu`).
- [x] Tray menu in QML (`main.qml`: `trayMenu` + `Instantiator` with
  `insertItem` for the recents), the model as the only dispatcher
  (`requestTrayMenu` signal, `trayRecentGames`, `trayAction`
  incl. `"play:<appid>"`, `trayDefaultsAvailable`); `kirigami_app`
  registers the callbacks and `tray.py` is a QSystemTrayIcon owner.
- [x] `QApplication` → `QGuiApplication` in `kirigami_app.py` and the
  conftest fixture; `tests/test_tray.py` QtWidgets-free; new QML case
  `test_tray_menu_entries_and_dispatch`; out-of-process boot check in
  `tests/test_kirigami_app.py` (main() never loads QtWidgets).
- [x] Deleted the widgets package + parked reference tests, dropped the
  ruff `exclude`, refreshed the catalog QML-only (one `lupdate6` pass +
  `lrelease6` in `scripts/refresh-translations.sh`) and rebuilt the .qm.
- [ ] `--edit <appid>` / pre-launch `--menu` still return the retired
  "needs the settings UI" stub even though the QML settings window
  exists: wire `--edit` to `gameSettings` for the AppID (and keep the
  direct-launch fallback for `--menu`), then retire `run_editor_menu`.
- [ ] Single GUI instance: the widgets app held a `QLocalServer` and a
  second launch raised the running window (its test went away with the
  parked file); the QML app currently opens a second window. Reimplement
  as a `QLocalServer`/local-socket "show" ping (QtNetwork, no new
  dependency).

Measured (2026-10-15), offscreen:
- `QSystemTrayIcon` is **not** a `QWidget` (it derives from QObject) and
  constructs fine under a `QGuiApplication`; `isSystemTrayAvailable()`
  works. The hard blocker was **`QMenu` (a QWidget): constructing it
  under `QGuiApplication` aborts the process** ("Cannot create a QWidget
  without QApplication") — hence the QML menu.
- The QML menu (`popupType: Popup.Window`) opens fine while the main
  window is **hidden**, and closing it does **not** emit
  `lastWindowClosed` (its window is transient on the shell), so the
  close-to-tray flow cannot quit the app by opening the menu.
- `QQuickMenu.itemAt()` is unreachable from PySide (the QML type has no
  Python wrapper: the call returns `None`), so QML tests measure entry
  order and visibility through the delegates (`objectName` +
  `mapToScene`) instead.
- Recents use the Qt-documented `Instantiator` + `insertItem(index,
  object)` pattern (a Repeater would feed a QVariantList into a
  positioner, the documented landmine); `onAboutToShow` reassigns the
  model so the list is fresh on every open and the delegate indexes are
  offset past "Show / Hide" + separator.
- Position: `QSystemTrayIcon.geometry()` (global) → model signal →
  `contentItem.mapFromGlobal` → `popup(contentItem, x, y)`; an empty
  geometry (no host) falls back to `QCursor.pos()`.
- Translation tooling: `pylupdate6` is not installed here, and system
  `lupdate6` reads Python natively but writes `{expr}` placeholders
  where the retired tool wrote `{}` — irrelevant now that no Python
  string is translatable (all GUI text is `qsTr` in QML).

Open (needs the real display): the menu is a non-native QQC2 window —
check position under the icon (panel-dependent), keyboard focus and
click-outside dismissal, and whether the compositor accepts a transient
popup of a hidden window at all. Fallback if not: a
`Window { flags: Qt.Popup }` menu with hand-built rows.

Options not taken: option 2 (hand-rolled StatusNotifierItem over
QtDBus) is the only path to zero QtWidgets — `PySide6.QtDBus` is
installed and the session bus is reachable, no new dependency, but it
is ~400 lines of SNI + `com.canonical.dbusmenu` with layout semantics to
reimplement. Option 3 (`PyKF6` `KStatusNotifierItem`) is dominated: it
does not drop QtWidgets (`setContextMenu(QMenu*)` still wants a QWidget
and a `QApplication`) and adds an ABI-matched runtime dependency.
Qt documents `QSystemTrayIcon` on Linux as a StatusNotifierItem client
("all Linux desktop environments that implement the D-Bus
StatusNotifierItem"), so options 1 and 2 land in the same place on the
desktop; only option 2 buys module purity.

### Drawer (after tableview)
- [x] Drawer Mode… into GlobalDrawer `footer:` (icon buttons, always
  reachable; hidden when collapsed)
- [x] Persist mode (modal/collapsible/collapsed) in prefs, restore on start
- [x] Test close→reopen keeps mode (nothing in Kirigami resets `modal`)

### Qt 6.11 QML landmines (AGENTS.md has the full list)
- Repeater models must stay JS arrays (QVariantList from setProperty
  lays out at zero width); test via moveColumn(), never setProperty.
- QEventPoint has no modifiers → MouseArea for Ctrl/Shift rows.
- Tests: structure-aware lookup only (rowColumn objectNames + parent
  modelData match); pump frames until delegates settle; XDG_CACHE_HOME
  already isolated per test, do NOT disable disk cache (breaks layout).
- `Kirigami.Card.clicked()` carries no mouse event (and exposes no
  `acceptedButtons`): the cards view keeps plain selection on
  `clicked()` and takes the context menu plus Ctrl/Shift clicks from a
  `MouseArea` that claims only those presses (`onPressed:
  mouse.accepted = ...`), leaving plain presses to the card and the
  footer's Play action. A full cover swallows Play — guarded by
  `test_card_play_button_clickable`. Anchoring that MouseArea above the
  footer is not an option: Qt refuses anchors to a non-sibling item
  ("Cannot anchor to an item that isn't a parent or sibling") and
  `z: -1` lands under the card background, which eats the press.

### Real-display checks (offscreen cannot verdict these)

Everything below passed offscreen assertions only (geometry, state,
dispatch). Each needs one look on a real compositor:

- Tray menu popup: position under the icon (it comes from
  `QSystemTrayIcon.geometry()`, so panel-dependent), keyboard focus,
  click-outside dismissal, the non-native QQC2 look, and whether the
  compositor accepts a transient popup of a hidden shell window at all
  (offscreen it does; fallback is a `Window { flags: Qt.Popup }` menu
  with hand-built rows).
- Settings window: FormCard rows side by side (the widgets QFormLayout
  put label and field on one line) and the Environment / Pre-Post tabs.
- Table: the added columns (Source, Category, ...) and the header
  drag / resize / autofit gestures.
- Category and Artwork dialogs, and the pt_BR catalog in situ.
- Audio sink picker (left untouched on this branch).
