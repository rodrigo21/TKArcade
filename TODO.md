# TODO — deferred ideas

- [ ] Kirigami game settings (deferred while the rest lands): port
  GameDialog to QML — real Edit/Clone/Reset/Global Defaults, Steam
  add flow with picker, AddSource chooser. Until then Edit opens the
  local name+executable dialog as a stand-in.
- [ ] Kirigami File Export/Import (tarball, SteamTinkerLaunch,
  predecessor copy). Scan Steam Library already exists.
- [ ] System tray with recent games (needs QGuiApplication to
  QApplication migration; tray prefs already exist).
- [ ] Column drag-reorder in the QML header (the Move left/right
  menu covers reordering; drag is fragile in QML layouts).
- [ ] QML i18n catalog (pt_BR for the strings added since the
  Kirigami work started; QML `qsTr` calls are in place).

- [ ] Per-game display mode: save current resolution/refresh, apply the
  game's, restore afterwards (same save/restore pattern as nightlight).
  Providers with auto-detect: Plasma (`kscreen-doctor`), GNOME
  (`org.gnome.Mutter.DisplayConfig` over D-Bus), wlroots
  (`wlr-randr`/`kanshi`), X11 (`xrandr`), `off`.
- [ ] Per-game audio output: route to a chosen sink via `pactl`/`pw-cli`
  on launch, restore on exit.
- [ ] Review env presets against vendor docs (Mesa/NVIDIA semantics drift;
  verify `vblank_mode` / `__GL_SYNC_TO_VBLANK` values). Recurring: re-audit
  on every release tag (last: 2026-09-30 + installed-build checks).
- [ ] Block Internet per game (net namespace, unprivileged). DEFERRED for
  now: not cheap enough (LAN/achievements/Proton-under-userns risk matrix).
  Lighter alternative already shipped: `WINE_BLOCK_HOSTS` preset.
- [ ] vkBasalt successor: vkBasalt is unmaintained; evaluate forks or
  ReShade-on-Linux successors when mature (out for now).
- [ ] FPS cap field (MangoHud `fps_limit`) + libstrangle wrapper option for
  DX12 titles without overlay (`DXVK_FRAME_RATE` preset covers DX9-11 only).
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
Status: list/icons/cards views, drawer modes, toolbar Play/Add/Edit/Remove,
game context menu, Tools menu, prefs/about/history/scan dialogs,
issues-only filter, geometry + column prefs, movable columns — all pushed
to `kirigami` (see git log).

### Equivalence map (audit 2026-10-07)
- [x] QMainWindow → ApplicationWindow
- [x] QListWidget sources → GlobalDrawer actions
- [x] QMenu/QToolBar → Action + menus, centered toolbar row, per-row
  Play removed (play via double-click, toolbar or menu)
- [x] QDialog+ButtonBox → Kirigami.Dialog
- [x] QComboBox/Spin/Slider/Check/LineEdit → QQC2 direct
- [x] QTableWidget+QHeaderView → Addons ListTableView (+ kirigami-addons
  dep, landed with the import; keep game* roles via textRole,
  sort through existing sortBy, selectionModel replaces selectedIds).
  Use ListTableView, never KTableView (its inner TableView spins the
  offscreen event loop forever).
- [x] QShortcut Quit → QML Shortcut (Ctrl+Q)
- [ ] QMessageBox → Kirigami.PromptDialog (base kirigami, revise our confirms)
- [ ] QFormLayout (prefs) → Addons FormCard (same new dep, zero extra cost)
- [ ] QTabWidget (future settings UI) → pageStack pages + TabBar
- [ ] QFileDialog/QInputDialog → portal picker / Dialog+ComboBox (with config UI)
- [ ] QSystemTrayIcon → needs QApplication migration (deferred)

### Drawer (after tableview)
- [ ] Drawer Mode… into GlobalDrawer `footer:` (bottom, space reserved above)
- [ ] Persist mode (modal/collapsible/collapsed) in prefs, restore on start
- [ ] Test close→reopen keeps mode (nothing in Kirigami resets `modal`)

### Qt 6.11 QML landmines (AGENTS.md has the full list)
- Repeater models must stay JS arrays (QVariantList from setProperty
  lays out at zero width); test via moveColumn(), never setProperty.
- QEventPoint has no modifiers → MouseArea for Ctrl/Shift rows.
- Tests: structure-aware lookup only (rowColumn objectNames + parent
  modelData match); pump frames until delegates settle; XDG_CACHE_HOME
  already isolated per test, do NOT disable disk cache (breaks layout).
