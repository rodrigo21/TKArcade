# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `add-game-flow`, two commits ahead of `main`, in sync with
  `origin/add-game-flow`, working tree clean (the only dirty file is the
  `-git` PKGBUILD `pkgver`, left uncommitted on purpose). Not merged:
  `main` awaits the maintainer's approval.
- Last landed: the Add game flow and the `.exe` hint. `AddDialog` keeps
  `Steam Game` / `Local Game` and, for local games, a labelled Game Type
  combo that preselects the same field in Settings
  (`openNewGameSettings` → `openNew(gameType)`); the type stays editable
  and saves as usual. Settings (Launch tab, under the executable) warns
  when a `.exe`/`.bat`/`.msi` runs as Linux native, with `Switch to
  Wine` (local) or `Switch to Proton` (Steam): it only changes the combo
  and never blocks saving. New strings translated in pt_BR.
- Verified: 384 passed under `scripts/check.sh --qml`, ruff check and
  format clean, offscreen screenshots of the Add dialog and the hint row
  (no clipping, rows aligned), `.venv` reinstalled. Nothing code-side
  changed since, so nothing was re-run.
- Next: the capitalization audit (TODO "Add game flow and casing", last
  item) in a new session and branch — Title Case for labels, buttons,
  menus, titles and columns, sentence case kept for tooltips/info text,
  tool names unchanged, pt_BR catalog carried over before
  `refresh-translations.sh`.
- Open decisions for that audit: placeholders (`empty = …`, `e.g. …`)
  stay lowercase (recommended), and whether Title Case reaches the pt_BR
  translations (recommended: keep them sentence case).
- Nothing blocking.
