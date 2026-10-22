# AGENTS.md — instructions for AI coding agents on TKArcade

TKArcade is a minimal Steam launch wrapper: per-game TOML configs,
a stdlib-only launcher CLI (`tkarcade %command%`) and a PySide6 GUI.
License: GPL-3.0-or-later.

## Communication

- Chat with the maintainer in Portuguese; code, docs, comments, commit
  messages and GUI strings in English.
- Short, factual, no superlatives. Surface disagreements honestly.

## Environment

- Python >= 3.12, Linux. Default flow is `uv` with system site packages:
  `uv venv --system-site-packages` (reuses Arch/CachyOS packages, never
  plain `venv`/`pip` into the system interpreter). Run checks with
  `.venv/bin/python`; `ruff` stays the system binary. Refresh the project
  with `uv pip install -e . --no-deps`: plain `uv pip install -e .`
  installs a PyPI PySide6 into the venv, whose QML dir has no
  org.kde.kirigami/org.kde.desktop and every GUI boot test then fails.
- Exception: `PKGBUILD check()` always uses system packages only
  (no uv in the chroot).
- The launcher (`src/tkarcade/launcher.py`, `config.py`, `backends/`,
  `proton.py`, `steam.py`, `xdg.py`, `nightlight_holder.py`) must stay
  **stdlib-only**: it runs on every game start. PySide6/vdf/jeepney are
  for GUI/helpers only.

## Verify before finishing

```bash
.venv/bin/python -m pytest tests/ -q
ruff check src/ tests/
ruff format --check src/ tests/  # line-length 100, see pyproject.toml
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -c "..."  # GUI smoke
```

The suite must pass with and without `pytest-qt` installed: never
monkeypatch Qt globals at fixture scope (patch inside the test body so
teardown hooks see a healthy QApplication).
QML cases live in `tests/kirigami_qml_cases.py` (not collected by
default); `tests/test_kirigami_qml.py` runs them in short-lived
subprocess batches (the whole file aborts in one process on Qt 6.12 GC
teardown) and re-runs in isolation whatever a crashing batch swallowed.
Single case: `pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"`.
Fast loop without the QML suite (~15s; the QML driver is marked `qml`):
`pytest tests/ -q -m "not qml"`. The driver reads `TKARCADE_QML_BATCH`
(cases per subprocess; default 8 serial, 4 with up to four workers, 2
above) and `TKARCADE_QML_WORKERS` (parallel subprocesses, default one
per CPU capped at 8; parallel runs can flake timing-sensitive cases
under load, set 1 to force serial). `pytest -v -rP
tests/test_kirigami_qml.py` prints one line per finished batch with its
wall time; the `-git` PKGBUILD `check()` runs it that way so a slow
build names the culprit (the driver is one test, ~85% of the wall time)
and adds `--show-capture=stdout`: plain `-rP` also dumps the captured
log/stderr of every passing test, and those expected warnings and errors
read like build failures.

GUI changes need an offscreen screenshot check. Push each commit batch
created during build mode (the Arch package builds from git); never
rewrite pushed history or tags.

## Commits (one per area/theme)

- Message + `Co-Authored-By: OpenCode <noreply@opencode.ai>` trailer.
- `AI-Model:` trailer comes from `.opencode-model` (gitignored) via the
  `scripts/git-hooks/commit-msg` hook (`core.hooksPath` is set repo-local).
- Keep `opencode.json` in sync with the models actually in use: root
  `model` is the default for new sessions, `agents.build.model` is the
  build agent (only the agent field takes a `#variant`). Update both, plus
  `.opencode-model`, when the model changes.
- User-facing changes get a `CHANGELOG.md` entry under Unreleased, with
  explicit **BREAKING** notes.

## Branches and merges

- Big changes (multi-file features, GUI/QML work, risky refactors,
  anything that needs manual testing) land on a short-lived branch off
  `main`; `main` stays untouched until the change is approved. Trivial
  fixes and docs may commit to `main` directly.
- Integrate with `git merge --squash <branch>` and one commit on `main`
  (no merge commit when a squash is possible), then delete the branch
  locally and on the remote.
- The squashed commit carries the final message and the usual trailers;
  the branch keeps the granular history for review.
- A squash leaves the branch "unmerged" to git, so delete it with
  `git branch -D` and `git push origin --delete <branch>`.
- The `-git` PKGBUILD pins the branch it is built from: if a feature
  branch was used for `-git` builds, point the pin back at `main`
  before deleting the branch.

## Kirigami/QML rules (hard-won, do not regress)

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
  defines done).
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

## Project policies (do not regress)

- No config migration/compat shims (pre-1.0): incompatible configs load
  as fresh built-ins.
- XDG Base Directory for all files; per-game TOML snapshots (full files,
  never sparse); `defaults.toml` is a new-game template only.
- New third-party deps need GPLv3-compatible licenses (MIT/BSD/
  Apache-2.0/PSF/LGPL). External tools via subprocess, never linked.
- Third-party recipes under `packaging/arch/` (linux-rt-upscaler*,
  pyproject-appimage) are synced copies from TKSteamLaunch: check
  drift with `diff -r` against it before tagging, copy the winner
  in a commit of its own.
- Rebuild `-git` locally to verify each batch; its `pkgver` churn
  stays dirty in the tree and out of commits (never `add -A` it).
  At release time commit the current `-git` PKGBUILD with everything
  else. On a feature branch the `-git` source pins that branch; at
  release time check every package for new versions, update every
  PKGBUILD and build them all.
- Flatpak Ludusavi cannot see Proton prefixes: always warn, never
  silently accept it.
- Exit codes are part of the CLI contract (10 no AppID, 12 pre-hook,
  13 missing exe, 14 missing prefix/wine/umu/Proton runtime, 15 no display,
  16 import/export, 17 validation issues, 18 game type not set).
