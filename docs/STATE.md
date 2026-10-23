# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `block-internet` (short-lived, not merged yet); the only
  dirty file besides the feature is the `-git` PKGBUILD `pkgver`, left
  uncommitted on purpose.
- Last landed on the branch: Block Internet per game
  (`[network] block_internet`). The launcher wraps the game innermost in
  `unshare -Urn -- <game>`: a user namespace (no root) plus a network
  namespace with no route, DNS or interface except a loopback that is
  never brought up. Ludusavi cloud restore/backup and the pre/post hooks
  stay outside and keep their network. When the host forbids
  unprivileged user namespaces the launcher refuses (exit 14) instead
  of going online; `--validate` reports it (exit 17). The option lives
  in Settings → System → Network, with a red hint when the host cannot
  build the namespace. Risk matrix and decisions:
  `docs/plans/network-isolation.md`.
- Verified on the branch: `scripts/check.sh --qml` 401 passed, ruff
  check and format clean, `refresh-translations.sh` 0 untranslated
  (pt_BR strings added), offscreen screenshots of the Network section
  and of the unavailable-hint variant showed no clipping, overlap or
  QML warnings. A pytestqt teardown segfault (leftover model timers
  firing during the QML driver) was fixed by stopping/ deleting the
  model in `test_model_running_role_and_terminate`.
- Also complete (landed earlier): the Add game flow, the `.exe` hint,
  the running indicator and Terminate action.
- Next: the remaining deferred `TODO.md` item — the vkBasalt successor
  (vkBasalt is unmaintained; evaluate forks or ReShade-on-Linux when
  mature), or whatever the maintainer asks for. New branch off `main`;
  read `docs/POLICIES.md` first.
- Open decisions: none for the running indicator or block_internet.
  Nothing blocking.
