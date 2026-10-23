# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean (`git log -1` for the tip).
- Last landed: context-hygiene pass — `scripts/check.sh` as the single
  dev gate, bounded QML failure reports, trimmed ambient docs, tighter
  `tool_output`/`compaction` caps.
- Next: `runtime.prefix_name` (friendly prefix directory name) is the
  only open decision; no queued task.
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose.
  Design docs go in `docs/plans/`.
