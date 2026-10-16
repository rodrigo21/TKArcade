"""Qt translations for the Kirigami GUI (QtCore only, no widgets).

Installs the bundled `tkarcade.translations` catalogs; `tests/test_i18n.py`
keeps them complete against the QML `qsTr()` calls.
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


def _candidate_locales(choice: str) -> list[str]:
    """Locale codes to try, in order ([] means run untranslated)."""
    if choice.lower() in ("en", "c"):
        return []
    if choice and choice != "system":
        return [choice]
    locale = QLocale.system().name()
    candidates = [locale]
    if "_" in locale:
        candidates.append(locale.split("_")[0])
    return candidates


def _load_translator(pkg_files, lang: str):
    """Load the bundled catalog for lang, or None if it is absent/broken."""
    from importlib import resources

    try:
        ref = pkg_files.joinpath(f"tkarcade_{lang}.qm")
        if not ref.is_file():
            return None
        with resources.as_file(ref) as path:
            translator = QTranslator()
            if not translator.load(str(path)):
                return None
    except Exception:
        return None
    return translator


def _already_installed(app, translator) -> bool:
    """True when this app already carries a translator of the same language."""
    return any(
        installed_app is app and t.language() == translator.language()
        for installed_app, t in _translators
    )


def install_translations(app, language: str = "") -> str:
    """Install the matching bundled translator, if any.

    language: "" or "system" follows the OS locale, "en" forces
    English, anything else is tried as a locale code first.
    Returns the loaded locale name or "". English (and unknown
    locales) run untranslated. Safe to call repeatedly.
    """
    from importlib import resources

    candidates = _candidate_locales((language or "").strip())
    if not candidates:
        return ""
    try:
        pkg_files = resources.files("tkarcade.translations")
    except Exception:
        return ""
    for lang in candidates:
        translator = _load_translator(pkg_files, lang)
        if translator is None or _already_installed(app, translator):
            continue
        app.installTranslator(translator)
        _translators.append((app, translator))
        return lang
    return ""
