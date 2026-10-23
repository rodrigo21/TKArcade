# AGENTS.md — instructions for AI coding agents on TKArcade

TKArcade is a minimal Steam launch wrapper: per-game TOML configs,
a stdlib-only launcher CLI (`tkarcade %command%`) and a PySide6 GUI.
License: GPL-3.0-or-later.

## Communication

- Chat with the maintainer in Portuguese; code, docs, comments, commit
  messages and GUI strings in English.
- Short, factual, no superlatives. Surface disagreements honestly.
- Rename the session to the task in progress whenever the work moves to
  a new area: the title is what a later session sees first.

## Work state

`docs/STATE.md` is an ambient instruction (`instructions` in
`opencode.json`), so it is already in context: it carries the branch,
the last landed change, the next step and the open decisions. Refresh
it with `/handoff` before stopping mid-task. Larger designs are
ordinary committed docs under `docs/plans/`; plan-mode scratch files
(`$HOME/.opencode/plan`) do not travel between clones.

## Context hygiene

Every request re-sends the whole session. Keep sessions short and
their output small:

- One session per feature: `/handoff` at the boundary and start a new
  one. Visual checks (offscreen screenshots) run in a subagent or a
  short session: a screenshot stays in context as base64.
- Never dump a whole file, binary or large diff: `grep`, `sed -n`,
  `tail`, `git diff --stat`. `strings` on a binary is banned.
- Test files are large: grep the case name and read a range. Broad code
  searches go through the `explore` subagent.
- Batch independent tool calls in one turn instead of one at a time;
  prefer counts and tails (`grep -c`, `pytest -q | tail`) over full
  output. `tool_output` in `opencode.json` is only a backstop.

## Environment

- Python >= 3.12, Linux. `uv venv --system-site-packages` reuses the
  Arch/CachyOS packages; never plain `venv`/`pip` into the system
  interpreter. Run checks with `.venv/bin/python`; `ruff` stays the
  system binary. Refresh with `uv pip install -e . --no-deps`: plain
  `uv pip install -e .` installs a PyPI PySide6 whose QML dir lacks
  org.kde.kirigami/org.kde.desktop and every GUI boot test then fails.
- The launcher (`src/tkarcade/launcher.py`, `config.py`, `backends/`,
  `proton.py`, `steam.py`, `xdg.py`, `nightlight_holder.py`,
  `winetricks.py`) must stay **stdlib-only**: it runs on every game
  start. PySide6/vdf/jeepney are for GUI/helpers only.

## Verify before finishing

```bash
scripts/check.sh        # ruff check + format --check + fast suite (~17s)
```

The full suite (QML driver included, ~90s) runs once per task, and only
when `tests/` or QML changed. Single QML case:
`pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"`,
with `--tb=long` on that case when a nested fixture hides the frame.
The suite must pass with and without `pytest-qt`; never monkeypatch Qt
globals at fixture scope (patch inside the test body so teardown hooks
see a healthy QApplication). Driver knobs and QML rules live in
`docs/QML-NOTES.md`. GUI changes need an offscreen screenshot check.

## Commits (one per area/theme)

- Message + `Co-Authored-By: OpenCode <noreply@opencode.ai>` trailer.
- `AI-Model:` comes from the versioned `.opencode-model` via
  `scripts/git-hooks/commit-msg` (`core.hooksPath` is repo-local).
- Keep `opencode.json` and `.opencode-model` in sync with the models in
  use: root `model` and `agents.build.model` (only the agent field takes
  a `#variant`).
- User-facing changes get a `CHANGELOG.md` entry under Unreleased, with
  explicit **BREAKING** notes.

## Branches and merges

- Multi-file features, GUI/QML work and risky refactors land on a
  short-lived branch off `main`; `main` stays untouched until the change
  is approved. Trivial fixes and docs may commit to `main`.
- Integrate with `git merge --squash <branch>` and one commit on `main`,
  then delete the branch with `git branch -D` and
  `git push origin --delete <branch>`: a squash leaves it "unmerged" to
  git. The branch keeps the granular history for review.
- Push each commit batch (the Arch package builds from git); never
  rewrite pushed history or tags.

## Detailed references

Read the relevant one before the first change in that area:

- `docs/QML-NOTES.md` — Kirigami/QML rules and the QML test driver.
- `docs/DEVELOPMENT.md` — dev environment, commits/tags/releases,
  packaging, AppImage.
- `docs/POLICIES.md` — config compatibility, XDG, deps, `-git` builds,
  Flatpak, CLI exit codes.
