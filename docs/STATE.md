# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's `pkgver` churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed.
- Landed: fifty-two batches. The latest replaced artwork storage: every
  imported image (URL, picked file, `.exe` icon, provider download) is
  decoded by Qt and written in the format set under Preferences →
  Artwork → Stored Images (`[ui] artwork_format`/`artwork_quality`; auto
  is AVIF q85, then WebP/JPEG at 90, then PNG). Icons never use JPEG and
  are capped at 1024 px. An executable icon keeps the best ICO frame
  (PNG extracted, BMP reordered, versioned sidecar), beats a donor
  AppID's official Steam art, and a 32 px official icon is upgraded from
  SteamGridDB once. Re-encode Existing Artwork rewrites the cache and
  the manual slots; the maintainer's cache was re-encoded (36 files, 0
  failures), so only the generated `*-exe.png/ico` stay outside the
  format. Record: CHANGELOG.
- Verified: `scripts/check.sh --qml` (800 passed, 3 skipped), ruff check
  and format clean, and an offscreen shot of the Preferences Artwork
  page with the new Stored Images section. The venv was refreshed after
  the merge.
- Next: the maintainer's tag changes (the follow-up promised after the
  Tags lock), then the library import. The VNDB release picker sits in
  `TODO.md` before 1.0. Open follow-up: after the import, decide whether
  categories derive from tags, whether the tags get a filter/editor and
  whether a bulk download is worth it. Epic/GOG is 2.0, and so is the
  IGDB per-user credential review (`TODO.md`). The 1.0 visual pass, the
  packaging check, the shim removal and the release pass wait for the
  maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none block the next theme.
  `docs/plans/epic-gog-sources.md` is parked for 2.0 with its own four
  decisions (scope, discovery, launch, import UI).
- Nothing blocking.
