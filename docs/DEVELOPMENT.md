# Development

Dev flow uses `uv` with system site packages (reuses the distro's
PySide6/vdf/jeepney); never plain `venv`/`pip` into the system
interpreter. Run checks with `.venv/bin/python`; `ruff` stays the
system binary. Exception: `PKGBUILD check()` always uses system
packages only (no uv in the chroot).

On a fresh clone, `./scripts/bootstrap.sh` creates the venv, installs
the tree editable and enables the commit hook. It writes only inside
the working tree, never in `$HOME`. The explicit commands:

```bash
uv venv --system-site-packages .venv
uv pip install --python .venv/bin/python --no-deps --no-build-isolation -e .
.venv/bin/python -m pytest tests/ -q
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
`winetricks.py`) must stay **stdlib-only**: it runs on every game start.
PySide6/vdf/jeepney are for GUI/helpers only. Exit codes 10-18 are part
of the CLI contract.
No config migration shims pre-1.0; since 0.9.0 files carry a
`config_version` stamp and newer files fail loudly, never silently.

## Commits, tags, releases

One commit per area/theme, message plus
`Co-Authored-By: OpenCode <noreply@opencode.ai>` trailer. The
`AI-Model:` trailer comes from the versioned `.opencode-model` via the
`scripts/git-hooks/commit-msg` hook (`core.hooksPath` is set
repo-local). Sign commits/tags with GPG when pinentry answers, push
each signed batch, never rewrite pushed history or tags. User-facing
changes get a `CHANGELOG.md` entry under Unreleased, with explicit
**BREAKING** notes. Tags are `vVER` (annotated, signed), releases
`VER` with CHANGELOG notes. After a tag: bump the release PKGBUILD
(`pkgver` + tarball sha), rebuild `-git`, check upscale/presets.

Big changes go on a short-lived branch off `main`; `main` stays intact
until the change is approved. Land them with `git merge --squash` plus
one commit (no merge commit when a squash is possible), then delete the
branch locally and on the remote. Trivial fixes and docs may commit to
`main` directly.

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
a `Co-Authored-By` trailer plus an `AI-Model:` trailer with the model
in use (from the versioned `.opencode-model` file, one model per line;
several lines join into a single trailer for a batch a second model
worked on); a local `commit-msg` hook (see `scripts/git-hooks/`,
enabled via `git config core.hooksPath scripts/git-hooks`) adds both
automatically. Agent instructions live in `AGENTS.md`.

The working state travels through `docs/STATE.md` and the git history,
never through plan-mode scratch files: OpenCode writes those under
`$HOME/.opencode/plan`, which is per-machine and outside the repo. A
larger design is a normal, committed document under `docs/plans/`.
Sessions are not versioned either (the SQLite database and its JSON
exports are large and machine-local); to move one on purpose:

```bash
opencode session export <session-id> > /shared/tkarcade-session.json
opencode session import --directory <checkout> /shared/tkarcade-session.json
```

## Translations (Qt Linguist)

GUI strings go through QML `qsTr()`, with one Python exception: the
native tray menu (`gui/tray.py`) has no QML counterpart, so its labels
use `QCoreApplication.translate()` in a `TrayMenu` context. Display text
and saved data stay split in combos so translations never break config
round-trips. CLI/launcher text stays English by design.

```bash
bash scripts/refresh-translations.sh  # lupdate + the untranslated report
# translate leftovers, then rerun it to recompile the .qm
```
Never run lupdate on a subset of files: it marks every other context
vanished. The refresh script always passes the full QML set plus
`gui/tray.py`, and `-no-obsolete` prunes the vanished entries.

Commit both `.ts` (source) and `.qm` (runtime payload, travels in the
wheel). `tests/test_i18n.py` fails on any untranslated `qsTr()` or
`translate()` literal.
