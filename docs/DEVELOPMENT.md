# Development

Dev flow uses `uv` with system site packages (reuses the distro's
PySide6/vdf/jeepney); never plain `venv`/`pip` into the system
interpreter. Run checks with `.venv/bin/python`; `ruff` stays the
system binary. Exception: `PKGBUILD check()` always uses system
packages only (no uv in the chroot).

```bash
uv venv --system-site-packages .venv
uv pip install --python .venv/bin/python --no-deps .
python3 -m pytest tests/ -q
ruff check src/ tests/
ruff format --check src/ tests/  # line-length 100, see pyproject.toml
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -c "..."  # GUI smoke
```

The suite must pass with and without `pytest-qt` installed: never
monkeypatch Qt globals at fixture scope (patch inside the test body so
teardown hooks see a healthy QApplication). GUI changes need an
offscreen screenshot check.

The launcher (`src/tksteamlaunch/launcher.py`, `config.py`, `backends/`,
`proton.py`, `steam.py`, `xdg.py`, `nightlight_holder.py`) must stay
**stdlib-only**: it runs on every game start. PySide6/vdf/jeepney are
for GUI/helpers only. Exit codes 10-17 are part of the CLI contract.
No config migration shims pre-1.0; since 0.9.0 files carry a
`config_version` stamp and newer files fail loudly, never silently.

## Commits, tags, releases

One commit per area/theme, message plus
`Co-Authored-By: OpenCode <noreply@opencode.ai>` trailer. The
`AI-Model:` trailer comes from `.opencode-model` (gitignored) via the
`scripts/git-hooks/commit-msg` hook (`core.hooksPath` is set
repo-local). Sign commits/tags with GPG when pinentry answers, push
each signed batch, never rewrite pushed history or tags. User-facing
changes get a `CHANGELOG.md` entry under Unreleased, with explicit
**BREAKING** notes. Tags are `vVER` (annotated, signed), releases
`VER` with CHANGELOG notes. After a tag: bump the release PKGBUILD
(`pkgver` + tarball sha), rebuild `-git`, check upscale/presets.

## Packaging

* `packaging/arch/tksteamlaunch` — release tarball package.
* `packaging/arch/tksteamlaunch-git` — VCS package (`pkgver()` from
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
in use (from the gitignored `.opencode-model` file); a local
`commit-msg` hook (see `scripts/git-hooks/`, enabled via
`git config core.hooksPath scripts/git-hooks`) adds both
automatically. Agent instructions live in `AGENTS.md`.

## Translations (Qt Linguist)

GUI strings go through `self.tr()` (or `QCoreApplication.translate`
at module level); display text and saved data stay split in combos so
translations never break config round-trips. CLI/launcher text stays
English by design.

```bash
python3 scripts/extract-messages.py  # refresh translations/*.ts
# translate new strings (Linguist GUI or edit XML), then:
lrelease6 translations/tksteamlaunch_pt_BR.ts \
  -qm src/tksteamlaunch/translations/tksteamlaunch_pt_BR.qm
```

Commit both `.ts` (source) and `.qm` (runtime payload, travels in the
wheel). `tests/test_i18n.py` fails on any untranslated `tr()` literal.
