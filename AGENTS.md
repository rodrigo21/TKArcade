# AGENTS.md — instructions for AI coding agents on TKArcade

TKArcade is a minimal Steam launch wrapper: per-game TOML configs,
a stdlib-only launcher CLI (`tkarcade %command%`) and a PySide6 GUI.
License: GPL-3.0-or-later.

## Communication

- Chat with the maintainer in Portuguese; code, docs, comments, commit
  messages and GUI strings in English.
- Short, factual, no superlatives. Surface disagreements honestly.
- Rename the session to the task in progress whenever the work moves to
  a new area.

## Work state

`docs/STATE.md` is an ambient instruction (`instructions` in
`opencode.json`), so it is already in context: branch, last landed
change, next step. Refresh it with `/handoff` before stopping mid-task;
designs are committed docs under `docs/plans/`, never plan-mode scratch
files outside the repo.

## Context hygiene

Every request re-sends the whole session, so cost grows with the number
of turns, not with the size of the project. Budget: **~25 tool calls per
commit**; measure at the end with `opencode stats --project .`.

- One commit per session: `/handoff` and start a new one after each
  push. A session that carries several features is the main way one
  reaches the context limit.
- Batch independent calls in one turn. Never re-run a check that already
  passed without a code change since.
- Never dump a whole file, binary or large diff: `grep`, `sed -n`,
  `tail`, `git diff --stat`. `strings` on a binary is banned. Test files
  are large: grep the case name. Broad searches go through the `explore`
  subagent.
- Visual checks (offscreen screenshots) run in a subagent or a short
  session: a screenshot stays in context as base64.

## Invariants

The launcher (`launcher.py`, `config.py`, `backends/`, `proton.py`,
`steam.py`, `xdg.py`, `nightlight_holder.py`, `winetricks.py`) stays
**stdlib-only**: it runs on every game start. PySide6/vdf/jeepney are
for GUI/helpers only.

## Verify before finishing

```bash
scripts/check.sh --changed   # the modules git shows as touched
scripts/check.sh             # whole fast suite (~20s), before closing
```

`--changed` widens to the whole fast suite when a touched file has no
test module of its own, so it never skips a change silently. The full
suite with the QML driver (`scripts/check.sh --qml`, ~90s) runs once per
task and whenever QML or the tests changed; a single case runs with
`pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"`,
plus `--tb=long` when a fixture hides the frame. The suite must pass with
and without `pytest-qt`; never monkeypatch Qt globals at fixture scope
(patch inside the test body). GUI changes need an offscreen screenshot
check.

Refresh the local venv after the last change on the branch and again
after the merge, so the maintainer can test the new build before and
after landing it (the version comes from git describe):

```bash
uv pip install --python .venv/bin/python --no-deps --no-build-isolation -e .
```

## Commits

One per area/theme: message plus a
`Co-Authored-By: OpenCode <noreply@opencode.ai>` trailer. `AI-Model:`
comes from `.opencode-model` via `scripts/git-hooks/commit-msg`. Keep
`opencode.json` and `.opencode-model` in sync with the models in use
(only the agent field takes a `#variant`). User-facing changes get a
`CHANGELOG.md` entry under Unreleased, with explicit **BREAKING** notes.

## Branches

Multi-file features, GUI/QML work and risky refactors land on a
short-lived branch off `main`; `main` stays untouched until the change is
approved. Trivial fixes and docs may commit to `main`. Integrate with
`git merge --squash` and one commit, then `git branch -D` and
`git push origin --delete`: a squash leaves the branch "unmerged" to git.
Push each batch; never rewrite pushed history or tags.

## Detailed references

Read the relevant one before the first change in that area:

- `docs/QML-NOTES.md` — Kirigami/QML rules and the QML test driver.
- `docs/DEVELOPMENT.md` — environment, tags and releases, packaging,
  AppImage.
- `docs/POLICIES.md` — config compatibility, XDG, deps, `-git` builds,
  Flatpak, CLI exit codes.
