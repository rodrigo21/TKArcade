#!/usr/bin/env python3
"""Extract tr() messages from the GUI into a Qt Linguist .ts file.

Covers self.tr("...") / self.tr(f"...") in classes (context = class
name) and QCoreApplication.translate("Ctx", "...") anywhere (explicit
context). f-string placeholders become {} for translators. Re-run
after adding UI strings; new messages land as unfinished.
"""

from __future__ import annotations

import ast
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "tksteamlaunch" / "gui"


def _source_text(node: ast.expr) -> str | None:
    """Literal (or f-string with {} holes) or None when dynamic."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                parts.append("{}")
            else:
                return None
        return "".join(parts)
    return None


class Visitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stack: list[str] = []
        self.messages: list[tuple[str, str, str, int]] = []  # (ctx, src, file, line)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _record(self, context: str, node: ast.expr) -> None:
        text = _source_text(node)
        if text is None:
            print(f"warn: dynamic tr() arg skipped at {self.path}:{node.lineno}", file=sys.stderr)
        elif text:
            rel = str(self.path.relative_to(ROOT))
            self.messages.append((context, text, rel, node.lineno))

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "tr"
            and isinstance(func.value, ast.Name)
            and func.value.id == "self"
            and node.args
            and self.stack
        ):
            self._record(self.stack[-1], node.args[0])
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "translate"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            self._record(node.args[0].value, node.args[1])
        self.generic_visit(node)


def main() -> int:
    out = ROOT / "translations" / "tksteamlaunch_pt_BR.ts"
    previous: dict[tuple[str, str], str | None] = {}
    if out.exists():
        old = ET.parse(str(out)).getroot()
        for ctx in old.findall("context"):
            name = ctx.findtext("name") or ""
            for msg in ctx.findall("message"):
                src = msg.findtext("source") or ""
                tr = msg.find("translation")
                text = (tr.text or "") if tr is not None else ""
                if text.strip():
                    previous[(name, src)] = text
    found: dict[tuple[str, str], list[tuple[str, int]]] = {}
    order: list[tuple[str, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        visitor = Visitor(path)
        visitor.visit(ast.parse(path.read_text(), filename=str(path)))
        for context, source, rel, line in visitor.messages:
            key = (context, source)
            if key not in found:
                found[key] = []
                order.append(key)
            found[key].append((rel, line))
    ts = ET.Element("TS", version="2.1", language="pt_BR")
    contexts: dict[str, ET.Element] = {}
    for context, source in order:
        if context not in contexts:
            el = ET.SubElement(ts, "context")
            ET.SubElement(el, "name").text = context
            contexts[context] = el
        msg = ET.SubElement(contexts[context], "message")
        for rel, line in found[(context, source)]:
            ET.SubElement(msg, "location", filename=rel, line=str(line))
        ET.SubElement(msg, "source").text = source
        tr = ET.SubElement(msg, "translation")
        if (context, source) in previous:
            tr.text = previous[(context, source)]
        else:
            tr.set("type", "unfinished")
    out.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(ts)
    ET.indent(tree, space="    ")
    tree.write(out, encoding="utf-8", xml_declaration=True)
    print(f"{len(order)} messages -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
