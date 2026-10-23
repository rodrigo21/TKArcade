# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, clean, in sync with `origin/main`.
- Last landed: context-hygiene pass — `scripts/check.sh` as the single
  dev gate (`--changed` selects the test modules git reports, `--qml`
  runs the full suite, bare paths replace the default; an unmatched file
  widens to the fast suite), bounded QML failure reports with
  `/tmp/tkarcade-qml-fail-*.log` for the full output, `--tb=short` by
  default, trimmed ambient docs (`AGENTS.md` ~3.8 KB), `tool_output`
  120 lines/8 KB, compaction keep 10k, `webfetch`/`websearch` denied,
  and a per-commit tool-call budget in `AGENTS.md`.
- Verified: 381 tests fast (17.5s) and 382 with the QML driver (92.8s)
  via `scripts/check.sh` / `--qml`, ruff check and format clean; the
  selective gate picked 3 modules/147 tests in 1.5s for a config+backends
  change. Trimming the tool catalog further was tried and dropped:
  `permission` accepts a closed action set and `tools` (deprecated) does
  not remove the built-in helper tools.
- Next: nothing queued. `runtime.prefix_name` (friendly prefix directory
  name) is the only open decision; designs go in `docs/plans/`.
- Nothing blocking. The `-git` PKGBUILD `pkgver` stays dirty on purpose
  and is never committed as part of a work-state update.
