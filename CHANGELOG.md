# Changelog

All notable changes to TKArcade are documented here.
Breaking config changes are called out explicitly under `Changed`.

## [Unreleased]

### Changed
- **BREAKING**: a local game's WINEPREFIX is always a subfolder now.
  `[runtime] prefix` (and the Preferences prefix base) is the **base**;
  the prefix itself is `<base>/<folder>`, where the folder is
  `[runtime] prefix_name`, else the game name normalised (`TK's
  good-game_1` → `TKsGoodGame1`: apostrophes dropped, other punctuation
  splits words, each word capitalised), else the AppID. The GUI pins the
  derived name into `prefix_name` on save, so renaming a game never moves
  the prefix; the `Wine Prefix` field is the base. On the next launch a
  prefix still sitting at the base is moved into the subfolder (a target
  with files in it blocks the launch instead of being merged). Steam's
  compatdata dir is untouched.
- Graphics (DXVK/vkd3d) is a Wine-only setting: `umu` and Steam's Proton
  already ship both, so the section is hidden for them and `[graphics]`
  is ignored (an existing install is neutralised at launch). `--validate`
  no longer reports missing layer versions for those environments.

### Fixed
- Play on a local game no longer launches whatever `tkarcade` sits on
  `PATH`: the child runs the interpreter that owns the GUI, so a branch
  opened from the venv plays the branch. Before, a system package built
  from another branch ran instead and could refuse the launch (exit 18,
  "game type not set") while the GUI in front was new. The Steam
  launch-options row now names the `tkarcade` Steam resolves (with its
  version) and warns when it is another build or missing from `PATH`.
- Prefix hint: a typed Prefix Dir is the WINEPREFIX itself and it wins
  over the friendly name, so the hint reports that path instead of the
  subdirectory under the prefix base it used to promise. The local field
  is labelled `WINEPREFIX:` (tooltip with the semantics) and `Open`/
  `Clear…` now work for local games with a dir.
- The interactive winetricks/protontricks window keeps its output in
  `$XDG_STATE_HOME/tkarcade/games/<appid>-winetricks.log` and a non-zero
  exit is reported in the dialog with that path; protontricks also
  refuses earlier when the game has no compatdata prefix (it needs the
  game installed and launched once, which used to fail silently).

### Added
- Winetricks UI in Settings → Runtime → Prefix: `Add…` opens a
  searchable `winetricks list-all` picker (parsed once per process) that
  appends verbs to the field the launcher already runs, and the section
  lists what the prefix holds from its own `winetricks.log`, apart from
  the verbs the field only installs at the next launch. `Protontricks…`
  (Steam) or `Winetricks…` (local games, with the resolved `WINEPREFIX`
  and `WINE`) opens the interactive tool in its own window and refreshes
  the list when it exits; a missing binary, an uncreated prefix and a
  Steam game with a custom `[runtime] prefix` (protontricks cannot
  target it) are refused with a message instead of opening the wrong
  prefix. The wrapped prefix hint no longer widens the form past the
  frame: at the 612 px minimum the Prefix buttons were unreachable.
- `TKARCADE_OPEN=<surface>` opens one GUI dialog at launch (`settings`,
  `settings:<appid>`, `artwork:<appid>`, `defaults`, `add`, `category`,
  `prefs`, `about`), and `scripts/display-check.sh` launches the shell
  against a throwaway profile with three seeded games. Together they are
  the runbook in `docs/plans/real-display-checks.md` for the checks
  offscreen tests cannot verdict. Nothing changes without the variable.
- Block Internet per game (Settings, "Network" section): the game runs
  in an unprivileged network namespace (`unshare -Urn`), so it has no
  route, DNS or interface except loopback. Multiplayer, achievements,
  online services and anything else that needs the network stop working,
  which is the point. The wrapper is applied innermost: pre/post hooks
  and the Ludusavi cloud restore/backup keep their own network. When the
  kernel or a sandbox forbids unprivileged user namespaces, the launcher
  refuses to start the game (exit 14) instead of silently going online,
  and `--validate` reports it. Known caveats (Proton and anti-cheat
  behaviour) are in `docs/plans/network-isolation.md`.
- Running indicator and Terminate action in the GUI: the launcher
  records the game it is playing under
  `$XDG_STATE_HOME/tkarcade/running/` and removes the record on exit, so
  every launch path (GUI, tray, Steam's launch options) shows the game
  as running in the table, icons and cards views. `Terminate` in the
  game context menu (and on the card) sends SIGTERM to the launcher,
  which forwards it to the game's process group — wrappers such as
  `gamemoderun`, `gamescope` and `ludusavi wrap` included — and then
  restores the display, audio and nightlight sessions on the way out;
  a launcher that ignores the signal is SIGKILLed with its group after
  ten seconds. Stale records left by a crashed launcher are swept at the
  next launch or by the GUI.
- Add game flow: the Add dialog keeps its two sources (Steam Game,
  Local Game) and, for local games, a Game Type combo (Linux native,
  Windows Wine, Windows Proton via UMU) that preselects the same field
  in Settings. The type stays editable there afterwards.
- Settings warns when the configured executable ends in `.exe`/`.bat`/
  `.msi` but the game type is Linux (native), and offers a one-click
  switch to Wine (local games) or Proton (Steam games). The hint does
  not block saving.
- Friendly prefix names for local Windows games: `[runtime] prefix_name`
  puts the prefix under the prefix base as a readable directory instead
  of the game id (`prefix_dir` still wins when set). Settings offers a
  name field, a hint with the resolved directory and a picker of the
  existing Wine prefixes under the base; sharing a prefix between games
  stays possible and is reported there. Renaming only changes the config
  — nothing on disk is moved.
- Settings Compatibility for local games: a Windows runtime section
  (Wine binary or one of the discovered umu Proton installs, prefix dir
  with the Preferences default as placeholder, graphics layer) and a
  "Remove from prefix" button that deletes only the files the graphics
  marker records.
- Graphics layers for local Windows games: DXVK, vkd3d-proton or Wine's
  builtin vkd3d per game. At launch the newest version found in the
  configured directories is copied into the prefix and selected with
  `WINEDLLOVERRIDES`; a marker file records exactly what was copied, so
  removal (GUI button or `uninstall`) never touches other files, and
  switching layers does not delete anything. Missing versions warn and
  fall back to the builtin DLLs instead of blocking the launch.
- Local Windows games: the explicit game type now includes Wine (system
  `wine` or a configured binary) and Proton through `umu-run`. Both use
  `WINEPREFIX` under the configurable prefix base (per-game override
  wins) and never borrow Steam's Proton runtime; `umu` also needs a
  chosen Proton install (`PROTONPATH`). Missing pieces fail with exit 14
  (or 13 when no executable is configured) instead of a broken launch.
- Winetricks for local Windows games: `[runtime] winetricks_verbs` runs
  the host `winetricks` against the game prefix before launch, with
  `WINE` set to the chosen Wine binary or, for umu, the selected
  Proton's `files/bin/wine`. The prefix must exist (launch once first);
  the recorded prefix+verbs skip the rerun, and failures only warn.
- Pre-launch menu (widgets parity): landscape artwork with a play-icon
  fallback, the "name (appid)" header and the "Proton: <tool>" line.
- Settings General (widgets parity): the Game name field shows the Steam
  name read-only for Steam ids (it used to appear only for local games),
  a read-only Detected Runtime row reports the Proton tool/version, and
  the Game type row moves into the widgets field order.
- Session history (widgets parity): bold header row (Game, Last played,
  Sessions, Total time, Failures), per-game Sessions/Failures columns,
  and a confirmed "Clear History..." bulk action in the footer.
- Toolbar icon fallback: the columns button (and later buttons) pick
  the first name the theme ships (`iconName` slot) — `view-column`
  exists only in some themes, `table` in others.
- Theme-proof icons: runtime chains everywhere (`view-column` →
  `view-split-left-right` → `configure`; gamepad → `applications-games`;
  hamburger → `application-menu`) plus our own hicolor fallbacks for
  `view-column`/`overflow-menu` shipped by the package.
- Per-game settings as a modal window (point 1, widgets parity): a
  separate resizable `Window` (`WindowModal`, transient on the main
  window) with the centered capped scrolling form; the pageStack
  experiment is reverted (tiled wrong on a real display). Model
  load/save/profile slots and the profile-name prompt stay as landed.
- Settings gains Environment and Pre/Post Commands tabs (env table
  with add/remove, shell-quoted args fields).
- Scan, history and preferences as modal windows (point 2, widgets
  parity): separate resizable `Window`s (`WindowModal`, transient on
  the main window) with `open()` keeping the old call sites; the scan
  list scrolls. Confirms/about/utilities stay small dialogs.
- Settings Performance tab (System group with the mutually exclusive
  GameMode pair).
- Settings Display tab (Display Mode with Refresh + dip rule, Gamescope
  with presets, MangoHud with config combo + New flow, RT Upscaler).
- Settings Ludusavi tab (enable/restore/backup/override/prompts +
  threaded coverage check) and System tab (Notifications, Idle
  Suspend, Night Light groups); General gains the log file row.
- Settings Wine / Proton tab (fresh prefix, winetricks verbs, Proton
  log + Open, Wine Debug combo; off for native local games).
- Settings Reset (factory fields, saved on Save) and Global Defaults
  window (same tabs over the template); tray gains its Defaults entry.
- AddSource chooser (Steam game picker opens settings for the AppID,
  Local opens blank); save creates missing Steam configs.
- Clone Settings To... (game picker + overwrite confirm) and Reset to
  Global Defaults in bulk (confirm), in the game menu.
- Env Bulk Edit (KEY=value text) and Add Preset (chooser with driver/
  Proton tags, mismatch confirm, merge-missing).
- Settings show config load warnings and disable tool toggles whose
  binaries are missing (gamemoderun, gamescope, mangohud, ludusavi).
- Launch command preview (collapsible, Refresh, wrapper line) and Diff
  vs Defaults for the live dialog state; the settings window defaults
  taller so tab controls stay above the fold.
- Dependency Status box (widgets parity): the draft's custom prefix,
  executable/hook paths and tool/Steam launch-options checks as two
  columns of ✓/⚠/● lines, in the widgets' nested panel below the tabs,
  with the same wording and an "Open folder" link for broken paths.
  Refreshed with the preview; only opening the dialog scans the Steam
  userdata.
- Settings Display tab (widgets parity): the Display Mode, Gamescope,
  MangoHud and RT Upscaler groups draw as centered framed sections
  again, their checkboxes sit in the field column, and the Gamescope/
  Upscaler option rows gained the widgets' labels.
- Settings forms fill their panel: a `WidgetsFormLayout` sizes the label
  column to its labels and hands the rest to the field column, so fields
  reach the panel edge instead of a compact form centered with a hole
  left of the labels.
- Settings Performance/System/Ludusavi/Wine tabs (widgets parity): the
  groups draw as centered framed sections like Display's, every form
  fills the tab (the General tab lost its centered width cap), and the
  Ludusavi tab becomes a widgets form — checkboxes indented into the
  field column, "Game Name Override:"/"Coverage:" right-aligned labels
  and the prompts note in a spanning row.
- Settings Environment tab (widgets parity): a bold Variable/Value
  header row over the field columns and the widgets' Add/Remove pair —
  Remove drops the row whose field last took focus (the table selection
  it replaces); the per-row remove buttons stay.
- Settings window title and footer (widgets parity): the title names the
  game (`Game Settings — <name> (<appid>)`, `Game Settings (<appid>)`
  when unnamed) and the button box matches the widgets' — Diff vs
  Defaults and Reset to Global Defaults lead, Save (default, save icon)
  and Cancel close the row on the right.
- Dialogs (widgets parity): About looks like the widgets'
  `QMessageBox.about` (information icon, text beside it, window sized to
  the content, one right-aligned OK), Preferences becomes a widgets
  QFormLayout (right-aligned label column, checkboxes indented in the
  field column, form-sized window, widgets tooltips; the
  kirigami-addons FormCard is gone) and every dialog button row
  right-aligns Save/OK/Add Selected as the default button (Add, Scan,
  Import, Pre-launch, Category, Columns, editor picker, the settings
  prompts and the profile bulk edit).
- Profile semantics (widgets parity): Save writes to the active profile
  target (live file keeps only the selection), dirty profile switches
  ask to discard first, Save As/Clone/Delete confirm overwrites, Reset
  confirms then persists factory now.
- General tab pilot on Kirigami.FormLayout: side-by-side aligned labels
  when wide (QFormLayout parity), stacked labels when narrow.
- pt_BR catalog complete (719 strings, QML + Python): translator install
  in the Kirigami app, language picker in Preferences (restart to apply).
- Library phase: categories/tags (settings field, drawer filter, bulk
  set, Category column), Lutris-parity columns (Last Played, Platform,
  Runner, Wine, Install Dir), manual artwork (icon/cover/banner +
  Steam donor fallback in the table), per-game Wine prefix
  (point/create/clear) and compat-tool selector, launch args/cwd
  overrides, MangoHud FPS limit (libstrangle fallback), per-game
  audio sink with restore on exit.
- FormLayout across settings: Pre/Post fully, Display Mode and MangoHud
  groups, Wine fully; tables/checks-only groups and single-pair tabs
  stay stacked (a label column would orphan their checkboxes).
- File Export/Import (step 4): portal save picker, Export/Import menu
  entries, one modal Import window (tarball / STL checklist /
  predecessor copy). Lutris/Playnite/Faugus formats stay for the
  library phase.
- Confirms as PromptDialog (step 5): remove/cleanup/shader/history
  (Warning) and validate (Information, issues as subtitle); actions
  keep objectNames and fire via trigger(), cleanup keeps its checklist
  as mainItem.
- Column drag-reorder (step 7): title drag past a threshold drops the
  column in view order (step-swaps, persisted); taps still sort
  (TapHandler folded into the same gesture).
- About as a modal window too; Ctrl+Q always quits for real
  (Close-to-tray never blocks it, widgets parity): explicit sequence
  at application scope, `Keys.onPressed` on every window root, and a
  window-scoped Python filter — plus Kirigami's built-in Quit action
  (which calls close() instead) cleared of the sequence.
- System tray with recent games (step 6): `QApplication` migration,
  native context menu in the tray controller (Show/Hide, recents via
  Play, Preferences, About, Quit), close/minimize-to-tray in the shell;
  Global Defaults entry returns with the defaults UI.
- Drawer collapsed state persists: closing open reopens open (was
  always forced collapsed); dead mode-switch helper removed.
- Header bottom line spans the full width like the foot rule.
- Rule closing the table above the status line (same 1px/0.18
  hairline family).
- Drawer header without the collapse button: gamepad icon toggles,
  centered Library (balanced spacer), Kirigami built-in close row
  off, footer buttons centered.
- Gamepad icon (`input-gamepad`) for icon-less games and the drawer
  handle: `applications-games` renders as card suits in some themes.
- Drawer mode switch in the drawer footer as icon buttons (reachable
  when the toolbar overflows; hidden with a collapsed drawer); tiny
  pages collapse the title spacers so the icons never hide.
- Header separator double-click autofits the column to its contents
  (measured on the model, persisted per column, survives restarts);
  fresh profiles and resets start fitted capped at 300px instead of
  the old fixed widths. Header cells tile manually so fitted widths
  apply live.
  Separators also drag-resize (live preview, persists on release),
  the fit counts the sort glyph and the game icon, and the game
  column absorbs leftover width so fitted tables still fill up. A
  horizontal bar rescues columns dragged past the edge, with the
  header row following the scroll. Narrow windows shrink fitted
  columns to fit (24px floors) instead of overflowing. Divider
  gestures never sort, and
  the release after a double-click no longer re-applies the drag
  width over the fresh autofit.
- `--edit` and the pre-launch `--menu` are wired to the QML settings
  window: the launcher spawns `python -m tkarcade.gui.edit` with a
  sanitized environment (`clean_gui_env`) and reads one JSON line
  (`{"outcome", "appid"}`) — exit 2 means "no PySide6/display", any
  crash reads as cancelled (never launch on unknown intent). The child
  loads a small `Editor.qml` host that shows the settings window (with
  Launch and Save & Launch when a game command exists, `--pick` listing
  configured + Steam + local games) or the `PrelaunchMenu` (Launch /
  Settings… / Cancel, `menu_timeout` countdown stopped — not resumed —
  when Settings… opens, exactly like the widgets `MenuDialog`).
- `--menu` accepts a positional AppID like `--edit` (`tkarcade --menu
  588950`), and both take a configured local game id too (`tkarcade
  --edit local-glxgears`): a lone positional naming a game — Steam
  digits or a configured id — is read as the AppID, never as a command.
  Before, a local id fell through to the picker (and `--menu` opened an
  empty pre-launch menu), because only all-digit tokens were peeled.
- Single GUI instance: the shell listens on a per-user local socket
  (`$TMPDIR/tkarcade-gui-<uid>`, QtNetwork, no new dependency) and a
  second launch pings it and exits 0; the primary comes back from the
  tray (clears minimized, shows, raises, activates). A socket left
  behind by a crash is removed and reclaimed.
- Developer setup: `scripts/bootstrap.sh` recreates the venv (system
  site packages), the editable install and the commit hook on a fresh
  clone, writing only inside the working tree. `.opencode-model` is
  versioned now, so `AI-Model:` trailers match on every machine.

### Changed
- **BREAKING**: `[artwork] donor_appid` is now
  `[artwork] artwork_appid`, the Steam AppID whose art a game uses (it
  does not have to be installed): a local game can borrow a Steam game's
  images. The field is renamed "Artwork Source AppID", and the art is
  resolved per kind (icon, cover, banner) through the manual slot, the
  cache, Steam's own cache and the source AppID's.
- Artwork is now fetched from Steam first: the official assets (client
  icon, `library_600x900` capsule, `library_hero`) come from Steam's
  public CDN and need no key. A multi-size client icon is unwrapped to
  its 256x256 PNG, since Qt reads the 16x16 frame otherwise. SteamGridDB
  is the community fallback and still needs a key; a new Preferences
  setting, "Artwork Source" (`[ui] artwork_source`, `steam` by default),
  lets a fetch try SteamGridDB first and use the official art only for
  what the community has no entry for. `Fetch Artwork` in the
  Artwork/Notes tab re-downloads the three kinds (so a provider change
  takes effect) and the Status row names the provider — "Official Steam
  Artwork" or "SteamGridDB Artwork" — while the art's copy lives in a
  sidecar. The background fetch covers games whose source AppID is set.
  "Find…" filters by the AppID or name already typed in the field.
- "Clear…" (Artwork/Notes) removes the artwork downloaded for the
  Artwork Source AppID — the cache belongs to that AppID, so every game
  pointing there falls back together — and marks it, so the background
  fetch stops filling it back until `Fetch Artwork` is pressed again.
  Manual picks are untouched.
- **BREAKING**: the per-game runtime settings live in one `[runtime]`
  section. `[runtime] prefix` replaces `[proton] wine_prefix` (Steam
  compatdata dir) and `[runtime] prefix_dir` (local `WINEPREFIX`), and
  `[runtime] tool` replaces `[proton] wine_version` (Steam compat tool),
  `[runtime] wine_binary` and `[runtime] proton_path`: the key means
  whatever `[general] environment` needs (compatdata dir vs full prefix;
  compat tool vs Wine binary vs `PROTONPATH`). `[proton]` disappears and
  `winetricks_verbs`/`fresh_prefix` move to `[runtime]`. There is no
  migration shim (pre-1.0): old files keep the stale keys as ignored
  unknown entries (nothing reads them) and the moved settings must be
  re-picked in Settings.
- The game dialog drops the Launch and Compatibility tabs: Game and
  Launch merge on General, the pre/post commands move next to the env
  vars on Environment, and the new Runtime tab holds the environment
  selector, the tool, the prefix, winetricks verbs, the graphics layers
  and the Proton debug switches. System now lists Night Light before
  Network, and the executable row reads "Game Executable:" for local
  games and "Custom Executable (Override):" for Steam games. The other
  tabs keep their names.
- Local AppIDs get a proper slug. Runs of non-alphanumerics collapse into
  one dash and apostrophes are elided, so `Bad Hero - Episode 1` becomes
  `local-bad-hero-episode-1` instead of `local-bad-hero---episode-1`, and
  `Hero's Rhapsody -_- Jianghu Dream` becomes
  `local-heros-rhapsody-jianghu-dream`. Accents are folded to ASCII
  (`Pokémon Café` → `local-pokemon-cafe`); a name with no ASCII letters
  left (Japanese, Cyrillic, Arabic) uses a short stable hash of the name
  (`local-1f0c3a9d`) instead of a run of underscores. IDs are still
  generated once, when the game is added, and renaming a game never
  changes its ID.
- **BREAKING**: existing local AppIDs are migrated automatically once, at
  GUI startup, and on demand with `tkarcade --migrate-ids`. The game
  config, profiles, artwork, grid images, per-game log, winetricks state
  and session-history lines move to the new ID, and `[artwork]
  donor_appid` references are repointed. Prefix directories are never
  renamed (Wine's registry holds absolute paths): the config pins the old
  directory through `[runtime] prefix_name` instead. Steam shortcuts
  created before this change still pass the old AppID in their launch
  options and must be fixed by hand; a running game keeps its old ID
  until it exits.
- Tools → Clean Profiles is now **Clean Up Leftovers**: it still deletes
  saved profiles of games that were removed, and now also their session
  log, Proton logs and session-history lines. A new optional checkbox
  deletes the Proton/Wine prefix too (off by default; Steam's
  `compatdata` is never touched, and a prefix shared with a configured
  game is kept).
- **BREAKING**: the game type is explicit. `auto` and configs without a
  `game_type` load as "not set": the settings window blocks Save until
  Steam games pick Windows (Proton) or Linux (native), and the launcher
  refuses to guess with exit 18. There is no migration shim (pre-1.0);
  existing files are kept as they are, nothing is rewritten or deleted.
  Local games now pick native, Wine or Proton via `umu-run` explicitly.
- **BREAKING**: graphics layers combine instead of picking one.
  `graphics.layer` is replaced by `graphics.dxvk` (bool) and
  `graphics.vkd3d` (`"proton"`, `"wine"` or off): DXVK covers
  D3D9/10/11 and vkd3d-proton covers D3D12, so both run in the same
  prefix, selected per API through `WINEDLLOVERRIDES`. Settings show a
  DXVK checkbox plus a D3D12 layer combo, and the status line/removal
  covers both. Configs with the old key load with every layer off (no
  migration shim, pre-1.0).
- UI wording is Title Case across the program: labels, buttons, menus,
  window and dialog titles, checkboxes, table columns and status
  messages, in English and in the pt_BR catalog. Tool names keep their
  own spelling (`wine`, `umu-run`, `winetricks`, `vkd3d-proton`,
  `MangoHud`, `DXVK`, `logind`, `compatibilitytools.d`), command-line
  flags and paths stay verbatim, and the "(s)"/"(ies)" plural markers
  stay lowercase.
- Package metadata requires `PySide6>=6.12`: Qt 6.12.0 is the first
  branch with the fixes for CVE-2026-8168 (SVG nesting DoS),
  CVE-2026-105923 (VectorImage null dereference) and CVE-2026-15037
  (QDom XML injection). Tool and AppImage installs now resolve a
  patched Qt; the Arch package already depended on 6.12.
- vkBasalt is out of scope, roadmap included, and any successor would
  be a separate project. The SteamTinkerLaunch importer therefore stops
  carrying `VKBASALT_*` variables and stops counting STL's two vkBasalt
  toggles among the ignored settings; a profile that enabled vkBasalt in
  STL imports without it (the layer was never installed by TKArcade, so
  the variables did nothing here).

### Removed
- The parked QtWidgets implementation (`src/tkarcade/widgets/` and its
  test module): the Kirigami QML shell replaced it, the launcher already
  opened the QML app, and the tray menu was the last piece to move.
  `--edit`/`--menu` are wired to the QML windows through
  `gui/edit.py` (the same subprocess protocol the widgets child used).
- The pt_BR catalog dropped the widget strings with their sources; the
  refresh script is one `lupdate6` pass (QML plus the tray menu) and
  `lrelease6`, and `-no-obsolete` prunes dead entries instead of letting
  them pile up.

### Fixed
- Header sorting now repaints the table on the first click. The proxy
  order was correct, but QtQuick's TableView did not re-request its rows
  after `QSortFilterProxyModel.sort()`, so the view stayed one order
  behind (the arrow moved, the rows did not).
- The library columns (Last Played, Platform, Runner, Wine, Install Dir,
  Category) render their values. The table delegate only had cells for
  App ID and Source, so enabled columns stayed blank; the double-click
  autofit only looked inert because those columns were already fitted.
  Install Dir and Category show the full value in a tooltip when elided.
- The Steam scan window sizes itself from the longest `name [appid]`
  instead of a fixed 40 grid units, and its list can scroll horizontally
  when the screen cap is reached; long names were clipped before.
- Preferences opens wide enough for the form (30 grid units minimum,
  34 by default); at the old 23 the placeholders and translated labels
  were cut.
- Session History has a real table header: button-set background, bold
  centred titles, vertical rules between the columns and the closing
  hairline, matching the games table. The action column is labelled
  Actions and its per-row Clear buttons show a button frame.
- Validate Game names the game in the title and drops the repeated
  AppID prefix from each issue; the CLI report is unchanged.
- The header actions (view, Columns, hamburger/Preferences) no longer
  disappear in pt_BR: once the window is wide enough to show the four
  title buttons with text, the search filter's width came from a fixed
  380px guess for them. Wider translated labels made the title row
  overrun the space Kirigami reserves, and the whole actions row went to
  the overflow menu. The cap now follows the real button widths,
  measured inside the title component; English never hit it.
- The Kirigami shell follows `preferences.language`: only the
  standalone editor installed the bundled catalog, and the shell built
  its window untranslated, so the language picker (or a seeded
  `pt_BR`) left the whole interface in English. `main()` installs the
  catalog before the engine loads, which covers the QML strings and the
  Python-side tray menu alike.
- Settings never stacks a label above its field: Kirigami's `FormLayout`
  drops to a one-column form whenever the dialog is narrower than the
  form's *natural* width, and the Launch tab's hidden `.exe` hint row
  (a wrapped sentence at its full line width) inflated that width on a
  real display, so only that tab showed labels above the fields.
  `WidgetsFormLayout` pins `wideMode`, the hint label no longer reports
  its unwrapped line as width, and a QML case checks every tab at the
  default and at the minimum width.
- View switching keeps the selected game (list → icons → cards): the
  hidden `TableView` drops its selection model's selection and clears it
  again when it comes back, and the reverse sync mirrored that empty
  selection back into the page's `selectedIds`, which the grids and the
  row highlight read. The page now owns the selection (every keyboard
  and click path writes it) and the table is a one-way mirror.
- Audio output sink picker lists the `pactl` Description instead of the
  raw node name (`alsa_output.pci-…analog-stereo`): `list_sinks` parsed
  only `pactl list short sinks` and returned `(name, name)`, so the
  promised description was a dead end — `audioSinks` re-duplicated it and
  the combo read the first column. The long form is parsed now (a sink
  without a Description falls back to its name) and the config keeps
  storing the node name the launcher needs.
- Settings tabs scroll again: `ScrollView` takes its scrollable size
  from the content's implicit size, so the tab wrappers (an explicit
  `height:` only) left `contentHeight` at -1 and everything below the
  fold was unreachable in short windows — Display, General and the
  other tabs now show a scroll bar and reach their last fields. Same
  fix in the Preferences form and the import dialog's STL list.
- Middle-click on a game opens its settings in all three views (table
  rows, icons grid, cards), matching the widgets event filter; the QML
  gesture layer only accepted the left and right buttons.
- Preferences (widgets parity): the SteamGridDB key row sits inside the
  form card, indented like the delegates and ordered before the Language
  picker, and the window opens at a height that fits the form instead of
  leaving an empty third.
- Empty library state (widgets parity): the middle button is `Import...`
  (the Steam scan stays in the menu, like the widgets Tools entry), the
  hint walks the three setup steps, and no table header floats over the
  placeholder.
- Settings footer and wrapper summary (widgets parity finish):
  `Reset to Global Defaults` moves from the profile row to the footer,
  and the wrapper summary reads "Will launch with: …" and sits above the
  buttons instead of below them. The summary no longer advertises a
  wrapper the command builder skips: the preview ran before the
  missing-binary pass unchecked the toggle, so a stored `gamemoderun`
  could appear in the "will launch with" line while the preview warned it
  was skipped.
- `--edit` and `--menu` opened nothing and hung until Ctrl+C: the editor
  child (`gui/edit.py`) set up `Editor.qml` and jumped straight into
  `app.exec()` without calling the host's `start()`, which is what creates
  the settings/picker/pre-launch window. The offscreen QML harness called
  `start()` itself, so the suite stayed green while the real CLI flows
  froze.
- The tray icon's right-click menu never opened: on Plasma the SNI host
  only shows a context menu the app exports through `setContextMenu()`
  and never delivers `activated(Context)` without one, so the QML menu
  could not be reached from the tray. The menu is now a native `QMenu`
  built in `gui/tray.py` (same entries, recents and Global Defaults
  rebuilt on every open).
- The tray menu labels are translated again: the retired QML menu used
  `qsTr()`, so the native `QMenu` left the pt_BR menu English-only with
  five orphaned `main` entries in the catalog. They now go through a
  `TrayMenu` Python context, covered by `tests/test_i18n.py`.
- Steam library scan reads the legacy `libraryfolders.vdf` layout too
  (capitalized root key, bare `"1" "/path"` strings): secondary
  libraries no longer vanish on old Steam installs, with or without
  the `vdf` package.
- Removed dead imports: `logging` in the Kirigami tray controller,
  `urllib.error` in the artwork and ProtonDB helpers.
- Config: cloning a game rewrites the destination snapshot with the
  destination AppID (live config and profiles); prefs cleaners drop
  non-decimal "digits" instead of crashing `int()`; pre/post hook
  timeout clamps to 1–3600s on load (same as the save path).
- Library model: the "Steam detected" count no longer includes local
  games, cached validation issues are dropped on every refresh, and
  saving Preferences propagates the tray state (close/minimize-to-tray
  take effect without a restart).
- Launcher launch path: the game config is parsed once (the refresh
  re-parse only runs after `--edit`/`--menu` may have saved), repeat
  `setup_logging()` calls no longer stack a second file handler on the
  same `<appid>.log`, and a non-executable game binary returns the
  contract exit 13 (log + notification) instead of a traceback.
- Library: resized column widths persist for every column. The prefs
  cleaner only accepted logical columns 0–5, so widths set on Last
  Played, Platform, Runner, Wine, Install Dir and Category were written
  and then silently dropped on the next load.
- Library header: the table header used its own static defaults (90px
  for the Last Played/Platform/Runner/Wine/Install Dir/Category
  columns) while the table rendered 80px, so every unfitted one of
  those columns shifted its title and divider 10px off. Header,
  delegate and `columnWidthProvider` now read a single
  `defaultColumnWidth` helper.
- Library footer: the shown count also appears while the drawer's
  Category filter is active (it already did for search, issues-only
  and source, so the list looked unfiltered).
- Cards view: the right-click game menu and click-to-select never
  worked. `Kirigami.Card.clicked()` carries no mouse event, so the
  right-click branch was dead and the left-click branch threw
  (`mouse` undefined); the menu now runs through a `MouseArea` that
  claims only right-clicks and Ctrl/Shift clicks, so plain presses
  still reach the card and the Play action. Ctrl/Shift multi-select
  now works in the cards view like in the list and icons views.
- Removed residual dead code and stale notes: duplicated portal debug
  line, unreachable `launch_args` exception handler (`split_args` never
  raises), redundant artwork cleanup loop, and the nightlight holder /
  STL importer comments that no longer matched the code.
- Preferences dialog uses FormCard delegates (native settings look);
  the API key row stays plain (FormTextFieldDelegate needs a
  KLocalizedContext the engine does not install).
- Header toolbar split in three zones: buttons + centered filter live
  in the title row (plain RowLayout honors fill), view icons stay in
  the actions row pinned right at any window width. Narrow windows
  show icon-only buttons; the filter clamps to 600–1200px and the
  icons never hide or overflow into a menu.
- Narrow toolbar fits without hiding the icon row (honest minimum
  width, slimmer filter fraction); the toolbar test now asserts the
  right-aligned order instead of the retired centering. The geometry
  dump still identifies each row item by class, and the icon dump
  reports rendered sizes plus null pixmaps.
- Geometry dump also logs the toolbar row (bar widths, visible
  delegates, hidden count) and the icon theme lookup, for real-display
  diagnosis in one run.
- Columns button back to `view-column`: the supra-theme audit proved
  wrong (the chain here ships it, not `table`); toolbar icon names are
  theme-relative, so no local audit test.
- Toolbar popups open deferred past the release click, which dismissed
  them instantly on a real display.
- Columns button uses the `table` icon: `view-column` ships in no icon
  theme and rendered an empty button; a test audits every toolbar icon
  against the Breeze actions set.
- Window minimum forced to 1280x720 so the toolbar never crowds into
  the overflow chaos on small windows.
- Header grid line starts past the gutter and stops at the vertical
  encounter (that segment does not exist in TKS); footer line kept.
- Header toolbar: action row right-pins the corner icons; the filter
  fills buttons-to-icons and grows proportionally; no header title and
  no balancing dead weight, so no blank corner anywhere.
- Gutter back strip runs the full table height behind rows and empty
  area, so the framed number column stays complete with zero games.
- Gutter header has no "#" title and no divider stub into the game
  column (TKS has no gutter column); the divider is a sibling overlay
  above delegates and highlight, spanning rows and empty area.
- Grid lines in the original divider style: full-width line under the
  header row plus the gutter divider running the whole table height
  (rows and empty area, never scrolls).
- Drawer header is a plain Item so the drawer-edge separator runs full
  height and meets the header lines (a ToolBar header makes Kirigami
  inset it around the header zone); status text steps right off the
  divider tip.
- Table frame hugs the list flush with rounded corners (TKS look); no
  margins, so its top edge never reads as a second header separator.
- Drawer Library bar shares the Kirigami global toolbar height, so its
  separator meets the Games header line; header heights locked by test.
- Header titles are centered TKS-style with a small ▲/▼ mark overlaid
  at the right edge, vertically centered.
- View button is icon-only like Dolphin (icons per mode plus
  Ctrl+1/2/3); menu button uses the existing overflow-menu icon;
  geometry dump behind TKARCADE_DEBUG_GEOMETRY=1.
- Header strip shares the body x origin (stray outer margins had
  shifted every title and divider away from its column); header
  geometry locked by test.
- Number gutter frames rows like the widgets vertical header
  (Button set, follows selection highlight).
- Selected rows paint highlightColor behind highlightedTextColor
  text (tier badge joins the highlight); selection state lives on
  the delegate via selectedIds, no row index involved.
- Row clicks pass the page explicitly (QML ids are file-scoped, so
  the bare `gamesPage` reference inside RowClickHandler.qml resolved
  to nothing and every click died silent: no selection, no
  highlight, no multi-select).
- List view migrated from Addons ListTableView to plain QtQuick
  TableView with a custom Button-set header bar (full-bleed
  background, centered bold titles, sort indicators, tap-to-sort
  and right-click column menu). The proxy is now a real 6-column
  table model with order/visibility mapping, so icons and cells
  always track their rows through sorts.
- Header actions (Play/Add/Edit/Remove, search, views, columns,
  hamburger) live in the window header like plasma-systemmonitor,
  buttons centered with symmetric spacers.
- Header bar borrows the toolbar background (full-bleed Button
  set, bold titles) and the table sits flush under the window
  toolbar, like plasma-systemmonitor. The delegate carries its
  own implicit size (zero-size collapse hid text and background).
- Hamburger menu no longer overlaps (popup at cursor); header
  titles use the toolbar Button set, semibold off; selected rows
  use highlighted text; icons and tooltips track rows through sorts.
- Invented row dividers removed again; alternating tint stays off.
- Kirigami count properties live on the QMetaObject (drawer and
  status counts rendered `undefined` before); Steam play validates
  the AppID and drops the menu skip when the handoff fails.
- Reset to Global Defaults applies the user's `defaults.toml` template
  again (the built-in factory values had silently replaced it, ignoring
  a customised template); the defaults editor gains the widgets "Reset
  to Factory Defaults", in memory only so Cancel still discards it.
- Save and Reset over a config written by a newer TKArcade ask first
  and then really overwrite the file (the save path used to reject the
  newer-version file outright, so the accepted downgrade failed).
- Switching profiles with unsaved edits offers Save again (widgets
  Save/Discard/Cancel); the old Discard/Cancel pair could only drop the
  edits.
- Global Defaults is reachable from the hamburger menu (it was
  tray-only, so a shell without a tray could not open the editor).
- The defaults editor no longer offers Diff vs Defaults (widgets had
  that action for a game only; the editor edits the template itself).
- Escape cancels the separate dialog windows (widgets parity): a QML
  `Window` has no `QDialog` reject(), so Escape did nothing in About,
  Preferences, Scan, Import, the game settings, Add, the editor picker,
  Session History and the pre-launch menu. Each dialog now installs the
  window-scoped filter that turns Escape into the same close its Cancel
  button does (settings, picker and pre-launch keep reporting their
  cancel outcome from `onClosing`), and an open popup — a confirmation
  dialog or a combo menu — is dismissed first, in the widgets order,
  instead of the window closing behind it.
- Enter activates a dialog's default button (widgets parity): the QML
  `Window`s ignored Return, so About, Preferences, Scan, Import, Add,
  the game settings, the picker, Session History and the pre-launch
  menu could only be confirmed with the mouse. Every dialog body now
  takes the key and fires the button the widgets made default (Save,
  Save & Launch in the editor's launch mode, the current import page's
  own Import, Launch while it can launch); an open popup's accept goes
  first, and an editable TextArea keeps Return for its own newline.
- Keyboard navigation in the game list (widgets parity): the views
  never took focus, so the table's Up/Down — and the icons grid's
  arrows — were dead code, and the table had no Home/End/Page keys at
  all. The visible view now holds the focus like the widgets view did,
  the TableView's own navigation is off (it moved the current index
  behind the page's selection bookkeeping), and Home/End/PageUp/
  PageDown move the selection through the same path as a click.
- The settings dialog keeps its Launch Command Preview and Dependency
  Status live: the widgets wired every field to a rebuild, the QML
  dialog only refreshed on load, the runtime combo and its own button,
  so the box could describe a command the fields no longer built. The
  dialog now watches its own draft (the same snapshot the dirty check
  uses) and rebuilds when it moved.
- Every launch path reports itself (widgets parity): the model emitted
  nothing, so a failed Steam handoff, a launcher that could not spawn
  and a play request from the tray recents were all silent, and the
  status line never carried the widgets' "Launched X." — the model now
  emits `launchReported` and the shell shows the sticky status line or a
  transient warning. The two "Open ... folder" menu entries and the
  Dependency Status links no longer discard their `openPath` failures.
- Two widgets menu entries are back where they belong: Validate Game
  leads the Tools entries in the hamburger (it only existed in the game
  context menu, and it validates the current selection, asking for one
  like the widgets did) and the table header's right-click menu closes
  with Reset Columns, as the widgets header context menu did — only the
  columns dialog offered it before.
- The settings dialog re-reads its profile list whenever the window is
  focused again (widgets `focusInEvent`): a profile written from outside
  — the CLI, a second editor — shows up without reopening the dialog,
  and an active profile that vanished on disk is cleared.

### Added
- View switcher with per-view icons and Ctrl+1/2/3 shortcuts;
  menu button uses the vertical ellipsis.
- Single-row toolbar (title, centered actions, search, views,
  columns gear, hamburger); Tools lives in the hamburger with a
  persisted Drawer Mode section; Configure Columns dialog
  (show/hide + Up/Down) plus header right-click.
- List is a native table (Addons ListTableView): real header with
  relief, centered titles and sort indicator, row selection with
  highlight, gutter numbers; needs kirigami-addons at runtime.
- Movable data columns (Move left/right menu, Reset Columns) with
  order and visibility persisted to prefs; Game stays first.
- Tools menu (Scan Steam Library, History viewer, Ludusavi, Logs,
  Clean Profiles, Reload, Preferences, About, Quit), issues-only
  filter, shown count in the footer, 3-button empty state, and
  background ProtonDB/artwork refresh with an offline kill-switch.
- Drawer options below a separator (sources stay on top) and
  window geometry: 1280x720 default, last size/maximized restored
  and persisted debounced.
- Multi-selection (Ctrl toggles, Shift extends, single tap resets)
  with toolbar Play/Add/Edit/Remove, per-game context menu (copies,
  install/prefix folders, shader cache, ProtonDB, validate, clear
  history, remove with profile cleanup), footer notices.
- List matches the widgets table: plain left-aligned headers over
  the data, single-line names (no played sub-line), row numbers in
  an outside gutter, played hover tooltip, tier badge opens ProtonDB
  on double-click, `gamePlayedTip` role and `openProtonDB` slot.
- Gallery-style drawer modes (Overlay/Sidebar/Collapsible Sidebar
  with collapse header) and gallery-style views: details list,
  icons grid and cards (Kirigami CardsLayout) behind a split-button
  view switcher (button cycles, arrow opens the Zoom/Sort panel);
  uniform delegate selection overlay across views, `idAt` proxy
  slot so keyboard navigation follows the highlight.
- List view selection (tap + arrow keys + highlight), positional
  `#` column, Columns menu (App ID/Played/ProtonDB/Source driven
  by proxy flags), styled header with sort indicators.
- Main-window UI parity in Kirigami: source drawer with counts,
  search field, rich rows (name, ID · played, tier badge), status
  counts. Filtering runs through a proxy model (tested in Python).
- List view like the widgets table (Game/App ID/Played/ProtonDB/
  Source, clickable headers, per-view row height).
- Async native file picker: Browse never freezes the UI (worker
  thread + result signal); `TKARCADE_VERBOSE=1` (or `--verbose`)
  shows portal handshake debug lines.
- Native file picker: the Add dialog uses the desktop's own picker
  via xdg-desktop-portal (jeepney) instead of the Qt fallback.
- Kirigami spike (branch only): QtWidgets parked under `widgets/`
  as reference, new Kirigami list/add/launch UI in `gui/` reusing
  the stdlib core untouched; `--gui` opens it, `--edit`/`--menu`
  report unavailable until its settings UI lands.

### Added
- New application icon: arcade cabinet with TK screen and play
  triangle (monochrome outline variant for the tray).
- Double-click plays the game, middle-click opens its settings
  (ProtonDB column still opens the page).
- Centered main toolbar actions; window opens at 1280x720 and
  remembers its size across runs (floored at 640x480).
- View menu with a Main Toolbar toggle; toolbar buttons show icon
  beside text.
- `TKARCADE_NO_NOTIFY` kill-switch: the test suite sets it, so test
  runs (and PKGBUILD checks) never pop desktop notifications.
- Main window restores maximized state across runs (size kept
  separately, never overwritten while maximized).
- Dependency Status hides Steam-only entries for local games.
- Display modes load on first opening the Display tab (Refresh and
  provider/output edits still re-query).

### Fixed
- Diff vs Defaults ignores identity fields (appid, name) and the
  profile selection memory.

### Added
- Source sidebar: All/Steam/Local filter list with counts beside
  the games table (future sources appear there on their own).
- TKSteamLaunch import: one click copies games/profiles/defaults/
  preferences from the predecessor XDG dirs (missing files only,
  never overwrites) — do it early, formats still match.
- Menu bar + slim toolbar replace the Games/Tools/Application button
  rows (File/Game/Tools/Settings/Help; Play/Add/Edit/Remove up front).
  Copy Launch Options and the rest of the per-game actions live only
  in the row menu now, shown per source (no ProtonDB page for local
  games); Validate/Clone guard empty selections.
- Single Add Game entry: a source chooser (Steam / Local Linux)
  replaces the per-source buttons; room for Wine and UMU later.
- Local native Linux games: Add Local... (name + executable, unique
  `local-<slug>` ID), direct Play (detached, same logs/history/menu
  skip as Steam), Copy Launch Command, and exe-dir working directory.
  Settings show the editable name and hide Steam-only bits; clone and
  validation accept local IDs (missing custom executables flagged).
- Game identity groundwork for local (non-Steam) games: string IDs
  (`local-<slug>` alongside numeric Steam AppIDs), per-game display
  names, and a Source column (Steam/Local) in the games list.
  Steam-only lookups (ProtonDB, artwork) skip local rows.

### Changed
- Settings window: every tab now shares the same framed sections. General
  splits into Game and Profile, Environment gets an "Environment
  Variables" box that fills the tab (its Add/Bulk Edit/Add Preset/Remove
  row stays under the frame), and the Notes box is five lines tall
  instead of a half-page editor. The last tab is "Artwork/Notes": an
  ampersand in a QQC2 button text is a mnemonic, and the escaped source
  elided at the default width.
- Compatibility stays reachable for local games: the Proton box is
  hidden and the Wine fields are disabled with a note saying the
  settings apply to Steam games only, instead of a greyed-out tab button.
- Settings window: eight tabs instead of ten. The new Launch tab gathers
  the executable, prefix, extra args, working directory, pre-launch menu
  and log file, with the pre/post commands as a group of their own;
  Ludusavi becomes a "Saves" group inside System and Notes sits under
  Artwork; MangoHud and the RT upscaler join Performance; Wine/Proton
  becomes Compatibility, split into Wine and Proton groups.
- Settings footer blocks (Dependency Status, Launch Command Preview)
  start collapsed: they are reference material, and expanded they cost
  every tab a third of its height. Expanding one still persists the
  choice for the next window.
- Dialog bodies use a 12px layout margin, matching the widgets
  `QDialog`/`QMessageBox` (10px under Breeze, 11px offscreen), and each
  content-driven window height reads that margin back from its body.
- Dialog sizes follow the widgets windows (r240): About is 396 wide
  (400 there), Preferences 414 (420), the pre-launch chooser 468 (480)
  with a height that hugs its content instead of a fixed 198px box, and
  Scan (Add Games) and Import size themselves to their lists instead of
  a fixed rectangle — the STL import buttons leave the scrolling list
  for a widgets-style Select All / Select None / Import row, and the
  Import window follows the page on screen (a long STL list no longer
  stretches the backup-file page).
- Environment tab: a game without variables opens with one empty row
  already there (the widgets table always showed one to type into; an
  empty key is still dropped on save), the four buttons are centered and
  ordered Add, Bulk Edit..., Add Preset..., Remove, and every tab keeps
  a wider gap before the Dependency Status block below it.
- Settings bottom blocks: Dependency Status and Launch Command Preview
  are group boxes with a centered checkbox title now (the dependency
  list also lost its redundant second, nested frame) and unchecking
  either one collapses the whole block, giving the tabs their room
  back. Both choices persist (`[ui] show_dependency_status`, the
  preview reuses the existing `show_preview`, so the Preferences dialog
  and the dialog stay in sync).
- The tray context menu is a QML menu now, opened at the icon through
  the model; entries, recent games and Close/Minimize-to-tray behave
  as before, and `Quit` still bypasses Close-to-tray. The shell still
  builds a `QApplication`: on Plasma the tray comes from the platform
  theme as a `KStatusNotifierItem`, which creates a `QMenu` (a widget)
  in its constructor, so a `QGuiApplication` aborts the process inside
  `QSystemTrayIcon.show()`.
- TKArcade starts here as a standalone repo renamed from
  TKSteamLaunch 1.1.1 (full history preserved, new remote).
  **BREAKING**: config/state/cache now live under the `tkarcade`
  XDG directories, so no settings carry over automatically.
- Pre-0.1: `-git` is the only Arch package (normal PKGBUILD
  returns with the 0.1.0 release); third-party recipes under
  `packaging/arch/` stay in sync with TKSteamLaunch until this
  project supplants it.
- AppImage release asset now carries the version
  (`TKArcade-<version>.AppImage`).

### Changed
- **BREAKING**: `[general] game_type` is now `[general] environment`,
  with the same values (`proton`, `native`, `wine`, `umu`) and the same
  launch behaviour. The field answers "how does it run", not "what is
  it": origin (Steam/Local) and platform (Linux/Windows) are derived.
  A config with the old key loads with the environment unset, so the
  launcher refuses to launch (exit 18) until it is chosen again; the
  old key stays in the file untouched (no migration shim).
- **BREAKING**: the free `[general] platform` label is removed. The
  Platform column no longer holds a typed label such as "PC"; it shows
  the system the game is built for (`Linux` for `native`, `Windows`
  otherwise), derived from the environment. Categories cover labels
  like "Steam Deck".
- Library and settings vocabulary follows Lutris: `Source` is now
  `Origin` (Steam/Local), `Platform` is the target system and `Runner`
  names the environment (`Steam Proton`, `Steam Runtime`, `Native`,
  `Wine`, `Proton (UMU)`). Settings renames "Game Type" to
  "Environment" and drops the platform hint from its choices, because
  Windows is a platform, not an environment.

## [1.1.1] - 2026-10-05

### Fixed
- Profile Delete asks first and Save/Clone ask before overwriting an
  existing profile.
- Save and Reset over a newer-version config need an explicit Ok, so a
  loud fallback can no longer be silently downgraded.
- Steam quick-launch rejects non-numeric App IDs, and a failed Steam
  handoff no longer plants a menu skip that would eat the next menu.
- Game add/clone pickers reject non-numeric App IDs instead of writing
  garbage configs.
- Mode list no longer queries on dialog open (Refresh/provider/output
  only) and rapid Refresh never stacks workers.
- `summarize().last` is the newest stamp, not file order.
- Launch-without-save now persists just the profile selection, so the
  launcher resolves the profile shown in the dialog (never overwriting
  an unreadable live file on this path).
- Unreadable (not just invalid) config files fall back to defaults
  everywhere instead of crashing dialogs.
- Display mode no longer gets stuck on the dip mode when the target
  apply fails or the launch is interrupted: the original mode is
  recorded after the first apply and restored best-effort.
- xrandr mode lines keep every refresh rate (e.g. `164.96*+ 60.00`),
  so same-resolution dips avoid a resolution flicker.
- Shipped Qt translations actually load from installed packages: the
  catalog dir is a real package with an explicit wheel rule (previously
  English-only outside a source checkout), and repeat installs on one
  process no longer skip a second app.

## [1.1.0] - 2026-10-05

### Added
- Play button (Games row) and Play in the context menu for launching
  through the client; Play uses the real selection. Launching from
  the program (button, tray, menu) skips the pre-launch menu once
  via a fresh sentinel, even with show-menu enabled.
- Backup now includes preferences.toml; context menu order mirrors
  the button rows, with Copy Launch Options leading the copies group.
- In-app language option (Preferences): system default, English, or
  shipped locales — restart to apply, games unaffected (no LC_ALL leak).
- Display dip delay slider (3-15 s, per game, default 8 s) for the
  same-mode VRAM clock workaround; slider and note show only for
  the current mode.
- Display same-mode workaround for the AMD VRAM clock bug: requesting
  the current mode dips one mode down and back before the game starts
  (same resolution, closest lower refresh; logged, never aborts).
- Mode picker shows backend numbers and the current mode, keeps manual
  entry valid, and warns that same-mode requests dip first.
- Export/import now carries profiles (whitelist extended, traversal
  still rejected), and games clone live config plus profiles to
  another AppID ("Clone Settings To...", picking from the Steam
  game list, with overwrite confirm).
- Display mode picker lists detected modes (manual entry kept) with
  a Refresh button; apply/restore log values and failures loudly.
- Per-game history clearing: exact token match, atomic rewrite, in
  the History dialog (Clear Selected) and the game context menu.
- System tab grouped (Notifications / Idle Suspend / Night Light)
  with the night-light toggle named; PT-BR strings included.

### Fixed
- Pre-launch menu shows the active profile's wrappers (it rendered
  the live file while launching the profile).
- Display mode goes through kscreen numeric mode IDs (the WxH@rate
  string form is silently ignored) and the picker lists offered
  modes sorted by resolution then rate, descending.
- Mode list fills in a worker thread (a wedged kscreen-doctor once
  hung dialog construction); dialog open performs zero backend
  queries, and worker threads stop cleanly on accept/reject.
- Crafted AppIDs can no longer escape the log/proton-log dirs
  (`safe_stem` centralized in xdg, applied to every AppID path).
- Validate and the pre-launch countdown check the effective
  (profile-resolved) config, not just live.
- Clone replaces (not merges) destination profiles; export skips
  hand-placed nested profile junk the importer would refuse.

## [1.0.0] - 2026-10-04

### Added
- GUI translations via Qt Linguist, starting with PT-BR (351 strings;
  CLI stays English). New UI strings require `tr()` (enforced by test).

### Added
- Display dip delay slider (3-15 s, per game) for the same-mode
  VRAM clock workaround.
- Display same-mode workaround for the AMD VRAM clock bug: requesting
  the current mode dips one mode down and back before the game starts
  (same resolution, closest lower refresh; logged, never aborts).
- Mode picker shows backend numbers and the current mode, keeps manual
  entry valid, and warns that same-mode requests dip first.
- Mode picker shows backend numbers and the current mode, keeps manual
  entry valid, and warns that same-mode requests dip first.
- Export/import now carries profiles (whitelist extended, traversal
  still rejected), and games clone live config plus profiles to
  another AppID ("Clone Settings To...", picking from the Steam
  game list, with overwrite confirm).
- Display mode picker lists detected modes (manual entry kept) with
  a Refresh button; apply/restore log values and failures loudly.
- Per-game history clearing: exact token match, atomic rewrite, in
  the History dialog (Clear Selected) and the game context menu.

### Fixed
- Pre-launch menu shows the active profile's wrappers (it rendered
  the live file while launching the profile).
- Display mode goes through kscreen numeric mode IDs (the WxH@rate
  string form is silently ignored) and the picker lists offered
  modes sorted by resolution then rate, descending.
- Dip slider (default 8 s) and note show only for the current mode;
  worker threads stop on dialog close (close() bypasses reject,
  which once aborted suite teardown).
- Mode list fills in a worker thread (a wedged kscreen-doctor once
  hung dialog construction); dialog open performs zero backend
  queries, and worker threads stop cleanly on accept/reject.
- Crafted AppIDs can no longer escape the log/proton-log dirs
  (`safe_stem` centralized in xdg, applied to every AppID path).
- Validate and the pre-launch countdown check the effective
  (profile-resolved) config, not just live.
- Clone replaces (not merges) destination profiles; export skips
  hand-placed nested profile junk the importer would refuse.

## [0.9.0] - 2026-10-04

### Added
- Single binary: bare `tksteamlaunch` (or `--gui`) opens the settings
  GUI, `--cli` guarantees launcher mode; the `tksteamlaunch-gui` and
  `tksteamlaunch-appimage` entry points are gone (BREAKING for direct
  callers; the desktop file and AppImage use `tksteamlaunch` now).
- Gear-and-play app icon (font-free paths, gray gear + orange play),
  also wired as the AppImage icon.
- Scan Library batch-add for Steam games without a config, and
  per-game Clear Shader Cache (with size) in the context menu.
- User-focused README (uv tool/pipx/local package installs) with dev
  docs split into docs/DEVELOPMENT.md; new man page installed by both
  Arch packages; single-entry AppImage recipe in packaging/appimage/.
- FPS Limit (DXVK) now uses `DXVK_CONFIG="dxgi.maxFrameRate = 60;
  d3d9.maxFrameRate = 60"`: the `DXVK_FRAME_RATE` env var was removed
  upstream (doitsujin/dxvk#5331); DX9/10/11 only.
- Tray quick-launch: recent games section (steam:// URLs, 1-10
  configurable) with Preferences toggle and count.

### Changed
- Config files carry a `config_version` stamp (current: 1). Files from
  the future fail loudly (dialog warning, launcher fallback with an
  error, validate issue) instead of silently resetting; pre-stamp
  files load as before.

## [0.8.1] - 2026-10-04

### Added
- Movable game-list columns (drag the header) with a header context
  menu to show/hide columns (Game always on) and reset to the
  Game | App ID | Played | ProtonDB default; layout persists.

## [0.8.0] - 2026-10-04

### Changed
- **BREAKING**: selecting a profile now affects the launch: the
  launcher runs the active profile's content, falling back to the
  live config (with a warning) when the selection is missing or
  unreadable. Saving with a profile active writes the profile file
  and keeps only the selection in the live file, so Game Defaults
  stays pristine; `--validate` reports dangling selections.
- Reset to Global Defaults persists immediately (with confirmation):
  no more staged reset silently discarded by Cancel. Profiles are
  never touched by Reset.
- Fixed populate clobbering: live preview collects no longer overwrite
  the config mid-populate, which left late fields (Ludusavi, Wine /
  Proton, notes) stale on Reset and profile switches — looking like
  "nothing changed".

### Added
- Per-game display mode (phase 1: Plasma via kscreen-doctor, X11 via
  xrandr): optional output + WIDTHxHEIGHT[@RATE], applied on launch
  and restored on exit, failures warn without aborting. Empty mode
  disables it; GNOME/wlroots detect but warn as phase 2.
- Main window Played column (total time, sorts by seconds) fed by the
  session log; History dialog gained Clear History with confirmation.
- FPS Limit (DXVK) env preset (`DXVK_FRAME_RATE=60`, DX9/10/11 only).
- Proton Wayland env preset (`PROTON_ENABLE_WAYLAND=1` for GE,
  CachyOS and DW builds); No Esync and Disable D3D9 presets note
  where the toggle is a known no-op.
- Right-click context menu on the game list: Edit, Copy App ID /
  Game Name / Launch Options, Open Install Folder / Proton Prefix /
  ProtonDB Page, Validate, Remove (entries disable when N/A).
- Multi-select (Ctrl/Shift+click) for Remove and Reset to Global
  Defaults, with one confirmation listing the games; removing offers
  to clean up leftover profiles via a checkbox table.
- Context menu shows only multi-game actions on multiple selection;
  Tools row has Clean Profiles for orphaned profiles anytime, Games
  row has Reset, and empty Remove/Reset hint at selecting first.

### Added
- Opening the game dialog on a config file that cannot be parsed warns
  that defaults are shown (and will be written on save) instead of
  silently switching to them. The same warning fires when switching to
  an unreadable profile or back to an unreadable live file, and
  unreadable (not just invalid) files no longer crash the dialog open.

### Fixed
- Config writer escapes control characters (CR, ESC, NUL, …) and quotes
  exotic keys: a pasted line break can no longer produce an unreadable
  TOML file that resets the game to defaults on the next load.
- Config saves (games, profiles, defaults, preferences) are atomic
  (temp file + rename): a crash mid-write no longer truncates the file.
- Atomic saves sweep stale temp files left by a previous crash.
- Saving with a profile active writes the profile file and keeps
  only the selection in the live file (see Changed above); edits no
  longer revert on reopen and Game Defaults stays pristine.
- Game list App ID column sorts numerically (9, 80, 1044620) instead
  of lexicographically.

## [0.7.0] - 2026-09-30

### Added
- Guided empty state on the main window (Add / Import / Copy Launch
  Options) when no games are configured.
- Game list filter by name or App ID plus "With issues only" (same
  checks as `--validate`), with a "N shown" status suffix.
- Live "Will launch with: ..." wrappers summary in the game dialog
  footer, updated on every field change.
- Advanced tabs (Environment, Pre/Post Commands, Wine / Proton) hidden
  behind an "Advanced" footer toggle; auto-expanded when the game
  already uses them.
- Broken custom-executable/hook paths surface as live Dependency
  Status warnings with an "Open folder" link when the parent exists.
- New presets: DXVK Sarek for pre-1.3 Vulkan GPUs, D7VK switch for
  GE-Proton.

### Fixed
- SteamTinkerLaunch importer drops default-off (`"0"`/`"none"`) flags
  via allowlist (numeric scales and unknown keys kept) and reports
  pre/post hooks or custom executables missing on disk (cross-PC paths).
- Env preset applicability audited against current Valve/CachyOS/GE
  docs and the installed Proton scripts: CachyOS-only vars no longer
  offered on Valve/GE, GE-only `PROTON_NO_NTSYNC` no longer offered
  elsewhere, DW-Proton recognized as its own flavor.

## [0.6.0] - 2026-09-30

### Added
- Profile selection persists per game; Clone confirms before copying
  live settings; profile list refreshes on dialog focus.
- Profile combo starts with `(Game Defaults)` to reload the saved game
  settings; switching (or deleting the active) profile with unsaved
  edits asks Save / Discard / Cancel.
- SteamTinkerLaunch importer: common settings land in a
  `steamtinkerlaunch` profile (live config untouched), with usage
  notice; profile Clone button.

## [0.5.0] - 2026-09-28

### Added
- Proton log capture per game (off by default, warning in notification).
- WINEDEBUG selector per game (Off/-all/+err/+warn,+err).
- VSync disable presets for Mesa and NVIDIA (verified against docs).
- Idle suspend inhibitor per game (logind idle lock only).
- Proton prefix fresh-start toggle (deletes compatdata before launch).
- Winetricks verbs per game via protontricks (unattended, skips repeats).
- Config diff viewer (game vs global defaults).
- SteamGridDB artwork fallback (API key in Preferences, own cache).
- RT upscaler support (linux-rt-upscaler wrap, XWayland enforced).
- Richer pre-launch menu: centered buttons with icons, landscape game
  art, `Name (AppID)` header, playtime and active wrappers, optional
  auto-launch countdown (`menu_timeout`).
- Compat preset catalog (FSR4, sync, D3D fallbacks, locale, HDR...) with
  GPU/Proton applicability tags and mismatch confirm.

### Changed
- Settings dialog regrouped: Environment, System and Display tabs;
  status box in two columns with blanks packed last; collapsible
  3-line command preview.
- Main window and dialogs center on the available area; game list
  sorts A-Z by default with clickable headers.

### Fixed
- SteamGridDB single-object game responses handled (artwork works).

## [0.4.0] - 2026-09-28

### Added
- Dynamic versioning from git tags (`uv-dynamic-versioning`); releases
  are cut by tagging. PKGBUILD derives `pkgver()` the same way.
- Real pre-launch menu dialog (Launch / Settings / Cancel) for `--menu`.
- Status tray icon (normal/monochrome) with menu, minimize/close to
  tray and a Preferences dialog (`preferences.toml`).
- Bundled application icons and freedesktop desktop entry.

### Changed
- **BREAKING:** `show_preview` moved from `defaults.toml [ui]` to
  `preferences.toml`; old key ignored.
- LICENSE file removed (SPDX common license covers GPL-3.0-or-later);
  nightlight-holder console script removed (use `python -m`).

### Fixed
- Minimize-to-tray deferred past the state-change event.
- Reload rescans Steam games again (per-process cache is cleared).
- GUI test suite hermetic to pytest-qt presence.

### Added
- Live launch-command preview box in dialogs (global `[ui] show_preview`
  toggle); tool toggles disable when their binaries are missing.
- Per-game config profiles (switch/save-as/delete, in-memory until Save).
- ProtonDB tier column in the main window (30-day cache, background
  refresh; double-click opens the game page).
- Session history dialog (last played, sessions, total time, failures).
- Steam launch-options verifier (dialog status + `--validate` input).
- Gamescope option presets (1080p144, 1440p165, 4K60, borderless, Deck).
- Per-game notes tab.
- Config export/import tarballs (`--export`/`--import`, GUI buttons).
- MangoHud starter templates (minimal, fps-cap, full) in New Configuration.
- Env presets (FSR, RADV shaders, SDL Wayland) via Add Preset.
- pytest suite (`tests/`, 41 tests) and ruff config in `pyproject.toml`.
- `Co-Authored-By` trailer policy + `scripts/git-hooks/commit-msg` hook.
- "Preview Command" button in the game dialog (dry-run parity).
- `tksteamlaunch --list` prints configured and detected games.
- Per-game logs rotate at 1 MiB (3 backups).
- Desktop `notify-send` alerts on hook failures and launch blockers.
- Transient game-start notification (per-game `[notifications]` toggle,
  game icon, Proton version lookup).
- Session-end notification with playtime.
- Detected Proton runtime shown read-only in the game dialog.
- Ludusavi coverage check (manifest entry + local saves via preview).
- Pre-launch menu: `--menu` flag and per-game `show_menu` setting
  (Launch / Settings / Cancel, display fallback launches directly).
- `--edit` accepts a positional AppID and shows a game picker when
  no AppID is given.

### Changed
- "Preview Command..." button removed (replaced by the live preview box);
  ludusavi shown by bare name in previews, like other wrappers.
- Build backend setuptools → hatchling; local install via
  `uv venv --system-site-packages` + `uv pip install --no-deps .`.
- `--help` documents the exit-code contract.
- **BREAKING:** `nightlight.provider = "kde"` no longer recognized
  (renamed to `"plasma"`); unknown values fall back to auto-detect.
- **BREAKING:** legacy ludusavi keys (`enable_restore`, `enable_backup`,
  `use_gui_progress`) no longer honored; affected games load with
  ludusavi off.
- **BREAKING:** no config migration machinery remains; sparse/unknown
  files load as-is with built-in defaults for missing keys.

### Fixed
- Minimize-to-tray deferred past the state-change event.
- Ctrl+Q quits the app; closing without close-to-tray drops the tray
  icon so the app really exits.
- Single GUI instance: followers raise the open window and exit.
- Status tray rebuilt safely: persistent menu reference, update in
  place instead of delete/recreate, guarded teardown.
- Steam launch-options check now parses real `localconfig.vdf` files
  (lowercase `apps` node, nested blocks); venv paths with flags match.
- Command preview uses `%command%` instead of `<game-command>`.
- Start notification folds runtime and wrappers into one line and uses
  the same Proton tool display as the game dialog (no more lone
  "Proton" when only the tool mapping exists).
- Dialog buttons ordered Launch | Save | Save & Launch with theme
  icons; "Launch" runs with the saved configuration, discarding
  unsaved edits.
- Settings dialogs opened from Steam no longer fall back to the Fusion
  style: the editor runs in a subprocess with Steam-runtime library
  paths filtered out of `LD_LIBRARY_PATH`.
- `--menu` flag no longer opens the pre-launch menu twice.
- Qt/desktop environment logged per run to diagnose GUI theming.
- NightLight holder spawned twice per launch, leaking an inhibitor;
  single spawn with idempotent start().
- Empty game command executed a bare prefix stack; now skipped with
  a log line, and "Save && Launch" hides when nothing can launch.
- Unbalanced quotes in prefix/args fields no longer crash launch,
  validation or Save (whitespace fallback).
- String booleans in TOML (`"false"`) now parse correctly.
- Ludusavi coverage tolerates non-integer `bytes` values.
- GameMode/CachyOS conflict resolved on dialog load (Feral wins).
- Add Game ignores blank names instead of writing `unknown.toml`.
- Copy Launch Options handles missing clipboard (headless).
- Command preview never kills the dialog on unexpected errors.
- Ludusavi coverage check runs off the UI thread; worker threads
  always joined (terminate fallback) before their owners close.
- "Check Coverage" button hidden in Global Defaults (per-game only).
- Pre/post hooks with `run_in_shell` now receive the game's env vars
  (previously dropped).

## [0.1.0] - 2026-09-23

First tagged baseline: launcher pipeline, PySide6 GUI, ludusavi `wrap`,
per-game snapshots, night light holder.
