# AGENTS.md — instructions for AI coding agents on TKArcade

TKArcade is a minimal Steam launch wrapper: per-game TOML configs,
a stdlib-only launcher CLI (`tkarcade %command%`) and a PySide6 GUI.
License: GPL-3.0-or-later.

## Communication

- Chat with the maintainer in Portuguese; code, docs, comments, commit
  messages and GUI strings in English.
- Short, factual, no superlatives. Surface disagreements honestly.

## Work state

`docs/STATE.md` is an ambient instruction (`instructions` in
`opencode.json`), so it is already in context: it carries the branch,
the last landed change, the next step and the open decisions. Refresh
it with `/handoff` before stopping mid-task — session history is not
memory, and this file is what a fresh session sees.

Larger designs are ordinary committed docs under `docs/plans/`. Never
rely on plan-mode scratch files: they live in `$HOME/.opencode/plan`,
outside the repo, and do not travel between clones.

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
- `AI-Model:` trailer comes from the versioned `.opencode-model` via the
  `scripts/git-hooks/commit-msg` hook (`core.hooksPath` is set repo-local).
  Versioning it keeps the trailer identical on every clone.
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

## Detailed references

Two rule sets were moved out of this file to keep the agent prompt
short. Read the relevant one before the first change in that area:

- `docs/QML-NOTES.md` — Kirigami/QML rules (hard-won, do not regress):
  Repeater/JS-array models, test navigation, ScrollView and dialog
  sizing, QQC2 behaviour, tray/QApplication, single-instance shell.
- `docs/POLICIES.md` — project policies (do not regress): config
  compatibility, XDG layout, dependency licenses, `-git` builds,
  Flatpak Ludusavi, CLI exit codes.
