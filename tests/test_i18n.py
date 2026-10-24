"""pt_BR catalog: complete, covering QML and the tray menu, loadable."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS = ROOT / "translations" / "tkarcade_pt_BR.ts"
QML = ROOT / "src" / "tkarcade" / "gui" / "qml"
TRAY = ROOT / "src" / "tkarcade" / "gui" / "tray.py"

LITERAL = re.compile(r"""qsTr\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')""")
TRANSLATE = re.compile(
    r"""QCoreApplication\.translate\(\s*"([^"]*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)"""
)


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


def _py_strings(path: Path) -> set[tuple[str, str]]:
    """(context, source) from QCoreApplication.translate() literals."""
    return {
        (m.group(1), _unescape(m.group(2)))
        for m in TRANSLATE.finditer(path.read_text(encoding="utf-8"))
    }


def _messages() -> list[tuple[str, ET.Element]]:
    """(context, message) for every entry in the catalog."""
    return [
        (ctx.findtext("name"), msg)
        for ctx in ET.parse(TS).getroot().findall("context")
        for msg in ctx.findall("message")
    ]


def _catalog() -> dict[tuple[str, str], str]:
    out = {}
    for name, msg in _messages():
        tr = msg.find("translation")
        out[(name, msg.findtext("source"))] = (tr.text or "") if tr is not None else ""
    return out


def test_ts_has_no_unfinished():
    """No empty text and no leftover lupdate flag: lrelease would carry both."""
    empty = [key for key, text in _catalog().items() if not text.strip()]
    assert empty == []
    unfinished = [
        (name, msg.findtext("source"))
        for name, msg in _messages()
        if (tr := msg.find("translation")) is not None and tr.get("type") == "unfinished"
    ]
    assert unfinished == []


def test_ts_covers_qml_literals():
    catalog = _catalog()
    missing = [
        (context, source)
        for path in sorted(QML.glob("*.qml"))
        for context, source in ((path.stem, s) for s in sorted(_qml_strings(path)))
        if (context, source) not in catalog
    ]
    assert missing == []


def test_ts_covers_python_translate_literals():
    """The tray menu is the one Python-translatable spot: keep it covered."""
    catalog = _catalog()
    literals = _py_strings(TRAY)
    assert literals, "no QCoreApplication.translate() literals found in tray.py"
    missing = sorted(literal for literal in literals if literal not in catalog)
    assert missing == []


def _drop_installed(app) -> None:
    """Uninstall what install_translations() left on the app.

    A translator is process-wide and outlives the test, so a later test
    asserting source strings (the tray menu) would see pt_BR instead.
    """
    from tkarcade.gui import i18n as i18nmod

    for installed_app, translator in list(i18nmod._translators):
        if installed_app is app:
            app.removeTranslator(translator)
    i18nmod._translators.clear()


def test_qm_loads_and_translates(qgui_app):
    from PySide6.QtCore import QCoreApplication

    from tkarcade.gui import i18n as i18nmod

    assert i18nmod.install_translations(qgui_app, "pt_BR") == "pt_BR"
    try:
        assert QCoreApplication.translate("MainPage", "Games") == "Jogos"
        assert QCoreApplication.translate("GameSettings", "Save") == "Salvar"
        assert QCoreApplication.translate("TrayMenu", "Show / Hide") == "Mostrar / Ocultar"
        assert [c for c, _label in i18nmod.available_languages() if c == "pt_BR"] == ["pt_BR"]
    finally:
        _drop_installed(qgui_app)
