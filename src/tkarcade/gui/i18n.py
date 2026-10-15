"""Qt translations for the Kirigami GUI (no widgets imports here).

Same bundled `tkarcade.translations` catalogs the widgets side ships;
this is the GUI-side installer (test_no_widgets forbids reaching into
the widgets package).
"""

from __future__ import annotations

from PySide6.QtCore import QLocale, QTranslator

_translators: list = []  # kept alive: Qt unloads GC'd translators

#: Autonyms for shipped locales (never translated by definition).
LANGUAGE_NAMES = {"pt_BR": "Português (Brasil)"}


def preferred_language() -> str:
    """GUI language from preferences ("" on any error: system default)."""
    try:
        from .. import config as cfgmod

        return cfgmod.load_preferences().language
    except Exception:
        return ""


def available_languages() -> list[tuple[str, str]]:
    """Shipped [(code, label)] for the language picker (English included)."""
    codes: set[str] = set()
    try:
        from importlib import resources

        pkg = resources.files("tkarcade.translations")
        for ref in pkg.iterdir():
            name = ref.name
            if name.startswith("tkarcade_") and name.endswith(".qm"):
                codes.add(name[len("tkarcade_") : -len(".qm")])
    except Exception:
        pass
    out = [("system", "System"), ("en", "English")]
    out += [(code, LANGUAGE_NAMES.get(code, code)) for code in sorted(codes)]
    return out


def install_translations(app, language: str = "") -> str:
    """Install the matching bundled translator, if any.

    language: "" or "system" follows the OS locale, "en" forces
    English, anything else is tried as a locale code first.
    Returns the loaded locale name or "". English (and unknown
    locales) run untranslated. Safe to call repeatedly.
    """
    from importlib import resources

    choice = (language or "").strip()
    if choice.lower() in ("en", "c"):
        return ""
    if choice and choice != "system":
        candidates = [choice]
    else:
        locale = QLocale.system().name()
        candidates = [locale]
        if "_" in locale:
            candidates.append(locale.split("_")[0])
    try:
        pkg_files = resources.files("tkarcade.translations")
    except Exception:
        return ""
    for lang in candidates:
        name = f"tkarcade_{lang}.qm"
        try:
            ref = pkg_files.joinpath(name)
            if not ref.is_file():
                continue
            with resources.as_file(ref) as path:
                translator = QTranslator()
                if not translator.load(str(path)):
                    continue
        except Exception:
            continue
        if not any(
            installed_app is app and t.language() == translator.language()
            for installed_app, t in _translators
        ):
            app.installTranslator(translator)
            _translators.append((app, translator))
            return lang
    return ""
