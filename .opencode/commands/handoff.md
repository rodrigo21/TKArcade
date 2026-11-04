---
description: Refresh docs/STATE.md and commit it
agent: build
---
Update the work-state file so a fresh session can pick up where this
one stopped.

1. `git log --oneline -5`, `git status --short` and, when code changed
   since the last recorded state, the verification commands from
   `AGENTS.md`. Do not re-run the full suite if nothing changed. Git
   rules are in `docs/GIT.md`.
2. Rewrite the bullets in `docs/STATE.md`: current branch and whether it
   is clean (no commit hash — it changes on every commit), what landed,
   what was verified (with the numbers), the next concrete step, open
   decisions, anything blocking. Keep the header paragraph
   and the "keep it short" character of the file intact — no history,
   no narrative, that belongs in `CHANGELOG.md` and git. Never record
   the `-git` PKGBUILD `pkgver` churn as work: it stays uncommitted.
   If a document was added, moved or retired this session, update
   `docs/README.md` (the ambient map) in the same pass.
   The "Landed" bullet is at most 3 lines: what changed and its effect.
   Do not narrate the previous batch or copy `CHANGELOG.md`: history
   lives there and in git, and `docs/STATE.md` is re-sent on every
   request. "Verified" carries this batch's numbers only.
3. Commit only `docs/STATE.md` (plus any other file this command
   changed) with the message `docs: update the work state`, then push
   it if the branch is already on the remote.
4. Report the session cost in one line, from the newest row:

   ```bash
   sqlite3 -readonly "${XDG_DATA_HOME:-$HOME/.local/share}/opencode/opencode.db" \
     "select (select count(*) from session_message m where m.session_id=s.id and m.type='assistant')||' steps, '||round(s.tokens_cache_read/1e6,1)||'M cache read, '||round(s.cost,2)||' USD' from session_v2 s where s.directory like '%TKArcade%' order by s.time_updated desc limit 1;"
   ```
