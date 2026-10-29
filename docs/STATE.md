# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` (`5c3bf22`, the squash of
  `feature/settings-decisions`, plus this STATE refresh). The tree is
  clean apart from the maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD`, plus the `.SRCINFO`/src
  `.tar.gz` build leftovers next to it. The venv was refreshed from this
  commit.
- Landed three decisions the maintainer took in the previous session,
  one squash:
  - **Steam Linux Runtime for local native games.** `[runtime]
    steam_runtime = ""|scout|soldier|sniper|steamrt4` (`STEAM_RUNTIMES`,
    `normalize_steam_runtime()`, `steam_runtime_label()` in
    `config.py`), applied only by `launcher._steam_runtime_for()` (Local
    + `native`). `_wrap_steam_runtime` prepends `umu-run` and
    `_steam_runtime_env` sets `PROTONPATH=umu-<name>` +
    `GAMEID=tkarcade-<appid>`, with no WINEPREFIX and no graphics layer.
    A runtime umu has not downloaded yet is a hint in the dialog
    (`gameModel.steamRuntimeState`) and a `(note)` line in `--validate`
    (`launcher.validate_notes`), never an issue — `docs/POLICIES.md`
    records that the exit-14 contract no longer covers it. The combo
    shows the full name, the Runner column `runner_label()`'s short
    "Steam Runtime (sniper)". Verified end to end with the local
    `steamrt4` (umu: "steamrt4 is up to date", game exit 0).
  - **`Environment` tab is `Commands`** (env vars + pre/post hooks); the
    `[general] environment` field on the Runtime tab keeps its label. No
    config key moved. `SETTINGS_TAB_TITLES`/`TAB_COMMANDS` in the QML
    driver follow.
  - **Winetricks for a Steam game with a custom `[runtime] prefix`**
    (protontricks cannot target it): the game's Proton (explicit
    `[runtime] tool`, else `proton.compat_tool_name`) supplies `WINE`
    and `<custom>/pfx` is the WINEPREFIX;
    `winetricks.PROTON_ENVIRONMENTS` treats `proton` like `umu`, and the
    dialog button reads `Winetricks…` in that case.
- Also fixed in the same landing: both Runtime hints sit in a shrinkable
  `RowLayout`, so they wrap inside the frame at the 612 px minimum width
  (as bare form items the long text was cut mid-word); the QML case
  asserts it.
- Verified: `scripts/check.sh` → 470 passed, `--qml` → 471 passed, ruff
  check/format clean, translations refreshed (601 finished, pt_BR
  included), README/man/CHANGELOG updated. Offscreen screenshots at 756
  and 612 px: `Commands` fits the tab bar, a Steam game shows no
  `Steam Runtime:` row, labels and fields stay aligned in both widths.
  The only elision at 612 px is the pre-existing `Artwork/No…` tab. The
  squash has the same tree as the branch, so these runs still hold.
- Next concrete step: `TODO.md` in order — the icons/cards views (the
  list is done); then the artwork leftovers: per-game provider override
  and "Artwork Cleared" in the Status row.
- Open decision: the game taxonomy (`TODO.md`, "Game taxonomy and
  terminology") — Origin/Platform/Runner names and what `[general]
  environment` becomes. It was deferred again; the `Commands` rename
  only settles the tab label, not the model.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533, and Steam expands
  `tkarcade %command%` through PATH (the dialog warns about it). The
  PKGBUILD already pins `#branch=main`.
- Nothing blocking.
