# Running indicator and Terminate

Status: implemented on `running-indicator` (2026-10-23).

Goal: the GUI shows which game is running and can stop it, without
taking ownership of the process and without leaving the desktop on the
game's resolution or audio sink.

## Decisions (the open questions in `docs/STATE.md`)

**Where the record lives.** One JSON file per game under the XDG state
dir next to the logs: `$XDG_STATE_HOME/tkarcade/running/<stem>.json`,
holding `appid`, `pid` (the launcher's), `start` (`/proc/<pid>/stat`
field 22) and the wall-clock `started`. A lock or socket would add
lifetime problems (a killed launcher leaves the lock held, a socket has
nothing to say while the game runs) and nothing here needs mutual
exclusion: the record is a fact, not a reservation. The start time
turns the PID into an identity, so a reused PID cannot be signalled or
reported as running.

**Cleaning up.** The launcher writes the record right before it spawns
the game and removes it in the `with` block, so a normal exit, an error
path and a Terminate all clear it. A launcher that dies without cleanup
(SIGKILL, OOM) leaves the file behind; `sweep()` drops records whose
process is gone or whose start time no longer matches, and runs both at
launcher start and on every GUI poll.

**What Terminate signals.** SIGTERM to the launcher's PID only. The
launcher installs handlers for SIGTERM/SIGINT/SIGHUP before it writes
the record, forwards the first one to the game's whole process group
(where the wrappers and the game live) and ignores repeats, so it stays
alive to restore the display, audio and nightlight sessions and to
write the history line. The GUI escalates to SIGKILL of the same
process group after ten seconds (`TERMINATE_GRACE_MS`), guarded by the
start-time identity check.

**How the indicator updates.** The GUI polls the directory every two
seconds (small files, `QTimer`). A file watcher would react faster but
misses a replaced or recreated directory and needs the same poll as a
safety net; two seconds is well below what a user notices and costs
nothing.

## Shape

- `src/tkarcade/running.py` (stdlib only): record file helpers
  (`Record`, `read`, `list_running`, `sweep`), identity (`is_alive`),
  `forward_signals` for the launcher and `terminate`/`kill` for the GUI.
- `launcher._run_game_process`: `Popen` + `proc.wait()` instead of
  `subprocess.run`, wrapped in `forward_signals` and `Record`.
- `gui/model.py`: `RunningRole`/`gameRunning`, `runningIds` (the
  notifying dependency for QML bindings), `isRunning`, `terminate`,
  `terminateReported`, poll timer and the escalation timer.
- QML: terminator in the game context menu and on the card, a small
  play glyph in the table's name column, "Running" in place of the
  played time in the icons and cards views.

## Out of scope

Refusing a second launch of a game that is already running (the record
is overwritten and the first launcher then clears it early); stopping a
Steam game launched without the wrapper (no launcher, no record);
per-game process stats.
