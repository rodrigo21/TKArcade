# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's packaging churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed.
- Landed: thirty-five batches. The latest makes the AI token rules
  measurable: a working per-session query, a cost warning past ~60 steps
  or ~100k re-sent per step, and `/handoff` reporting the numbers.
- Verified: `tests/test_docs.py` (6 pass); docs-only, no code or test
  touched. Session cost: 70 steps, 3.4M cache read, US$ 0.
- Next: the `TODO.md` design-review items — the runtime version
  manager, then name-based artwork for local games, then the deferred
  research/release items.
- Nothing blocking.
