"""pt_BR catalog: complete, covering QML, and loadable at runtime."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS = ROOT / "translations" / "tkarcade_pt_BR.ts"
QML = ROOT / "src" / "tkarcade" / "gui" / "qml"

LITERAL = re.compile(r"""qsTr\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')""")


def _unescape(raw: str) -> str:
    # .ts stores resolved escapes (real newlines); decode like QML.
    try:
        return raw.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
    except Exception:
        return raw


def _qml_strings(path: Path) -> set[str]:
    out = set()
    for match in LITERAL.finditer(path.read_text(encoding="utf-8")):
        raw = match.group(1) if match.group(1) is not None else match.group(2)
        out.add(_unescape(raw))
    return out


def _catalog() -> dict[tuple[str, str], str]:
    tree = ET.parse(TS)
    out = {}
    for ctx in tree.getroot().findall("context"):
        name = ctx.findtext("name")
        for msg in ctx.findall("message"):
            tr = msg.find("translation")
            out[(name, msg.findtext("source"))] = (tr.text or "") if tr is not None else ""
    return out


def test_ts_has_no_unfinished():
    catalog = _catalog()
    empty = [k for k, v in catalog.items() if not v.strip()]
    assert empty == []


def test_ts_covers_qml_literals():
    catalog = _catalog()
    missing = [
        (context, source)
        for path in sorted(QML.glob("*.qml"))
        for context, source in ((path.stem, s) for s in sorted(_qml_strings(path)))
        if (context, source) not in catalog
    ]
    assert missing == []


def test_qm_loads_and_translates(qgui_app):
    from PySide6.QtCore import QCoreApplication

    from tkarcade.gui import i18n as i18nmod

    assert i18nmod.install_translations(qgui_app, "pt_BR") == "pt_BR"
    assert QCoreApplication.translate("MainPage", "Games") == "Jogos"
    assert QCoreApplication.translate("GameSettings", "Save") == "Salvar"
    assert [c for c, _label in i18nmod.available_languages() if c == "pt_BR"] == ["pt_BR"]
