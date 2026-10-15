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
- [x] System tray with recent games (`QApplication` migration done;
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
- [x] QSystemTrayIcon → migrated to QApplication (tray controller
  with recents)

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
