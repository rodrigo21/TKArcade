# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, at the merge of `feature/drop-category-column` (now
  deleted): f0e1245 (drop the Category column) and 3ea0d31 (runtime
  rename to `[runtime] type`), plus this handoff. The maintainer's
  uncommitted `pkgver` in `packaging/arch/tkarcade-git/PKGBUILD` is still
  outside the commits. The venv was refreshed after the merge.
- Landed:
  - The library list dropped its Category column (`GameFilterModel` has
    11 view columns, `_DEFAULT_HIDDEN = {7, 8, 9, 10}`); `CategoryRole`
    still feeds the drawer filter, and the Game tab, bulk "Set
    Categories…" and `CategoryDialog` are untouched.
  - The stored runtime moved from `[general] environment` to
    `[runtime] type` (`RuntimeType` enum, `normalize_runtime()`,
    `runtime_label()`); the column, sort role and settings combo are
    `Runtime` (was `Runner`), and local choices read `Native`, `Wine`,
    `UMU`.
  - The matrix is explicit: Proton is Steam-exclusive and Wine/UMU are
    local-only; `runtime_label()` returns `""` for an invalid pairing and
    `runtime_problem()` makes the launcher exit 18 naming the valid
    choices. The settings combo only offers the origin's values.
  - Legacy `[general] environment` is a known-but-ignored key: it loads
    as unset and is dropped on the next save (no shim, pre-1.0);
    `game_type`/`platform` still ride along as unknown keys.
- Verified before the merge (content unchanged by the squash): the whole
  fast suite plus the QML driver → 471 passed; offscreen shot with every
  column visible (slot 8 `Runtime`, cells `Native`/`Wine`/`UMU`/`Not
  Set`, no clipping); translations 602 messages, 0 unfinished.
- Next: the views beyond the list (icons and cards) — the Cover slot
  still has no consumer; read `docs/QML-NOTES.md` first. Then the artwork
  leftovers and the categories redesign's remaining half.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
