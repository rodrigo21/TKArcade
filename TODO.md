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
- [x] Lint expansion (decided 2026-10-06, done 2026-10-16): the agreed
  batch is enabled — `RET`, `SIM` (minus `SIM105`, our best-effort
  `try/except: pass` is deliberate), `ERA`, `FLY`, `LOG`, `TCH`,
  `RUF022`, `A`, plus `C90` (initially `max-complexity = 10`, then
  tightened to 9 in a follow-up sweep). Every finding was fixed, none
  suppressed; the functions over the cap (worst: `launcher.main` 52,
  `stl_import.map_to_gameconfig` 26, the display backends 19) were split
  into helpers with behaviour, exit codes and report order unchanged.
  `N` (naming) was reviewed and stays off: the camelCase Qt slots the QML
  calls are the API (`hideOnClose`, `trayAction`, ...). Deliberately off
  (documented in `pyproject.toml`): `PLC0415` (lazy PySide imports isolate
  the launcher), `S` (subprocess is the whole project), `EM`/`TRY`
  (readable raise style), `T201` (print is the CLI interface), `SLF`
  (tests touch privates), `D`/`ANN` (churn, much later).

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

### Parity finish (2026-10-16, paired offscreen audit)

Closed against the widgets r240 reference (paired screenshots, same seed):
settings footer (`Reset to Global Defaults` moved out of the profile row)
and wrapper summary (`Will launch with: …`, above the buttons; the summary
now refreshes after the missing-binary pass so it never lists a tool the
command builder skips); session history columns (Sessions/Total
time/Failures) + bold header + confirmed bulk `Clear History...`; General
`Detected Runtime:` row, the Steam `Game name` (read-only) and the widgets
field order; empty-state `Import...` + three-step hint with the table
header hidden; pre-launch artwork / `name (appid)` / `Proton:` line;
preferences SteamGridDB row inside the card, ordered before Language, with
the window sized to the form.

Left open (deliberate, not regressions): the widgets `Dependency Status`
group (replaced here by the disabled tool toggles + preview warnings) and
the widgets `Reset to Factory Defaults` in the Global Defaults dialog. The
General form keeps Kirigami's wider side margins; the wide/narrow switch
(`KirigamiLayouts.FormLayout`) already mirrors the QFormLayout behaviour.

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
- [x] QSystemTrayIcon → kept (it needs a `QApplication` on Plasma)
  with a native `QMenu` context menu (tray controller with recents, model
  dispatches the entries)

### Widgets removal: done (survey 2026-10-15)

Goal reached: `src/tkarcade/widgets/` and `tests/gui_widgets_reference.py`
are deleted, the ruff `exclude` is gone, and `tests/test_no_widgets.py`
allows exactly two QtWidgets names (`QSystemTrayIcon` and `QMenu`, both
from `gui/tray.py`) while still failing on `QDialog` or any other widget
class.
No module imports the widgets package.

Chosen: option 1 (`QSystemTrayIcon` + a native `QMenu` context menu),
with the shell on a `QApplication` (see Measured: the Plasma tray needs
one).
- [x] Tray menu native (`gui/tray.py` builds the `QMenu` and exports it
  through `setContextMenu`, rebuilt on `aboutToShow` for the recents and
  Global Defaults), the model as the only dispatcher (`trayRecentGames`,
  `trayAction` incl. `"play:<appid>"`, `trayDefaultsAvailable`);
  `kirigami_app` registers the callbacks (incl. `"quit"`) and `tray.py`
  owns the icon.
- [x] Tray menu labels translated again through a `TrayMenu` Python
  context (`gui/tray.py`); the refresh script feeds that file to
  `lupdate` next to the QML set and passes `-no-obsolete` to drop the
  five orphaned `main` entries the native menu left behind.
- [x] `QGuiApplication` → back to `QApplication` in `kirigami_app.py`
  and the conftest fixture (the icon aborts on Plasma under the former;
  the try was the bug fixed on 2026-10-15); the controller's menu is
  covered in `tests/test_tray.py`; out-of-process boot check plus a
  widget-construction guard in `tests/test_kirigami_app.py`.
- [x] Deleted the widgets package + parked reference tests, dropped the
  ruff `exclude`, refreshed the catalog without the widget strings (one
  `lupdate6` pass + `lrelease6` in `scripts/refresh-translations.sh`) and
  rebuilt the .qm.
- [x] `--edit <appid>` / pre-launch `--menu` wired to the QML windows:
  `gui/edit.py` is the child (same flags and one-JSON-line protocol as
  the widgets one, `clean_gui_env`), `Editor.qml` hosts it,
  `PrelaunchMenu.qml` is the menu (`menu_timeout` countdown, stopped
  when Settings… opens) and `run_editor_menu` spawns + parses. The
  in-process fallback is gone: a missing child reads as "unavailable"
  (`--edit` exit 15, `--menu` warns and launches directly).
- [x] Single GUI instance: the shell holds a `QLocalServer`
  (`$TMPDIR/tkarcade-gui-<uid>`, QtNetwork) and a second launch sends
  "show" and exits 0; the primary restores from minimized, shows, raises
  and activates. Stale sockets (crash) are removed and reclaimed.
  Covered by `single_instance`/`show_requested` tests plus an
  out-of-process ping; the boot check pins `TMPDIR` so a real running
  shell cannot answer for it.

Measured (2026-10-15):
- A `Window` declared inside another window **never shows** while the
  enclosing one is hidden (`visible = true` from QML and `show()` both
  no-op; measured offscreen and on Wayland, Qt 6.12): the standalone
  editor has no main window, so `Editor.qml` creates its UI windows with
  `createObject(null)` instead — top-levels, shown normally, kept alive
  by a JS property (no QObject parent).

Measured (2026-10-15):
- `QSystemTrayIcon` is **not** a `QWidget` (it derives from QObject), but
  on Plasma it **needs a `QApplication` anyway**: `show()` goes to the
  platform theme (`KDEPlasmaPlatformTheme6.so`), which builds a
  `KStatusNotifierItem` and its constructor a `QMenu` — a `QWidget` — so
  a `QGuiApplication` aborts the process ("Cannot create a QWidget
  without QApplication"). Offscreen never caught it: the theme plugin is
  not loaded there. Backtrace (gdb):
  `QSystemTrayIcon::setVisible` → `KDEPlasmaPlatformTheme6.so` →
  `KStatusNotifierItem::KStatusNotifierItem` → `QMenu::QMenu` → fatal.
  With a `QApplication` the icon registers with the Plasma
  `StatusNotifierWatcher` (its own bus connection's unique name, e.g.
  `:1.2236/StatusNotifierItem`) and shows up in the panel.
- The QML menu (`popupType: Popup.Window`) opened fine while the main
  window is **hidden**, and closing it did **not** emit
  `lastWindowClosed` (its window is transient on the shell), so the
  close-to-tray flow could not quit the app by opening the menu. It was
  still useless: the Plasma SNI host never delivers `activated(Context)`
  without a `setContextMenu` menu, so it could not be opened from the
  tray at all (see the resolved open item below).
- A native `QMenu` skips invisible actions outright, so the conditional
  entries (recents separators, Global Defaults) are simply left out —
  no blank-row collapse needed as in QQC2.
- Recents and Global Defaults are rebuilt on `aboutToShow`, the same
  freshness the QML menu had; the host positions the menu under the icon
  itself, so the `geometry()`/`QCursor.pos()` → model signal → `popup()`
  plumbing is gone.
- Translation tooling: `pylupdate6` is not installed here, and system
  `lupdate6` reads Python natively but writes `{expr}` placeholders
  where the retired tool wrote `{}`. The native menu reintroduced one
  Python-translatable spot (`gui/tray.py`, `TrayMenu` context), which
  lupdate extracts cleanly (the labels are plain strings), so the refresh
  script feeds it alongside the QML set.

Resolved (2026-10-16, real display): the QML menu never opened from the
tray — the Plasma SNI host shows only a `setContextMenu` menu and never
delivers `activated(Context)` without one — so the context menu is now a
native `QMenu` in `gui/tray.py`. Position, keyboard focus and
click-outside dismissal are the host's.

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

- Tray menu popup: right-click must deliver `activated(Context)` on the
  KStatusNotifierItem path (left click is already wired through
  `Trigger`); position under the icon (the SNI reports no geometry, so
  it comes from `QCursor.pos()`), keyboard focus, click-outside
  dismissal, the non-native QQC2 look, and whether the compositor
  accepts a transient popup of a hidden shell window at all (offscreen
  it does; fallback is a `Window { flags: Qt.Popup }` menu with
  hand-built rows). The icon itself registers in the Plasma
  `StatusNotifierWatcher` (measured).
- Settings window: FormCard rows side by side (the widgets QFormLayout
  put label and field on one line) and the Environment / Pre-Post tabs.
- Table: the added columns (Source, Category, ...) and the header
  drag / resize / autofit gestures.
- Category and Artwork dialogs, and the pt_BR catalog in situ.
- Audio sink picker (left untouched on this branch).
