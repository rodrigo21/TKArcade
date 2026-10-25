# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` after the Session History
  header merge (`7b89d41`, squashed from
  `fix/history-header-alignment`; the branch was deleted locally and on
  the remote). The tree is clean apart from the maintainer's
  uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed: the Session History header follow-up. All six titles are
  centred, the action column is named Actions, and its per-row Clear
  buttons draw a button frame. The QML test pins each header cell to
  the `x` and `width` of its row cell; the pt_BR catalog has `Ações`.
- Also landed: the GUI review batch — header sorting forces the table
  layout after the proxy sort; library columns 6–11 render their
  values; the Steam scan window measures the longest `name [appid]`;
  Preferences opens at 30/34 grid units; Validate Game shows the game
  name without the AppID prefixes; Tools → Clean Up Leftovers removes
  profiles, session log, Proton logs and history lines, with an optional
  prefix (never Steam `compatdata` or a shared prefix).
- Verified on the merged tree: fast suite 410 passed, 1 deselected; the
  branch run had the full suite 411 passed (one earlier run aborted in
  Qt teardown, the immediate rerun passed); ruff/format clean. Offscreen
  pixel check: header centres within 1 px, no truncation, Clear frame
  present. Venv refreshed after the merge at
  `0.0.0.post532.dev0+7b89d41`.
- Next concrete step: the game taxonomy and terminology research
  (priority in TODO), then the Preferences and Global Defaults content
  reviews.
- Open decisions: the taxonomy terms (Origin/Platform/Runner) wait for
  the Lutris/Faugus analysis in TODO.
- Nothing blocking.
