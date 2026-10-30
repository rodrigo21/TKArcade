# Git workflow (single source)

Branch, commit, merge and push rules live here. `AGENTS.md` keeps a
short checklist, `DEVELOPMENT.md` covers tags/releases and
`POLICIES.md` covers packaging exceptions; if any of them disagrees
with this file, this file wins and the other document must be fixed.

This file is ambient (`instructions` in `opencode.json`), so every
session has the rules in context.

## 1. Start

- Read `git status --short` and the recent log before touching git:
  know the branch and every dirty file.
- The maintainer's `pkgver` churn in
  `packaging/arch/tkarcade-git/PKGBUILD` stays dirty and out of
  commits. Never use `git add -A` or `git add .`: stage explicit paths.
- Multi-file features, GUI/QML work and risky refactors land on a
  short-lived branch off `main` (`git switch -c <theme> main`);
  `main` stays untouched until the change is approved. Trivial fixes
  and docs-only changes may commit on `main`.
- One theme per session. If the work moves to another area, stop,
  hand off and start a new session.

## 2. Commit

- One commit per area/theme. A feature branch may carry several working
  commits; `main` receives exactly one squash commit when it lands.
- Refresh the venv before committing (version comes from
  `git describe`):
  `uv pip install --python .venv/bin/python --no-deps --no-build-isolation -e .`
- Message: `type(scope): imperative summary` (Conventional Commits,
  summary under 70 characters), plus a body explaining the *why* when
  it is not obvious.
- The local `commit-msg` hook adds `Co-Authored-By: OpenCode` and
  `AI-Model:` from `.opencode-model`; keep `opencode.json` and
  `.opencode-model` in sync with the models actually used.
- Sign with GPG when pinentry answers (`git commit -S`). Never bypass a
  failing hook or signing check (`--no-verify`, `--no-gpg-sign`).
- User-facing changes get a `CHANGELOG.md` entry under Unreleased, with
  explicit **BREAKING** notes.
- A change that makes a document wrong updates it in the same commit.
  `tests/test_docs.py` enforces the document map and the open-only
  `TODO.md`.

## 3. Land and push

1. `git switch main`.
2. `git merge --squash <branch>` and commit the result as one commit.
3. `git branch -D <branch>`; if the branch exists on the remote,
   `git push origin --delete <branch>`. A squash leaves the branch
   "unmerged" to git, so the delete is expected.
4. Before deleting a feature branch, point the `-git` PKGBUILD pin back
   at `main` (`POLICIES.md`).
5. Refresh the venv again after the merge, so the local build matches
   the landed version.
6. `git push origin main`. Push each batch; never rewrite pushed
   history or tags, and never force-push.

After the push, run `/handoff` (refresh and commit `docs/STATE.md`),
then re-enter plan mode for the next theme (`AGENTS.md`); start a new
session when the context budget calls for it.

## 4. Tags and releases

Only when the maintainer opens the subject. Tags are `vVER` (annotated,
signed); releases are `VER` with CHANGELOG notes. The release pass also
updates the release PKGBUILD, commits the current `-git` PKGBUILD and
runs the display checks; see `DEVELOPMENT.md` and `POLICIES.md`.

## 5. Handoff state

- `docs/STATE.md` records the branch, whether the tree is clean, what
  landed, verification numbers, the next concrete step and blockers.
  No commit hash (it changes on every commit) and no history.
- PKGBUILD `pkgver` churn is never recorded as work.
- The handoff commit (`docs: update the work state`) closes the landing
  batch; push it when the branch is already on the remote.
