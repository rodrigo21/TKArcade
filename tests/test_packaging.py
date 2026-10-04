"""Packaging metadata: build backend, entry points, license (install contract)."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    assert isinstance(data, dict)
    return data


def test_hatchling_backend():
    build = _pyproject()["build-system"]
    assert build["build-backend"] == "hatchling.build"
    assert any("hatchling" in r for r in build["requires"])


def test_console_scripts():
    scripts = _pyproject()["project"]["scripts"]
    assert scripts["tksteamlaunch"] == "tksteamlaunch.launcher:main"
    assert len(scripts) == 1
    for target in scripts.values():
        module, _, func = target.partition(":")
        assert (ROOT / "src" / module.replace(".", "/")).with_suffix(".py").is_file()
        assert func


def test_python_floor_and_files():
    project = _pyproject()["project"]
    assert project["requires-python"] == ">=3.12"
    assert (ROOT / "README.md").is_file()
    assert "GPL" in project["license"]["text"]


def test_version_single_source():
    import tksteamlaunch

    assert isinstance(tksteamlaunch.__version__, str) and tksteamlaunch.__version__
    # Dynamic versioning: git tags are the single source, not pyproject.
    assert "version" not in _pyproject()["project"]
    assert _pyproject()["tool"]["hatch"]["version"]["source"] == "uv-dynamic-versioning"
