# Development

Dev flow uses `uv` with system site packages (reuses the distro's
PySide6/vdf/jeepney); never plain `venv`/`pip` into the system
interpreter. Run checks with `.venv/bin/python`; `ruff` stays the
system binary. Exception: `PKGBUILD check()` always uses system
packages only (no uv in the chroot).

On a fresh clone, `./scripts/bootstrap.sh` creates the venv, installs
the tree editable and enables the commit hook. It writes only inside
the working tree, never in `$HOME`. Re-run it after a pull or a machine
switch: a synced/copied `.venv` keeps the other machine's path.

`scripts/check.sh` is the single gate for a change: lint, format, then
tests. It takes a mode, then optional pytest targets:

```bash
scripts/check.sh                       # fast suite, no QML driver (~30s)
scripts/check.sh --changed             # only what git shows as touched
scripts/check.sh --qml                 # full suite, QML driver included
scripts/check.sh tests/test_config.py  # the given targets only
```

`--changed` maps `src/tkarcade/<name>.py` to `tests/test_<name>.py`
(anything under `backends/` to `tests/test_backends.py`, `test_no_widgets.py`
always when source changed, `pyproject.toml`/`packaging/` to
`tests/test_packaging.py`, any `*.md`/`opencode.json` to
`tests/test_docs.py`). A touched file without that pair, or any
`.qml` change, widens the run to the whole suite: the gate never skips a
change silently. Use it while working; run the fast suite whole once per
approval round, before handing the diff over (plus `--qml` when QML or
the tests themselves changed), not on every small correction.

What bootstrap runs, and the raw commands:

```bash
uv venv --system-site-packages .venv
uv pip install --python .venv/bin/python --no-deps --no-build-isolation -e .
.venv/bin/python -m pytest tests/ -q          # full suite, ~2 min on 4 cores
ruff check src/ tests/
ruff format --check src/ tests/  # line-length 100, see pyproject.toml
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -c "..."  # GUI smoke
```

`-e` keeps `./.venv/bin/tkarcade` on the live tree and
`--no-build-isolation` reuses the system build backend. `--no-deps` is
load-bearing: without it uv installs its own PySide6 into the venv,
which shadows the distro one and makes Qt miss the system QML modules
(`module "org.kde.kirigami" is not installed`).

The suite must pass with and without `pytest-qt` installed: never
monkeypatch Qt globals at fixture scope (patch inside the test body so
teardown hooks see a healthy QApplication). GUI changes need an
offscreen screenshot check.

The launcher (`src/tkarcade/launcher.py`, `config.py`, `backends/`,
`proton.py`, `steam.py`, `xdg.py`, `nightlight_holder.py`,
`winetricks.py`) must stay **stdlib-first**: it runs on every game
start and may import `vdf` (pure Python, a runtime dependency of the
package) to read Steam files; any other third-party import needs its
own decision. PySide6/jeepney are for GUI/helpers only. The GUI-only
runtime archive helper imports `zstandard` lazily below Python 3.14
(stdlib `compression.zstd` above); the launcher never imports it. The
exit-code contract, the no-shims policy and the `config_version` stamp
are in `docs/POLICIES.md`.

## Tags and releases

Branch, commit, merge and push rules live in `docs/GIT.md`; this
section covers tags and releases only.

Tags are `vVER` (annotated, signed), releases `VER` with CHANGELOG
notes. After a tag: bump the release PKGBUILD (`pkgver` + tarball sha),
rebuild `-git`, check upscale/presets.

## Packaging

* `packaging/arch/tkarcade` — release tarball package.
* `packaging/arch/tkarcade-git` — VCS package (`pkgver()` from
  `git describe`; the static `pkgver` is build noise, commit the bump
  after `makepkg` runs when it changes).
* `packaging/arch/linux-rt-upscaler*` — vendored upscaler packages.
* Build with `makepkg -Ccfrs --noconfirm`. Build outputs are
  git-ignored; `PKGDEST` points outside the repo.

## AppImage

`libappimage` is the spec implementation (inspect/integrate AppImages)
— not a builder. Builds use `pyproject-appimage` (JakobDev):
it turns the pyproject into a self-contained AppImage (~150-250 MB
with PySide6). A fixed and updated recipe (upstream AUR was stale at
4.2) lives in `packaging/arch/pyproject-appimage/` — note its
`python-desktop-entry-lib` dependency is AUR-only and must be
installed first. External tools (GameMode, MangoHud, Ludusavi, …) stay
on the host by design; the build recipe lives in `packaging/appimage/`.
Verify the bundle on a clean session: GUI opens, dialog saves,
`--validate` passes, and Steam accepts it in Launch Options.
GitHub releases accept files up to 2 GB, so size is not an issue.

## AI assistance

This project is developed with AI assistance (OpenCode with
managed/free models), reviewed by the maintainer. Every commit carries
a `Co-Authored-By` trailer plus an `AI-Model:` trailer, both naming the
model in use (from the versioned `.opencode-model` file, one model per
line; several lines join into a single trailer for a batch a second
model worked on); only an empty file falls back to the tool's name. A
local `commit-msg` hook (see `scripts/git-hooks/`,
enabled via `git config core.hooksPath scripts/git-hooks`) adds both
automatically. Agent instructions live in `AGENTS.md`. Token cost is
measured per session from the OpenCode database: the commands sit under
"Context hygiene" in `AGENTS.md`, and `/handoff` reports the numbers.

The working state travels through `docs/STATE.md` and the git history,
never through plan-mode scratch files: OpenCode writes those under
`$HOME/.opencode/plan`, which is per-machine and outside the repo. A
larger design is a normal, committed document under `docs/decisions/`.
Sessions are not versioned either (the SQLite database and its JSON
exports are large and machine-local); to move one on purpose:

```bash
opencode session export <session-id> > /shared/tkarcade-session.json
opencode session import --directory <checkout> /shared/tkarcade-session.json
```

## UI wording

UI strings are Title Case: labels, buttons, menus, window and dialog
titles, checkboxes, table columns and status messages. Tool names keep
their own spelling (`wine`, `umu-run`, `winetricks`, `vkd3d-proton`,
`MangoHud`, `DXVK`, `logind`, `compatibilitytools.d`), and command-line
flags, config keys and paths stay verbatim. A diagnostic that starts
with a config key keeps it as-is: the `Error:`/`Warning:` label carries
the capitalization instead.

## Translations (Qt Linguist)

GUI strings go through QML `qsTr()`, with one Python exception: the
native tray menu (`gui/tray.py`) has no QML counterpart, so its labels
use `QCoreApplication.translate()` in a `TrayMenu` context. Display text
and saved data stay split in combos so translations never break config
round-trips. CLI/launcher text stays English by design.

Translations are suspended until 1.0 (2026-11-08). Do not run the
refresh script or translate new strings: they ship in English and fall
back to the source text under pt_BR, and the catalog tests in
`tests/test_i18n.py` are skipped. At 1.0, run the script, translate
every message, remove the skips and update this section.

```bash
bash scripts/refresh-translations.sh  # lupdate + the untranslated/unfinished report
# translate leftovers, then rerun it to recompile the .qm
```
Never run lupdate on a subset of files: it marks every other context
vanished. The refresh script always passes the full QML set plus
`gui/tray.py`, and `-no-obsolete` prunes the vanished entries.
`lrelease` runs with `-fail-on-unfinished`, so the script stops before
writing a `.qm` while any message still carries the `type="unfinished"`
flag, even when it already has text.

Commit both `.ts` (source) and `.qm` (runtime payload, travels in the
wheel). `tests/test_i18n.py` fails on any untranslated `qsTr()` or
`translate()` literal, and on any leftover `unfinished` flag.
