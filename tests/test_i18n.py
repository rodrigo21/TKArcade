"""i18n workflow: every tr() literal has a .ts entry (all translated)."""

import ast
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _load_extractor():
    spec = importlib.util.spec_from_file_location(
        "extract_messages", ROOT / "scripts" / "extract-messages.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ts_entries():
    tree = ET.parse(str(ROOT / "translations" / "tkarcade_pt_BR.ts"))
    return {
        (ctx.findtext("name"), (msg.findtext("source") or "")): (msg.find("translation").text or "")
        for ctx in tree.getroot().findall("context")
        for msg in ctx.findall("message")
    }


def test_all_tr_literals_translated():
    ext = _load_extractor()
    entries = _ts_entries()
    assert len(entries) > 300
    missing, untranslated = [], []
    for path in sorted((ROOT / "src" / "tkarcade" / "gui").rglob("*.py")):
        visitor = ext.Visitor(path)
        visitor.visit(ast.parse(path.read_text(), filename=str(path)))
        for context, source, _rel, _line in visitor.messages:
            if (context, source) not in entries:
                missing.append(f"{context}: {source}")
            elif not entries[(context, source)].strip():
                untranslated.append(f"{context}: {source}")
    assert not missing, missing[:5]
    assert not untranslated, untranslated[:5]


def test_shipped_qm_covers_ts():
    shipped = {p.stem for p in (ROOT / "src" / "tkarcade" / "translations").glob("*.qm")}
    sources = {p.stem for p in (ROOT / "translations").glob("*.ts")}
    assert sources, "no source catalogs found"
    assert sources <= shipped, sources - shipped


def test_available_languages_lists_shipped():
    from tkarcade.gui import helpers as helpersmod

    codes = dict(helpersmod.available_languages())
    assert codes["en"] == "English"
    assert codes["pt_BR"] == "Português (Brasil)"


def test_install_translations_corrupt_qm_falls_back(qt_app, tmp_path, monkeypatch):
    import importlib.resources as res

    from tkarcade.gui import helpers as helpersmod

    (tmp_path / "tkarcade_xx_YY.qm").write_bytes(b"not a qt catalog")
    monkeypatch.setattr(res, "files", lambda package: tmp_path)
    assert helpersmod.install_translations(qt_app, "xx_YY") == ""
