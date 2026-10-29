"""Documentation contract: one map, no history in TODO, frozen decisions.

`docs/README.md` is an ambient instruction (`opencode.json`), so every
session sees where each answer lives. These checks keep that route table
honest: a new document must be indexed, `TODO.md` stays open-only, the
landing records keep their banner, nothing points at the retired
`docs/plans/` directory and the ambient wiring survives.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
MAP = DOCS / "README.md"
DOCS_PLANS = "docs/plans"


def _map_text() -> str:
    return MAP.read_text(encoding="utf-8")


def _documents() -> list[Path]:
    return sorted(p for p in DOCS.rglob("*.md") if p != MAP)


def test_map_lists_every_document():
    text = _map_text()
    missing = [
        str(p.relative_to(DOCS)) for p in _documents() if str(p.relative_to(DOCS)) not in text
    ]
    assert not missing, f"not in docs/README.md: {missing}"


def test_map_paths_resolve():
    text = _map_text()
    broken = []
    for token in re.findall(r"`([^`]+)`", text):
        if not (token.endswith(".md") or token.endswith("/")):
            continue
        if not ((ROOT / token).exists() or (DOCS / token).exists()):
            broken.append(token)
    assert not broken, f"docs/README.md points at missing paths: {broken}"


def test_todo_has_no_finished_items():
    todo = (ROOT / "TODO.md").read_text(encoding="utf-8")
    done = re.findall(r"^\s*[-*]\s*\[[xX]\]", todo, re.MULTILINE)
    assert not done, "TODO.md carries finished items: history belongs to CHANGELOG.md and git"


def test_retired_plans_directory_is_gone():
    scanned = [
        *ROOT.glob("*.md"),
        *DOCS.rglob("*.md"),
        *ROOT.glob("scripts/*.sh"),
        *ROOT.glob("packaging/man/*"),
        *ROOT.glob("packaging/**/*.md"),
        *ROOT.glob(".opencode/**/*.md"),
        ROOT / "opencode.json",
    ]
    offenders = [
        str(p.relative_to(ROOT))
        for p in scanned
        if p.is_file() and DOCS_PLANS in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not offenders, f"references to the retired {DOCS_PLANS}/: {offenders}"


def test_decisions_are_marked_as_landing_records():
    unmarked = [
        p.name
        for p in sorted((DOCS / "decisions").glob("*.md"))
        if "Landing record" not in p.read_text(encoding="utf-8")
    ]
    assert not unmarked, f"decision records without the landing banner: {unmarked}"


def test_ambient_instructions_include_state_and_map():
    config = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    instructions = config["instructions"]
    assert "docs/STATE.md" in instructions
    assert "docs/README.md" in instructions
