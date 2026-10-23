# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `casing-audit`, one signed commit on top of `add-game-flow`,
  both pushed to origin (added with a plain `git push -u`, no
  force). `add-game-flow` must land before this one, and it still
  awaits the maintainer's approval.
- Last landed: the capitalization audit. Every QML label, button, menu
  entry, dialog title, checkbox, column and status message is Title
  Case, and so is the pt_BR catalog (capitalize content words, lowercase
  pt articles/prepositions). Tool names keep their spelling (`wine`,
  `umu-run`, `winetricks`, `vkd3d-proton`, `logind`,
  `compatibilitytools.d`, `MangoHud`, `DXVK`), flags and paths stay
  verbatim, `(s)`/`(ies)` plural markers stay lowercase. The same pass
  hit the status messages the GUI model builds in Python
  (`gui/model.py`, not translated) and the tray menu.
- Verified: 384 passed under `scripts/check.sh --qml`, ruff check and
  format clean, `refresh-translations.sh` reports 0 untranslated,
  offscreen screenshots of the main page, Add dialog, all eight Settings
  tabs and Preferences show no clipped or overlapping text.
- Next: the two branches land (squash `add-game-flow`, then
  `casing-audit`), then the deferred items in `TODO.md` ("After
  game-types": running indicator and Terminate action).
- Nothing blocking.
