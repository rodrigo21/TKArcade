# Documentation map

What each document is for and where the source of truth lives.

| Question | Document |
| --- | --- |
| What TKArcade does and how to use it | `README.md` (repository root) |
| What changed, and when | `CHANGELOG.md` and the git history |
| Current config keys and launch behaviour | `README.md` ("Local games", "Config files") and `src/tkarcade/config.py` |
| Standing project decisions | `POLICIES.md` |
| Open work | `TODO.md` |
| Current session state (ambient) | `STATE.md` |
| QML/Kirigami rules learned the hard way | `QML-NOTES.md` |
| Dev environment, tests, packaging, releases | `DEVELOPMENT.md` |
| Why a landed design is the way it is | `decisions/` (frozen landing records) |
| Manual display checks before a release | `runbooks/real-display-checks.md` |

## Rules

- `TODO.md` is the open list only. Finished work goes to `CHANGELOG.md`
  and git; standing decisions go to `POLICIES.md`.
- `STATE.md` and this map are the only ambient documents (injected
  through `opencode.json`), so an agent always knows where each answer
  lives without searching: keep both short and refresh `STATE.md` with
  `/handoff`.
- `AGENTS.md` routes by trigger ("before touching X, read Y"); this map
  is the exhaustive index behind it.
- `decisions/` are frozen landing records: they describe the state at
  landing, not necessarily today's behaviour. Correct them only when
  the rationale or the historical record is wrong; current behaviour
  belongs in `README.md`/`CHANGELOG.md`.
- `runbooks/` are procedures, not designs; keep them executable.
- A change that makes a document wrong updates it in the same commit.
  `tests/test_docs.py` enforces the rules above: every document must be
  listed here, `TODO.md` cannot carry a finished item, every decision
  keeps its landing banner, and nothing may point at the retired plans
  directory (its content moved to `decisions/` and `runbooks/`).

## Decisions

- `decisions/game-taxonomy.md` — Origin/Platform/Runtime axes and the
  `[runtime]` key.
- `decisions/settings-reorg.md` — the seven-tab game dialog and the
  merged runtime config.
- `decisions/prefix-name.md` — local prefix base and `<base>/<folder>`
  resolution.
- `decisions/network-isolation.md` — per-game `unshare -Urn` and its
  failure policy.
- `decisions/running-indicator.md` — running records, signal forwarding
  and Terminate.
