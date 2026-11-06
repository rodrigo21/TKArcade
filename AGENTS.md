# AGENTS.md — instructions for AI coding agents on TKArcade

TKArcade is a minimal Steam launch wrapper: per-game TOML configs,
a stdlib-first launcher CLI (`tkarcade %command%`) and a PySide6 GUI.
License: GPL-3.0-or-later.

## Communication

- Chat with the maintainer in Portuguese; code, docs, comments, commit
  messages and GUI strings in English.
- Short, factual, no superlatives. Surface disagreements honestly.
- Rename the session to the task in progress whenever the work moves to
  a new area.

## Changes require approval

Never create, edit, delete, stage, commit or push without the
maintainer's explicit approval. Investigate read-only, then present a
plan (files, exact edits, verification, risks) and wait for approval.

Commit only after the maintainer approves the implemented diff:
implement in the working tree, run the verification, show the diff and
stop. The approval covers that one commit. Never amend a commit that is
already there; a design change before the commit is a working-tree
change, not a history rewrite. Landing is a second gate: after the
branch commit and the venv refresh, stop and wait for the maintainer's
approval before squash-merging into `main`, pushing or running
`/handoff` (`docs/GIT.md`). If the scope changes mid-task, stop and ask
again.

## Work state

`docs/STATE.md`, `docs/README.md` and `docs/GIT.md` are ambient
instructions (`instructions` in `opencode.json`), so all three are
already in context: current branch, last landed change and next step;
the map of every document; and the branch/commit/push rules. Refresh
`STATE.md` with `/handoff` before stopping mid-task and after each
landing (`docs/GIT.md`); designs are
committed docs under `docs/decisions/`, never plan-mode scratch files
outside the repo.

## Context hygiene

Every request re-sends the whole session: ~90k tokens per step on
average, 116-184k in the marathon sessions and 17-38k in the short
ones. Cost grows with steps times context, not with the size of the
project.

- One theme per batch (normally one commit): `/handoff` after each
  landing/push; start a new session when the context budget calls for
  it (`docs/GIT.md`). A session that carries several features is the
  main way one reaches the context limit.
- Watch the cost, do not cap it: past ~60 steps, or when a step
  re-sends more than ~100k tokens, say so and prefer a new session for
  the next theme.
- Budget **~25 tool calls per commit**. Measure the newest session and
  the project totals:

  ```bash
  sqlite3 -readonly "${XDG_DATA_HOME:-$HOME/.local/share}/opencode/opencode.db" \
    "select round(tokens_cache_read/1e6,1) from session_v2
     where directory like '%TKArcade%' order by time_updated desc limit 1"
  opencode stats --project . --cost --standalone
  ```

  The stats command needs `--standalone`: without it, it fails unless a
  server is running. `/handoff` reports the session numbers.
- Batch independent calls in one turn. Never re-run a check that already
  passed without a code change since.
- A file already read is in context: read it again only after it
  changed on disk, otherwise edit the text you have.
- Never dump a whole file, binary or large diff: `grep`, `sed -n`,
  `tail`, `git diff --stat`. `strings` on a binary is banned. Test files
  are large: grep the case name, and a test run ends in `tail -3`.
  Broad searches go through the `explore` subagent.
- Visual checks (offscreen screenshots) run in a subagent or a short
  session: a screenshot stays in context as base64.

## Invariants

The launcher (`launcher.py`, `config.py`, `backends/`, `proton.py`,
`steam.py`, `xdg.py`, `nightlight_holder.py`, `winetricks.py`) stays
**stdlib-first**: it runs on every game start and may import `vdf`
(pure Python, a runtime dependency of the package) to read Steam
files. Any other third-party import on the launch path needs its own
decision; PySide6/jeepney stay GUI/helper-only.

## Verify before finishing

```bash
pytest tests/test_<module>.py -k <case>   # the case being fixed
scripts/check.sh --changed               # the modules git shows as touched
scripts/check.sh                         # whole fast suite (~15s), before approval
scripts/check.sh --qml                   # + QML driver (~60s), once per task
```

Run the smallest check that covers the edit while iterating — single
case, then `--changed` — and the full suite **once per approval round**,
on the diff that goes to the maintainer. The maintainer approves a
verified diff; do not spend the whole suite on every small correction,
and never commit or claim a pass without having run the check yourself.
`--changed` widens to the whole fast suite when a touched file has no
test module of its own, so it never skips a change silently. The full
suite with the QML driver runs once per task and whenever QML or the
tests changed; a single case runs with
`pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"`,
plus `--tb=long` when a fixture hides the frame. The suite must pass with
and without `pytest-qt`; never monkeypatch Qt globals at fixture scope
(patch inside the test body). A change that renders something new or
differs visually (layout, label, visibility, style) needs an offscreen
screenshot check; logic behind unchanged QML (model, clipboard plumbing)
is covered by tests instead.

Tests and GUI smoke checks run with temporary XDG/HOME dirs (the
`xdg_env` fixture for pytest), never the maintainer's real config,
prefix or Steam library. Report any check that could not run or does
not cover the change; never claim it passed.

Refresh the local venv after the commit on the branch and again after
the merge, so the maintainer can test the new build before and after
landing it. The version comes from `git describe`, so a refresh taken
before the commit carries the previous hash:

```bash
uv pip install --python .venv/bin/python --no-deps --no-build-isolation -e .
```

The GUI's Play path runs the interpreter that owns it, so the venv is
the build under test: refresh it after every change, before committing,
or the maintainer tests a stale install.

## Git

`docs/GIT.md` (ambient) is the single source for branch, commit, merge
and push rules. Non-negotiables:

- One theme per batch. Multi-file features, GUI/QML work and risky
  refactors land on a short-lived branch off `main`; `main` stays
  untouched until approval. Trivial fixes and docs may commit to `main`.
- Squash-merge the branch into one commit, delete it locally and
  remotely, push each batch, and never rewrite pushed history or tags.
- Stage explicit paths: the maintainer's `pkgver` churn in
  `packaging/arch/tkarcade-git/PKGBUILD` stays out of commits, so never
  `git add -A` or `git add .`.
- Review the full diff before each commit; never discard uncommitted
  work or commit secrets/machine-local data (`docs/GIT.md`).
- Commits carry `Co-Authored-By` + `AI-Model` through the local hook;
  keep `opencode.json` and `.opencode-model` in sync. User-facing
  changes get a `CHANGELOG.md` entry under Unreleased, with explicit
  **BREAKING** notes.

## Document routing

Read the triggered document **before** the first change in that area;
`docs/README.md` (ambient) is the exhaustive index behind this table.

| Before you touch | Read |
| --- | --- |
| a branch, commit, merge or push | `docs/GIT.md` |
| config keys, launch order, exit codes, XDG paths | `docs/POLICIES.md`, then `README.md` ("Local games", "Config files") |
| any `.qml`, or a QML test | `docs/QML-NOTES.md` |
| GUI strings or translations (`.ts`/`.qm`) | `docs/DEVELOPMENT.md` |
| tests, venv, packaging, tags/releases, AppImage | `docs/DEVELOPMENT.md` |
| new dependencies, Steam-owned files, save/backup integration, packaging recipes | `docs/POLICIES.md` |
| a design question ("why is it like this?") | `docs/decisions/` through `docs/README.md` |
| what is still open | `TODO.md` |
| a release display check | `docs/runbooks/real-display-checks.md` |
| session state, handoff | `docs/STATE.md` |

User-facing CLI flags, config keys and exit codes also update
`README.md` and `packaging/man/tkarcade.1` in the same commit.

A change that makes a document wrong updates it in the same commit:
`tests/test_docs.py` fails when a document is missing from the map, a
`TODO.md` item is finished, a decision loses its landing banner or a
link points at the retired plans directory.
