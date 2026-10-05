"""Shared pytest fixtures: isolated XDG dirs, HOME and Steam env."""

import os

import pytest

if os.environ.get("TKARCADE_TEST_GUI") != "1":
    # Forced (not setdefault): a user-exported QT_QPA_PLATFORM would pop
    # real windows mid-suite and strand modal dialogs. Opt out for visual
    # debugging with TKARCADE_TEST_GUI=1.
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

if os.environ.get("TKARCADE_TEST_LOCALE") != "1":
    # Pin the suite to English: installed translators follow the system
    # locale, and most tests assert source strings. Opt out with
    # TKARCADE_TEST_LOCALE=1 (tests then depend on your locale).
    os.environ["LC_ALL"] = "C"


@pytest.fixture(scope="module")
def qt_app():
    """Single offscreen QApplication shared by GUI tests in a module."""
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def xdg_env(monkeypatch, tmp_path):
    """Isolated XDG dirs, HOME and Steam-related env vars."""
    home = tmp_path / "home"
    cfg = tmp_path / "config"
    state = tmp_path / "state"
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    for d in (home, cfg, state, data, cache):
        d.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    for var in (
        "STEAMAPPID",
        "SteamAppId",
        "STEAM_APP_ID",
        "STEAM_COMPAT_DATA_PATH",
        "STEAM_ROOT",
    ):
        monkeypatch.delenv(var, raising=False)
    return {"home": home, "config": cfg, "state": state}


@pytest.fixture
def fake_bin(monkeypatch, tmp_path):
    """Empty dir prepended to PATH; return it so tests can drop fake binaries."""

    def _make(name, body="#!/bin/sh\nexit 0\n"):
        path = tmp_path / "bin" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        path.chmod(0o755)
        return path

    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    return _make
