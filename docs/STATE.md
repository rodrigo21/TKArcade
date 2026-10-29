# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` (the squash of
  `feature/settings-label-column` was approved and pushed; the branch was
  deleted locally). The tree is clean apart from the maintainer's
  uncommitted `pkgver` in `packaging/arch/tkarcade-git/PKGBUILD`, left
  out of the landing on purpose. The venv was refreshed at the end of the
  session.
- Landed, one squash — one label column per tab (the first item under
  "Settings and metadata" in `TODO.md`).
  - `WidgetsFormLayout` takes a `labelWidth` and pins Kirigami's internal
    grid to it: the leading spacer's min/pref/max and the buddies'
    maximum width. The field column's preferred width is the form width
    minus the label column, so QGridLayout's surplus sharing cannot grow
    the label column past its maximum; `onWidthChanged` reapplies.
  - `naturalLabelWidth` recomputes Kirigami's own column (`Math.ceil` per
    visible non-section buddy): `buddiesImplicitWidth` truncates to an
    int, which left a 1 px gap between sections.
  - Each tab's `ColumnLayout` declares `labelWidth: Math.max(...)` over
    its forms and every form binds it: General, Runtime (including the
    hand-written `Prefix`/`Debug` forms), Performance, Display, System
    and Artwork/Notes. Commands (`ppForm`) and `PrefsDialog` have a
    single form and keep their natural column; the Environment tab builds
    a form per row dynamically.
  - `test_settings_tabs_share_label_column` asserts exactly one field x
    per tab; `docs/QML-NOTES.md` carries the mechanism and why
    `twinFormLayouts` stays rejected.
- Verified: `scripts/check.sh` → 470 passed; `--qml` → 471 passed (the
  batch-abort warning re-runs cases in isolation, all pass); ruff clean.
  Offscreen screenshots at 756/612 px, one field x per tab: General 172,
  Commands 161, Runtime 133, Performance 176, Display 146, System 155,
  Artwork/Notes 158 — no elided labels, no overflow at 612 px, 0 QML
  warnings.
- Next concrete step: the views beyond the list (`TODO.md`, "Views beyond
  the list (icons and cards)"). The library is list-only today; `cover`
  is written, cleared and migrated but nothing renders it. The card's
  `Kirigami.Card` banner reads `gameIcon` (falls back to the source
  AppID's icon), not the cover, so giving the Cover slot a consumer and
  reviewing the banner framing is the core of the task. Also there: the
  Status row's long text wraps mid-sentence at the 612 px minimum
  ("…Use Fetch / Artwork.") next to a button with the same words. Read
  `docs/QML-NOTES.md` before the first QML change; the driver runs with
  `scripts/check.sh --qml`.
- After that: the artwork leftovers (per-game provider override,
  "Artwork Cleared" in the Status row).
- Open decision: the game taxonomy (`TODO.md`, "Game taxonomy and
  terminology") — Origin/Platform/Runner names and what `[general]
  environment` becomes. It was deferred again; the `Commands` rename
  only settles the tab label, not the model.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533, and Steam expands
  `tkarcade %command%` through PATH (the dialog warns about it). The
  PKGBUILD already pins `#branch=main`.
- Nothing blocking.
