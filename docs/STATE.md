# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `running-indicator`, commit `fb60907` (not merged yet); the
  only dirty file is the `-git` PKGBUILD `pkgver`, left uncommitted on
  purpose.
- Last landed on the branch: the running indicator and Terminate action.
  The launcher writes `$XDG_STATE_HOME/tkarcade/running/<appid>.json`
  (PID plus start time) before the game and removes it on exit; the GUI
  polls every 2 s and offers Terminate in the context menu and on the
  card. Terminate SIGTERMs the launcher, which forwards the signal to
  the game's process group (wrappers included), stays alive for the
  display/audio/nightlight cleanup, and the GUI escalates to SIGKILL
  after 10 s. Design and out-of-scope notes: `docs/plans/running-indicator.md`.
- Verified on the branch: `scripts/check.sh --qml` 396 passed (the one
  pre-existing QML-batch isolation warning), ruff check and format
  clean, `refresh-translations.sh` 0 untranslated. The first full run
  segfaulted in pytestqt's event loop; the fix stops the model's timers
  on `destroyed` and guards the timer callbacks with a closing flag.
- Next: the two deferred items in `TODO.md` — Block Internet per game
  (net namespace, unprivileged) and the vkBasalt successor (vkBasalt is
  unmaintained; evaluate forks). Both are deferred research; pick one
  when asked. New branch off `main`; read `docs/POLICIES.md` first.
- Open decisions: none for the running indicator (recorded in the
  plan). The Add game flow and the `.exe` hint are complete and tested.
- Nothing blocking.
